from __future__ import annotations

import base64
import mimetypes
from pathlib import PurePosixPath
import posixpath
from zipfile import ZipFile

from lxml import etree

from .parser import _find_opf_path, get_spine_xhtml_paths_by_order

_OPF_NS = {"opf": "http://www.idpf.org/2007/opf"}
_XHTML_NS = {"xhtml": "http://www.w3.org/1999/xhtml"}
_NCX_NS = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
_XLINK_NS = "http://www.w3.org/1999/xlink"
_BLOCK_TAGS = ("p", "h1", "h2", "h3", "h4", "h5", "h6", "li")


def get_chapter_titles(zf: ZipFile) -> list[str]:
    spine_paths = get_spine_xhtml_paths_by_order(zf)
    title_map = _load_nav_title_map(zf)
    if not title_map:
        title_map = _load_ncx_title_map(zf)

    return [title_map.get(path, _fallback_title_from_path(path)) for path in spine_paths]


def extract_chapter_paragraphs(
    source_zf: ZipFile | None,
    translation_zf: ZipFile,
    chapter_idx: int,
    chapter_id: str,
) -> list[dict]:
    translation_paths = get_spine_xhtml_paths_by_order(translation_zf)
    chapter_path = translation_paths[chapter_idx]

    translation_items = _extract_block_inner_html(translation_zf, chapter_path)
    source_items = _extract_block_inner_html(source_zf, chapter_path) if source_zf is not None else []

    paragraphs: list[dict] = []
    for index, translation_html in enumerate(translation_items):
        paragraphs.append(
            {
                "id": f"{chapter_id}_p{index}",
                "source": source_items[index] if index < len(source_items) else "",
                "translation": translation_html,
            }
        )
    return paragraphs


def render_chapter_html(zf: ZipFile, chapter_idx: int, chapter_id: str) -> str:
    spine_paths = get_spine_xhtml_paths_by_order(zf)
    chapter_path = spine_paths[chapter_idx]
    root = etree.fromstring(zf.read(chapter_path.as_posix()), parser=etree.XMLParser(recover=True))

    for link in root.xpath(".//*[local-name()='link']"):
        rel = (link.get("rel") or "").lower().split()
        href = (link.get("href") or "").strip()
        if "stylesheet" not in rel:
            continue
        if not href or "://" in href or href.startswith("//"):
            link.getparent().remove(link)
            continue

        css_path = _resolve_relative_path(chapter_path, href)
        try:
            css_content = zf.read(css_path.as_posix()).decode("utf-8", errors="replace")
        except KeyError:
            link.getparent().remove(link)
            continue

        ns = etree.QName(link).namespace
        style_tag = f"{{{ns}}}style" if ns else "style"
        style = etree.Element(style_tag)
        style.text = css_content
        link.getparent().replace(link, style)

    _inline_image_assets(root, zf, chapter_path)
    _inject_runtime_style_guard(root)

    for index, element in enumerate(_iter_block_elements(root)):
        element.set("data-paragraph-id", f"{chapter_id}_p{index}")

    rendered = etree.tostring(root, encoding="utf-8", method="xml", xml_declaration=True)
    return rendered.decode("utf-8", errors="replace")


def _load_nav_title_map(zf: ZipFile) -> dict[PurePosixPath, str]:
    opf_path = _find_opf_path(zf)
    root = etree.fromstring(zf.read(opf_path.as_posix()))
    manifest_items = root.xpath(".//opf:item[@properties='nav']", namespaces=_OPF_NS)
    if not manifest_items:
        return {}

    nav_href = manifest_items[0].get("href")
    if not nav_href:
        return {}

    nav_path = PurePosixPath(posixpath.normpath(posixpath.join(opf_path.parent.as_posix(), nav_href)))
    nav_root = etree.fromstring(zf.read(nav_path.as_posix()))

    title_map: dict[PurePosixPath, str] = {}
    for link in nav_root.xpath(".//xhtml:nav//xhtml:a[@href]", namespaces=_XHTML_NS):
        href = (link.get("href") or "").split("#", 1)[0]
        if not href:
            continue
        chapter_path = _resolve_relative_path(nav_path, href)
        title = "".join(link.itertext()).strip()
        if title:
            title_map[chapter_path] = title
    return title_map


def _load_ncx_title_map(zf: ZipFile) -> dict[PurePosixPath, str]:
    opf_path = _find_opf_path(zf)
    root = etree.fromstring(zf.read(opf_path.as_posix()))

    manifest: dict[str, PurePosixPath] = {}
    for item in root.xpath(".//opf:item[@id][@href]", namespaces=_OPF_NS):
        item_id = item.get("id")
        item_href = item.get("href")
        if item_id and item_href:
            manifest[item_id] = _resolve_relative_path(opf_path, item_href)

    spine_toc = root.xpath("string(.//opf:spine/@toc)", namespaces=_OPF_NS).strip()
    ncx_path = manifest.get(spine_toc)
    if ncx_path is None:
        for item in root.xpath(".//opf:item[@media-type='application/x-dtbncx+xml'][@href]", namespaces=_OPF_NS):
            ncx_href = item.get("href")
            if ncx_href:
                ncx_path = _resolve_relative_path(opf_path, ncx_href)
                break
    if ncx_path is None:
        return {}

    ncx_root = etree.fromstring(zf.read(ncx_path.as_posix()))
    title_map: dict[PurePosixPath, str] = {}
    for nav_point in ncx_root.xpath(".//ncx:navPoint", namespaces=_NCX_NS):
        content_src = nav_point.xpath("string(ncx:content/@src)", namespaces=_NCX_NS).strip()
        title = nav_point.xpath("string(ncx:navLabel/ncx:text)", namespaces=_NCX_NS).strip()
        if not content_src or not title:
            continue
        chapter_path = _resolve_relative_path(ncx_path, content_src.split("#", 1)[0])
        title_map[chapter_path] = title
    return title_map


def _extract_block_inner_html(zf: ZipFile | None, chapter_path: PurePosixPath) -> list[str]:
    if zf is None:
        return []

    root = etree.fromstring(zf.read(chapter_path.as_posix()))
    return [_inner_html(element).strip() for element in _iter_block_elements(root)]


def _inner_html(element: etree._Element) -> str:
    parts: list[str] = []
    if element.text:
        parts.append(element.text)
    for child in element:
        parts.append(etree.tostring(child, encoding="unicode"))
    return "".join(parts)


def _resolve_relative_path(base_path: PurePosixPath, href: str) -> PurePosixPath:
    return PurePosixPath(posixpath.normpath(posixpath.join(base_path.parent.as_posix(), href)))


def _iter_block_elements(root: etree._Element) -> list[etree._Element]:
    xpath = " | ".join(f".//*[local-name()='{tag}']" for tag in _BLOCK_TAGS)
    return list(root.xpath(xpath))


def _inline_image_assets(root: etree._Element, zf: ZipFile, chapter_path: PurePosixPath) -> None:
    for image in root.xpath(".//*[local-name()='img'][@src]"):
        data_uri = _load_data_uri(zf, chapter_path, image.get("src") or "")
        if data_uri:
            image.set("src", data_uri)

    for svg_image in root.xpath(".//*[local-name()='image']"):
        xlink_attr = f"{{{_XLINK_NS}}}href"
        href_value = svg_image.get(xlink_attr) or svg_image.get("href") or ""
        data_uri = _load_data_uri(zf, chapter_path, href_value)
        if not data_uri:
            continue

        if svg_image.get(xlink_attr) is not None:
            svg_image.set(xlink_attr, data_uri)
        else:
            svg_image.set("href", data_uri)


def _load_data_uri(zf: ZipFile, chapter_path: PurePosixPath, href: str) -> str | None:
    href = href.strip()
    if not href:
        return None
    if href.startswith(("data:", "http://", "https://", "//", "#")):
        return None

    asset_href = href.split("#", 1)[0].split("?", 1)[0]
    if not asset_href:
        return None

    asset_path = _resolve_relative_path(chapter_path, asset_href)
    try:
        payload = zf.read(asset_path.as_posix())
    except KeyError:
        return None

    media_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _inject_runtime_style_guard(root: etree._Element) -> None:
    runtime_css = """
html, body {
  overflow-x: hidden;
  overscroll-behavior-x: none;
  touch-action: pan-y;
}

img, svg, video, canvas {
  max-width: 100%;
  height: auto;
}

table, pre {
  max-width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
""".strip()

    head = root.xpath(".//*[local-name()='head']")
    if head:
        head_elem = head[0]
    else:
        ns = etree.QName(root).namespace
        head_tag = f"{{{ns}}}head" if ns else "head"
        head_elem = etree.Element(head_tag)
        root.insert(0, head_elem)

    ns = etree.QName(head_elem).namespace
    style_tag = f"{{{ns}}}style" if ns else "style"
    runtime_style = etree.Element(style_tag)
    runtime_style.text = runtime_css
    runtime_style.set("data-viewer-runtime", "1")
    head_elem.append(runtime_style)


def _fallback_title_from_path(path: PurePosixPath) -> str:
    title = path.name
    while True:
        base, ext = posixpath.splitext(title)
        if not base:
            break
        if ext.lower() in {".xhtml", ".html", ".htm"}:
            title = base
            continue
        break
    return title
