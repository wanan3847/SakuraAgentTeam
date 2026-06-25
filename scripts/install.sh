#!/usr/bin/env bash
set -e

echo "🌸 樱花小队 — 一键安装脚本"
echo "============================"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python 3，请先安装 Python 3.10+"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ 未找到 Node.js，请先安装 Node.js 18+"
    exit 1
fi

# 选择安装方式
echo ""
echo "选择安装方式："
echo "  1. pip 安装（推荐，最简单）"
echo "  2. 源码安装（开发用）"
read -p "请选择 [1/2]: " choice

case $choice in
    1)
        echo "📦 正在通过 pip 安装..."
        pip install sakura-agent-team
        echo "✅ 安装完成！"
        echo ""
        echo "启动：sakura start"
        ;;
    2)
        echo "📦 正在从源码安装..."
        # 后端
        cd backend
        pip install -e .
        # 前端
        cd ../frontend
        npm install
        echo "✅ 安装完成！"
        echo ""
        echo "启动后端：cd backend && python -m uvicorn app.api.main:app --reload"
        echo "启动前端：cd frontend && npm run dev"
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac

echo ""
echo "🌸 感谢安装樱花小队！"
echo "文档：https://github.com/wanan3847/SakuraAgentTeam"
