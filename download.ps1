# 日本語Wikipediaダンプを dumps/ にダウンロードする。
# 使い方: .\download.ps1 [日付] [出力ディレクトリ]
#   日付なし: latest を取得
#   例: .\download.ps1 20260201
#   例: .\download.ps1 latest .\dumps

param(
  [string]$Date = 'latest',
  [string]$OutDir = 'dumps'
)

$BaseUrl = 'https://dumps.wikimedia.org/jawiki'
$Files = @(
  'page.sql.gz',
  'categorylinks.sql.gz',
  'pages-articles.xml.bz2',
  'linktarget.sql.gz'
)

if (-not (Test-Path $OutDir)) {
  New-Item -ItemType Directory -Path $OutDir | Out-Null
}
Push-Location $OutDir
try {
  foreach ($f in $Files) {
    $name = "jawiki-$Date-$f"
    $url = "$BaseUrl/$Date/$name"
    if (Test-Path $name) {
      Write-Host "Skip (exists): $name"
    } else {
      Write-Host "Download: $url"
      Invoke-WebRequest -Uri $url -OutFile $name -UseBasicParsing
    }
  }
  Write-Host "Done. Files in $(Get-Location):"
  Get-ChildItem "jawiki-$Date-*"
} finally {
  Pop-Location
}
