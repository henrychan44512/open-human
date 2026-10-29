# Build the beta zip: everything needed to double-click and run, nothing personal.
#
#   powershell -ExecutionPolicy Bypass -File scripts\pack_beta.ps1 -DryRun
#   powershell -ExecutionPolicy Bypass -File scripts\pack_beta.ps1
#
# ASCII only on purpose: without a BOM, Windows PowerShell 5.1 reads .ps1 with the
# OEM codepage and mangles non-ASCII text (same trap as install_shortcut.ps1).
#
# What goes in: source, docs, the demo persona, models, the portable toolchain,
# the .venv, LICENSE. What stays out: git history, runtime junk, local config.

param(
    [switch]$DryRun,
    [string]$Out = ""
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$name = 'open-human'

$pyproject = Get-Content (Join-Path $root 'pyproject.toml') -Raw
if ($pyproject -match '(?m)^version\s*=\s*"([^"]+)"') { $version = $Matches[1] } else { $version = '0.0.0' }
if (-not $Out) { $Out = Join-Path $root "dist\$name-$version-beta.zip" }

# Directories never shipped (relative to the repo root).
$skipDirs = @(
    '.git'
    'data'
    'dist'
    'vendor\git'          # portable git: a dev tool, the runtime never calls it (91.8 MB)
    'vendor\webview2'     # WebView2 spike SDK, not part of the runtime
)
# Never shipped anywhere in the tree.
$skipNames = @('__pycache__', '.pytest_cache', '.ruff_cache', '.pyphen-cache')
$skipFiles = @('config.toml')   # local settings, may hold a key
$skipPatterns = @('*.log', 'pytest-of-*')

function Test-Skipped([string]$rel, [System.IO.FileInfo]$file) {
    foreach ($d in $skipDirs) {
        if ($rel -eq $d -or $rel.StartsWith($d + [System.IO.Path]::DirectorySeparatorChar)) { return $true }
    }
    foreach ($part in $rel.Split([System.IO.Path]::DirectorySeparatorChar)) {
        if ($skipNames -contains $part) { return $true }
        # pytest-of-*/ is a directory too: matching only file names let 170 files
        # of pytest scratch data into the zip once.
        foreach ($p in $skipPatterns) { if ($part -like $p) { return $true } }
    }
    if ($skipFiles -contains $file.Name) { return $true }
    foreach ($p in $skipPatterns) { if ($file.Name -like $p) { return $true } }
    return $false
}

$files = New-Object System.Collections.Generic.List[string]
$bytes = 0L
Get-ChildItem -LiteralPath $root -Recurse -File -Force | ForEach-Object {
    $rel = $_.FullName.Substring($root.Length + 1)
    if (-not (Test-Skipped $rel $_)) {
        $files.Add($rel)
        $bytes += $_.Length
    }
}

Write-Host ("open human {0} beta" -f $version)
Write-Host ("  files: {0:N0}" -f $files.Count)
Write-Host ("  size : {0:N0} MB" -f ($bytes / 1MB))
Write-Host ("  out  : {0}" -f $Out)

# Refuse to ship personal state by accident. Runs before the dry-run return on
# purpose: this check used to sit after it, so -DryRun never caught a stale name.
$mustHave = @('LICENSE', 'README.md', 'pyproject.toml', 'Open Human.cmd',
              'src\openhuman\cli.py', 'humans\demo\human_data.md', '.venv\Scripts\python.exe')
$mustNotHave = @('data\', 'config.toml', '.git\')
foreach ($m in $mustHave) {
    if (-not ($files | Where-Object { $_ -eq $m })) { throw "missing from the pack: $m" }
}
foreach ($m in $mustNotHave) {
    $hit = $files | Where-Object { $_ -like "$m*" } | Select-Object -First 1
    if ($hit) { throw "should not be in the pack: $hit" }
}
$gguf = $files | Where-Object { $_ -like 'models\*.gguf' } | Select-Object -First 1
if (-not $gguf) { throw 'missing the model weights' }
if (-not ($files | Where-Object { $_ -like 'vendor\llama\llama-server.exe' })) {
    throw 'missing vendor\llama\llama-server.exe'
}

if ($DryRun) {
    Write-Host "`n  -- skipped --"
    foreach ($d in $skipDirs) {
        $full = Join-Path $root $d
        if (Test-Path -LiteralPath $full) {
            $s = (Get-ChildItem -LiteralPath $full -Recurse -File -Force -ErrorAction SilentlyContinue |
                    Measure-Object Length -Sum).Sum
            Write-Host ("  {0,-18} {1,8:N1} MB" -f $d, ($s / 1MB))
        }
    }
    Write-Host "`n  dry run only - nothing was written."
    return
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Out) | Out-Null
$list = Join-Path $env:TEMP ("oh-pack-{0}.txt" -f $PID)
[System.IO.File]::WriteAllLines($list, $files, (New-Object System.Text.UTF8Encoding($false)))

Write-Host "`n  packing (a minute or two)..."
$sw = [System.Diagnostics.Stopwatch]::StartNew()
# Not tar: Windows' bsdtar writes non-ASCII names in the OEM codepage, and even
# refuses a -T list that contains one. zip_tree.py writes UTF-8 + flag bit 11.
& (Join-Path $root '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'zip_tree.py') `
    --root $root --list $list --out $Out
$code = $LASTEXITCODE
$sw.Stop()
Remove-Item -LiteralPath $list -Force -ErrorAction SilentlyContinue
if ($code -ne 0) { throw "packing failed with $code" }

# Read the archive back: the file list above is a promise, this is the check.
& (Join-Path $root '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'zip_tree.py') --out $Out --check
if ($LASTEXITCODE -ne 0) { throw "archive failed verification" }

Write-Host ("  done in {0:N0}s" -f $sw.Elapsed.TotalSeconds)
Write-Host ("  {0}" -f $Out)
