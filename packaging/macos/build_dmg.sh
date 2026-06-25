#!/usr/bin/env bash
# 🌸 樱花小队 — 生成 macOS .dmg 安装包
#
# 依赖: hdiutil (macOS 自带)
# 用法: ./build_dmg.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/dist"
APP_NAME="SakuraAgentTeam"
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"
DMG_NAME="$APP_NAME-0.2.0.dmg"
DMG_PATH="$BUILD_DIR/$DMG_NAME"

if [ ! -d "$APP_BUNDLE" ]; then
    echo "❌ 未找到 .app 包，请先运行 build.sh"
    exit 1
fi

echo "🌸 生成 .dmg 安装包"
echo "===================="

# 清理旧 dmg
rm -f "$DMG_PATH"

# 创建临时目录用于 dmg 内容
DMG_STAGING="$BUILD_DIR/dmg_staging"
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"

# 复制 .app 到临时目录
cp -R "$APP_BUNDLE" "$DMG_STAGING/"

# 创建 /Applications 快捷方式
ln -sf /Applications "$DMG_STAGING/Applications"

# 生成 dmg
echo "📦 正在生成 $DMG_NAME ..."
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$DMG_STAGING" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

# 清理临时目录
rm -rf "$DMG_STAGING"

echo ""
echo "✅ DMG 生成完成: $DMG_PATH"
echo ""
echo "用户可以双击 .dmg 拖拽安装到 Applications"
