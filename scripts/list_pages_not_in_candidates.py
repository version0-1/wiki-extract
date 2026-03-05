#!/usr/bin/env python3
"""
character_candidates.csv に1件も出力されていないページのリストを取得する。

使い方:
  python scripts/list_pages_not_in_candidates.py [--output-dir OUT]
  # 出力: ページ名（1行1件）を stdout、件数を stderr に表示
  python scripts/list_pages_not_in_candidates.py --csv missing_pages.csv
  # 出力: missing_pages.csv に page_id,ページ名 で保存
"""

import argparse
import csv
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description='character_candidates.csv に含まれないページのリストを出力する'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('out'),
        help='out と page_meta.json / pages/ / character_candidates.csv の親。既定: out',
    )
    parser.add_argument(
        '--csv',
        type=Path,
        default=None,
        help='結果をこのCSVに保存（page_id,ページ名）。指定しなければ stdout にページ名のみ',
    )
    args = parser.parse_args()

    out = args.output_dir.resolve()
    meta_path = out / 'page_meta.json'
    pages_dir = out / 'pages'
    csv_path = out / 'character_candidates.csv'

    if not meta_path.is_file():
        print(f'Error: {meta_path} が見つかりません', file=sys.stderr)
        sys.exit(1)
    if not pages_dir.is_dir():
        print(f'Error: {pages_dir} が見つかりません', file=sys.stderr)
        sys.exit(1)
    if not csv_path.is_file():
        print(f'Error: {csv_path} が見つかりません', file=sys.stderr)
        sys.exit(1)

    with open(meta_path, encoding='utf-8') as f:
        meta = json.load(f)
    main_id_to_title = meta['main_id_to_title']

    # CSV に出現するページ名の集合（1列目。ヘッダー除く）
    pages_in_csv: set[str] = set()
    with open(csv_path, encoding='utf-8', newline='') as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            if row:
                pages_in_csv.add(row[0].strip())

    # out/pages/*.txt のうち、CSV に1件もないページ
    missing: list[tuple[str, str]] = []
    for path in sorted(pages_dir.glob('*.txt'), key=lambda p: (not p.stem.isdigit(), p.stem)):
        if not path.stem.isdigit():
            continue
        page_id = path.stem
        page_title = main_id_to_title.get(page_id, page_id)
        page_display = page_title.replace('_', ' ')
        if page_display not in pages_in_csv:
            missing.append((page_id, page_display))

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with open(args.csv, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(['page_id', 'ページ名'])
            w.writerows(missing)
        print(f'Wrote {len(missing)} rows to {args.csv}', file=sys.stderr)
    else:
        for _pid, name in missing:
            print(name)
    print(f'{len(missing)} ページが character_candidates.csv に含まれていません', file=sys.stderr)


if __name__ == '__main__':
    main()
