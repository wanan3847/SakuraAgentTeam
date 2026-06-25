# 🌸 樱花小队 — 一键启动脚本 (Windows PowerShell)
# 同时启动后端和前端，Ctrl+C 停止所有服务

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"

$BackendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }
$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5173" }

Write-Host "🌸 樱花小队 — 启动中..." -ForegroundColor Magenta
Write-Host "  后端: http://localhost:$BackendPort"
Write-Host "  前端: http://localhost:$FrontendPort"
Write-Host ""

# 启动后端
Push-Location $BackendDir
$backend = Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", $BackendPort -PassThru -NoNewWindow
Pop-Location

# 启动前端
Push-Location $FrontendDir
$frontend = Start-Process -FilePath "npm" -ArgumentList "run", "dev", "--", "--port", $FrontendPort -PassThru -NoNewWindow
Pop-Location

Write-Host "✅ 服务已启动" -ForegroundColor Green
Write-Host "   后端 API: http://localhost:$BackendPort/docs"
Write-Host "   前端页面: http://localhost:$FrontendPort"
Write-Host "   按 Ctrl+C 停止所有服务"
Write-Host ""

try {
    Wait-Process -Id $backend.Id
} catch {
    # Ctrl+C 或异常退出
} finally {
    Write-Host ""
    Write-Host "🛑 正在停止服务..." -ForegroundColor Yellow
    if (-not $backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
    if (-not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "👋 已停止" -ForegroundColor Magenta
}
