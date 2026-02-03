"""
進捗ログを stderr に出力する。
"""

import sys
import time
from typing import Optional


def log(msg: str) -> None:
    """メッセージを stderr に書き出す（UTF-8）。"""
    print(msg, file=sys.stderr, flush=True)


def format_elapsed(seconds: float) -> str:
    """秒数を実行時間表示用に整形する（例: 1時間23分45秒、12分34秒）。"""
    if seconds < 0:
        return "0秒"
    s = int(round(seconds))
    if s < 60:
        return f"{s}秒"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}分{s}秒"
    h, m = divmod(m, 60)
    return f"{h}時間{m}分{s}秒"


def log_progress(stage: str, count: Optional[int] = None, elapsed: Optional[float] = None) -> None:
    """進捗をログ出力: ステージ名と任意で件数・経過秒数。"""
    parts = [f"[{stage}]"]
    if count is not None:
        parts.append(f"count={count}")
    if elapsed is not None:
        parts.append(f"elapsed={elapsed:.1f}s")
    log(" ".join(parts))


class Timer:
    """経過時間を計測する簡易コンテキストマネージャ。"""

    def __init__(self) -> None:
        self.start: float = 0.0

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        pass

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.start
