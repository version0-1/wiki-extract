"""
XML ページ処理用のワーカープロセス補助（ProcessPoolExecutor 用）。
ワーカーが __main__ として実行されても _init_worker / process_page を解決できるよう、名前付きモジュールに置く必要がある。
"""

from wiki_extract.section_parser import extract_fictional_links_from_page

_worker_toujo_page_ids: set[int] = set()


def init_worker(toujo_page_ids: set[int]) -> None:
    """ワーカープロセス用にグローバル toujo_page_ids を設定する。"""
    global _worker_toujo_page_ids
    _worker_toujo_page_ids = toujo_page_ids


def process_page(item: tuple[int, int, str]) -> set[str]:
    """1ページ (page_id, ns, text) を処理し、リンク先タイトルの集合を返す。"""
    page_id, ns, text = item
    return extract_fictional_links_from_page(
        page_id, ns, text, _worker_toujo_page_ids
    )
