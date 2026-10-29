# 在桌面和开始菜单放一个「Open Human」：自己的图标、自己的名字，双击就开。
# 只在用户机器上跑一次，不进 runtime：python 一行都不知道捷径的存在。

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot          # 本文件在 scripts/ 下，上一级是仓库根
$cmd = Join-Path $root 'Open Human.cmd'
$ico = Join-Path $root 'assets\OpenHuman.ico'

if (-not (Test-Path -LiteralPath $cmd)) { throw "找不到 $cmd" }
if (-not (Test-Path -LiteralPath $ico)) { throw "找不到 $ico" }

$shell = New-Object -ComObject WScript.Shell

$targets = @(
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Open Human.lnk')
    (Join-Path (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs') 'Open Human.lnk')
)

foreach ($path in $targets) {
    $dir = Split-Path -Parent $path
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $sc = $shell.CreateShortcut($path)
    $sc.TargetPath = $cmd
    $sc.WorkingDirectory = $root
    $sc.IconLocation = "$ico,0"
    # 7 = 最小化：启动时那个控制台别挡在前面，先看见他
    $sc.WindowStyle = 7
    $sc.Description = '打开一个人格文件夹，AI 以第一人称成为他'
    $sc.Save()
    Write-Host "created $path"
}
