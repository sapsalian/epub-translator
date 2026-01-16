"""
Experimental demo: Text replacement strategies for EPUB translation.

This demo explores different approaches to identify and replace text nodes
in XHTML content. Each strategy has different trade-offs:

1. replace_text_by_checking_ancestors: Uses predefined block-level tags and
   checks ancestor chain to avoid duplicate processing.

2. replace_text_by_checking_text: Replaces text wherever elem.text or child.tail
   contains non-empty content.

3. replace_text_by_checking_inline: Replaces text only when all children are
   phrasing (inline) content elements.
"""

from epub_editor import edit_epub
from lxml import etree
from zipfile import ZipInfo

TARGET_TAGS = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'td', 'th', 'dt', 'dd', 'caption', 'figcaption'}

def replace_text_by_checking_ancestors(tree: etree._Element, file_info: ZipInfo) -> None:
    """
    Example DOM editor that translates text nodes in the XHTML content.

    This is a placeholder function. Replace the translation logic with actual implementation.
    """
    def is_already_processed(elem):
        for ancestor in elem.iterancestors():
            tag_name = etree.QName(ancestor).localname
            if tag_name in TARGET_TAGS:
                return True
        return False

    for elem in list(tree.iter()):# 반드시 list로 감싸서 복사본을 만들어야 함. iter() 도중에 트리를 수정하면 놀라운 일이 발생할 수 있음.
        tag_name = etree.QName(elem).localname
        
        if tag_name in TARGET_TAGS and not is_already_processed(elem):
            text = "".join(elem.itertext()).strip()
            if not text:
                continue
            for child in list(elem):
                elem.remove(child)
            elem.text = f"[번역된 텍스트: {text}]"

def replace_text_by_checking_text(tree: etree._Element, file_info: ZipInfo) -> None:
    """
    Example DOM editor that translates text nodes in the XHTML content.

    This is a placeholder function. Replace the translation logic with actual implementation.
    """
    for elem in list(tree.iter()):# 반드시 list로 감싸서 복사본을 만들어야 함. iter() 도중에 트리를 수정하면 놀라운 일이 발생할 수 있음.
        def is_text_emerge(elem):
            if (elem.text and elem.text.strip()):
                return True
            for child in elem:
                if (child.tail and child.tail.strip()):
                    return True
            return False
        
        if is_text_emerge(elem):
            text = "".join(elem.itertext()).strip()
            if not text:
                continue
            for child in list(elem):
                elem.remove(child)
            elem.text = f"[번역된 텍스트: {text}]"

def replace_text_by_checking_inline(tree: etree._Element, file_info: ZipInfo) -> None:
    PHRASING_CONTENT_TAGS = {
        'span', 'strong', 'em', 'b', 'i', 'u', 's', 'small', 'mark', 'cite', 'dfn', 'abbr',
        'sub', 'sup', 'code', 'kbd', 'samp', 'var', 'q', 'data', 'time',
        'a', 'img', 'picture', 'map', 'area', 'ruby', 'rt', 'rp', 'br', 'wbr'
    }

    def is_only_phrasing_children(elem):
        """자식 요소가 없거나, 모든 자식이 Phrasing Content인 경우 True 반환"""
        for child in elem:
            child_tag = etree.QName(child).localname
            if child_tag not in PHRASING_CONTENT_TAGS:
                return False
        return True
    
    for elem in list(tree.iter()):
        if is_only_phrasing_children(elem):
            text = "".join(elem.itertext()).strip()
            if not text:
                continue
            for child in list(elem):
                elem.remove(child)
            elem.text = f"[번역된 텍스트: {text}]"


def translate_xhtml_file(xhtml_path: str) -> None:
    """
    Open and parse a standalone XHTML file, then apply translate_dom to it.

    Args:
        xhtml_path: Path to the XHTML file.
    """
    with open(xhtml_path, 'rb') as f:
        parser = etree.HTMLParser(encoding='utf-8')
        tree = etree.parse(f, parser=parser)

    dummy_info = ZipInfo(filename=xhtml_path)
    replace_text_by_checking_ancestors(tree, dummy_info)


edit_epub('demo_files/sample.epub', 'demo_files/translated.epub', replace_text_by_checking_text)
