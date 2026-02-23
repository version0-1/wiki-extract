"""
LLM バッチ実行の共通ループ。split / filter で共有する。
"""

import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from wiki_extract.llm.parser_common import log_ollama_connection_refused_hint
from wiki_extract.util.log import log, log_progress


def stagger_batch_start(batch_start: int, batch_size: int, workers: int) -> None:
    """
    並列ワーカーで API 同時打ちを避けるため、バッチ開始を最大 (workers-1) 秒ずらす。
    _process_one_batch の先頭で呼ぶ。
    """
    delay = (batch_start // batch_size) % workers
    if delay > 0:
        time.sleep(delay)


def run_llm_batch_loop(
    rows_to_do: list,
    batch_size: int,
    process_batch_fn: Callable[..., Any],
    process_batch_kwargs: dict,
    workers: int,
    total_timer: Any,
    log_progress_name: str,
    skipped_count: int,
    total_rows: int,
    on_success: Callable[[int, list, Any, int], None],
    on_after_batch: Callable[[], None] | None = None,
) -> int:
    """
    バッチを ThreadPoolExecutor で並列実行し、完了ごとに on_success で結果を書き出す。
    on_success(batch_start, batch_rows, result, processed_count_after) の
    processed_count_after は、このバッチを足した後の処理済み行数（skipped_count 含む）。
    返り値: エラー数。
    """
    errors = 0
    connection_error_hint_shown = False
    processed_count = skipped_count

    batches = [
        (batch_start, rows_to_do[batch_start : batch_start + batch_size])
        for batch_start in range(0, len(rows_to_do), batch_size)
    ]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            batch_start: executor.submit(
                process_batch_fn,
                batch_start,
                batch_rows,
                **process_batch_kwargs,
            )
            for batch_start, batch_rows in batches
        }
        future_to_batch = {f: bs for bs, f in futures.items()}
        for future in as_completed(futures.values()):
            batch_start = future_to_batch[future]
            batch_rows = rows_to_do[batch_start : batch_start + batch_size]
            try:
                result = future.result()
                processed_count += len(batch_rows)
                on_success(batch_start, batch_rows, result, processed_count)
                if processed_count % 1500 == 0 or processed_count >= total_rows:
                    log(f'  行 {processed_count}/{total_rows} 完了')
            except (urllib.error.URLError, OSError) as e:
                log(f'  API エラー バッチ行 {batch_start + 1}-{batch_start + len(batch_rows)}: {e}')
                errors += 1
                if not connection_error_hint_shown and (
                    'Connection refused' in str(e) or '111' in str(e)
                ):
                    connection_error_hint_shown = True
                    log_ollama_connection_refused_hint()
            except Exception as e:
                log(f'  API エラー バッチ行 {batch_start + 1}-{batch_start + len(batch_rows)}: {e}')
                errors += 1
            if on_after_batch is not None:
                on_after_batch()
            log_progress(log_progress_name, count=processed_count, elapsed=total_timer.elapsed)
    return errors
