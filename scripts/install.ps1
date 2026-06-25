# 🌸 樱花小队 — Windows 一键安装脚本 (PowerShell)
# 用法: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"

Write-Host "🌸 樱花小队 — 一键安装脚本" -ForegroundColor Magenta
Write-Host "============================"

# 检查 Python
$pythonOk = $false
try { $null = & python --version 2>&1; if ($LASTEXITCODE -eq 0) { $pythonOk = $true } } catch {}
if (-not $pythonOk) {
    try { $null = & python3 --version 2>&1; if ($LASTEXITCODE -eq 0) { $pythonOk = $true } } catch {}
}
if (-not $pythonOk) {
    Write-Host "❌ 未找到 Python，请先安装 Python 3.10+" -ForegroundColor Red
    Write-Host "   下载: https://www.python.org/downloads/"
    exit 1
}

# 检查 Node.js
$nodeOk = $false
try { $null = & node --version 2>&1; if ($LASTEXITCODE -eq 0) { $nodeOk = $true } } catch {}
if (-not $nodeOk) {
    Write-Host "❌ 未找到 Node.js，请先安装 Node.js 18+" -ForegroundColor Red
    Write-Host "   下载: https://nodejs.org/"
    exit 1
}

# 选择安装方式
Write-Host ""
Write-Host "选择安装方式："
Write-Host "  1. pip 安装（推荐，最简单）"
Write-Host "  2. 源码安装（开发用）"
$choice = Read-Host "请选择 [1/2]"

switch ($choice) {
    "1" {
        Write-Host "📦 正在通过 pip 安装..." -ForegroundColor Cyan
        pip install sakura-agent-team
        Write-Host "✅ 安装完成！" -ForegroundColor Green
        Write-Host ""
        Write-Host "启动：sakura start"
    }
    "2" {
        Write-Host "📦 正在从源码安装..." -ForegroundColor Cyan
        # 后端
        Push-Location backend
        pip install -e .
        Pop-Location
        # 前端
        Push-Location frontend
        npm install
        Pop-Location
        Write-Host "✅ 安装完成！" -ForegroundColor Green
        Write-Host ""
        Write-Host "启动后端：cd backend && python -m uvicorn app.api.main:app --reload"
        Write-Host "启动前端：cd frontend && npm run dev"
    }
    default {
        Write-Host "无效选择" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "🌸 感谢安装樱花小队！" -ForegroundColor Magenta
Write-Host "文档：https://github.com/wanan3847/SakuraAgentTeam"
