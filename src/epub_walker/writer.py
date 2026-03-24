from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from .parser import get_spine_xhtml_paths_by_order
from src.matchers.implementations import TextEmergenceMatcher
from src.pipeline.constants import UNTRANSLATABLE_TAGS

_PARAGRAPH_ID_PATTERN = re.compile(r"^ch(?P<chapter>\d+)_p(?P<paragraph>\d+)$")


def patch_epub_paragraphs(epub_path: Path, edits: dict[str, str]) -> None:
    """
    Patch inner HTML of chapter block elements in place.

    Args:
        epub_path: Path to output EPUB file.
        edits: Paragraph edits keyed by paragraph id (`chNNN_pM`).

    Raises:
        FileNotFoundError: EPUB path is missing.
        ValueError: Invalid paragraph id, out-of-range target, or invalid fragment HTML.
    """
    if not edits:
        return
    if not epub_path.exists():
        raise FileNotFoundError(f"EPUB file not found: {epub_path}")

    edits_by_chapter = _group_edits_by_chapter(edits)
    temp_path = epub_path.with_suffix(f"{epub_path.suffix}.tmp")

    try:
        with ZipFile(epub_path, "r") as zin:
            spine_paths = get_spine_xhtml_paths_by_order(zin)
            patched_payloads = _build_patched_payloads(zin, spine_paths, edits_by_chapter)

            with ZipFile(temp_path, "w") as zout:
                for item in zin.infolist():
                    payload = patched_payloads.get(item.filename)
                    if payload is None:
                        payload = zin.read(item.filename)
                    zout.writestr(item, payload)

        os.replace(temp_path, epub_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _group_edits_by_chapter(edits: dict[str, str]) -> dict[int, dict[int, str]]:
    grouped: dict[int, dict[int, str]] = defaultdict(dict)
    for paragraph_id, html in edits.items():
        match = _PARAGRAPH_ID_PATTERN.match(paragraph_id)
        if not match:
            raise ValueError(f"Invalid paragraph id: {paragraph_id}")

        chapter_idx = int(match.group("chapter"))
        paragraph_idx = int(match.group("paragraph"))
        grouped[chapter_idx][paragraph_idx] = html
    return dict(grouped)


def _build_patched_payloads(
    zf: ZipFile,
    spine_paths: list,
    edits_by_chapter: dict[int, dict[int, str]],
) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    parser = etree.XMLParser(recover=True)

    for chapter_idx, paragraph_edits in edits_by_chapter.items():
        if chapter_idx < 0 or chapter_idx >= len(spine_paths):
            raise ValueError(f"Chapter index out of range: {chapter_idx}")

        chapter_path = spine_paths[chapter_idx]
        root = etree.fromstring(zf.read(chapter_path.as_posix()), parser=parser)
        block_elements = _iter_block_elements(root)

        for paragraph_idx, html in paragraph_edits.items():
            if paragraph_idx < 0 or paragraph_idx >= len(block_elements):
                raise ValueError(
                    f"Paragraph index out of range: chapter={chapter_idx}, paragraph={paragraph_idx}"
                )
            _replace_inner_html(block_elements[paragraph_idx], html)

        payloads[chapter_path.as_posix()] = etree.tostring(
            root,
            encoding="utf-8",
            method="xml",
            xml_declaration=True,
        )

    return payloads


def _iter_block_elements(root: etree._Element) -> list[etree._Element]:
    matcher = TextEmergenceMatcher()
    result = []
    for elem in root.iter():
        if not isinstance(elem.tag, str):
            continue
        tag = etree.QName(elem).localname.lower()
        if tag in UNTRANSLATABLE_TAGS:
            continue
        if any(
            isinstance(a.tag, str) and etree.QName(a).localname.lower() in UNTRANSLATABLE_TAGS
            for a in elem.iterancestors()
        ):
            continue
        if matcher.match(elem):
            result.append(elem)
    return result


def _replace_inner_html(element: etree._Element, inner_html: str) -> None:
    for child in list(element):
        element.remove(child)
    element.text = None

    if inner_html == "":
        return

    namespace = etree.QName(element).namespace
    if namespace:
        wrapper = f'<wrapper xmlns="{namespace}">{inner_html}</wrapper>'
    else:
        wrapper = f"<wrapper>{inner_html}</wrapper>"

    try:
        fragment = etree.fromstring(wrapper.encode("utf-8"), parser=etree.XMLParser(recover=False))
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"Invalid HTML fragment: {inner_html}") from exc

    element.text = fragment.text
    for child in list(fragment):
        fragment.remove(child)
        element.append(child)
