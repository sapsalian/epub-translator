from pathlib import Path
from zipfile import ZipFile

import pytest


def _build_strong_para_epub(epub_path: Path) -> None:
    """Create a minimal EPUB with a single chapter containing <p><strong>original</strong></p>."""
    with ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        zf.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <manifest>
    <item id="c1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="c1"/>
  </spine>
</package>""",
        )
        zf.writestr(
            "OEBPS/chapter1.xhtml",
            """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Ch1</title></head>
  <body>
    <p><strong>original</strong></p>
  </body>
</html>""",
        )


@pytest.fixture
def strong_para_epub(tmp_path: Path) -> Path:
    """EPUB fixture: single chapter with <p><strong>original</strong></p>."""
    path = tmp_path / "strong_para.epub"
    _build_strong_para_epub(path)
    return path
