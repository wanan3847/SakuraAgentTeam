# ============================================================
# 樱花小队 (SakuraAgentTeam) Windows PowerShell 一键安装脚本
# 用法: irm https://raw.githubusercontent.com/wanan3847/SakuraAgentTeam/main/scripts/install.ps1 | iex
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host "🌸 樱花小队 (SakuraAgentTeam) 一键安装脚本" -ForegroundColor Blue
Write-Host "   PowerShell 一键安装" -ForegroundColor Blue
Write-Host ""

# 配置
$RepoUrl = "https://github.com/wanan3847/SakuraAgentTeam.git"
$InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { "$env:USERPROFILE\SakuraAgentTeam" }
$Branch = "main"

# ============================================================
# 1. 检查依赖
# ============================================================
Write-Host "[1/6] 检查依赖..." -ForegroundColor Yellow

function Check-Command {
    param([string]$cmd, [string]$hint)
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Host "  ✗ 未找到 $cmd,请先安装" -ForegroundColor Red
        Write-Host "    $hint"
        exit 1
    }
    $ver = (Invoke-Expression "$cmd --version" 2>&1 | Select-Object -First 1)
    Write-Host "  ✓ $cmd ($ver)" -ForegroundColor Green
}

Check-Command "git" "  参考: https://git-scm.com/downloads"
Check-Command "python" "  参考: https://www.python.org/downloads/"
Check-Command "node" "  参考: https://nodejs.org/"

Write-Host "  ✓ 依赖检查完成" -ForegroundColor Green

# ============================================================
# 2. 克隆仓库
# ============================================================
Write-Host ""
Write-Host "[2/6] 克隆仓库..." -ForegroundColor Yellow

if (Test-Path "$InstallDir\.git") {
    Write-Host "  目录已存在,拉取最新代码..." -ForegroundColor Yellow
    Set-Location $InstallDir
    git pull origin $Branch 2>&1 | ForEach-Object { Write-Host "    $_" }
} else {
    git clone --depth 1 -b $Branch $RepoUrl $InstallDir 2>&1 | ForEach-Object { Write-Host "    $_" }
    Set-Location $InstallDir
}
Write-Host "  ✓ 代码已就绪" -ForegroundColor Green

# ============================================================
# 3. 安装后端依赖
# ============================================================
Write-Host ""
Write-Host "[3/6] 安装后端依赖 (Python)..." -ForegroundColor Yellow

if (-not (Test-Path "backend\.venv")) {
    python -m venv backend\.venv
    Write-Host "  ✓ 创建虚拟环境" -ForegroundColor Green
}

& backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip 2>&1 | Select-Object -Last 1 | ForEach-Object { Write-Host "    $_" }

if (Test-Path "backend\requirements.txt") {
    pip install -r backend\requirements.txt 2>&1 | Select-Object -Last 3 | ForEach-Object { Write-Host "    $_" }
} elseif (Test-Path "backend\pyproject.toml") {
    pip install -e backend\ 2>&1 | Select-Object -Last 3 | ForEach-Object { Write-Host "    $_" }
}
Write-Host "  ✓ 后端依赖已安装" -ForegroundColor Green

# ============================================================
# 4. 安装前端依赖
# ============================================================
Write-Host ""
Write-Host "[4/6] 安装前端依赖 (Node)..." -ForegroundColor Yellow

Set-Location frontend
npm install 2>&1 | Select-Object -Last 5 | ForEach-Object { Write-Host "    $_" }
Write-Host "  ✓ 前端依赖已安装" -ForegroundColor Green
Set-Location ..

# ============================================================
# 5. 配置 .env
# ============================================================
Write-Host ""
Write-Host "[5/6] 配置环境变量..." -ForegroundColor Yellow

if (-not (Test-Path "backend\.env")) {
    Copy-Item "backend\.env.example" "backend\.env"
    $secretKey = python -c "import secrets; print(secrets.token_hex(32))"
    (Get-Content "backend\.env") -replace "^SECRET_KEY=.*", "SECRET_KEY=$secretKey" | Set-Content "backend\.env"
    Write-Host "  ✓ 已生成 backend\.env (SECRET_KEY 已自动生成)" -ForegroundColor Green
    Write-Host "  ⚠ 请编辑 backend\.env 填入 OPENAI_API_KEY" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ backend\.env 已存在" -ForegroundColor Green
}

# ============================================================
# 6. 完成
# ============================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Blue
Write-Host "🌸 安装完成!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Blue
Write-Host ""
Write-Host "下一步:"
Write-Host "  1. 编辑配置:  notepad $InstallDir\backend\.env"
Write-Host "  2. 启动开发:  cd $InstallDir; .\deploy.sh dev"
Write-Host "  3. 启动生产:  cd $InstallDir; .\deploy.sh prod"
Write-Host ""
Write-Host "文档:"
Write-Host "  - 安装: https://github.com/wanan3847/SakuraAgentTeam#readme"
Write-Host "  - 部署: $InstallDir\docs\DEPLOY.md"
Write-Host "  - CLI:  $InstallDir\docs\CLI.md"
Write-Host ""
Write-Host "🌸 Just say it. 你的 AI 虚拟团队。" -ForegroundColor Blue
