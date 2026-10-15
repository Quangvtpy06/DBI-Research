$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$interpreter = Join-Path $projectDirectory '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $interpreter)) {
    $interpreter = Join-Path (Split-Path $projectDirectory -Parent) '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $interpreter)) { throw "Chưa có môi trường Python. Hãy làm bước cài đặt trong README.md." }
Set-Location -LiteralPath $projectDirectory
& $interpreter -m streamlit run app.py --server.address 127.0.0.1
