// 🌸 樱花小队 — Electron preload 脚本
//
// 在渲染进程加载前注入，提供安全的 IPC 桥接。
// 暴露 LLM 配置管理 API 给渲染进程。

const { contextBridge, ipcRenderer } = require('electron');

// 通过 contextBridge 暴露安全 API 给渲染进程
contextBridge.exposeInMainWorld('sakura', {
  // 平台信息
  platform: process.platform,
  isElectron: true,

  // 版本信息
  versions: {
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node,
  },

  // 后端地址（渲染进程可用此地址发请求）
  backendUrl: `http://127.0.0.1:${process.env.SAKURA_BACKEND_PORT || 8000}`,

  // 简单的日志桥接（方便调试）
  log: {
    info: (...args) => console.log('[sakura]', ...args),
    error: (...args) => console.error('[sakura]', ...args),
  },

  // ===== LLM 配置管理 =====
  llm: {
    // 测试任意 LLM 连接（用你自己的 key）
    testConnection: (baseUrl, apiKey, model) =>
      ipcRenderer.invoke('llm:test-connection', { baseUrl, apiKey, model }),

    // 拉取可用模型列表
    fetchModels: (baseUrl, apiKey) =>
      ipcRenderer.invoke('llm:fetch-models', { baseUrl, apiKey }),

    // 获取内置供应商列表
    getProviders: (free = false) =>
      ipcRenderer.invoke('llm:providers', { free }),

    // 获取用户已保存的配置
    getMyConfigs: (token) =>
      ipcRenderer.invoke('llm:my-configs', { token }),

    // 保存新配置
    saveConfig: (token, data) =>
      ipcRenderer.invoke('llm:save-config', { token, data }),

    // 删除配置
    deleteConfig: (token, configId) =>
      ipcRenderer.invoke('llm:delete-config', { token, configId }),

    // 测试已保存的配置
    testConfig: (token, configId) =>
      ipcRenderer.invoke('llm:test-config', { token, configId }),

    // 刷新已保存配置的模型列表
    refreshModels: (token, configId) =>
      ipcRenderer.invoke('llm:refresh-models', { token, configId }),

    // 环境变量检测
    envCheck: () =>
      ipcRenderer.invoke('llm:env-check'),
  },

  // ===== Shell 操作 =====
  shell: {
    // 用系统浏览器打开外部链接
    openExternal: (url) =>
      ipcRenderer.invoke('shell:open-external', url),
  },

  // ===== 应用通知 =====
  app: {
    // 显示通知
    notify: (title, body) =>
      ipcRenderer.invoke('app:notify', { title, body }),

    // 监听来自主进程的通知
    onNotification: (callback) => {
      ipcRenderer.on('app:notification', (event, data) => callback(data));
    },
  },
});
