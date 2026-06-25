# Agent 创建指南

> 本文档教你如何为樱花小队 (SakuraAgentTeam) 创建自定义专家智能体，并通过界面或 API 提交到社区。

---

## 目录

1. [Agent 结构](#1-agent-结构)
2. [分类列表](#2-分类列表)
3. [创建示例](#3-创建示例)
4. [通过界面提交](#4-通过界面提交)
5. [通过 API 提交](#5-通过-api-提交)
6. [审核流程](#6-审核流程)

---

## 1. Agent 结构

每个 Agent 由一个 `AgentDef` 数据结构定义，包含以下字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 唯一标识，使用英文 + 下划线（如 `code_reviewer`） |
| `name` | string | 是 | 显示名，中文（如 `代码审查专家`） |
| `role` | string | 是 | 职业角色，英文（如 `Code Reviewer`） |
| `category` | string | 是 | 分类，见 [分类列表](#2-分类列表) |
| `avatar` | string | 是 | emoji 头像（如 `🔍`） |
| `color` | string | 是 | 主题色，hex 格式（如 `#3b82f6`） |
| `tagline` | string | 是 | 一句话描述（如 `专治各种代码坏味道`） |
| `goal` | string | 是 | 目标，描述这个 agent 要做什么 |
| `backstory` | string | 是 | 背景故事，8-15 年经验描述 |
| `skills` | string[] | 是 | 技能列表 |
| `allow_delegation` | boolean | 否 | 是否允许委派，默认 `false` |

### 字段详解

- **id**：全局唯一，注册表按此索引。建议使用 `领域_角色` 的命名风格，例如 `tech_code_reviewer`、`design_ui_designer`。
- **name / role**：`name` 面向中文用户展示，`role` 面向系统与 LLM prompt，使用英文职业头衔。
- **avatar**：单个 emoji，用于团队组建界面与聊天界面的头像展示。
- **color**：6 位 hex 色值，决定该 Agent 在界面上的主题色（头像背景、消息边框等）。
- **goal**：清晰、可执行的目标描述，会注入到 LLM 的 system prompt 中。
- **backstory**：8-15 年经验的背景叙述，用于塑造 Agent 的人设与专业深度，会注入到 LLM 的 system prompt 中。
- **skills**：技能关键词列表，用于团队组建时的检索匹配与 prompt 构建。
- **allow_delegation**：在管家模式 (master) 与转交模式 (handoff) 中，决定该 Agent 能否将子任务委派给其他 Agent。

---

## 2. 分类列表

系统支持以下 30 个分类（`category` 字段取值），共 100 位预设专家：

| 分类标识 | 中文含义 | 数量 | 示例角色 |
|----------|----------|------|----------|
| `creative` | 创意 | 4 | 文案、主笔、小说家、诗人 |
| `design` | 设计 | 4 | 视觉、交互、插画、动效 |
| `tech` | 技术 | 7 | 全栈、前端、后端、AI 工程、数据、运维、安全 |
| `research` | 研究 | 4 | 行研、数据科学、用户研究、产品经理 |
| `strategy` | 策略 | 7 | 增长、战略、商务、销售、财务、运营、项目 |
| `qa` | 审核 | 2 | 审核、测试 |
| `industry` | 行业 | 12 | 法务、私教、教授、翻译、公关、演讲、健康、职涯、SaaS、教育、金融、医疗 |
| `education` | 教育 | 3 | 在线教师、课程设计师、教育顾问 |
| `finance` | 金融 | 3 | 财务顾问、投资分析师、会计 |
| `legal` | 法律 | 2 | 法律顾问、合同审查 |
| `healthcare` | 健康 | 2 | 健康顾问、心理咨询师 |
| `media` | 媒体 | 3 | 视频编导、播客制作人、摄影师 |
| `music` | 音乐 | 2 | 音乐制作人、作曲家 |
| `writing` | 写作 | 3 | 小说家、剧本作家、诗人 |
| `data` | 数据 | 3 | 数据科学家、数据工程师、ML 工程师 |
| `devops` | DevOps | 3 | DevOps 工程师、SRE、安全工程师 |
| `business` | 商业 | 3 | 商业顾问、项目经理、运营经理 |
| `academic` | 学术 | 7 | 文献调研、方法设计、数据分析、论文写作、编辑润色、项目管理、论文审查 |
| `translation` | 翻译 | 3 | 英文翻译、日文翻译、多语种翻译 |
| `ecommerce` | 电商 | 3 | 电商运营、选品专家、直播策划 |
| `game` | 游戏 | 3 | 游戏设计师、游戏开发、游戏剧情 |
| `travel` | 旅游 | 2 | 旅行规划师、旅游文案 |
| `food` | 美食 | 2 | 菜谱开发、美食评论 |
| `sports` | 体育 | 2 | 运动教练、体育分析 |
| `agriculture` | 农业 | 2 | 农业技术、园艺师 |
| `energy` | 能源 | 2 | 新能源、电力系统 |
| `aerospace` | 航空 | 2 | 航空工程、无人机 |
| `environment` | 环保 | 2 | 环境工程、碳中和 |
| `social` | 社交 | 2 | 社交媒体、社群运营 |
| `psychology` | 心理 | 1 | 职业规划 |

### 2.1 完整 Agent 清单

#### 创意 (creative) — 4 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `copywriter` | 文案 | Senior Copywriter | ✍ |
| `editor` | 主笔 | Chief Editor | 📝 |
| `novelist` | 小说家 | Novelist | 📖 |
| `poet` | 诗人 | Poet | 🌸 |

#### 设计 (design) — 4 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `visual_designer` | 视觉 | Senior Visual Designer | 🎨 |
| `ux_designer` | 交互 | UX Designer | 🧭 |
| `illustrator` | 插画 | Illustrator | 🖌 |
| `motion_designer` | 动效 | Motion Designer | ✨ |

#### 技术 (tech) — 7 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `fullstack` | 全栈 | Senior Full-stack Engineer | ⚡ |
| `frontend` | 前端 | Senior Frontend Engineer | 🌐 |
| `backend` | 后端 | Senior Backend Engineer | ⚙ |
| `ai_engineer` | AI 工程 | Senior AI Engineer | 🤖 |
| `data_engineer` | 数据 | Senior Data Engineer | 📊 |
| `devops` | 运维 | DevOps Engineer | 🔧 |
| `security` | 安全 | Security Engineer | 🛡 |

#### 研究 (research) — 4 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `analyst` | 行研 | Senior Industry Analyst | 🔍 |
| `data_scientist` | 数据科学 | Data Scientist | 📈 |
| `ux_researcher` | 用户研究 | UX Researcher | 👤 |
| `product_manager` | 产品经理 | Senior Product Manager | 📋 |

#### 策略 (strategy) — 7 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `growth` | 增长 | Growth Lead | 🚀 |
| `strategist` | 战略 | Strategy Consultant | ♟ |
| `bd` | 商务 | Senior BD Manager | 🤝 |
| `sales` | 销售 | Senior Sales Lead | 💰 |
| `finance` | 财务 | CFO Advisor | 💵 |
| `operations` | 运营 | Senior Operations Manager | 🔄 |
| `project_manager` | 项目 | Senior Project Manager | 📅 |

#### 审核 (qa) — 2 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `reviewer` | 审核 | Chief Quality Reviewer | 🛡 |
| `tester` | 测试 | Senior QA Engineer | 🧪 |

#### 行业 (industry) — 12 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `legal` | 法务 | Senior Legal Counsel | ⚖ |
| `tutor` | 私教 | Personal Tutor | 📚 |
| `professor` | 教授 | University Professor | 🎓 |
| `translator` | 翻译 | Senior Translator | 🌐 |
| `pr` | 公关 | Senior PR Manager | 📢 |
| `speechwriter` | 演讲 | Chief Speechwriter | 🎤 |
| `health_coach` | 健康 | Senior Health Coach | 🌿 |
| `career_coach` | 职涯 | Senior Career Coach | 🧭 |
| `saas_expert` | SaaS | Senior SaaS Expert | ☁ |
| `education_expert` | 教育 | Senior Education Expert | 🏫 |
| `fintech_expert` | 金融 | Senior FinTech Expert | 🏦 |
| `medical_expert` | 医疗 | Senior Medical Expert | ⚕ |

#### 教育 (education) — 3 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `online_teacher` | 在线教师 | Online Teacher | 👩‍🏫 |
| `course_designer` | 课程设计师 | Course Designer | 📐 |
| `education_consultant` | 教育顾问 | Education Consultant | 🎯 |

#### 金融 (finance) — 3 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `financial_advisor` | 财务顾问 | Financial Advisor | 💼 |
| `investment_analyst` | 投资分析师 | Investment Analyst | 📊 |
| `accountant` | 会计 | CPA Accountant | 🧮 |

#### 法律 (legal) — 2 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `legal_advisor` | 法律顾问 | Legal Advisor | ⚖️ |
| `contract_reviewer` | 合同审查 | Contract Reviewer | 🔍 |

#### 健康 (healthcare) — 2 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `health_consultant` | 健康顾问 | Health Consultant | 🥗 |
| `psychologist` | 心理咨询师 | Psychologist | 🧠 |

#### 媒体 (media) — 3 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `video_director` | 视频编导 | Video Director | 🎬 |
| `podcast_producer` | 播客制作人 | Podcast Producer | 🎙 |
| `photographer` | 摄影师 | Photographer | 📷 |

#### 音乐 (music) — 2 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `music_producer` | 音乐制作人 | Music Producer | 🎹 |
| `composer` | 作曲家 | Composer | 🎼 |

#### 写作 (writing) — 3 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `novelist_2` | 小说家 | Professional Novelist | 📕 |
| `screenwriter` | 剧本作家 | Screenwriter | 🎞 |
| `poet_2` | 诗人 | Modern Poet | 🖋 |

#### 数据 (data) — 3 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `data_scientist_2` | 数据科学家 | Data Scientist | 📈 |
| `data_engineer_2` | 数据工程师 | Data Engineer | 🔗 |
| `ml_engineer` | ML 工程师 | ML Engineer | 🤖 |

#### DevOps (devops) — 3 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `devops_engineer` | DevOps 工程师 | DevOps Engineer | 🚀 |
| `sre_engineer` | SRE | Site Reliability Engineer | 📡 |
| `security_engineer` | 安全工程师 | Security Engineer | 🔐 |

#### 商业 (business) — 3 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `business_consultant` | 商业顾问 | Business Consultant | 📊 |
| `project_manager_2` | 项目经理 | Project Manager | 📋 |
| `operations_manager` | 运营经理 | Operations Manager | ⚙️ |

#### 学术 (academic) — 7 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `literature_review_agent` | 文献调研 | Literature Review Expert | 📚 |
| `methodology_design_agent` | 方法设计 | Methodology Design Expert | 🔬 |
| `data_analysis_agent` | 数据分析 | Data Analysis Expert | 📊 |
| `paper_writing_agent` | 论文写作 | Academic Paper Writer | 📝 |
| `editing_polishing_agent` | 编辑润色 | Academic Editor | ✏️ |
| `paper_project_manager` | 论文项目管理 | Paper Project Manager | 📋 |
| `paper_review_agent` | 论文审查 | Paper Review & Audit Expert | 🔍 |

#### 翻译 (translation) — 3 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `en_translator` | 英文翻译 | English Translator | 🌐 |
| `jp_translator` | 日文翻译 | Japanese Translator | 🗾 |
| `multi_translator` | 多语种翻译 | Multilingual Translator | 🌍 |

#### 电商 (ecommerce) — 3 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `ecommerce_ops` | 电商运营 | E-commerce Operations Specialist | 🛒 |
| `product_sourcer` | 选品专家 | Product Sourcing Expert | 📦 |
| `livestream_planner` | 直播策划 | Livestream E-commerce Planner | 🎥 |

#### 游戏 (game) — 3 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `game_designer` | 游戏设计师 | Game Designer | 🎮 |
| `game_developer` | 游戏开发 | Game Developer | 💻 |
| `game_writer` | 游戏剧情 | Game Narrative Designer | 📖 |

#### 旅游 (travel) — 2 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `travel_planner` | 旅行规划师 | Travel Planner | ✈️ |
| `travel_copywriter` | 旅游文案 | Travel Copywriter | 🏝 |

#### 美食 (food) — 2 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `recipe_developer` | 菜谱开发 | Recipe Developer | 🍳 |
| `food_critic` | 美食评论 | Food Critic | 🍽 |

#### 体育 (sports) — 2 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `fitness_coach` | 运动教练 | Fitness Coach | 💪 |
| `sports_analyst` | 体育分析 | Sports Analyst | 📈 |

#### 农业 (agriculture) — 2 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `agri_tech` | 农业技术 | Agricultural Technology Expert | 🌾 |
| `horticulturist` | 园艺师 | Horticulturist | 🌱 |

#### 能源 (energy) — 2 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `renewable_energy` | 新能源 | Renewable Energy Expert | ⚡ |
| `power_engineer` | 电力系统 | Power Systems Engineer | 🔌 |

#### 航空 (aerospace) — 2 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `aero_engineer` | 航空工程 | Aerospace Engineer | 🚀 |
| `drone_expert` | 无人机 | Drone Expert | 🛩 |

#### 环保 (environment) — 2 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `env_engineer` | 环境工程 | Environmental Engineer | 🌱 |
| `carbon_expert` | 碳中和 | Carbon Management Expert | 🌍 |

#### 社交 (social) — 2 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `social_media_manager` | 社交媒体 | Social Media Manager | 💬 |
| `community_manager` | 社群运营 | Community Manager | 👥 |

#### 心理 (psychology) — 1 位

| ID | 名称 | 角色 | 头像 |
|----|------|------|------|
| `career_coach_2` | 职业规划 | Career Coach | 🧠 |

---

## 3. 创建示例

下面给出 3 个完整的 Agent 创建示例，分别以 Python 代码和 JSON 格式呈现。

### 示例 1：代码审查专家（QA 类）

**Python 代码：**

```python
from app.agents.registry import AgentDef

code_reviewer = AgentDef(
    id="qa_code_reviewer",
    name="代码审查专家",
    role="Code Reviewer",
    category="qa",
    avatar="🔍",
    color="#3b82f6",
    tagline="专治各种代码坏味道，让每一行代码都经得起推敲",
    goal="对提交的代码进行系统性审查，发现潜在 bug、安全漏洞、性能问题与可维护性隐患，并给出可执行的改进建议。",
    backstory=(
        "拥有 12 年软件工程经验的资深代码审查专家，曾在多家一线互联网公司担任技术专家与架构师。"
        "审查过超过 1000 万行代码，涵盖后端服务、前端应用、移动端与基础设施。"
        "擅长从命名规范、设计模式、并发安全、错误处理、性能瓶颈等多个维度评估代码质量，"
        "坚持「代码是写给人看的」理念，推动团队建立高质量的代码文化。"
    ),
    skills=[
        "代码静态分析",
        "设计模式识别",
        "并发安全审查",
        "性能瓶颈定位",
        "安全漏洞检测",
        "可维护性评估",
    ],
    allow_delegation=True,
)
```

**JSON 格式：**

```json
{
  "id": "qa_code_reviewer",
  "name": "代码审查专家",
  "role": "Code Reviewer",
  "category": "qa",
  "avatar": "🔍",
  "color": "#3b82f6",
  "tagline": "专治各种代码坏味道，让每一行代码都经得起推敲",
  "goal": "对提交的代码进行系统性审查，发现潜在 bug、安全漏洞、性能问题与可维护性隐患，并给出可执行的改进建议。",
  "backstory": "拥有 12 年软件工程经验的资深代码审查专家，曾在多家一线互联网公司担任技术专家与架构师。审查过超过 1000 万行代码，涵盖后端服务、前端应用、移动端与基础设施。擅长从命名规范、设计模式、并发安全、错误处理、性能瓶颈等多个维度评估代码质量，坚持「代码是写给人看的」理念，推动团队建立高质量的代码文化。",
  "skills": [
    "代码静态分析",
    "设计模式识别",
    "并发安全审查",
    "性能瓶颈定位",
    "安全漏洞检测",
    "可维护性评估"
  ],
  "allow_delegation": true
}
```

### 示例 2：UI 设计师（设计类）

**Python 代码：**

```python
from app.agents.registry import AgentDef

ui_designer = AgentDef(
    id="design_ui_designer",
    name="UI 设计师",
    role="UI Designer",
    category="design",
    avatar="🎨",
    color="#ec4899",
    tagline="用像素与色彩讲述产品故事",
    goal="根据产品需求与品牌调性，产出高保真界面设计、设计规范与可复用组件，确保视觉一致性用户体验。",
    backstory=(
        "拥有 10 年数字产品设计经验的 UI 设计师，服务过电商、金融、教育、SaaS 等多个行业。"
        "精通 Figma、Sketch、Principle 等设计工具，擅长从用户研究洞察推导视觉语言。"
        "主导过 30+ 款产品的从 0 到 1 设计，作品获红点、IF 设计奖。"
        "坚信好的设计是「看不见」的——用户感受不到设计本身，却能顺畅地完成任务。"
    ),
    skills=[
        "高保真界面设计",
        "设计系统构建",
        "品牌视觉推导",
        "交互原型制作",
        "可用性评估",
        "响应式布局",
    ],
    allow_delegation=False,
)
```

**JSON 格式：**

```json
{
  "id": "design_ui_designer",
  "name": "UI 设计师",
  "role": "UI Designer",
  "category": "design",
  "avatar": "🎨",
  "color": "#ec4899",
  "tagline": "用像素与色彩讲述产品故事",
  "goal": "根据产品需求与品牌调性，产出高保真界面设计、设计规范与可复用组件，确保视觉一致性用户体验。",
  "backstory": "拥有 10 年数字产品设计经验的 UI 设计师，服务过电商、金融、教育、SaaS 等多个行业。精通 Figma、Sketch、Principle 等设计工具，擅长从用户研究洞察推导视觉语言。主导过 30+ 款产品的从 0 到 1 设计，作品获红点、IF 设计奖。坚信好的设计是「看不见」的——用户感受不到设计本身，却能顺畅地完成任务。",
  "skills": [
    "高保真界面设计",
    "设计系统构建",
    "品牌视觉推导",
    "交互原型制作",
    "可用性评估",
    "响应式布局"
  ],
  "allow_delegation": false
}
```

### 示例 3：财务分析师（金融类）

**Python 代码：**

```python
from app.agents.registry import AgentDef

financial_analyst = AgentDef(
    id="finance_analyst",
    name="财务分析师",
    role="Financial Analyst",
    category="finance",
    avatar="📊",
    color="#10b981",
    tagline="用数字看透商业本质",
    goal="基于财务报表与业务数据，完成财务建模、估值分析、风险评估与投资建议，支撑商业决策。",
    backstory=(
        "拥有 14 年金融行业经验的特许金融分析师 (CFA)，曾就职于顶级投行与私募基金。"
        "精通 DCF、可比公司、可比交易等多种估值方法，擅长搭建复杂财务模型。"
        "覆盖过科技、消费、医疗、新能源等多个赛道，主导过 50+ 个投资项目的财务尽调。"
        "信奉「数字不会说谎，但需要正确解读」，致力于把复杂的财务逻辑讲给非财务人听懂。"
    ),
    skills=[
        "财务报表分析",
        "DCF 估值建模",
        "可比公司分析",
        "风险评估",
        "投资尽调",
        "行业研究",
    ],
    allow_delegation=True,
)
```

**JSON 格式：**

```json
{
  "id": "finance_analyst",
  "name": "财务分析师",
  "role": "Financial Analyst",
  "category": "finance",
  "avatar": "📊",
  "color": "#10b981",
  "tagline": "用数字看透商业本质",
  "goal": "基于财务报表与业务数据，完成财务建模、估值分析、风险评估与投资建议，支撑商业决策。",
  "backstory": "拥有 14 年金融行业经验的特许金融分析师 (CFA)，曾就职于顶级投行与私募基金。精通 DCF、可比公司、可比交易等多种估值方法，擅长搭建复杂财务模型。覆盖过科技、消费、医疗、新能源等多个赛道，主导过 50+ 个投资项目的财务尽调。信奉「数字不会说谎，但需要正确解读」，致力于把复杂的财务逻辑讲给非财务人听懂。",
  "skills": [
    "财务报表分析",
    "DCF 估值建模",
    "可比公司分析",
    "风险评估",
    "投资尽调",
    "行业研究"
  ],
  "allow_delegation": true
}
```

---

## 4. 通过界面提交

1. 打开前端应用，进入 **`/tutorial`** 页面（教程 / 提交页面）。
2. 在「提交新 Agent」表单中依次填写：
   - Agent ID（英文下划线）
   - 显示名（中文）
   - 职业角色（英文）
   - 分类（从下拉框选择）
   - 头像（emoji）
   - 主题色（hex 色值，或使用取色器）
   - 一句话描述
   - 目标
   - 背景故事
   - 技能（每行一个，或逗号分隔）
3. 点击「预览」可即时查看 Agent 卡片效果。
4. 点击「提交」将 Agent 发送到审核队列。

> 提交前请先注册并登录，提交记录会关联到你的账号。

---

## 5. 通过 API 提交

通过 HTTP 接口提交 Agent，适合脚本化批量提交或集成到其他工具。

### 请求

```bash
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my_agent",
    "agent_name": "我的助手",
    "agent_role": "Personal Assistant",
    "agent_avatar": "🌟",
    "agent_color": "#ec4899",
    "agent_category": "creative",
    "agent_tagline": "你的贴心小助手",
    "agent_goal": "协助用户完成日常任务规划、信息整理与决策支持，提升工作与生活效率。",
    "agent_backstory": "拥有 8 年个人助理与知识管理经验的虚拟助手，擅长任务拆解、日程规划与信息检索。",
    "agent_skills": ["任务规划", "信息检索", "日程管理", "决策支持"]
  }'
```

### 获取 token

如果还没有账号，先注册并登录获取 JWT token：

```bash
# 注册
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "your_name", "password": "your_password"}'

# 登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "your_name", "password": "your_password"}'
# 返回的 JSON 中包含 access_token，填入上方 <token> 处
```

### 字段映射

API 请求体字段与 `AgentDef` 字段的对应关系：

| 请求字段 | AgentDef 字段 |
|----------|---------------|
| `agent_id` | `id` |
| `agent_name` | `name` |
| `agent_role` | `role` |
| `agent_avatar` | `avatar` |
| `agent_color` | `color` |
| `agent_category` | `category` |
| `agent_tagline` | `tagline` |
| `agent_goal` | `goal` |
| `agent_backstory` | `backstory` |
| `agent_skills` | `skills` |

### 响应

提交成功后返回：

```json
{
  "success": true,
  "data": {
    "submission_id": "sub_xxxxxxxx",
    "status": "pending"
  }
}
```

---

## 6. 审核流程

提交的 Agent 会进入审核队列，完整流程如下：

```
用户提交 Agent
      │
      ▼
  进入审核队列 (status: pending)
      │
      ▼
  管理员审核 ──────┬────── 通过 ──────▶ 加入 Agent 库 (status: approved)
                   │                       │
                   │                       ▼
                   │                 上线到 /experts 页面
                   │                 用户可在团队组建中使用
                   │
                   └────── 驳回 ──────▶ 标记问题 (status: rejected)
                                           │
                                           ▼
                                     反馈给提交者修改后重新提交
```

### 审核标准

管理员会从以下维度评估提交的 Agent：

- **完整性**：所有必填字段是否填写，背景故事是否达到 8-15 年经验的描述深度。
- **专业性**：目标与技能是否清晰、专业，是否与所选分类匹配。
- **独特性**：是否与现有 Agent 高度重复。
- **合规性**：内容是否合法合规，不包含敏感、违规或侵权信息。

### 查看审核状态

提交者可在 `/tutorial` 页面或通过 API 查看自己提交的 Agent 的审核状态：

```bash
curl http://localhost:8000/api/v1/submissions \
  -H "Authorization: Bearer <token>"
```

审核通过后，该 Agent 将出现在专家库 (`/experts`) 中，所有用户都可以在团队组建时选用它。
