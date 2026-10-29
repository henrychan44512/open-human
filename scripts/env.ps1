# 把项目自带的便携工具接进当前 PowerShell 会话。
# 用法：  . .\scripts\env.ps1
#
# 为什么要这个文件：这些工具没有装进系统，都在 vendor\ 下。
# 每次新开终端都要先 dot-source 一次。

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# uv 的 Python 和缓存都放项目内，避免写 %LOCALAPPDATA%
$env:UV_PYTHON_INSTALL_DIR = Join-Path $root 'vendor\python'
$env:UV_CACHE_DIR = Join-Path $root 'vendor\uv-cache'
$env:UV_NO_MODIFY_PATH = '1'

# 让 uv / git / llama.cpp 能被直接调用
$dirs = @(
    'vendor\uv'
    'vendor\git\cmd'
    'vendor\llama'
)
$py = Get-ChildItem 'vendor\python' -Directory -Filter 'cpython-3.12*' -ErrorAction SilentlyContinue |
      Select-Object -First 1
if ($py) { $dirs += "vendor\python\$($py.Name)" }
if (Test-Path '.venv\Scripts') { $dirs += '.venv\Scripts' }

$add = $dirs | ForEach-Object { Join-Path $root $_ } | Where-Object { Test-Path $_ }
$env:PATH = ($add -join ';') + ';' + $env:PATH

Write-Host "env ready:" -ForegroundColor DarkGray
Write-Host "  uv        $(if (Get-Command uv -ErrorAction SilentlyContinue) { uv --version } else { 'MISSING' })" -ForegroundColor DarkGray
Write-Host "  python    $(if (Get-Command python -ErrorAction SilentlyContinue) { python --version } else { 'MISSING' })" -ForegroundColor DarkGray
Write-Host "  git       $(if (Get-Command git -ErrorAction SilentlyContinue) { git --version } else { 'MISSING' })" -ForegroundColor DarkGray
Write-Host "  llama     $(if (Test-Path 'vendor\llama\llama-server.exe') { 'vendor\llama\llama-server.exe' } else { 'MISSING' })" -ForegroundColor DarkGray
