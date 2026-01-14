"""
---------------------------------------------------------------------------------------------
"""

from pathlib import Path
from enum import Enum
from pydantic import BaseModel, Field


class Language(str, Enum):
    KOREAN = "ko"
    ENGLISH = "en"
    JAPANESE = "ja"
    CHINESE = "zh"

class Summary(BaseModel):
    file_id: str = Field(..., description="Unique identifier for the xhtml file")
    summary_content: str = Field(..., description="The summarized content of the xhtml file")
    
class TermMapping(BaseModel):
    src_term: str = Field(..., description="The term to be mapped")
    target_term: str = Field(..., description="The translation of the term in the target language")

def translate_epub(epub_path: Path, src_lang: Language, target_lang: Language) -> None:
    """
    Translates the content of an EPUB file from src_lang to target_lang.

    Args:
        epub_path (Path): The path to the EPUB file.
        src_lang (Language): The source language.
        target_lang (Language): The target language.
    """


'''
------------------------------extract_demo---------------------------------------
'''

from lxml import etree
from zipfile import ZipFile

XHTML_NS = "http://www.w3.org/1999/xhtml"
NS = {"x": XHTML_NS}

BR_TAG = f"{{{XHTML_NS}}}br"

def extract_all_texts_from_xhtml(xhtml) -> str:
    """
    Extracts all text from XHTML in reading order using iterparse and a stack-based approach.

    Args:
        xhtml: File-like object containing XHTML content

    Returns:
        str: All text content joined together in reading order
    """
    from collections import deque

    stack = []  # Stack of (node, deque) tuples

    for event, cur_elem in etree.iterparse(xhtml, events=("end",)):
        cur_text = cur_elem.text or ""
        cur_tail = cur_elem.tail or ""
        
        if cur_elem.tag == BR_TAG:
            cur_text = "\n" + cur_text

        # 스택이 비어있으면
        if not stack:
            cur_deque = deque([cur_text, cur_tail])
            stack.append((cur_elem, cur_deque))
            continue

        # 스택에서 pop
        prev_node, prev_deque = stack.pop()

        # 1. 이전 노드가 자식 요소라면 (prev_node가 elem의 직접 자식)
        if prev_node.getparent() is cur_elem:
            prev_node.clear()
            cur_deque = prev_deque
            cur_deque.appendleft(cur_text)
            cur_deque.append(cur_tail)
            
            # 여기서 하나 더 꺼내 보기 (그 이전 형제까지 올라왔을 수도 있으니까)
            if stack:
                sibling_candidate_node, _ = stack[-1]
                # 진짜 sibling인지 확인 (sibling_candidate도 elem의 자식이면 형제)
                if sibling_candidate_node.getparent() is cur_elem.getparent():
                    sibling_node, sibling_deque = stack.pop()
                    sibling_node.clear()
                    cur_deque.extendleft(reversed(sibling_deque))

            stack.append((cur_elem, cur_deque))

        # 2. 이전 노드가 형제 요소라면 (같은 부모를 가짐)
        elif prev_node.getparent() is cur_elem.getparent():
            prev_node.clear()
            cur_deque = prev_deque
            cur_deque.append(cur_text)
            cur_deque.append(cur_tail)
            stack.append((cur_elem, cur_deque))

        # 3. 이전 노드가 조상의 형제 요소라면 (앞의 둘 다 아니면)
        else:
            cur_deque = deque([cur_text, cur_tail])
            stack.append((prev_node, prev_deque))
            stack.append((cur_elem, cur_deque))

    # 최종 결과 수집
    final_deque = deque()
    for node, node_deque in stack:
        final_deque.extend(node_deque)
        node.clear()

    return "".join(final_deque)

from epub_walker import walk_xhtmls

walk_xhtmls(Path("demo_files/sample.epub"), lambda xhtml: print(extract_all_texts_from_xhtml(xhtml)))
    

