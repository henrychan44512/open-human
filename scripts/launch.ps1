# Open Human  beta v0.1  —  启动器
#
# 中文只写在这里：cmd.exe 用 OEM 代码页读 .bat，中文放进 .bat 会变成乱码命令。
# 这个文件必须是 **UTF-8 带 BOM**，否则 Windows PowerShell 5.1 会按 GBK 读，
# 中文全糊。`scripts\_fix_eol.py` 负责补 BOM 和 CRLF。

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

$variants = @(
    [pscustomobject]@{
        Key   = '1'
        File  = 'models\MiniCPM5-1B-Q4_K_M.gguf'
        Name  = 'MiniCPM5-1B'
        Title = '1B  轻快'
        Note  = '开口快，回答短，4 GB 内存的老机器也跑得动'
    }
    [pscustomobject]@{
        Key   = '2'
        File  = 'models\MiniCPM5-2B-Q4_K_M.gguf'
        Name  = 'MiniCPM5-2B'
        Title = '2B  更像人'
        Note  = '记得更多、话更像人，慢一两秒'
    }
)

foreach ($v in $variants) {
    $full = Join-Path $root $v.File
    $size = 0
    if (Test-Path -LiteralPath $full) { $size = (Get-Item -LiteralPath $full).Length }
    $v | Add-Member -NotePropertyName Size -NotePropertyValue $size -Force
}

$pick = $null
# 先把参数存进变量：scriptblock 里的 $args 是它自己的，会把脚本参数遮掉。
$firstArg = ''
if ($args.Count -gt 0 -and $args[0]) { $firstArg = ([string]$args[0]).Trim() }

if ($firstArg) {
    $pick = $variants | Where-Object { $_.Key -eq $firstArg }
    if (-not $pick) {
        Write-Host ''
        Write-Host ("  参数只认 1 或 2，收到的是：{0}" -f $firstArg)
        Read-Host '  按回车退出'
        exit 2
    }
}

if (-not $pick) {
    Write-Host ''
    Write-Host '  =================================================='
    Write-Host '    Open Human   beta v0.1'
    Write-Host '    一个文件夹就是一个人。'
    Write-Host '  =================================================='
    Write-Host ''
    Write-Host '    先选这个人的脑子 —— 两个都能聊，只是快慢和记性不同：'
    Write-Host ''
    foreach ($v in $variants) {
        if ($v.Size -gt 0) { $size = '{0:N0} MB' -f ($v.Size / 1MB) } else { $size = '缺文件' }
        Write-Host ('      [{0}]  {1}   {2,9}   {3}' -f $v.Key, $v.Title, $size, $v.Note)
    }
    Write-Host ''
    Write-Host '    默认 2B。直接按回车就行。'
    Write-Host ''
    $answer = Read-Host '    输入 1 或 2，回车 = 2'

    $answer = ([string]$answer).Trim()
    if ($answer -eq '1') { $pick = $variants[0] }
    elseif ($answer -eq '2') { $pick = $variants[1] }
    else { $pick = $variants[1] }
}

# 选的那个没下、另一个在：用有的那个，说清楚，不要直接退出。
if ($pick.Size -le 0) {
    $other = $variants | Where-Object { $_.Key -ne $pick.Key -and $_.Size -gt 0 } | Select-Object -First 1
    Write-Host ''
    Write-Host ('  找不到 {0} 的权重：{1}' -f $pick.Title, $pick.File) -ForegroundColor Yellow
    if ($other) {
        Write-Host ('  改用已经下好的 {0}。' -f $other.Title) -ForegroundColor Yellow
        $pick = $other
    }
    else {
        Write-Host '  两个权重都不在 models\ 里，没法启动。' -ForegroundColor Red
        Write-Host '  重新解压这个文件夹，或者按 README 里的地址把 .gguf 下到 models\。'
        Read-Host '  按回车退出'
        exit 1
    }
}

$env:OH_MODEL_FILE = $pick.File
$env:OH_MODEL_NAME = $pick.Name

Write-Host ''
Write-Host ('  用 {0} 启动。窗口一两秒就出来，模型在后面读进内存（第一次十几秒）。' -f $pick.Title) -ForegroundColor Green
Write-Host '  关掉窗口 = 这段对话存下来了，下次回来接着聊。'
Write-Host ''

& (Join-Path $root 'Open Human.cmd')
exit $LASTEXITCODE
