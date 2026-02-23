"""
page テーブルを読む: ns=0 の page_id→title、ns=14（カテゴリ）の page_id→title、登場人物の page_ids。
"""

import re
import unicodedata
from pathlib import Path

from mwsql import Dump

from wiki_extract.util.log import log_progress, Timer


NS_MAIN = 0
NS_CATEGORY = 14

# 登場人物ページのタイトルパターン（MediaWiki ではアンダースコア、テスト等では「一覧」も）。
# 例: "○○の登場人物"、"○○の登場人物一覧"、"○○の主要な登場人物" にマッチ。
TOUJO_PATTERN = re.compile(r".+の.*登場人物(?:_一覧|一覧)?$")


def _normalize_page_title(s: str) -> str:
    """NFKC 正規化し、空白・全角スペースをアンダースコアに（ダンプの表記揺れ対策）。"""
    if not s:
        return ""
    t = unicodedata.normalize('NFKC', str(s))
    return re.sub(r'[\s\u3000]+', '_', t).strip().strip('_') or ""


def run_page(
    page_path: Path,
    *,
    log_progress_fn: bool = True,
) -> tuple[dict[int, str], dict[int, str], set[int]]:
    """
    page ダンプを読む。返り値:
    - main_id_to_title: ns=0 の page_id → page_title
    - category_id_to_title: ns=14 の page_id → page_title
    - toujo_page_ids: *の…登場人物 や *の…登場人物一覧 のタイトルを持つページの page_id の集合（例: 主要な登場人物）
    """
    with Timer() as timer:
        if log_progress_fn:
            log_progress("page: ダンプ読込", elapsed=timer.elapsed)
        dump = Dump.from_file(str(page_path))
        col = dump.col_names
        idx_id = col.index('page_id') if 'page_id' in col else 0
        idx_ns = col.index('page_namespace') if 'page_namespace' in col else 1
        idx_title = col.index('page_title') if 'page_title' in col else 2
        main_id_to_title: dict[int, str] = {}
        category_id_to_title: dict[int, str] = {}
        toujo_page_ids: set[int] = set()
        n_main = 0
        n_cat = 0
        for row in dump.rows(convert_dtypes=True):
            if len(row) <= max(idx_id, idx_ns, idx_title):
                continue
            page_id, page_namespace, page_title = row[idx_id], row[idx_ns], row[idx_title]
            title = _normalize_page_title(page_title or "")
            if page_namespace == NS_MAIN:
                main_id_to_title[page_id] = title
                n_main += 1
                if TOUJO_PATTERN.match(title):
                    toujo_page_ids.add(page_id)
            elif page_namespace == NS_CATEGORY:
                category_id_to_title[page_id] = title
                n_cat += 1

    if log_progress_fn:
        log_progress(
            "page: 完了",
            count=n_main + n_cat,
            elapsed=timer.elapsed,
        )
    return main_id_to_title, category_id_to_title, toujo_page_ids
