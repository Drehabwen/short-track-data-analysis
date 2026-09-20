$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms

$installRoot = Join-Path $env:LOCALAPPDATA 'SpeedTrackPro'
New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $installRoot 'data\uploads') -Force | Out-Null

$payload = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath = Join-Path $installRoot 'SpeedTrackPro.exe'
$dbPath = Join-Path $installRoot 'blood.db'
$fallbackDbPath = Join-Path $installRoot 'SpeedTrackPro-data.db'

# 更新程序和说明文件；不覆盖已有数据库，避免重装丢失教练录入。
Copy-Item -LiteralPath (Join-Path $payload 'SpeedTrackPro.exe') -Destination $exePath -Force
foreach ($name in @('README-教练试用.txt', 'SpeedTrackPro-教练端使用手册.docx', 'SpeedTrackPro-教练端使用手册.pdf')) {
    $source = Join-Path $payload $name
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $installRoot $name) -Force
    }
}

if (-not (Test-Path -LiteralPath $dbPath)) {
    Copy-Item -LiteralPath (Join-Path $payload 'blood.db') -Destination $dbPath -Force
} elseif (-not (Test-Path -LiteralPath $fallbackDbPath)) {
    # 给旧版数据库留下安全回退库；新版启动器会自动判断并使用它。
    Copy-Item -LiteralPath (Join-Path $payload 'blood.db') -Destination $fallbackDbPath -Force
}

$uninstaller = Join-Path $installRoot 'uninstall.ps1'
Copy-Item -LiteralPath (Join-Path $payload 'uninstall.ps1') -Destination $uninstaller -Force

$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\SpeedTrack Pro'
New-Item -ItemType Directory -Path $startMenu -Force | Out-Null

function New-Shortcut([string]$path, [string]$target, [string]$arguments = '') {
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = $target
    $shortcut.Arguments = $arguments
    $shortcut.WorkingDirectory = $installRoot
    $shortcut.IconLocation = "$exePath,0"
    $shortcut.Save()
}

New-Shortcut (Join-Path $desktop 'SpeedTrack Pro.lnk') $exePath
New-Shortcut (Join-Path $startMenu 'SpeedTrack Pro.lnk') $exePath
New-Shortcut (Join-Path $startMenu '卸载 SpeedTrack Pro.lnk') 'powershell.exe' "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$uninstaller`""

Start-Process -FilePath $exePath -WorkingDirectory $installRoot
[System.Windows.Forms.MessageBox]::Show('SpeedTrack Pro 已安装完成，桌面快捷方式已创建。', 'SpeedTrack Pro', 'OK', 'Information') | Out-Null
