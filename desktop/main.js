// 🌸 樱花小队 — Electron 主进程
//
// 功能:
//   1. 启动后端 Python 进程
//   2. 创建 BrowserWindow 加载前端
//   3. 菜单栏（LLM 配置 / 快速测试 / 团队管理 / 历史记录）
//   4. IPC 处理器（LLM 测试 / 拉取模型 / 配置管理）
//   5. 系统托盘
//   6. 处理关闭时杀掉后端进程

const { app, BrowserWindow, shell, Menu, ipcMain, Tray, nativeImage, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const https = require('https');
const { URL } = require('url');

let mainWindow = null;
let backendProcess = null;
let tray = null;

const BACKEND_PORT = process.env.SAKURA_BACKEND_PORT || 8000;
const FRONTEND_PORT = process.env.SAKURA_FRONTEND_PORT || 5173;
const isDev = process.argv.includes('--dev');

// ============================================================
// 后端进程管理
// ============================================================

function startBackend() {
  // 优先使用打包好的独立 binary(PyInstaller)
  // 路径: desktop/bin/sakura-backend (macOS/Linux) 或 sakura-backend.exe (Windows)
  const ext = process.platform === 'win32' ? '.exe' : '';
  const packagedBinary = path.join(__dirname, 'bin', `sakura-backend${ext}`);

  if (require('fs').existsSync(packagedBinary)) {
    console.log(`启动后端(打包版): ${packagedBinary}`);
    backendProcess = spawn(packagedBinary, [
      '--port', String(BACKEND_PORT),
    ], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  } else {
    // Fallback:用 python3 -m uvicorn(开发模式)
    const backendDir = path.join(__dirname, '..', 'backend');
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

    console.log(`启动后端(python): ${pythonCmd} -m uvicorn app.api.main:app --port ${BACKEND_PORT}`);

    backendProcess = spawn(pythonCmd, [
      '-m', 'uvicorn',
      'app.api.main:app',
      '--host', '127.0.0.1',
      '--port', String(BACKEND_PORT),
    ], {
      cwd: backendDir,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  }

  backendProcess.stdout.on('data', (data) => {
    console.log(`[backend] ${data.toString().trim()}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[backend] ${data.toString().trim()}`);
  });

  backendProcess.on('exit', (code) => {
    console.log(`后端进程退出 (code: ${code})`);
  });
}

function stopBackend() {
  if (backendProcess && !backendProcess.killed) {
    console.log('停止后端进程...');
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(backendProcess.pid), '/f', '/t']);
    } else {
      backendProcess.kill('SIGTERM');
      setTimeout(() => {
        if (backendProcess && !backendProcess.killed) {
          backendProcess.kill('SIGKILL');
        }
      }, 3000);
    }
  }
}

// ============================================================
// 等待后端就绪
// ============================================================

function waitForBackend(maxRetries = 30) {
  return new Promise((resolve, reject) => {
    let retries = 0;

    const check = () => {
      const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/health`, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else {
          retry();
        }
      });

      req.on('error', () => retry());
      req.setTimeout(2000, () => {
        req.destroy();
        retry();
      });
    };

    const retry = () => {
      retries++;
      if (retries >= maxRetries) {
        reject(new Error('后端启动超时'));
      } else {
        setTimeout(check, 1000);
      }
    };

    check();
  });
}

// ============================================================
// HTTP 请求工具（调用后端 API）
// ============================================================

function apiRequest(method, pathname, body = null, token = null) {
  return new Promise((resolve, reject) => {
    const url = new URL(`http://127.0.0.1:${BACKEND_PORT}${pathname}`);
    const options = {
      method,
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 60000,
    };
    if (token) {
      options.headers['Authorization'] = `Bearer ${token}`;
    }

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(new Error(`JSON 解析失败: ${e.message}`));
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy(new Error('请求超时'));
    });

    if (body) {
      req.write(JSON.stringify(body));
    }
    req.end();
  });
}

// ============================================================
// 菜单栏
// ============================================================

function buildMenu() {
  const template = [
    {
      label: '樱花小队',
      submenu: [
        {
          label: '关于樱花小队',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: '关于',
              message: '樱花小队 SakuraAgentTeam',
              detail: '多智能体协作平台\n100+ LLM 供应商支持\n7 种协作模式\n60+ 专家 Agent',
              buttons: ['确定'],
            });
          },
        },
        { type: 'separator' },
        { role: 'quit', label: '退出' },
      ],
    },
    {
      label: '编辑',
      submenu: [
        { role: 'undo', label: '撤销' },
        { role: 'redo', label: '重做' },
        { type: 'separator' },
        { role: 'cut', label: '剪切' },
        { role: 'copy', label: '复制' },
        { role: 'paste', label: '粘贴' },
        { role: 'selectAll', label: '全选' },
      ],
    },
    {
      label: '视图',
      submenu: [
        { role: 'reload', label: '重新加载' },
        { role: 'toggleDevTools', label: '开发者工具' },
        { type: 'separator' },
        { role: 'resetZoom', label: '重置缩放' },
        { role: 'zoomIn', label: '放大' },
        { role: 'zoomOut', label: '缩小' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: '全屏' },
      ],
    },
    {
      label: '导航',
      submenu: [
        {
          label: '首页',
          accelerator: 'CmdOrCtrl+1',
          click: () => mainWindow?.loadURL(getAppUrl('/')),
        },
        {
          label: '工作台',
          accelerator: 'CmdOrCtrl+2',
          click: () => mainWindow?.loadURL(getAppUrl('/workspace')),
        },
        {
          label: 'LLM 供应商',
          accelerator: 'CmdOrCtrl+3',
          click: () => mainWindow?.loadURL(getAppUrl('/providers')),
        },
        {
          label: '教学中心',
          accelerator: 'CmdOrCtrl+4',
          click: () => mainWindow?.loadURL(getAppUrl('/tutorial')),
        },
        {
          label: '专家库',
          accelerator: 'CmdOrCtrl+5',
          click: () => mainWindow?.loadURL(getAppUrl('/agents')),
        },
        { type: 'separator' },
        {
          label: '历史记录',
          accelerator: 'CmdOrCtrl+H',
          click: () => mainWindow?.loadURL(getAppUrl('/history')),
        },
        {
          label: '账户设置',
          accelerator: 'CmdOrCtrl+,',
          click: () => mainWindow?.loadURL(getAppUrl('/account')),
        },
      ],
    },
    {
      label: 'LLM',
      submenu: [
        {
          label: '快速测试连接…',
          accelerator: 'CmdOrCtrl+T',
          click: () => showQuickTestDialog(),
        },
        {
          label: '刷新内置供应商列表',
          click: async () => {
            try {
              const data = await apiRequest('GET', '/api/v1/llm/providers');
              dialog.showMessageBox(mainWindow, {
                type: 'info',
                title: '供应商列表',
                message: `共 ${data.total || 0} 个内置供应商`,
                detail: data.data?.slice(0, 10).map(p => `• ${p.name} (${p.id})`).join('\n') + (data.total > 10 ? `\n... 还有 ${data.total - 10} 个` : ''),
                buttons: ['确定'],
              });
            } catch (e) {
              dialog.showErrorBox('错误', `无法获取供应商列表: ${e.message}`);
            }
          },
        },
        {
          label: '查看已保存配置',
          click: async () => {
            // 读取 token（从 localStorage 通过 webContents 执行 JS）
            const token = await getTokenFromRenderer();
            if (!token) {
              dialog.showErrorBox('未登录', '请先登录后再查看 LLM 配置');
              return;
            }
            try {
              const data = await apiRequest('GET', '/api/v1/llm/configs', null, token);
              if (data.success && data.data?.length > 0) {
                dialog.showMessageBox(mainWindow, {
                  type: 'info',
                  title: '已保存的 LLM 配置',
                  message: `共 ${data.data.length} 个配置`,
                  detail: data.data.map(c => `• ${c.display_name} (${c.provider_id})\n  model: ${c.model}${c.is_default ? ' [默认]' : ''}`).join('\n'),
                  buttons: ['确定'],
                });
              } else {
                dialog.showMessageBox(mainWindow, {
                  type: 'info',
                  title: 'LLM 配置',
                  message: '还没有保存的 LLM 配置',
                  detail: '前往「LLM 供应商」页面添加配置',
                  buttons: ['去配置', '取消'],
                }).then(({ response }) => {
                  if (response === 0) mainWindow?.loadURL(getAppUrl('/providers'));
                });
              }
            } catch (e) {
              dialog.showErrorBox('错误', `获取配置失败: ${e.message}`);
            }
          },
        },
      ],
    },
    {
      label: '帮助',
      submenu: [
        {
          label: '文档',
          click: () => shell.openExternal('https://github.com/wanan3847/SakuraAgentTeam'),
        },
        {
          label: '检查更新',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: '检查更新',
              message: '当前版本',
              detail: app.getVersion(),
              buttons: ['确定'],
            });
          },
        },
        { type: 'separator' },
        {
          label: '报告问题',
          click: () => shell.openExternal('https://github.com/wanan3847/SakuraAgentTeam/issues'),
        },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

function getAppUrl(pathname) {
  if (isDev) {
    return `http://localhost:${FRONTEND_PORT}${pathname}`;
  }
  return `http://127.0.0.1:${BACKEND_PORT}${pathname}`;
}

async function getTokenFromRenderer() {
  if (!mainWindow) return null;
  try {
    const token = await mainWindow.webContents.executeJavaScript(
      `localStorage.getItem('sakura_token') || null`
    );
    return token;
  } catch {
    return null;
  }
}

// ============================================================
// 快速测试连接对话框
// ============================================================

async function showQuickTestDialog() {
  const result = await dialog.showMessageBox(mainWindow, {
    type: 'question',
    title: '快速测试 LLM 连接',
    message: '测试 LLM 连接',
    detail: '将打开 LLM 供应商页面，你可以在那里填入 API Key 并测试连接。',
    buttons: ['打开供应商页面', '取消'],
  });
  if (result.response === 0) {
    mainWindow?.loadURL(getAppUrl('/providers'));
  }
}

// ============================================================
// 系统托盘
// ============================================================

function createTray() {
  // 使用 16x16 的透明图标（如果没有图标文件）
  const icon = nativeImage.createEmpty();
  tray = new Tray(icon);
  tray.setToolTip('樱花小队 SakuraAgentTeam');

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示主窗口',
      click: () => {
        if (mainWindow) {
          if (mainWindow.isMinimized()) mainWindow.restore();
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    {
      label: '工作台',
      click: () => mainWindow?.loadURL(getAppUrl('/workspace')),
    },
    {
      label: 'LLM 供应商',
      click: () => mainWindow?.loadURL(getAppUrl('/providers')),
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => app.quit(),
    },
  ]);

  tray.setContextMenu(contextMenu);
  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
        mainWindow.focus();
      }
    }
  });
}

// ============================================================
// IPC 处理器 — 暴露给渲染进程
// ============================================================

function setupIpc() {
  // 测试 LLM 连接
  ipcMain.handle('llm:test-connection', async (event, { baseUrl, apiKey, model }) => {
    try {
      return await apiRequest('POST', '/api/v1/llm/test-connection', {
        base_url: baseUrl,
        api_key: apiKey,
        model,
      });
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // 拉取模型列表
  ipcMain.handle('llm:fetch-models', async (event, { baseUrl, apiKey }) => {
    try {
      return await apiRequest('POST', '/api/v1/llm/fetch-models', {
        base_url: baseUrl,
        api_key: apiKey,
      });
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // 获取内置供应商列表
  ipcMain.handle('llm:providers', async (event, { free = false }) => {
    try {
      const path = free ? '/api/v1/llm/providers/free' : '/api/v1/llm/providers';
      return await apiRequest('GET', path);
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // 获取用户已保存的配置
  ipcMain.handle('llm:my-configs', async (event, { token }) => {
    try {
      return await apiRequest('GET', '/api/v1/llm/configs', null, token);
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // 保存新配置
  ipcMain.handle('llm:save-config', async (event, { token, data }) => {
    try {
      return await apiRequest('POST', '/api/v1/llm/configs', data, token);
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // 删除配置
  ipcMain.handle('llm:delete-config', async (event, { token, configId }) => {
    try {
      return await apiRequest('DELETE', `/api/v1/llm/configs/${configId}`, null, token);
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // 测试已保存的配置
  ipcMain.handle('llm:test-config', async (event, { token, configId }) => {
    try {
      return await apiRequest('POST', `/api/v1/llm/configs/${configId}/test`, null, token);
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // 刷新已保存配置的模型列表
  ipcMain.handle('llm:refresh-models', async (event, { token, configId }) => {
    try {
      return await apiRequest('POST', `/api/v1/llm/configs/${configId}/refresh-models`, null, token);
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // 环境变量检测
  ipcMain.handle('llm:env-check', async () => {
    try {
      return await apiRequest('GET', '/api/v1/llm/env-check');
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // 打开外部链接
  ipcMain.handle('shell:open-external', async (event, url) => {
    if (url && (url.startsWith('http://') || url.startsWith('https://'))) {
      await shell.openExternal(url);
      return { success: true };
    }
    return { success: false, error: 'invalid url' };
  });

  // 显示通知
  ipcMain.handle('app:notify', async (event, { title, body }) => {
    if (mainWindow) {
      // 通过 webContents 发送通知到渲染进程
      mainWindow.webContents.send('app:notification', { title, body });
    }
    return { success: true };
  });
}

// ============================================================
// 窗口创建
// ============================================================

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: '樱花小队 — SakuraAgentTeam',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    backgroundColor: '#FAF8F5',
  });

  // 开发模式加载 Vite dev server，生产模式加载本地前端文件
  if (isDev) {
    await mainWindow.loadURL(`http://localhost:${FRONTEND_PORT}`);
    mainWindow.webContents.openDevTools();
  } else {
    // 生产模式：优先用本地 frontend-dist 目录（file:// 协议）
    const fs = require('fs');
    const frontendDist = path.join(__dirname, 'frontend-dist', 'index.html');
    if (fs.existsSync(frontendDist)) {
      console.log(`加载本地前端: ${frontendDist}`);
      await mainWindow.loadFile(frontendDist);
    } else {
      // Fallback：从后端 8000 端口加载
      console.log('加载后端内置前端...');
      try {
        await mainWindow.loadURL(`http://127.0.0.1:${BACKEND_PORT}`);
      } catch (e) {
        console.error('无法加载前端:', e);
      }
    }
  }

  // 外部链接用系统浏览器打开
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ============================================================
// App 生命周期
// ============================================================

app.whenReady().then(async () => {
  startBackend();

  try {
    console.log('等待后端就绪...');
    await waitForBackend();
    console.log('后端已就绪');
  } catch (e) {
    console.error(e.message);
  }

  setupIpc();
  await createWindow();
  buildMenu();
  createTray();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopBackend();
});

app.on('will-quit', () => {
  stopBackend();
});

process.on('SIGINT', () => {
  stopBackend();
  app.quit();
});

process.on('SIGTERM', () => {
  stopBackend();
  app.quit();
});
