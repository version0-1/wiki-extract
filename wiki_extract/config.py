"""
設定と CLI 引数。
"""

import argparse
from pathlib import Path


DEFAULT_DATA_DIR = Path("/data")
DEFAULT_OUTPUT_DIR = Path("/out")

# 必須ダンプのファイル名パターン（data_dir 内でマッチするもの）
CATEGORYLINKS_GZ = "categorylinks"
PAGE_SQL_GZ = "page"
PAGES_ARTICLES_XML_BZ2 = "pages-articles"


def parse_args() -> argparse.Namespace:
    """コマンドライン引数をパースする。"""
    p = argparse.ArgumentParser(description="日本語Wikipediaダンプから人物名を抽出する")
    p.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="SQL/XML ダンプを置くディレクトリ（既定: /data）",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="出力ファイルを置くディレクトリ（既定: /out）",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="XML 解析の並列ワーカー数（既定: 1）",
    )
    return p.parse_args()
