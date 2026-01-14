"""
Demo: Rewriting an EPUB file with modified content.

This script demonstrates how to read an EPUB, modify its XHTML content,
and write it back to a new EPUB file.
"""

import zipfile
from lxml import etree
from epub_walker import walk_all_files


def reverse_text_in_epub(input_epub, output_epub):
    """Read an EPUB and create a new one with all text reversed."""

    with zipfile.ZipFile(output_epub, 'w', compression=zipfile.ZIP_DEFLATED) as zout:

        def file_func(f, item):
            content = f.read()

            if item.filename.endswith(('.xhtml', '.html')):
                parser = etree.XMLParser(encoding='utf-8', recover=True)
                tree = etree.fromstring(content, parser=parser)

                for elem in tree.iter():
                    if elem.text and elem.text.strip():
                        elem.text = elem.text[::-1]
                    if elem.tail and elem.tail.strip():
                        elem.tail = elem.tail[::-1]

                new_content = etree.tostring(tree, encoding='utf-8', xml_declaration=True, method='xml')
                zout.writestr(item.filename, new_content)
            else:
                zout.writestr(item, content)

        walk_all_files(input_epub, file_func)


reverse_text_in_epub('demo_files/sample.epub', 'demo_files/reversed.epub')
print("Done: reversed.epub has been created.")