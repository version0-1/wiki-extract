"""
「架空の人物」カテゴリ配下の page_id を取得する。

MediaWiki 1.45+ では categorylinks に cl_to がなく cl_target_id のみのため、
linktarget で lt_id → カテゴリ名を解決する。page でカテゴリの page_id を取得する。
"""

import gzip
import re
import unicodedata
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, TextIO, Union

from mwsql import Dump

from wiki_extract.log import log_progress, Timer

NS_CATEGORY = 14

CATEGORY_FICTIONAL = "架空の人物"


@contextmanager
def _open_file_utf8_replace(
    file_path: Union[str, Path], encoding: Optional[str] = None
) -> Iterator[TextIO]:
    enc = encoding or 'utf-8'
    if str(file_path).endswith('.gz'):
        infile = gzip.open(file_path, mode='rt', encoding=enc, errors='replace')
    else:
        infile = open(file_path, mode='r', encoding=enc, errors='replace')
    try:
        yield infile
    finally:
        infile.close()


def _normalize_title(s: str) -> str:
    """MediaWiki タイトル: 空白・全角スペースをアンダースコアに、NFKC 正規化。"""
    if s is None:
        return ""
    t = unicodedata.normalize('NFKC', str(s) or "")
    return re.sub(r'[\s\u3000]+', '_', t).strip().strip('_')


def _canonical_title(s: str) -> str:
    """
    比較用: NFKC 正規化し、書式・制御文字（ゼロ幅スペース等）を除去し、
    空白・アンダースコア・全角スペースを除去。
    """
    if s is None:
        return ""
    t = unicodedata.normalize('NFKC', str(s) or "")
    t = ''.join(c for c in t if unicodedata.category(c) not in ('Cf', 'Cc'))
    return re.sub(r'[\s_\u3000]+', '', t)


def _is_garbage_linktarget_title(title: str) -> bool:
    if not title or not isinstance(title, str):
        return True
    t = title.strip()
    if '_+_' in t or 'data-mw-' in t:
        return True
    if t.startswith('"') and t.endswith('"') and len(t) <= 40:
        return True
    if t.startswith("'") and t.endswith("'") and len(t) <= 30:
        return True
    return False


def _build_category_set(
    subcat_rows: list[tuple[int, str]],
    category_page_id_to_title: dict[int, str],
    seed: str,
) -> set[str]:
    """固定点: seed 配下の全カテゴリ名。subcat_rows = (cl_from, 親カテゴリ名)。"""
    seed_n = _normalize_title(seed)
    c: set[str] = {seed_n}
    prev_size = 0
    while len(c) > prev_size:
        prev_size = len(c)
        for cl_from, cl_to in subcat_rows:
            cl_to_n = _normalize_title(cl_to)
            if cl_to_n not in c:
                continue
            title = category_page_id_to_title.get(cl_from)
            if title:
                c.add(_normalize_title(title))
    return c


def _build_category_page_id_set(
    subcat_rows_by_lt: list[tuple[int, int]],
    lt_id_to_page_id: dict[int, int],
    seed_page_id: int,
) -> set[int]:
    """
    固定点: seed_page_id 配下の全カテゴリの page_id。
    subcat_rows_by_lt = (cl_from=サブカテゴリの page_id, cl_target_id=親の lt_id)。
    """
    c: set[int] = {seed_page_id}
    prev_size = 0
    while len(c) > prev_size:
        prev_size = len(c)
        for cl_from, parent_lt_id in subcat_rows_by_lt:
            parent_page_id = lt_id_to_page_id.get(parent_lt_id)
            if parent_page_id not in c:
                continue
            c.add(cl_from)
    return c


def _resolve_seed_page_id(
    seed: str,
    category_page_id_to_title: dict[int, str],
) -> int | None:
    """
    page テーブルから seed に正規化一致するカテゴリの page_id を返す。
    完全一致が無い場合、seed で始まる最短のカテゴリ名を候補に採用する。
    """
    want = _canonical_title(seed)
    for pid, title in category_page_id_to_title.items():
        if _canonical_title(title) == want:
            return pid
    # 根カテゴリがダンプに無い場合: seed で始まる最短のカテゴリ名を候補にする（長さが一致すれば採用）
    candidates = [
        (pid, title)
        for pid, title in category_page_id_to_title.items()
        if _canonical_title(title).startswith(want) and len(_canonical_title(title)) >= len(want)
    ]
    if not candidates:
        return None
    best = min(candidates, key=lambda x: len(_canonical_title(x[1])))
    if len(_canonical_title(best[1])) == len(want):
        return best[0]
    return None


def _load_linktarget_category_titles(
    linktarget_path: Path,
    *,
    seed_titles: Optional[list[str]] = None,
    log_progress_fn: bool = True,
) -> dict[int, str]:
    """
    linktarget ダンプから ns=14 の行を読み、lt_id → 正規化タイトル を返す。
    seed_titles を渡すと、行内のいずれかの列がそのタイトルに正規化一致すれば採用する
    （パースずれ・列ずれ対策）。
    """
    import mwsql.dump as _mwsql_dump
    _orig_open = _mwsql_dump._open_file
    _mwsql_dump._open_file = _open_file_utf8_replace
    seed_canonicals = (
        {_canonical_title(s) for s in (seed_titles or [])} if seed_titles else set()
    )
    try:
        dump = Dump.from_file(str(linktarget_path))
        col = dump.col_names
        idx_id = col.index('lt_id') if 'lt_id' in col else 0
        idx_ns = col.index('lt_namespace') if 'lt_namespace' in col else 1
        idx_title = col.index('lt_title') if 'lt_title' in col else 2
        out: dict[int, str] = {}
        for row in dump.rows(convert_dtypes=False):
            if len(row) <= max(idx_id, idx_ns, idx_title):
                continue
            lt_id, lt_ns, lt_title = row[idx_id], row[idx_ns], row[idx_title]
            try:
                ns = int(lt_ns) if lt_ns is not None else -1
            except (TypeError, ValueError):
                continue
            if ns != NS_CATEGORY:
                continue
            raw = str(lt_title) if lt_title else ''
            if not _is_garbage_linktarget_title(raw):
                out[int(lt_id)] = _normalize_title(raw)
                continue
            if seed_canonicals:
                for i, cell in enumerate((row[idx_id], row[idx_ns], row[idx_title])):
                    if i == 1:
                        continue
                    cell_str = str(cell or '').strip()
                    if _canonical_title(cell_str) in seed_canonicals:
                        out[int(lt_id)] = _normalize_title(cell_str)
                        break
        if log_progress_fn:
            log_progress("linktarget: category titles loaded", count=len(out))
        return out
    finally:
        _mwsql_dump._open_file = _orig_open


def run_categorylinks(
    categorylinks_path: Path,
    category_page_id_to_title: dict[int, str],
    *,
    linktarget_path: Optional[Path] = None,
    log_progress_fn: bool = True,
) -> set[int]:
    """
    「架空の人物」カテゴリ配下の page_id を集める。
    MediaWiki 1.45+ のダンプ（cl_to なし）の場合は linktarget_path が必須。
    """
    import mwsql.dump as _mwsql_dump
    _orig_open = _mwsql_dump._open_file
    _mwsql_dump._open_file = _open_file_utf8_replace
    try:
        with Timer() as timer:
            if log_progress_fn:
                log_progress("categorylinks: reading dump", elapsed=timer.elapsed)
            dump = Dump.from_file(str(categorylinks_path))
            col = dump.col_names
            use_cl_to = 'cl_to' in col
            idx_from = col.index('cl_from') if 'cl_from' in col else 0
            idx_type = col.index('cl_type') if 'cl_type' in col else 5
            if use_cl_to:
                idx_to = col.index('cl_to')
                idx_target = 0
                target_id_to_title = {}
            else:
                idx_to = 0
                if 'cl_target_id' not in col or linktarget_path is None:
                    raise FileNotFoundError(
                        "categorylinks に cl_to がありません（MediaWiki 1.45+ 形式）。"
                        " jawiki-latest-linktarget.sql.gz が必要です。"
                        " ホストで download.ps1 または download.sh を実行し ./dumps に配置してから、コンテナを再実行してください。"
                    )
                idx_target = col.index('cl_target_id')
                if log_progress_fn:
                    log_progress("categorylinks: loading linktarget", elapsed=timer.elapsed)
                target_id_to_title = _load_linktarget_category_titles(
                    linktarget_path,
                    seed_titles=[CATEGORY_FICTIONAL],
                    log_progress_fn=log_progress_fn,
                )

            subcat_rows: list[tuple[int, str]] = []
            subcat_rows_by_lt: list[tuple[int, int]] = []
            fictional_ids: set[int] = set()
            P_fictional = _resolve_seed_page_id(CATEGORY_FICTIONAL, category_page_id_to_title)

            def _cl_type_is(s: object, want: str) -> bool:
                """cl_type が文字列または数値で want と一致するか。"""
                if s is None:
                    return False
                if isinstance(s, str):
                    return s.strip() == want
                # 数値の場合は MediaWiki の定数: page=0, subcat=1, file=2 の可能性
                if want == "page":
                    return s == 0 or str(s).strip() == "page"
                if want == "subcat":
                    return s == 1 or str(s).strip() == "subcat"
                return str(s).strip() == want

            n_cols = max(idx_from, idx_type, idx_to, idx_target)
            # 第1パス: サブカテゴリ行を収集（cl_to の場合は名前、1.45+ の場合は (cl_from, cl_target_id)）
            subcat_rows_by_lt: list[tuple[int, int]] = []
            for row in dump.rows(convert_dtypes=True):
                if len(row) <= n_cols:
                    continue
                cl_from = row[idx_from]
                cl_type = row[idx_type]
                if not _cl_type_is(cl_type, "subcat"):
                    continue
                if use_cl_to:
                    cl_to_n = _normalize_title(str(row[idx_to]) if row[idx_to] else "")
                    if cl_to_n:
                        subcat_rows.append((cl_from, cl_to_n))
                else:
                    tid = row[idx_target]
                    tid_int = int(tid) if tid is not None else 0
                    cl_to_n = target_id_to_title.get(tid_int, "")
                    if cl_to_n:
                        subcat_rows.append((cl_from, cl_to_n))
                    subcat_rows_by_lt.append((cl_from, tid_int))

            if not use_cl_to:
                # lt_id を category の page_id に対応させる（page のタイトル一致で対応）
                category_title_to_page_id: dict[str, int] = {}
                for pid, t in category_page_id_to_title.items():
                    nt = _normalize_title(t)
                    if nt and nt not in category_title_to_page_id:
                        category_title_to_page_id[nt] = pid
                lt_id_to_page_id: dict[int, int] = {}
                for lt_id, title in target_id_to_title.items():
                    pid = category_title_to_page_id.get(title)
                    if pid is not None:
                        lt_id_to_page_id[lt_id] = pid
                # linktarget に無い lt_id をサブカテゴリ出現数から推定して補う
                missing = {
                    tid for (_, tid) in subcat_rows_by_lt
                    if tid and tid not in target_id_to_title
                }
                subcat_counts = Counter(tid for (_, tid) in subcat_rows_by_lt if tid)
                best = max(
                    (m for m in missing if subcat_counts.get(m, 0) > 0),
                    key=lambda m: subcat_counts[m],
                    default=None,
                )
                if best is not None:
                    target_id_to_title[best] = _normalize_title(CATEGORY_FICTIONAL)
                    if P_fictional is not None:
                        lt_id_to_page_id[best] = P_fictional
                    for cl_from, tid in subcat_rows_by_lt:
                        if tid == best:
                            subcat_rows.append((cl_from, _normalize_title(CATEGORY_FICTIONAL)))

            if log_progress_fn:
                log_progress("categorylinks: building C (person)", elapsed=timer.elapsed)
            if use_cl_to:
                c_fictional = _build_category_set(
                    subcat_rows, category_page_id_to_title, _normalize_title(CATEGORY_FICTIONAL)
                )
                c_fictional_page_ids: set[int] = set()
            else:
                if P_fictional is not None:
                    c_fictional_page_ids = _build_category_page_id_set(
                        subcat_rows_by_lt, lt_id_to_page_id, P_fictional
                    )
                    c_fictional = set()
                else:
                    c_fictional_page_ids = set()
                    c_fictional = _build_category_set(
                        subcat_rows, category_page_id_to_title, _normalize_title(CATEGORY_FICTIONAL)
                    )

            if log_progress_fn:
                log_progress("categorylinks: collecting page_ids", elapsed=timer.elapsed)
            dump2 = Dump.from_file(str(categorylinks_path))
            for row in dump2.rows(convert_dtypes=True):
                if len(row) <= n_cols:
                    continue
                cl_from = row[idx_from]
                cl_type = row[idx_type]
                if not _cl_type_is(cl_type, "page"):
                    continue
                if use_cl_to:
                    cl_to_n = _normalize_title(str(row[idx_to]) if row[idx_to] else "")
                    if cl_to_n in c_fictional:
                        fictional_ids.add(cl_from)
                else:
                    tid = row[idx_target]
                    tid_int = int(tid) if tid is not None else 0
                    if c_fictional_page_ids and lt_id_to_page_id.get(tid_int) in c_fictional_page_ids:
                        fictional_ids.add(cl_from)
                    elif c_fictional and target_id_to_title.get(tid_int) in c_fictional:
                        fictional_ids.add(cl_from)

            if log_progress_fn:
                log_progress(
                    "categorylinks: done",
                    count=len(fictional_ids),
                    elapsed=timer.elapsed,
                )
            return fictional_ids
    finally:
        _mwsql_dump._open_file = _orig_open
