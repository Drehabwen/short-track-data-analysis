# ============================================================
# 短道速滑运动员血液数据分析平台 — 一键启动
# 启动 PostgreSQL + FastAPI 后端 + Next.js 前端
# 用法：双击运行，或 PowerShell 执行 .\start.ps1
# ============================================================
$ErrorActionPreference = "Stop"

$ROOT = $PSScriptRoot
$PG_BIN = "C:\pgsql18\pgsql\bin"
$PG_DATA = "C:\pgsql18\data"
$PG_LOG = "C:\pgsql18\pg.log"
$BACKEND = "$ROOT\backend"
$FRONTEND = "$ROOT\frontend"
$BACKEND_PORT = 8000
$FRONTEND_PORT = 3000

Write-Host "══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  短道速滑训练监测 · 血液数据分析平台 启动" -ForegroundColor Cyan
Write-Host "══════════════════════════════════════════════" -ForegroundColor Cyan

# ── 1. PostgreSQL ──
$pgRunning = $false
try {
    $conn = Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue
    if ($conn) { $pgRunning = $true }
} catch { }

if (-not $pgRunning) {
    Write-Host "[1/3] 启动 PostgreSQL ..." -ForegroundColor Yellow
    if (Test-Path "$PG_BIN\pg_ctl.exe") {
        & "$PG_BIN\pg_ctl.exe" -D $PG_DATA -l $PG_LOG -w -t 60 start | Out-Null
        Start-Sleep -Seconds 2
        Write-Host "      PostgreSQL 已启动 (localhost:5432)" -ForegroundColor Green
    } else {
        Write-Host "      [警告] 未找到 PostgreSQL (C:\pgsql18)，请先安装" -ForegroundColor Red
    }
} else {
    Write-Host "[1/3] PostgreSQL 已在运行 (localhost:5432)" -ForegroundColor Green
}

# ── 2. FastAPI 后端 ──
$backendRunning = $false
try {
    $r = Invoke-WebRequest -Uri "http://localhost:$BACKEND_PORT/api/health" -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) { $backendRunning = $true }
} catch { }

if (-not $backendRunning) {
    Write-Host "[2/3] 启动 FastAPI 后端 (端口 $BACKEND_PORT) ..." -ForegroundColor Yellow
    $py = "$BACKEND\.venv\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        Write-Host "      [警告] 未找到 venv，尝试用系统 Python" -ForegroundColor Red
        $py = "python"
    }
    Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "$BACKEND_PORT" -WorkingDirectory $BACKEND -WindowStyle Hidden
    Start-Sleep -Seconds 5
    Write-Host "      FastAPI 已启动 (http://localhost:$BACKEND_PORT)" -ForegroundColor Green
} else {
    Write-Host "[2/3] FastAPI 已在运行 (端口 $BACKEND_PORT)" -ForegroundColor Green
}

# ── 3. Next.js 前端 ──
$frontendRunning = $false
try {
    $r = Invoke-WebRequest -Uri "http://localhost:$FRONTEND_PORT" -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) { $frontendRunning = $true }
} catch { }

if (-not $frontendRunning) {
    Write-Host "[3/3] 启动 Next.js 前端 (端口 $FRONTEND_PORT) ..." -ForegroundColor Yellow
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" -WorkingDirectory $FRONTEND -WindowStyle Hidden
    Start-Sleep -Seconds 12
    Write-Host "      Next.js 已启动 (http://localhost:$FRONTEND_PORT)" -ForegroundColor Green
} else {
    Write-Host "[3/3] Next.js 已在运行 (端口 $FRONTEND_PORT)" -ForegroundColor Green
}

Write-Host ""
Write-Host "══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  访问地址: http://localhost:$FRONTEND_PORT" -ForegroundColor White
Write-Host "  API 文档: http://localhost:$BACKEND_PORT/docs" -ForegroundColor White
Write-Host "  数据不出网 · 全部本地运行" -ForegroundColor Green
Write-Host "══════════════════════════════════════════════" -ForegroundColor Cyan

# 打开浏览器
try { Start-Process "http://localhost:$FRONTEND_PORT" } catch { }
