"""
ダンプファイルのパスを解決し、存在を検証する。
"""

from pathlib import Path


def find_dump(data_dir: Path, substring: str) -> Path:
    """data_dir 内で名前が substring を含むファイルを1つ返す（例: 'categorylinks'）。"""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise FileNotFoundError(f"データディレクトリが存在しません: {data_dir}")
    for f in data_dir.iterdir():
        if f.is_file() and substring in f.name:
            return f
    raise FileNotFoundError(
        f"{data_dir} に '{substring}' を含むファイルがありません。"
        "ホスト（プロジェクトルート）で ./setup.sh または ./download.sh を実行してダンプを ./dumps に配置し、"
        "その後コンテナを再実行してください（./dumps は /data にマウントされます）。"
    )


def find_dump_optional(data_dir: Path, substring: str) -> Path | None:
    """data_dir 内で名前が substring を含むファイルを1つ返す。見つからなければ None。"""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        return None
    for f in data_dir.iterdir():
        if f.is_file() and substring in f.name:
            return f
    return None


def find_pages_articles(data_dir: Path) -> Path:
    """
    pages-articles ダンプを探す: 解凍済み .xml を優先、なければ .xml.bz2。
    """
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise FileNotFoundError(f"データディレクトリが存在しません: {data_dir}")
    candidates = [f for f in data_dir.iterdir() if f.is_file() and "pages-articles" in f.name]
    xml_plain = [f for f in candidates if f.name.endswith(".xml") and not f.name.endswith(".xml.bz2")]
    if xml_plain:
        return xml_plain[0]
    bz2_files = [f for f in candidates if f.name.endswith(".xml.bz2")]
    if bz2_files:
        return bz2_files[0]
    raise FileNotFoundError(
        f"pages-articles ダンプ（.xml または .xml.bz2）が {data_dir} にありません。"
        "jawiki-latest-pages-articles.xml.bz2 をダウンロードまたは解凍してください。"
    )


def _find_page_dump(data_dir: Path) -> Path:
    """page テーブル用の .sql.gz を返す。pages-articles は除外する。"""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise FileNotFoundError(f"データディレクトリが存在しません: {data_dir}")
    for f in data_dir.iterdir():
        if (
            f.is_file()
            and "page" in f.name
            and f.name.endswith(".sql.gz")
            and "pages-articles" not in f.name
        ):
            return f
    raise FileNotFoundError(
        f"page テーブル用 SQL ダンプ（*page*.sql.gz、*pages-articles* を除く）が {data_dir} にありません。"
        "ホスト（プロジェクトルート）で ./setup.sh または ./download.sh を実行してダンプを ./dumps に配置し、"
        "その後コンテナを再実行してください（./dumps は /data にマウントされます）。"
    )


def require_dumps(data_dir: Path) -> tuple[Path, Path, Path]:
    """
    (categorylinks_gz, page_sql_gz, pages_articles_path) を返す。
    pages_articles_path は解凍済み .xml または .xml.bz2。
    """
    cl = find_dump(data_dir, "categorylinks")
    page = _find_page_dump(data_dir)
    xml = find_pages_articles(data_dir)
    if "categorylinks" not in cl.name or not cl.name.endswith(".sql.gz"):
        raise FileNotFoundError(f"categorylinks 用 SQL ダンプ（例: *categorylinks*.sql.gz）が必要です: {cl}")
    if "page" not in page.name or not page.name.endswith(".sql.gz"):
        raise FileNotFoundError(f"page 用 SQL ダンプ（例: *page*.sql.gz）が必要です: {page}")
    if "pages-articles" not in xml.name:
        raise FileNotFoundError(f"pages-articles 用 XML ダンプが必要です: {xml}")
    if not (xml.name.endswith(".xml") or xml.name.endswith(".xml.bz2")):
        raise FileNotFoundError(f"pages-articles は .xml または .xml.bz2 である必要があります: {xml}")
    return cl, page, xml
