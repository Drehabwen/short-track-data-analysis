@echo off
setlocal
cd /d "%~dp0"

echo 正在启动 SpeedTrack Pro 教练端...
start "SpeedTrack Pro" "%~dp0SpeedTrackPro.exe"
timeout /t 4 /nobreak >nul
start "" "http://localhost:8000"
echo 已打开 http://localhost:8000
echo 关闭本窗口不会停止服务；请使用“停止教练端.bat”停止。
endlocal
