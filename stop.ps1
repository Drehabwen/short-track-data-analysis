# 一键停止：关闭后端和前端进程（PostgreSQL 保留运行）
$ROOT = $PSScriptRoot

Write-Host "停止 Next.js 前端..." -ForegroundColor Yellow
Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -match "next" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "停止 FastAPI 后端..." -ForegroundColor Yellow
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match "uvicorn" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "完成。PostgreSQL 继续运行（数据保留）。" -ForegroundColor Green
Write-Host "如需彻底停止 PostgreSQL：& 'C:\pgsql18\pgsql\bin\pg_ctl.exe' -D C:\pgsql18\data stop" -ForegroundColor DarkGray
