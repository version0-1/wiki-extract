# 初回セットアップ: dumps/ と out/ を自分の権限で作成し、ダンプをダウンロードする。
# 配布先で誰でも同じ手順で使えるように、必ずこのスクリプトを先に実行してから docker compose すること。
#
# 使い方: .\setup.ps1 [日付]
#   日付なし: latest を取得
#   例: .\setup.ps1 20260201
#

param(
  [string]$Date = 'latest'
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = (Get-Location).Path }
Set-Location $ScriptDir

Write-Host '1. dumps/ と out/ を作成します（自分の権限で）'
New-Item -ItemType Directory -Force -Path dumps, out | Out-Null

$existing = Get-ChildItem -Path dumps -File -ErrorAction SilentlyContinue
if ($existing) {
  Write-Host 'Error: dumps/ に既にファイルがあります。再ダウンロードする場合は古いファイルを削除してから実行してください。'
  Write-Host '  例: Remove-Item dumps\jawiki-* -Force'
  exit 1
}

Write-Host '2. ダンプファイルをダウンロードします（数GBのため時間がかかります）'
$downloadPs1 = Join-Path $ScriptDir 'download.ps1'
if (Test-Path $downloadPs1) {
  & $downloadPs1 -Date $Date -OutDir dumps
} else {
  Write-Host 'Error: download.ps1 が見つかりません。リポジトリのルートで実行してください。'
  exit 1
}

Write-Host ''
Write-Host 'セットアップ完了。次のコマンドでコンテナを起動してください:'
Write-Host '  docker compose up -d'
Write-Host '  docker compose exec wiki_extract uv run python -m wiki_extract extract-pages'
Write-Host '  docker compose exec wiki_extract uv run python -m wiki_extract extract-character-candidates'
Write-Host '  docker compose exec wiki_extract uv run python -m wiki_extract ai-characters-filter --input-list /out/character_candidates.csv ...'
Write-Host '  docker compose exec wiki_extract uv run python -m wiki_extract ai-characters-split ...'
