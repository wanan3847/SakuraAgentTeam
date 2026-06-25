"""用 macOS 系统 Apple Color Emoji 字体渲染 🌸 emoji → PNG
部署在 macOS 服务器时,这个 PNG 和用户在浏览器 tab 上看到的 favicon 一模一样。
部署到 Linux 服务器时,浏览器优先加载 PNG → 显示 macOS 风格 🌸,避免黑块。
"""
from PIL import Image, ImageDraw, ImageFont
import os

EMOJI = "\U0001F338"  # 🌸 Cherry Blossom
SIZE = 192
FONT_PATH = "/System/Library/Fonts/Apple Color Emoji.ttc"

# 透明背景, 192x192
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 加载 Apple Color Emoji 字体, 大小 160
font = ImageFont.truetype(FONT_PATH, 160)

# 居中
bbox = draw.textbbox((0, 0), EMOJI, font=font)
w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
x = (SIZE - w) // 2 - bbox[0]
y = (SIZE - h) // 2 - bbox[1]
draw.text((x, y), EMOJI, font=font, embedded_color=True)

# 多尺寸输出
out_dir = "/Users/yangyazhou/SakuraAgentTeam/frontend/public"
os.makedirs(out_dir, exist_ok=True)

for size, name in [(192, "favicon-192.png"),
                   (96,  "favicon-96.png"),
                   (72,  "favicon.png"),
                   (48,  "favicon-48.png"),
                   (32,  "favicon-32.png"),
                   (180, "apple-touch-icon.png")]:
    s = img.resize((size, size), Image.LANCZOS)
    s.save(os.path.join(out_dir, name), "PNG", optimize=True)
    print(f"saved {name} {size}x{size}")

# favicon.ico (Windows 兼容, 多分辨率打包)
img.save(os.path.join(out_dir, "favicon.ico"),
         format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("saved favicon.ico")
