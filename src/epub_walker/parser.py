'''
--------------------------------------------xhtml path from epub spine order--------------------------------------------
'''
from zipfile import ZipFile
from lxml import etree
from pathlib import PurePosixPath as Pu
import posixpath

_NS = {
    "ocf": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
}

_VALID_EXTS = (".xhtml", ".html", ".htm")


def get_spine_xhtml_paths_by_order(zf: ZipFile) -> list[Pu]:
    opf_path = _find_opf_path(zf)
    
    ITEM = f"{{{_NS['opf']}}}item"
    ITEMREF = f"{{{_NS['opf']}}}itemref"
    
    manifest = {}  
    spine = []   
    
    for event, elem in etree.iterparse(zf.open(opf_path.as_posix()), events=("end",)):
        if elem.tag == ITEM:
            elem_id = elem.get("id")
            elem_href = elem.get("href")
            if elem_id and elem_href:
                opf_dir = opf_path.parent.as_posix()
                abs_path = posixpath.normpath(posixpath.join(opf_dir, elem_href))
                manifest[elem_id] = Pu(abs_path)
        elif elem.tag == ITEMREF:
            idref = elem.get("idref")
            spine.append(idref)
        # 메모리 절약
        elem.clear()
        
    ordered_path = []
    for idref in spine:
        path = manifest.get(idref)
        if not path:
            continue
        if not path.as_posix().lower().endswith(_VALID_EXTS):
            continue
        else:
            ordered_path.append(path)
            
    return ordered_path

    

def _find_opf_path(zf: ZipFile) -> Pu:
    """
    EPUB 파일 내에서 OPF 파일 경로를 찾음.
    1) META-INF/container.xml에서 rootfile 요소를 찾음.
    2) 없으면 .opf 확장자 파일들 중에서 간단 검증을 통해 OPF 파일을 찾음.
    """
    
    try:
        data = zf.read("META-INF/container.xml")
        root = etree.fromstring(data)
        rootfiles = root.findall(".//ocf:rootfile", _NS)
        
        if rootfiles:
            return Pu(rootfiles[0].get("full-path"))
    except KeyError:
        pass  
    except etree.ParseError:
        pass  

    candidates = [n for n in zf.namelist() if n.lower().endswith(".opf")]
    for path in candidates:
        try:
            pkg = etree.fromstring(zf.read(path))
            if pkg.tag.endswith("package") and pkg.get("version"):
                return Pu(path)
        except Exception:
            continue

    raise FileNotFoundError("OPF could not be found in the EPUB file.")