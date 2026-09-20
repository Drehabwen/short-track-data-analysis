$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Windows.Forms
$installRoot = Join-Path $env:LOCALAPPDATA 'SpeedTrackPro'
$desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'SpeedTrack Pro.lnk'
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\SpeedTrack Pro'

Get-Process -Name 'SpeedTrackPro' -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item -LiteralPath $desktopShortcut -Force
Remove-Item -LiteralPath $startMenu -Recurse -Force

$answer = [System.Windows.Forms.MessageBox]::Show(
    '是否同时删除本机训练数据？选择“否”可保留数据供以后恢复。',
    '卸载 SpeedTrack Pro', 'YesNoCancel', 'Question'
)
if ($answer -eq 'Cancel') { exit 0 }
if ($answer -eq 'Yes') {
    Remove-Item -LiteralPath $installRoot -Recurse -Force
} else {
    Remove-Item -LiteralPath (Join-Path $installRoot 'SpeedTrackPro.exe') -Force
    Remove-Item -LiteralPath (Join-Path $installRoot 'README-教练试用.txt') -Force
    Remove-Item -LiteralPath (Join-Path $installRoot 'SpeedTrackPro-教练端使用手册.docx') -Force
    Remove-Item -LiteralPath (Join-Path $installRoot 'SpeedTrackPro-教练端使用手册.pdf') -Force
    Remove-Item -LiteralPath (Join-Path $installRoot 'uninstall.ps1') -Force
}
