# 🌸 樱花小队 — Windows .exe 构建脚本 (PowerShell)
#
# 流程:
#   1. 用 pyinstaller 打包后端为独立可执行文件
#   2. 用 electron 打包前端（或直接用浏览器）
#   3. 生成安装包目录
#
# 依赖: pip install pyinstaller
# 用法: powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$BuildDir = Join-Path $ScriptDir "dist"
$AppName = "SakuraAgentTeam"

Write-Host "🌸 构建 $AppName for Windows" -ForegroundColor Magenta
Write-Host "=============================="

# 清理旧构建
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null

# ============================================================
# 1. 打包后端 (PyInstaller)
# ============================================================
Write-Host ""
Write-Host "📦 [1/3] 打包后端 (PyInstaller)..." -ForegroundColor Cyan

Push-Location (Join-Path $ProjectRoot "backend")
pip install pyinstaller 2>$null | Out-Null

pyinstaller `
    --name "sakura-backend" `
    --onefile `
    --add-data "app;app" `
    --add-data "cli;cli" `
    --hidden-import "uvicorn.logging" `
    --hidden-import "uvicorn.protocols.http.auto" `
    --hidden-import "uvicorn.protocols.websockets.auto" `
    --hidden-import "uvicorn.lifespan.on" `
    --distpath (Join-Path $BuildDir "backend") `
    --workpath (Join-Path $BuildDir "backend_build") `
    --specpath $BuildDir `
    --noconfirm `
    -c `
    app/api/main.py

Pop-Location
Write-Host "✅ 后端打包完成" -ForegroundColor Green

# ============================================================
# 2. 打包前端 (可选)
# ============================================================
$NoFrontend = ($args -contains "--no-frontend")

if (-not $NoFrontend) {
    Write-Host ""
    Write-Host "📦 [2/3] 打包前端..." -ForegroundColor Cyan
    Push-Location (Join-Path $ProjectRoot "frontend")
    npm run build
    $frontendDist = Join-Path $BuildDir "frontend_dist"
    New-Item -ItemType Directory -Path $frontendDist -Force | Out-Null
    Copy-Item -Path "dist\*" -Destination $frontendDist -Recurse -Force
    Pop-Location
    Write-Host "✅ 前端打包完成" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "⏭️  [2/3] 跳过前端打包 (--no-frontend)" -ForegroundColor Yellow
}

# ============================================================
# 3. 组装安装包目录
# ============================================================
Write-Host ""
Write-Host "📦 [3/3] 组装安装包目录..." -ForegroundColor Cyan

$AppDir = Join-Path $BuildDir $AppName
New-Item -ItemType Directory -Path $AppDir -Force | Out-Null

# 复制后端可执行文件
Copy-Item -Path (Join-Path $BuildDir "backend\sakura-backend.exe") -Destination $AppDir -Force

# 复制前端静态文件（如果有）
if (-not $NoFrontend) {
    $frontendTarget = Join-Path $AppDir "frontend"
    New-Item -ItemType Directory -Path $frontendTarget -Force | Out-Null
    Copy-Item -Path (Join-Path $BuildDir "frontend_dist\*") -Destination $frontendTarget -Recurse -Force
}

# 创建启动脚本
$launchScript = Join-Path $AppDir "sakura-launch.bat"
@"
@echo off
cd /d "%~dp0"
start "" sakura-backend.exe
timeout /t 3 /nobreak >nul
start "" http://localhost:8000
"@ | Set-Content -Path $launchScript -Encoding UTF8

Write-Host ""
Write-Host "✅ 构建完成: $AppDir" -ForegroundColor Green
Write-Host ""
Write-Host "下一步: 使用 Inno Setup 编译 sakura-installer.iss 生成 .exe 安装包"
