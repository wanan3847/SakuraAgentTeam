const vscode = require('vscode');
const http = require('http');
const https = require('https');
const { URL } = require('url');

let teamsProvider;
let agentsProvider;
let llmProvidersProvider;

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
    console.log('樱花小队插件已激活');

    // ---- 树视图：团队 ----
    teamsProvider = new TeamsProvider();
    vscode.window.registerTreeDataProvider('sakura.teams', teamsProvider);

    // ---- 树视图：专家 ----
    agentsProvider = new AgentsProvider();
    vscode.window.registerTreeDataProvider('sakura.agents', agentsProvider);

    // ---- 树视图：LLM 供应商 ----
    llmProvidersProvider = new LLMProvidersProvider();
    vscode.window.registerTreeDataProvider('sakura.llmProviders', llmProvidersProvider);

    // ---- 命令 ----
    context.subscriptions.push(
        vscode.commands.registerCommand('sakura.start', cmdStart),
        vscode.commands.registerCommand('sakura.chat', cmdChat),
        vscode.commands.registerCommand('sakura.selectTeam', cmdSelectTeam),
        vscode.commands.registerCommand('sakura.openWeb', cmdOpenWeb),
        vscode.commands.registerCommand('sakura.refreshTeams', () => teamsProvider.refresh()),
        vscode.commands.registerCommand('sakura.refreshAgents', () => agentsProvider.refresh()),
        // LLM 相关命令
        vscode.commands.registerCommand('sakura.llmProviders', cmdLLMProviders),
        vscode.commands.registerCommand('sakura.llmTest', cmdLLMTest),
        vscode.commands.registerCommand('sakura.llmSaveConfig', cmdLLMSaveConfig),
        vscode.commands.registerCommand('sakura.llmConfigs', cmdLLMConfigs),
        vscode.commands.registerCommand('sakura.llmRefreshProviders', () => llmProvidersProvider.refresh()),
        vscode.commands.registerCommand('sakura.llmPanel', cmdLLMPanel),
        vscode.commands.registerCommand('sakura.llmFetchModels', cmdLLMFetchModels),
        vscode.commands.registerCommand('sakura.llmEnvCheck', cmdLLMEnvCheck),
    );
}

function deactivate() {}

module.exports = { activate, deactivate };

// ============================================================
// 配置读取
// ============================================================

function getConfig() {
    const cfg = vscode.workspace.getConfiguration('sakura');
    return {
        serverUrl: (cfg.get('serverUrl') || 'http://localhost:8000').replace(/\/+$/, ''),
        token: cfg.get('token') || '',
        llmDefaultModel: cfg.get('llmDefaultModel') || 'gpt-4o-mini',
    };
}

function authHeaders() {
    const { token } = getConfig();
    return token ? { Authorization: `Bearer ${token}` } : {};
}

// ============================================================
// HTTP 请求封装
// ============================================================

function httpRequest(pathname, { method = 'GET', body } = {}) {
    return new Promise((resolve, reject) => {
        const { serverUrl } = getConfig();
        const fullUrl = serverUrl + pathname;
        let url;
        try {
            url = new URL(fullUrl);
        } catch (e) {
            reject(new Error(`无效的服务器地址: ${serverUrl}`));
            return;
        }
        const lib = url.protocol === 'https:' ? https : http;
        const headers = { ...authHeaders() };
        let payload = null;
        if (body !== undefined) {
            payload = JSON.stringify(body);
            headers['Content-Type'] = 'application/json';
            headers['Content-Length'] = Buffer.byteLength(payload);
        }
        const req = lib.request(
            {
                hostname: url.hostname,
                port: url.port || (url.protocol === 'https:' ? 443 : 80),
                path: url.pathname + url.search,
                method,
                headers,
            },
            (res) => {
                let data = '';
                res.on('data', (chunk) => (data += chunk));
                res.on('end', () => {
                    if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
                        try {
                            resolve(data ? JSON.parse(data) : {});
                        } catch (e) {
                            resolve(data);
                        }
                    } else {
                        reject(new Error(`HTTP ${res.statusCode}: ${data}`));
                    }
                });
            },
        );
        req.on('error', reject);
        if (payload) req.write(payload);
        req.end();
    });
}

// ============================================================
// 基础命令
// ============================================================

async function cmdStart() {
    const { serverUrl } = getConfig();
    const item = await vscode.window.showInformationMessage(
        `樱花小队后端地址: ${serverUrl}`,
        '打开 API 文档',
        '打开网页版',
    );
    if (item === '打开 API 文档') {
        vscode.env.openExternal(vscode.Uri.parse(`${serverUrl}/docs`));
    } else if (item === '打开网页版') {
        cmdOpenWeb();
    }
    teamsProvider.refresh();
    agentsProvider.refresh();
    llmProvidersProvider.refresh();
}

async function cmdSelectTeam() {
    try {
        const res = await httpRequest('/api/v1/teams');
        const teams = res.teams || [];
        if (teams.length === 0) {
            vscode.window.showWarningMessage('暂无可用团队，请先在后端配置团队。');
            return;
        }
        const picks = teams.map((t) => ({
            label: `${t.icon || '🌟'} ${t.name}`,
            description: t.mode || '',
            detail: t.description || '',
            team: t,
        }));
        const picked = await vscode.window.showQuickPick(picks, {
            placeHolder: '选择一个团队进行协作',
        });
        if (picked) {
            await vscode.commands.executeCommand('sakura.chat', picked.team);
        }
    } catch (e) {
        vscode.window.showErrorMessage(`获取团队失败: ${e.message}`);
    }
}

async function cmdOpenWeb() {
    vscode.env.openExternal(vscode.Uri.parse('http://localhost:5173'));
}

async function cmdChat(team) {
    let selected = team;
    if (!selected) {
        try {
            const res = await httpRequest('/api/v1/teams');
            const teams = res.teams || [];
            if (teams.length === 0) {
                vscode.window.showWarningMessage('暂无可用团队。');
                return;
            }
            const picks = teams.map((t) => ({
                label: `${t.icon || '🌟'} ${t.name}`,
                description: t.mode || '',
                detail: t.description || '',
                team: t,
            }));
            const picked = await vscode.window.showQuickPick(picks, {
                placeHolder: '选择团队进行对话',
            });
            if (!picked) return;
            selected = picked.team;
        } catch (e) {
            vscode.window.showErrorMessage(`获取团队失败: ${e.message}`);
            return;
        }
    }
    ChatPanel.createOrShow(selected);
}

// ============================================================
// LLM 命令
// ============================================================

// 打开 LLM 供应商侧边栏视图
async function cmdLLMProviders() {
    await vscode.commands.executeCommand('workbench.view.extension.sakura-sidebar');
    // 切换到 LLM 供应商视图
    llmProvidersProvider.refresh();
    vscode.window.showInformationMessage('LLM 供应商列表已加载，点击任意供应商可保存配置或测试连接。');
}

// 测试 LLM 连接（支持从供应商传入，或手动输入）
async function cmdLLMTest(provider) {
    let baseUrl = '';
    let apiKey = '';
    let model = '';

    if (provider && provider.base_url) {
        baseUrl = provider.base_url;
    } else {
        const input = await vscode.window.showInputBox({
            prompt: '输入 LLM Base URL',
            placeHolder: 'https://api.openai.com/v1',
            ignoreFocusOut: true,
        });
        if (!input) return;
        baseUrl = input;
    }

    apiKey = await vscode.window.showInputBox({
        prompt: '输入你的 API Key（不会上传到服务器，仅本机使用）',
        password: true,
        placeHolder: 'sk-...',
        ignoreFocusOut: true,
    });
    if (!apiKey) return;

    const { llmDefaultModel } = getConfig();
    model = await vscode.window.showInputBox({
        prompt: '输入要测试的模型名',
        value: (provider && provider.models && provider.models[0]) || llmDefaultModel,
        placeHolder: 'gpt-4o-mini',
        ignoreFocusOut: true,
    });
    if (!model) return;

    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: `正在测试 ${baseUrl} ...`,
            cancellable: false,
        },
        async () => {
            try {
                const res = await httpRequest('/api/v1/llm/test-connection', {
                    method: 'POST',
                    body: { base_url: baseUrl, api_key: apiKey, model },
                });
                if (res.ok || res.success) {
                    vscode.window.showInformationMessage(
                        `✅ 连接成功！模型: ${res.model || model}，回复: ${(res.reply || res.message || '（空）').slice(0, 100)}`,
                    );
                } else {
                    vscode.window.showErrorMessage(`❌ 连接失败: ${res.error || res.message || JSON.stringify(res)}`);
                }
            } catch (e) {
                vscode.window.showErrorMessage(`测试连接失败: ${e.message}`);
            }
        },
    );
}

// 拉取模型列表
async function cmdLLMFetchModels() {
    const baseUrl = await vscode.window.showInputBox({
        prompt: '输入 LLM Base URL',
        placeHolder: 'https://api.openai.com/v1',
        ignoreFocusOut: true,
    });
    if (!baseUrl) return;

    const apiKey = await vscode.window.showInputBox({
        prompt: '输入你的 API Key',
        password: true,
        ignoreFocusOut: true,
    });
    if (!apiKey) return;

    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: '正在拉取模型列表...',
            cancellable: false,
        },
        async () => {
            try {
                const res = await httpRequest('/api/v1/llm/fetch-models', {
                    method: 'POST',
                    body: { base_url: baseUrl, api_key: apiKey },
                });
                const models = res.models || res.data || [];
                if (models.length === 0) {
                    vscode.window.showWarningMessage('未获取到任何模型。');
                    return;
                }
                // 用 QuickPick 展示模型列表
                const picks = models.map((m) => ({
                    label: typeof m === 'string' ? m : m.id || m.name,
                    description: typeof m === 'object' ? (m.owned_by || '') : '',
                }));
                const picked = await vscode.window.showQuickPick(picks, {
                    placeHolder: `共 ${models.length} 个模型，选择一个复制到剪贴板`,
                });
                if (picked) {
                    await vscode.env.clipboard.writeText(picked.label);
                    vscode.window.showInformationMessage(`已复制: ${picked.label}`);
                }
            } catch (e) {
                vscode.window.showErrorMessage(`拉取模型失败: ${e.message}`);
            }
        },
    );
}

// 保存 LLM 配置（支持从供应商传入）
async function cmdLLMSaveConfig(provider) {
    const { token } = getConfig();
    if (!token) {
        const action = await vscode.window.showWarningMessage(
            '保存配置需要登录。请在设置中配置 sakura.token，或先注册账号。',
            '打开设置',
            '取消',
        );
        if (action === '打开设置') {
            vscode.commands.executeCommand('workbench.action.openSettings', 'sakura.token');
        }
        return;
    }

    let providerId = '';
    let displayName = '';
    let baseUrl = '';
    let defaultModel = '';

    if (provider && provider.id) {
        providerId = provider.id;
        displayName = provider.name || provider.id;
        baseUrl = provider.base_url || '';
    } else {
        // 让用户从供应商列表选
        try {
            const res = await httpRequest('/api/v1/llm/providers');
            const providers = res.providers || res.items || [];
            if (providers.length === 0) {
                vscode.window.showWarningMessage('后端未配置任何供应商。');
                return;
            }
            const picks = providers.map((p) => ({
                label: p.name,
                description: p.region || '',
                detail: p.base_url + (p.free_tier ? ' · 免费额度' : ''),
                provider: p,
            }));
            const picked = await vscode.window.showQuickPick(picks, {
                placeHolder: '选择一个供应商（或按 Esc 手动输入）',
            });
            if (picked) {
                providerId = picked.provider.id;
                displayName = picked.provider.name;
                baseUrl = picked.provider.base_url;
            }
        } catch (e) {
            // 忽略，走手动输入
        }
    }

    if (!baseUrl) {
        const input = await vscode.window.showInputBox({
            prompt: '输入 Base URL',
            value: baseUrl,
            placeHolder: 'https://api.openai.com/v1',
            ignoreFocusOut: true,
        });
        if (!input) return;
        baseUrl = input;
    }

    const name = await vscode.window.showInputBox({
        prompt: '配置名称（用于区分）',
        value: displayName || '我的配置',
        ignoreFocusOut: true,
    });
    if (!name) return;

    const apiKey = await vscode.window.showInputBox({
        prompt: '输入你的 API Key（仅保存在你的账号下）',
        password: true,
        placeHolder: 'sk-...',
        ignoreFocusOut: true,
    });
    if (!apiKey) return;

    const { llmDefaultModel } = getConfig();
    defaultModel = await vscode.window.showInputBox({
        prompt: '默认模型名',
        value: (provider && provider.models && provider.models[0]) || llmDefaultModel,
        ignoreFocusOut: true,
    });
    if (!defaultModel) return;

    const isDefault = await vscode.window.showQuickPick(
        [
            { label: '是', value: true },
            { label: '否', value: false },
        ],
        { placeHolder: '设为默认配置？' },
    );

    try {
        const res = await httpRequest('/api/v1/llm/configs', {
            method: 'POST',
            body: {
                provider_id: providerId || null,
                display_name: name,
                base_url: baseUrl,
                api_key: apiKey,
                model: defaultModel,
                is_default: isDefault ? isDefault.value : false,
            },
        });
        vscode.window.showInformationMessage(`✅ 已保存配置: ${res.display_name || name}`);
    } catch (e) {
        vscode.window.showErrorMessage(`保存失败: ${e.message}`);
    }
}

// 查看已保存的 LLM 配置
async function cmdLLMConfigs() {
    const { token } = getConfig();
    if (!token) {
        vscode.window.showWarningMessage('请先在设置中配置 sakura.token。');
        return;
    }
    try {
        const res = await httpRequest('/api/v1/llm/configs');
        const configs = res.configs || res.items || [];
        if (configs.length === 0) {
            const action = await vscode.window.showInformationMessage(
                '暂无已保存的 LLM 配置。',
                '新建配置',
            );
            if (action === '新建配置') {
                cmdLLMSaveConfig();
            }
            return;
        }
        const picks = configs.map((c) => ({
            label: c.display_name,
            description: c.is_default ? '默认' : '',
            detail: `${c.base_url} · ${c.model}`,
            config: c,
        }));
        const picked = await vscode.window.showQuickPick(picks, {
            placeHolder: `共 ${configs.length} 条配置，选择操作`,
        });
        if (!picked) return;

        // 二级菜单
        const action = await vscode.window.showQuickPick(
            [
                { label: '测试连接', value: 'test' },
                { label: '刷新模型列表', value: 'refresh' },
                { label: '设为默认', value: 'default' },
                { label: '删除', value: 'delete' },
            ],
            { placeHolder: `对 "${picked.config.display_name}" 执行操作` },
        );
        if (!action) return;

        const configId = picked.config.id;
        if (action.value === 'test') {
            await vscode.window.withProgress(
                { location: vscode.ProgressLocation.Notification, title: '测试中...' },
                async () => {
                    try {
                        const r = await httpRequest(`/api/v1/llm/configs/${configId}/test`, { method: 'POST' });
                        if (r.ok || r.success) {
                            vscode.window.showInformationMessage(`✅ 连接成功: ${(r.reply || r.message || '').slice(0, 100)}`);
                        } else {
                            vscode.window.showErrorMessage(`❌ 失败: ${r.error || r.message}`);
                        }
                    } catch (e) {
                        vscode.window.showErrorMessage(`测试失败: ${e.message}`);
                    }
                },
            );
        } else if (action.value === 'refresh') {
            try {
                const r = await httpRequest(`/api/v1/llm/configs/${configId}/refresh-models`, { method: 'POST' });
                const models = r.models || [];
                vscode.window.showInformationMessage(`已刷新，共 ${models.length} 个模型。`);
            } catch (e) {
                vscode.window.showErrorMessage(`刷新失败: ${e.message}`);
            }
        } else if (action.value === 'default') {
            try {
                await httpRequest(`/api/v1/llm/configs/${configId}`, {
                    method: 'PUT',
                    body: { is_default: true },
                });
                vscode.window.showInformationMessage('已设为默认。');
            } catch (e) {
                vscode.window.showErrorMessage(`设置失败: ${e.message}`);
            }
        } else if (action.value === 'delete') {
            const confirm = await vscode.window.showWarningMessage(
                `确定删除 "${picked.config.display_name}"？`,
                { modal: true },
                '删除',
            );
            if (confirm === '删除') {
                try {
                    await httpRequest(`/api/v1/llm/configs/${configId}`, { method: 'DELETE' });
                    vscode.window.showInformationMessage('已删除。');
                } catch (e) {
                    vscode.window.showErrorMessage(`删除失败: ${e.message}`);
                }
            }
        }
    } catch (e) {
        vscode.window.showErrorMessage(`获取配置失败: ${e.message}`);
    }
}

// 环境变量检测
async function cmdLLMEnvCheck() {
    try {
        const res = await httpRequest('/api/v1/llm/env-check');
        const items = Object.entries(res.env_vars || res.items || {});
        if (items.length === 0) {
            vscode.window.showInformationMessage('后端未配置任何环境变量。');
            return;
        }
        const lines = items.map(([k, v]) => `${k}: ${v ? '✅ 已设置' : '❌ 未设置'}`);
        const doc = await vscode.workspace.openTextDocument({ content: lines.join('\n'), language: 'plaintext' });
        await vscode.window.showTextDocument(doc);
    } catch (e) {
        vscode.window.showErrorMessage(`检测失败: ${e.message}`);
    }
}

// 打开 LLM 管理面板（Webview）
async function cmdLLMPanel() {
    LLMPanel.createOrShow();
}

// ============================================================
// 团队树视图
// ============================================================

class TeamsProvider {
    constructor() {
        this.teams = [];
        this._onDidChangeTreeData = undefined;
    }
    refresh() {
        this._onDidChangeTreeData && this._onDidChangeTreeData.fire();
    }
    getTreeItem(element) {
        return element;
    }
    async getChildren() {
        try {
            const res = await httpRequest('/api/v1/teams');
            this.teams = res.teams || [];
            return this.teams.map((t) => {
                const item = new vscode.TreeItem(
                    `${t.icon || '🌟'} ${t.name}`,
                    vscode.TreeItemCollapsibleState.None,
                );
                item.description = t.mode || '';
                item.tooltip = t.description || '';
                item.contextValue = 'team';
                item.command = {
                    command: 'sakura.chat',
                    title: '对话',
                    arguments: [t],
                };
                return item;
            });
        } catch (e) {
            return [
                new vscode.TreeItem(
                    `⚠️ 无法连接后端: ${e.message}`,
                    vscode.TreeItemCollapsibleState.None,
                ),
            ];
        }
    }
}

// ============================================================
// 专家树视图
// ============================================================

class AgentsProvider {
    constructor() {
        this.agents = [];
    }
    refresh() {
        this._onDidChangeTreeData && this._onDidChangeTreeData.fire();
    }
    getTreeItem(element) {
        return element;
    }
    async getChildren() {
        try {
            const res = await httpRequest('/api/v1/experts');
            this.agents = res.agents || [];
            return this.agents.map((a) => {
                const item = new vscode.TreeItem(
                    `${a.avatar || '🤖'} ${a.name}`,
                    vscode.TreeItemCollapsibleState.None,
                );
                item.description = a.role || '';
                item.tooltip = a.tagline || a.goal || '';
                item.contextValue = 'agent';
                return item;
            });
        } catch (e) {
            return [
                new vscode.TreeItem(
                    `⚠️ 无法连接后端: ${e.message}`,
                    vscode.TreeItemCollapsibleState.None,
                ),
            ];
        }
    }
}

// ============================================================
// LLM 供应商树视图
// ============================================================

class LLMProvidersProvider {
    constructor() {
        this.providers = [];
    }
    refresh() {
        this._onDidChangeTreeData && this._onDidChangeTreeData.fire();
    }
    getTreeItem(element) {
        return element;
    }
    async getChildren() {
        try {
            const res = await httpRequest('/api/v1/llm/providers');
            this.providers = res.providers || res.items || [];
            if (this.providers.length === 0) {
                return [
                    new vscode.TreeItem(
                        '暂无供应商，请检查后端配置',
                        vscode.TreeItemCollapsibleState.None,
                    ),
                ];
            }
            // 分组：免费 / 国内 / 国际
            const free = this.providers.filter((p) => p.free_tier);
            const cn = this.providers.filter((p) => (p.region || '') === 'cn' && !p.free_tier);
            const intl = this.providers.filter((p) => (p.region || 'intl') === 'intl' && !p.free_tier);

            const items = [];
            if (free.length > 0) {
                const freeItem = new vscode.TreeItem(
                    `免费额度 (${free.length})`,
                    vscode.TreeItemCollapsibleState.Expanded,
                );
                freeItem.contextValue = 'group';
                freeItem.iconPath = new vscode.ThemeIcon('gift');
                items.push(freeItem);
            }
            if (cn.length > 0) {
                const cnItem = new vscode.TreeItem(
                    `国内厂商 (${cn.length})`,
                    vscode.TreeItemCollapsibleState.Collapsed,
                );
                cnItem.contextValue = 'group';
                cnItem.iconPath = new vscode.ThemeIcon('globe');
                items.push(cnItem);
            }
            if (intl.length > 0) {
                const intlItem = new vscode.TreeItem(
                    `国际厂商 (${intl.length})`,
                    vscode.TreeItemCollapsibleState.Collapsed,
                );
                intlItem.contextValue = 'group';
                intlItem.iconPath = new vscode.ThemeIcon('rocket');
                items.push(intlItem);
            }
            return items;
        } catch (e) {
            return [
                new vscode.TreeItem(
                    `⚠️ 无法连接后端: ${e.message}`,
                    vscode.TreeItemCollapsibleState.None,
                ),
            ];
        }
    }
}

// ============================================================
// Webview 聊天面板
// ============================================================

class ChatPanel {
    static createOrShow(team) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;
        if (ChatPanel.currentPanel) {
            ChatPanel.currentPanel._panel.reveal(column);
            ChatPanel.currentPanel._update(team);
            return;
        }
        const panel = vscode.window.createWebviewPanel(
            'sakuraChat',
            `🌸 ${team.name}`,
            column || vscode.ViewColumn.One,
            { enableScripts: true, retainContextWhenHidden: true },
        );
        ChatPanel.currentPanel = new ChatPanel(panel, team);
    }

    constructor(panel, team) {
        this._panel = panel;
        this._team = team;
        this._disposables = [];
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.onDidReceiveMessage(
            (msg) => this._handleMessage(msg),
            null,
            this._disposables,
        );
        this._update(team);
    }

    _update(team) {
        this._team = team;
        this._panel.title = `🌸 ${team.name}`;
        this._panel.webview.html = this._getHtml(team);
    }

    _getHtml(team) {
        const members = (team.members || [])
            .map((m) => `${m.avatar || '🤖'} ${m.name}`)
            .join('  ·  ');
        return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🌸 ${team.name}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background: #1e1e1e; color: #d4d4d4; height: 100vh; display: flex; flex-direction: column; }
  .header { padding: 12px 16px; background: #252526; border-bottom: 1px solid #333; }
  .header h2 { font-size: 15px; color: #ec4899; }
  .header .members { font-size: 12px; color: #888; margin-top: 4px; }
  .messages { flex: 1; overflow-y: auto; padding: 16px; }
  .msg { margin-bottom: 12px; }
  .msg .name { font-size: 12px; color: #569cd6; margin-bottom: 2px; }
  .msg .bubble { background: #2d2d2d; border-radius: 8px; padding: 8px 12px; font-size: 13px; line-height: 1.6; white-space: pre-wrap; }
  .msg.user .bubble { background: #3b3268; }
  .msg.error .bubble { background: #5a1d1d; color: #f87171; }
  .input-area { display: flex; padding: 12px; background: #252526; border-top: 1px solid #333; }
  .input-area input { flex: 1; background: #3c3c3c; border: 1px solid #555; color: #d4d4d4;
                      border-radius: 4px; padding: 8px 12px; font-size: 13px; outline: none; }
  .input-area button { margin-left: 8px; background: #ec4899; color: #fff; border: none;
                       border-radius: 4px; padding: 0 16px; cursor: pointer; font-size: 13px; }
  .input-area button:disabled { background: #555; cursor: not-allowed; }
</style>
</head>
<body>
  <div class="header">
    <h2>🌸 ${team.name} · ${team.mode || 'group'}</h2>
    <div class="members">${members}</div>
  </div>
  <div class="messages" id="messages"></div>
  <div class="input-area">
    <input id="input" type="text" placeholder="输入消息，回车发送…" autofocus />
    <button id="send" onclick="send()">发送</button>
  </div>
<script>
  const vscode = acquireVsCodeApi();
  const input = document.getElementById('input');
  const messages = document.getElementById('messages');
  const sendBtn = document.getElementById('send');

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') send();
  });

  function send() {
    const text = input.value.trim();
    if (!text) return;
    addMessage('user', '你', text);
    input.value = '';
    sendBtn.disabled = true;
    vscode.postMessage({ command: 'chat', text });
  }

  function addMessage(role, name, content) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.innerHTML = '<div class="name">' + escapeHtml(name) + '</div><div class="bubble">' + escapeHtml(content) + '</div>';
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  window.addEventListener('message', (e) => {
    const msg = e.data;
    if (msg.command === 'agent_message') {
      addMessage('agent', msg.name, msg.content);
    } else if (msg.command === 'done') {
      sendBtn.disabled = false;
    } else if (msg.command === 'error') {
      addMessage('error', '错误', msg.content);
      sendBtn.disabled = false;
    }
  });
</script>
</body>
</html>`;
    }

    async _handleMessage(msg) {
        if (msg.command !== 'chat') return;
        const text = msg.text;
        try {
            await this._streamChat(text);
        } catch (e) {
            this._panel.webview.postMessage({ command: 'error', content: e.message });
        }
    }

    _streamChat(message) {
        return new Promise((resolve, reject) => {
            const { serverUrl, token } = getConfig();
            const fullUrl = `${serverUrl}/api/v1/teams/${this._team.id}/chat`;
            const url = new URL(fullUrl);
            const lib = url.protocol === 'https:' ? https : http;
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers.Authorization = `Bearer ${token}`;
            const payload = JSON.stringify({ message, history: [] });
            headers['Content-Length'] = Buffer.byteLength(payload);

            const req = lib.request(
                {
                    hostname: url.hostname,
                    port: url.port || (url.protocol === 'https:' ? 443 : 80),
                    path: url.pathname,
                    method: 'POST',
                    headers,
                },
                (res) => {
                    if (res.statusCode !== 200) {
                        let d = '';
                        res.on('data', (c) => (d += c));
                        res.on('end', () => reject(new Error(`HTTP ${res.statusCode}: ${d}`)));
                        return;
                    }
                    let buffer = '';
                    let currentEvent = '';
                    res.on('data', (chunk) => {
                        buffer += chunk.toString();
                        const lines = buffer.split('\n');
                        buffer = lines.pop() || '';
                        for (const line of lines) {
                            if (line.startsWith('event:')) {
                                currentEvent = line.slice(6).trim();
                            } else if (line.startsWith('data:')) {
                                const dataStr = line.slice(5).trim();
                                if (!dataStr) continue;
                                try {
                                    const data = JSON.parse(dataStr);
                                    this._dispatchEvent(currentEvent, data);
                                } catch (e) {
                                    // 忽略解析错误
                                }
                            }
                        }
                    });
                    res.on('end', () => {
                        this._panel.webview.postMessage({ command: 'done' });
                        resolve();
                    });
                },
            );
            req.on('error', reject);
            req.write(payload);
            req.end();
        });
    }

    _dispatchEvent(eventType, data) {
        const payload = data.payload || data;
        if (eventType === 'agent_message' || eventType === 'agent_speak') {
            this._panel.webview.postMessage({
                command: 'agent_message',
                name: `${payload.avatar || '🤖'} ${payload.name || payload.role || '专家'}`,
                content: payload.content || payload.message || '',
            });
        } else if (eventType === 'error') {
            this._panel.webview.postMessage({
                command: 'error',
                content: payload.message || JSON.stringify(payload),
            });
        }
    }

    dispose() {
        ChatPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) d.dispose();
        }
    }
}

// ============================================================
// LLM 管理 Webview 面板
// ============================================================

class LLMPanel {
    static createOrShow() {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;
        if (LLMPanel.currentPanel) {
            LLMPanel.currentPanel._panel.reveal(column);
            return;
        }
        const panel = vscode.window.createWebviewPanel(
            'sakuraLLM',
            '🌸 LLM 管理',
            column || vscode.ViewColumn.One,
            { enableScripts: true, retainContextWhenHidden: true },
        );
        LLMPanel.currentPanel = new LLMPanel(panel);
    }

    constructor(panel) {
        this._panel = panel;
        this._disposables = [];
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.onDidReceiveMessage(
            (msg) => this._handleMessage(msg),
            null,
            this._disposables,
        );
        this._panel.webview.html = this._getHtml();
        // 初始加载
        this._postCommand('loadProviders', {});
        this._postCommand('loadConfigs', {});
    }

    _postCommand(command, data) {
        this._panel.webview.postMessage({ command, ...data });
    }

    async _handleMessage(msg) {
        try {
            if (msg.command === 'requestProviders') {
                const res = await httpRequest('/api/v1/llm/providers');
                this._postCommand('loadProviders', { providers: res.providers || res.items || [] });
            } else if (msg.command === 'requestConfigs') {
                const res = await httpRequest('/api/v1/llm/configs');
                this._postCommand('loadConfigs', { configs: res.configs || res.items || [] });
            } else if (msg.command === 'testConnection') {
                const res = await httpRequest('/api/v1/llm/test-connection', {
                    method: 'POST',
                    body: { base_url: msg.baseUrl, api_key: msg.apiKey, model: msg.model },
                });
                this._postCommand('testResult', { ok: !!(res.ok || res.success), result: res });
            } else if (msg.command === 'fetchModels') {
                const res = await httpRequest('/api/v1/llm/fetch-models', {
                    method: 'POST',
                    body: { base_url: msg.baseUrl, api_key: msg.apiKey },
                });
                this._postCommand('modelsResult', { models: res.models || res.data || [] });
            } else if (msg.command === 'saveConfig') {
                const res = await httpRequest('/api/v1/llm/configs', {
                    method: 'POST',
                    body: msg.data,
                });
                this._postCommand('saveResult', { ok: true, config: res });
                // 重新加载配置列表
                const r = await httpRequest('/api/v1/llm/configs');
                this._postCommand('loadConfigs', { configs: r.configs || r.items || [] });
            } else if (msg.command === 'deleteConfig') {
                await httpRequest(`/api/v1/llm/configs/${msg.id}`, { method: 'DELETE' });
                this._postCommand('deleteResult', { ok: true, id: msg.id });
                const r = await httpRequest('/api/v1/llm/configs');
                this._postCommand('loadConfigs', { configs: r.configs || r.items || [] });
            } else if (msg.command === 'testConfig') {
                const res = await httpRequest(`/api/v1/llm/configs/${msg.id}/test`, { method: 'POST' });
                this._postCommand('testConfigResult', { ok: !!(res.ok || res.success), result: res, id: msg.id });
            } else if (msg.command === 'setDefault') {
                await httpRequest(`/api/v1/llm/configs/${msg.id}`, {
                    method: 'PUT',
                    body: { is_default: true },
                });
                this._postCommand('setDefaultResult', { ok: true, id: msg.id });
                const r = await httpRequest('/api/v1/llm/configs');
                this._postCommand('loadConfigs', { configs: r.configs || r.items || [] });
            }
        } catch (e) {
            this._postCommand('error', { message: e.message });
        }
    }

    _getHtml() {
        return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🌸 LLM 管理</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background: #1e1e1e; color: #d4d4d4; padding: 16px; }
  h2 { color: #ec4899; font-size: 16px; margin-bottom: 12px; border-bottom: 1px solid #333; padding-bottom: 8px; }
  h3 { color: #c97b8a; font-size: 13px; margin: 16px 0 8px; }
  .tabs { display: flex; gap: 4px; margin-bottom: 12px; }
  .tab { padding: 6px 14px; background: #2d2d2d; border: 1px solid #444; border-radius: 4px 4px 0 0;
         cursor: pointer; font-size: 12px; color: #aaa; }
  .tab.active { background: #3b3268; color: #fff; border-color: #ec4899; }
  .panel { display: none; }
  .panel.active { display: block; }
  .row { display: flex; gap: 8px; margin-bottom: 8px; align-items: center; }
  .row label { width: 100px; font-size: 12px; color: #888; }
  .row input, .row select { flex: 1; background: #3c3c3c; border: 1px solid #555; color: #d4d4d4;
                            border-radius: 4px; padding: 6px 10px; font-size: 12px; outline: none; }
  .row input:focus, .row select:focus { border-color: #ec4899; }
  button { background: #ec4899; color: #fff; border: none; border-radius: 4px;
           padding: 6px 14px; cursor: pointer; font-size: 12px; }
  button:hover { background: #db2777; }
  button.secondary { background: #3c3c3c; }
  button.secondary:hover { background: #4c4c4c; }
  button.danger { background: #b91c1c; }
  button.danger:hover { background: #991b1b; }
  .list { margin-top: 8px; }
  .item { background: #252526; border: 1px solid #333; border-radius: 6px; padding: 10px 12px;
          margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
  .item .info { flex: 1; }
  .item .name { font-size: 13px; color: #fff; font-weight: 500; }
  .item .meta { font-size: 11px; color: #888; margin-top: 2px; }
  .item .actions { display: flex; gap: 4px; }
  .badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px;
           background: #3b3268; color: #c4b5fd; margin-left: 6px; }
  .badge.free { background: #14532d; color: #86efac; }
  .badge.default { background: #78350f; color: #fcd34d; }
  .result { padding: 8px 12px; border-radius: 4px; margin-top: 8px; font-size: 12px; font-family: monospace; }
  .result.ok { background: #14532d; color: #86efac; }
  .result.err { background: #5a1d1d; color: #f87171; }
  .empty { text-align: center; color: #666; padding: 24px; font-size: 12px; }
  .provider-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }
  .provider-card { background: #252526; border: 1px solid #333; border-radius: 6px; padding: 10px; cursor: pointer; }
  .provider-card:hover { border-color: #ec4899; }
  .provider-card .pname { font-size: 12px; color: #fff; font-weight: 500; }
  .provider-card .purl { font-size: 10px; color: #888; margin-top: 2px; word-break: break-all; }
</style>
</head>
<body>
  <h2>🌸 LLM 配置管理</h2>
  <div class="tabs">
    <div class="tab active" data-tab="providers">供应商列表</div>
    <div class="tab" data-tab="custom">自定义端点</div>
    <div class="tab" data-tab="configs">我的配置</div>
  </div>

  <!-- Tab 1: 供应商列表 -->
  <div class="panel active" id="panel-providers">
    <h3>从内置供应商选择（点击填充到自定义端点）</h3>
    <div class="provider-grid" id="providers-list">
      <div class="empty">加载中...</div>
    </div>
  </div>

  <!-- Tab 2: 自定义端点 -->
  <div class="panel" id="panel-custom">
    <h3>用自己的 API Key 测试连接</h3>
    <div class="row"><label>Base URL</label><input id="c-base" placeholder="https://api.openai.com/v1" /></div>
    <div class="row"><label>API Key</label><input id="c-key" type="password" placeholder="sk-..." /></div>
    <div class="row"><label>Model</label><input id="c-model" placeholder="gpt-4o-mini" /></div>
    <div class="row" style="justify-content: flex-end;">
      <button class="secondary" onclick="fetchModels()">拉取模型</button>
      <button onclick="testCustom()">测试连接</button>
      <button onclick="saveFromCustom()">保存为配置</button>
    </div>
    <div id="custom-result"></div>
    <div class="list" id="models-list"></div>
  </div>

  <!-- Tab 3: 我的配置 -->
  <div class="panel" id="panel-configs">
    <h3>已保存的配置（点击测试/设为默认/删除）</h3>
    <div class="list" id="configs-list">
      <div class="empty">加载中...</div>
    </div>
  </div>

<script>
  const vscode = acquireVsCodeApi();
  let providers = [];
  let configs = [];

  // Tab 切换
  document.querySelectorAll('.tab').forEach((t) => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach((x) => x.classList.remove('active'));
      document.querySelectorAll('.panel').forEach((x) => x.classList.remove('active'));
      t.classList.add('active');
      document.getElementById('panel-' + t.dataset.tab).classList.add('active');
    });
  });

  // 请求初始数据
  vscode.postMessage({ command: 'requestProviders' });
  vscode.postMessage({ command: 'requestConfigs' });

  // 渲染供应商列表
  function renderProviders() {
    const el = document.getElementById('providers-list');
    if (providers.length === 0) {
      el.innerHTML = '<div class="empty">暂无供应商</div>';
      return;
    }
    el.innerHTML = providers.map((p) => \`
      <div class="provider-card" onclick="useProvider('\${p.id}')">
        <div class="pname">\${p.name} \${p.free_tier ? '<span class="badge free">免费</span>' : ''}</div>
        <div class="purl">\${p.base_url}</div>
      </div>
    \`).join('');
  }

  // 渲染配置列表
  function renderConfigs() {
    const el = document.getElementById('configs-list');
    if (configs.length === 0) {
      el.innerHTML = '<div class="empty">暂无配置，去「自定义端点」保存一条吧</div>';
      return;
    }
    el.innerHTML = configs.map((c) => \`
      <div class="item">
        <div class="info">
          <div class="name">\${c.display_name} \${c.is_default ? '<span class="badge default">默认</span>' : ''}</div>
          <div class="meta">\${c.base_url} · \${c.model}</div>
        </div>
        <div class="actions">
          <button class="secondary" onclick="testConfig('\${c.id}')">测试</button>
          <button class="secondary" onclick="setDefault('\${c.id}')">设默认</button>
          <button class="danger" onclick="deleteConfig('\${c.id}')">删除</button>
        </div>
      </div>
    \`).join('');
  }

  // 点击供应商填充到自定义端点
  function useProvider(id) {
    const p = providers.find((x) => x.id === id);
    if (!p) return;
    document.getElementById('c-base').value = p.base_url;
    if (p.models && p.models[0]) document.getElementById('c-model').value = p.models[0];
    // 切换到自定义端点 tab
    document.querySelector('.tab[data-tab="custom"]').click();
    document.getElementById('c-key').focus();
  }

  // 测试自定义连接
  function testCustom() {
    const baseUrl = document.getElementById('c-base').value.trim();
    const apiKey = document.getElementById('c-key').value.trim();
    const model = document.getElementById('c-model').value.trim();
    if (!baseUrl || !apiKey || !model) {
      showResult('custom-result', false, '请填写完整');
      return;
    }
    vscode.postMessage({ command: 'testConnection', baseUrl, apiKey, model });
  }

  // 拉取模型
  function fetchModels() {
    const baseUrl = document.getElementById('c-base').value.trim();
    const apiKey = document.getElementById('c-key').value.trim();
    if (!baseUrl || !apiKey) {
      showResult('custom-result', false, '请填写 Base URL 和 API Key');
      return;
    }
    vscode.postMessage({ command: 'fetchModels', baseUrl, apiKey });
  }

  // 保存自定义配置
  function saveFromCustom() {
    const baseUrl = document.getElementById('c-base').value.trim();
    const apiKey = document.getElementById('c-key').value.trim();
    const model = document.getElementById('c-model').value.trim();
    if (!baseUrl || !apiKey || !model) {
      showResult('custom-result', false, '请填写完整');
      return;
    }
    const name = baseUrl.replace(/^https?:\\/\\//, '').split('/')[0];
    vscode.postMessage({
      command: 'saveConfig',
      data: {
        provider_id: null,
        display_name: name,
        base_url: baseUrl,
        api_key: apiKey,
        model: model,
        is_default: false,
      },
    });
  }

  // 测试已保存配置
  function testConfig(id) {
    vscode.postMessage({ command: 'testConfig', id });
  }

  // 设为默认
  function setDefault(id) {
    vscode.postMessage({ command: 'setDefault', id });
  }

  // 删除配置
  function deleteConfig(id) {
    if (!confirm('确定删除？')) return;
    vscode.postMessage({ command: 'deleteConfig', id });
  }

  // 显示结果
  function showResult(elId, ok, msg) {
    const el = document.getElementById(elId);
    el.className = 'result ' + (ok ? 'ok' : 'err');
    el.textContent = (ok ? '✅ ' : '❌ ') + msg;
  }

  // 接收主进程消息
  window.addEventListener('message', (e) => {
    const msg = e.data;
    if (msg.command === 'loadProviders') {
      providers = msg.providers || [];
      renderProviders();
    } else if (msg.command === 'loadConfigs') {
      configs = msg.configs || [];
      renderConfigs();
    } else if (msg.command === 'testResult') {
      const r = msg.result;
      const text = r.reply || r.message || r.error || JSON.stringify(r);
      showResult('custom-result', msg.ok, text.slice(0, 200));
    } else if (msg.command === 'modelsResult') {
      const el = document.getElementById('models-list');
      const models = msg.models || [];
      if (models.length === 0) {
        el.innerHTML = '<div class="empty">未获取到模型</div>';
        return;
      }
      el.innerHTML = models.map((m) => {
        const id = typeof m === 'string' ? m : (m.id || m.name);
        return '<div class="item"><div class="info"><div class="name">' + id + '</div></div></div>';
      }).join('');
    } else if (msg.command === 'saveResult') {
      if (msg.ok) {
        showResult('custom-result', true, '已保存: ' + (msg.config.display_name || ''));
      }
    } else if (msg.command === 'deleteResult') {
      // 列表会自动刷新
    } else if (msg.command === 'testConfigResult') {
      vscode.window && alert(msg.ok ? '连接成功' : '连接失败: ' + (msg.result.error || msg.result.message || ''));
    } else if (msg.command === 'error') {
      showResult('custom-result', false, msg.message);
    }
  });
</script>
</body>
</html>`;
    }

    dispose() {
        LLMPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) d.dispose();
        }
    }
}
