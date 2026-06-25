#!/usr/bin/env bash
# 🌸 樱花小队 — macOS .app 构建脚本
#
# 流程:
#   1. 用 pyinstaller 打包后端为独立可执行文件
#   2. 用 electron 打包前端（或直接用浏览器）
#   3. 组装 .app 包结构
#
# 用法: ./build.sh [--no-frontend]
#
# 依赖: pip install pyinstaller, npm install -g electron-builder

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/dist"
APP_NAME="SakuraAgentTeam"
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"

echo "🌸 构建 $APP_NAME.app for macOS"
echo "=============================="

# 清理旧构建
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# ============================================================
# 1. 打包后端 (PyInstaller)
# ============================================================
echo ""
echo "📦 [1/3] 打包后端 (PyInstaller)..."

cd "$PROJECT_ROOT/backend"
pip install pyinstaller 2>/dev/null || true

pyinstaller \
    --name "sakura-backend" \
    --onefile \
    --add-data "app:app" \
    --add-data "cli:cli" \
    --hidden-import "uvicorn.logging" \
    --hidden-import "uvicorn.protocols.http.auto" \
    --hidden-import "uvicorn.protocols.websockets.auto" \
    --hidden-import "uvicorn.lifespan.on" \
    --distpath "$BUILD_DIR/backend" \
    --workpath "$BUILD_DIR/backend_build" \
    --specpath "$BUILD_DIR" \
    --noconfirm \
    -c \
    app/api/main.py

echo "✅ 后端打包完成"

# ============================================================
# 2. 打包前端 (可选)
# ============================================================
NO_FRONTEND=false
if [[ "$1" == "--no-frontend" ]]; then
    NO_FRONTEND=true
fi

if [[ "$NO_FRONTEND" == "false" ]]; then
    echo ""
    echo "📦 [2/3] 打包前端..."
    cd "$PROJECT_ROOT/frontend"
    npm run build
    mkdir -p "$BUILD_DIR/frontend_dist"
    cp -r dist/* "$BUILD_DIR/frontend_dist/"
    echo "✅ 前端打包完成"
else
    echo ""
    echo "⏭️  [2/3] 跳过前端打包 (--no-frontend)"
fi

# ============================================================
# 3. 组装 .app 包
# ============================================================
echo ""
echo "📦 [3/3] 组装 .app 包..."

APP_DIR="$APP_BUNDLE/Contents"
MACOS_DIR="$APP_DIR/MacOS"
RESOURCES_DIR="$APP_DIR/Resources"

mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"

# 复制后端可执行文件
cp "$BUILD_DIR/backend/sakura-backend" "$MACOS_DIR/sakura-backend"

# 复制前端静态文件（如果有）
if [[ "$NO_FRONTEND" == "false" ]]; then
    cp -r "$BUILD_DIR/frontend_dist" "$RESOURCES_DIR/frontend"
fi

# 创建启动脚本
cat > "$MACOS_DIR/sakura-launch" << 'LAUNCH'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"
# 启动后端
"$DIR/sakura-backend" &
BACKEND_PID=$!
sleep 2
# 打开浏览器
if [ -d "$DIR/../Resources/frontend" ]; then
    open "http://localhost:8000"
fi
wait $BACKEND_PID
LAUNCH
chmod +x "$MACOS_DIR/sakura-launch"

# 复制 Info.plist
cp "$SCRIPT_DIR/Info.plist" "$APP_DIR/Info.plist"

# 设置图标（如果有）
if [ -f "$SCRIPT_DIR/sakura.icns" ]; then
    cp "$SCRIPT_DIR/sakura.icns" "$RESOURCES_DIR/sakura.icns"
fi

echo ""
echo "✅ 构建完成: $APP_BUNDLE"
echo ""
echo "下一步: 运行 build_dmg.sh 生成 .dmg 安装包"
