"""
MediaWiki の pages-articles.xml または .xml.bz2 からページをストリームし、(page_id, ns, text) を yield する。
iterparse でメモリに全ダンプを載せない。
"""

import bz2
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator


def _local_tag(tag: str) -> str:
    """名前空間を除いたローカル名を返す。"""
    return tag.split('}')[-1] if tag and '}' in str(tag) else (tag or '')


def stream_pages(xml_path: Path) -> Iterator[tuple[int, int, str]]:
    """
    pages-articles.xml（または .xml.bz2）を開き、各ページの (page_id, namespace, text) を yield する。
    本文は最終リビジョンのみ。UTF-8 でデコードする。
    """
    path_str = str(xml_path)
    if path_str.endswith(".bz2"):
        f = bz2.open(xml_path, "rt", encoding="utf-8", errors="replace")
    else:
        f = open(xml_path, "r", encoding="utf-8", errors="replace")
    try:
        context = ET.iterparse(f, events=("end",))
        for _event, elem in context:
            if _local_tag(elem.tag) != 'page':
                continue
            page_id = 0
            ns = 0
            text = ''
            for child in elem:
                tag = _local_tag(child.tag)
                if tag == 'id' and page_id == 0:
                    page_id = int(child.text or 0)
                elif tag == 'ns':
                    ns = int(child.text or 0)
                elif tag == 'revision':
                    text_elem = None
                    for c in child:
                        if _local_tag(c.tag) == 'text':
                            text_elem = c
                            break
                    if text_elem is not None and text_elem.text is not None:
                        text = text_elem.text
                    else:
                        text = ''
            if page_id:
                yield page_id, ns, text
            elem.clear()
    finally:
        f.close()
