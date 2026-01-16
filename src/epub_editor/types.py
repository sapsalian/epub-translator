from lxml import etree
from typing import Callable
from zipfile import ZipInfo
from typing import Union

ElemEditor = Callable[[etree._Element, ZipInfo], None]
DOMEditor = Callable[[etree._Element, ZipInfo], None]