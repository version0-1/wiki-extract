FROM python:3.14.0-slim

ENV UV_PROJECT_ENVIRONMENT=/usr/local
WORKDIR /app

# uv はコンテナ内に直接インストール（pip でインストール）
RUN pip install --no-cache-dir uv

# 依存は pyproject.toml で管理し、コンテナ内の uv でインストール
# hatchling がパッケージと README を参照するため、必要なファイルをコピーしてから sync
COPY pyproject.toml uv.lock* README.md ./
COPY wiki_extract/ ./wiki_extract/
# mwparserfromhell の C 拡張をビルドしない（slim に gcc なし → 純 Python トークナイザー）
ENV WITH_EXTENSION=0
RUN uv sync --no-dev

COPY . .
