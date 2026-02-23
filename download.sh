#!/usr/bin/env bash
#
# 日本語Wikipediaダンプを dumps/ にダウンロードする。
# 使い方: ./download.sh [日付]
#   日付なし: latest を取得
#   日付あり: 例 ./download.sh 20260201
#
set -e

BASE_URL='https://dumps.wikimedia.org/jawiki'
DATE="${1:-latest}"
OUT_DIR="${2:-dumps}"

FILES=(
  'page.sql.gz'
  'categorylinks.sql.gz'
  'pages-articles.xml.bz2'
  'linktarget.sql.gz'
)

mkdir -p "$OUT_DIR"
# 書き込み権限がない場合（例: dumps が Docker で root 作成）は案内して終了
if ! touch "$OUT_DIR/.write_test" 2>/dev/null; then
  echo "Error: 書き込みできません: $OUT_DIR" >&2
  echo "  Docker で dumps を作った場合は: sudo chown -R \$(whoami) $OUT_DIR" >&2
  exit 1
fi
rm -f "$OUT_DIR/.write_test"
cd "$OUT_DIR"

for f in "${FILES[@]}"; do
  name="jawiki-${DATE}-${f}"
  url="${BASE_URL}/${DATE}/${name}"
  if [[ -f "$name" ]]; then
    echo "Skip (exists): $name"
  else
    echo "Download: $url"
    if command -v curl &>/dev/null; then
      curl -L -O -C - "$url"
    elif command -v wget &>/dev/null; then
      wget -c "$url"
    else
      echo "Error: curl or wget required" >&2
      exit 1
    fi
  fi
done

echo "Done. Files in $(pwd):"
ls -la jawiki-"${DATE}"-*
