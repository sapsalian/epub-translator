from lxml import etree
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_STORED, ZIP_DEFLATED
from .base import ElemEditor, DOMEditor
from matchers import ElementMatcher, MatcherFactory, MatcherStrategy


def edit_epub(old_epub: Path, new_epub: Path, xhtml_editor: DOMEditor) -> None:
    """
    Create a new EPUB by applying an editor function to each XHTML document tree.

    Iterates through all XHTML/HTML files in the input EPUB and applies
    the xhtml_editor function to the entire DOM tree. Non-XHTML files are copied as-is.

    Args:
        old_epub: Path to the source EPUB file.
        new_epub: Path where the modified EPUB will be saved.
        xhtml_editor: A callable that takes an lxml Element tree and ZipInfo, modifies the tree in place.
    """

    with ZipFile(old_epub, 'r') as zin, ZipFile(new_epub, 'w') as zout:
        # Write mimetype first without compression (EPUB spec requirement)
        if 'mimetype' in zin.namelist():
            zout.writestr('mimetype', zin.read('mimetype'), compress_type=ZIP_STORED)

        for item in zin.infolist():
            if item.filename == 'mimetype':
                continue

            content: bytes = zin.read(item.filename)

            if item.filename.endswith(('.xhtml', '.html')):
                parser = etree.XMLParser(encoding='utf-8', recover=True)
                tree = etree.fromstring(content, parser=parser)

                xhtml_editor(tree, item)

                new_content = etree.tostring(tree, encoding='utf-8', xml_declaration=True, method='xml')
                zout.writestr(item.filename, new_content, compress_type=ZIP_DEFLATED)
            else:
                zout.writestr(item.filename, content, compress_type=ZIP_DEFLATED)


def edit_epub_elements(old_epub: Path, new_epub: Path, elem_editor: ElemEditor, elem_filter: ElementMatcher | None = None) -> None:
    """
    Create a new EPUB by applying an editor function to each XML element.

    Iterates through all XHTML/HTML files in the input EPUB and applies
    the elem_editor function to every element. Non-XHTML files are copied as-is.

    Args:
        old_epub: Path to the source EPUB file.
        new_epub: Path where the modified EPUB will be saved.
        elem_editor: An editor that modifies each element in place.
        elem_filter: A matcher to filter elements. Defaults to TextEmergenceMatcher.
    """
    if elem_filter is None:
        elem_filter = MatcherFactory.create(MatcherStrategy.ALL_ELEMENTS)

    def xhtml_editor(tree: etree._Element, item: ZipInfo) -> None:
        for elem in tree.iter():
            if elem_filter(elem):
                elem_editor(elem, item)

    edit_epub(old_epub, new_epub, xhtml_editor)