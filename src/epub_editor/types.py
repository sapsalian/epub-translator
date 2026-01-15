from lxml import etree
from typing import Callable
from zipfile import ZipInfo

ElemEditor = Callable[[etree._Element], None]
DOMEditor = Callable[[etree._Element, ZipInfo], None]