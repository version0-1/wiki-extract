#!/usr/bin/env python3
"""
ページタイトルから対象 page ファイルの番号（page_id）とパスを調べる。

使い方:
  python scripts/title_to_page_id.py "封神演義の登場人物一覧"
  # 出力: page_id と pages/{id}.txt のパス
  python scripts/title_to_page_id.py "封神演義" --search   # 部分一致で一覧（page_id, タイトル, パス）
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description='ページタイトルから page_id（対象 .txt の番号）を調べる'
    )
    parser.add_argument(
        'title',
        type=str,
        nargs='?',
        default=None,
        help='検索するページタイトル（省略時は --search と組み合わせで空で全件は出さない）',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('out'),
        help='page_meta.json と pages/ があるディレクトリ。既定: out',
    )
    parser.add_argument(
        '--search',
        action='store_true',
        help='部分一致で検索し、該当する (page_id, タイトル, パス) をすべて表示',
    )
    args = parser.parse_args()

    out = args.output_dir.resolve()
    meta_path = out / 'page_meta.json'

    if not meta_path.is_file():
        print(f'Error: {meta_path} が見つかりません', file=sys.stderr)
        sys.exit(1)

    with open(meta_path, encoding='utf-8') as f:
        meta = json.load(f)
    main_id_to_title = meta['main_id_to_title']

    if args.search:
        query = (args.title or '').strip()
        if not query:
            print('Error: --search のときはタイトルを指定してください', file=sys.stderr)
            sys.exit(1)
        matches = [
            (pid, title)
            for pid, title in main_id_to_title.items()
            if query in title or query in title.replace('_', ' ')
        ]
        if not matches:
            print(f'"{query}" に一致するページはありません', file=sys.stderr)
            sys.exit(1)
        pages_dir = out / 'pages'
        for pid, title in sorted(matches, key=lambda x: (x[1], x[0])):
            display = title.replace('_', ' ')
            path = pages_dir / f'{pid}.txt'
            print(f'{pid}\t{display}\t{path}')
        print(f'# {len(matches)} 件', file=sys.stderr)
        return

    title_arg = (args.title or '').strip()
    if not title_arg:
        parser.print_help(sys.stderr)
        print('Error: タイトルを指定してください', file=sys.stderr)
        sys.exit(1)

    # 完全一致: タイトルはアンダースコア／スペースの表記揺れあり
    norm_arg = title_arg.replace(' ', '_')
    found: list[tuple[str, str]] = []
    for pid, title in main_id_to_title.items():
        if title == title_arg or title == norm_arg:
            found.append((pid, title))
        elif title.replace('_', ' ') == title_arg.replace('_', ' '):
            found.append((pid, title))
    # 重複 page_id を除く（同じページの別表記）
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for pid, title in found:
        if pid not in seen:
            seen.add(pid)
            unique.append((pid, title))
    found = unique

    if not found:
        print(f'"{title_arg}" に完全一致するページはありません', file=sys.stderr)
        print('  --search で部分一致を試してください', file=sys.stderr)
        sys.exit(1)

    pages_dir = out / 'pages'
    for pid, title in found:
        path = pages_dir / f'{pid}.txt'
        print(f'{pid}\t{path}')


if __name__ == '__main__':
    main()
