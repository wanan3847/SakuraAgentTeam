// 🌸 樱花小队 — Electron 构建脚本
//
// 调用 electron-builder 生成 macOS .dmg / Windows .exe / Linux .AppImage
//
// 用法:
//   node build.js              # 当前平台
//   node build.js --mac        # macOS
//   node build.js --win        # Windows
//   node build.js --linux      # Linux
//   node build.js --all        # 所有平台

const { execSync } = require('child_process');
const path = require('path');

const args = process.argv.slice(2);
const isMac = args.includes('--mac');
const isWin = args.includes('--win');
const isLinux = args.includes('--linux');
const isAll = args.includes('--all');

// 确定目标平台
let target = '';
if (isAll) {
  target = '--mac --win --linux';
} else if (isMac) {
  target = '--mac';
} else if (isWin) {
  target = '--win';
} else if (isLinux) {
  target = '--linux';
}
// 不指定则 electron-builder 自动选当前平台

console.log('🌸 樱花小队 — Electron 构建');
console.log('==========================');
console.log(`目标: ${target || '当前平台'}`);
console.log('');

// 检查 electron-builder 是否安装
try {
  require.resolve('electron-builder');
} catch {
  console.log('📦 安装 electron-builder...');
  execSync('npm install --save-dev electron-builder', {
    stdio: 'inherit',
    cwd: __dirname,
  });
}

// 运行构建
const cmd = `npx electron-builder ${target}`.trim();
console.log(`执行: ${cmd}`);
console.log('');

try {
  execSync(cmd, {
    stdio: 'inherit',
    cwd: __dirname,
  });
  console.log('');
  console.log('✅ 构建完成！');
  console.log(`   输出目录: ${path.join(__dirname, 'dist')}`);
} catch (e) {
  console.error('❌ 构建失败:', e.message);
  process.exit(1);
}
