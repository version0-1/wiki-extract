"""
ダンプファイルのパスを解決し、存在を検証する。
"""

from pathlib import Path


def find_dump(data_dir: Path, substring: str) -> Path:
    """data_dir 内で名前が substring を含むファイルを1つ返す（例: 'categorylinks'）。"""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory does not exist: {data_dir}")
    for f in data_dir.iterdir():
        if f.is_file() and substring in f.name:
            return f
    raise FileNotFoundError(
        f"No file containing '{substring}' in {data_dir}. "
        "Download dumps first (e.g. run download.ps1 or download.sh) and put them in ./dumps, "
        "then start the container (./dumps is mounted as /data)."
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
        raise FileNotFoundError(f"Data directory does not exist: {data_dir}")
    candidates = [f for f in data_dir.iterdir() if f.is_file() and "pages-articles" in f.name]
    xml_plain = [f for f in candidates if f.name.endswith(".xml") and not f.name.endswith(".xml.bz2")]
    if xml_plain:
        return xml_plain[0]
    bz2_files = [f for f in candidates if f.name.endswith(".xml.bz2")]
    if bz2_files:
        return bz2_files[0]
    raise FileNotFoundError(
        f"No pages-articles dump (.xml or .xml.bz2) in {data_dir}. "
        "Download or decompress jawiki-latest-pages-articles.xml.bz2."
    )


def require_dumps(data_dir: Path) -> tuple[Path, Path, Path]:
    """
    (categorylinks_gz, page_sql_gz, pages_articles_path) を返す。
    pages_articles_path は解凍済み .xml または .xml.bz2。
    """
    cl = find_dump(data_dir, "categorylinks")
    page = find_dump(data_dir, "page")
    xml = find_pages_articles(data_dir)
    if "categorylinks" not in cl.name or not cl.name.endswith(".sql.gz"):
        raise FileNotFoundError(f"Expected categorylinks SQL dump (e.g. *categorylinks*.sql.gz): {cl}")
    if "page" not in page.name or not page.name.endswith(".sql.gz"):
        raise FileNotFoundError(f"Expected page SQL dump (e.g. *page*.sql.gz): {page}")
    if "pages-articles" not in xml.name:
        raise FileNotFoundError(f"Expected pages-articles XML dump: {xml}")
    if not (xml.name.endswith(".xml") or xml.name.endswith(".xml.bz2")):
        raise FileNotFoundError(f"Expected pages-articles .xml or .xml.bz2: {xml}")
    return cl, page, xml
