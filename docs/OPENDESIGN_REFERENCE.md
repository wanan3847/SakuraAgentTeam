# OpenDesign 风格前端参考手册

> 用途：当你准备用 [opendesign](https://github.com/yourname/opendesign) 这类「高密度信息 + 暖纸感 + 实时数据」的参考项目对 SakuraAgentTeam 前端做整体重设计时,这一份就是你的设计 intent + 实现 contract。
>
> 写这份文档的目的,不是"复制 opendesign",而是把"它在视觉上做对了什么"翻译成**可执行的 Tailwind token + 组件契约**,让你后续无论用 Vite + React、还是 Next.js、Astro 都能直接落地。

---

## 0. 核心一句话

> **"像一份昂贵的设计杂志排版的实时 dashboard —— 衬线大标题 + 等宽元数据 + 暖纸感背景 + 极少色相,所有数字都从 0 滚动到位。"**

SakuraAgentTeam 当前的 🌸 暖纸感风是 **V0 / Soft Mood**(轻、柔、樱花粉),opendesign 那一类是 **V1 / Editorial Dashboard**(理性、信息密度、克制的暖色),两者并不冲突 —— 真正的"高级感"恰恰是 **在不同的产品语境里都成立**。这份文档就是 V1 的 spec。

---

## 1. 五大反 AI-Slop 原则(必读)

这五条来自 opendesign / Linear / Vercel / Stripe Dashboard / FT.com 的共同点,**违反任意一条,出来的就是 AI 味**。

### 1.1 配色只用 60-30-10
- **60% 背景**:暖白/米色/深墨,**纯色 + 极轻纹理**,禁止纯白 `#FFFFFF`、禁止渐变。
- **30% 表面**:比背景再深/浅一档的卡片/容器色,提供"层级"。
- **10% 强调**:单一色相,只用在一个地方 —— 数字、链接、强调线、悬停态。

```css
/* 示例:Sakura 杂志版 */
--bg          : #F5F1E8;   /* 60% 米色纸 */
--bg-elevated : #FFFFFF;   /* 30% 卡片 */
--ink         : #0E0E0C;   /* 主文字 */
--ink-faint   : #6B655C;   /* 副文字 */
--accent      : #00D26A;   /* 10% signal 绿 — 只给数字 + 链接 */
--rule        : #D6CFC0;   /* 1px 分隔线 */
```

### 1.2 字体最多 3 种,每种各司其职
| 角色 | 字体 | 出现位置 |
|------|------|---------|
| **Display**(标题) | Fraunces / Tiempos / GT Sectra | H1-H3、品牌名、引用 |
| **Body**(正文) | Geist / Inter / Söhne | 段落、按钮、卡片标题 |
| **Mono**(元数据) | JetBrains Mono / Berkeley Mono | 编号 `/01`、数字 `12,510`、状态 `LIVE`、`thinking…`、代码 |

> **关键反 AI 习惯**:`/01`、`LIVEBETA`、`2.4%` 之类的小标识,不要用 sans-serif 圆体,而是**用等宽字体 + 略带 tracking-widest**,立刻就有"产品杂志"的味道。

### 1.3 数字是会动的
所有指标数字 **从 0 滚动到目标值**,用 `requestAnimationFrame + easeOutQuart`,1800ms。
**当且仅当元素进入视口**才触发(IntersectionObserver,threshold 0.3)。
数字必须 **千分位分隔**,但**不带 `+` 号**(增量写在旁边的小徽章里)。

```ts
// 推荐直接复用 frontend/src/components/CountUp.tsx
const easeOutQuart = (t: number) => 1 - Math.pow(1 - t, 4)
```

### 1.4 留白靠 8px 栅格,不做卡片堆
- 所有 padding / margin 都是 `4 / 8 / 12 / 16 / 24 / 32 / 48` 的整数倍。
- 卡片 **不是 UI 主体**,而是"分隔信息的手段" —— 一张长列表页里,卡片只用在**确实需要分组**的地方,其余用 1px 细线 + 留白分隔。
- 圆角 `6-10px`(`rounded-md` 到 `rounded-xl`),**禁止 `rounded-2xl / 3xl / full`**(那是 AI 模板味)。

### 1.5 永远不要"渐变 + 模糊 + 大圆角"三件套
`backdrop-blur` / `blur-3xl` / `bg-gradient-to-*` / `rounded-full` 出现在同一个元素上,99% 是 AI 模板生成。
**opendesign 风格里,这三件套出现次数 = 0**。

---

## 2. 色彩系统(Tailwind Token)

```ts
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        // 60% — 纸面
        paper: {
          DEFAULT: '#F5F1E8',   // 米色纸
          soft:    '#FAF7F0',   // 纸面高光
          warm:    '#EFE9DC',   // 纸面阴影
        },
        // 30% — 卡片 / 表面
        card: {
          DEFAULT: '#FFFFFF',
          subtle:  '#FBF8F1',
          ink:     '#1A1A18',   // 反色卡片(深墨)
        },
        // 10% — 强调
        accent: {
          DEFAULT: '#00D26A',   // signal 绿
          warm:    '#C97B8A',   // sakura(次要强调)
          amber:   '#C4955E',   // 数字 / 金额
        },
        // 文字
        ink: {
          DEFAULT: '#0E0E0C',   // 主文字
          soft:    '#3A3A36',   // 副文字
          faint:   '#6B655C',   // 提示
          muted:   '#A39E91',   // 禁用
        },
        // 1px 边线
        rule:     '#D6CFC0',
        'rule-strong': '#0E0E0C',
      },
      fontFamily: {
        display: ['Fraunces', 'ui-serif', 'Georgia', 'serif'],
        sans:    ['Geist',     'Inter', 'system-ui', 'sans-serif'],
        mono:    ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      letterSpacing: {
        tightest: '-0.04em',   // 衬线大标题
        widest:   '0.12em',    // mono 小标识
      },
    },
  },
}
```

> **OKLCh 备选**(若你升级到 Tailwind v4 / native CSS):
> 60% 纸 `oklch(96% 0.02 80)` / 30% 卡 `oklch(99% 0.01 80)` / 10% 强 `oklch(74% 0.18 145)`。
> 优势是亮色 / 暗色自动换算,缺点是很多老浏览器不支持,需要 fallback。

---

## 3. 字体加载与回退(关键)

```html
<!-- index.html — 一定要 preload + display=swap -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  rel="stylesheet"
  href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;1,9..144,400&family=Geist:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"
/>
```

**坑点预警**:
- `Fraunces` 是可变字体,**必须**用 `ital,opsz,wght@...` 三轴都声明,否则 italic 模式会回退成方块。
- "say" 这种字要斜体(opendesign 的标志动作),用 `<em class="italic font-display">say</em>` 而不是 unicode `𝑠𝑎𝑦`。
- `Geist` 在中文环境请叠 `PingFang SC` / `Noto Sans SC`,否则汉字字重不对。

---

## 4. 8 个核心组件契约

### 4.1 `<MetricCard />` —— 实时指标卡(整个产品的灵魂)

```tsx
interface MetricCardProps {
  label: string                // '累计完成任务'
  value: number                // 12510(直接传数字,内部 CountUp)
  delta?: number               // 2.4 → 显示 +2.4%(绿色徽章)
  suffix?: string              // '%' / '次' / '小时'(不带在数字里)
  sub?: string                 // 副标题 '本季度'
  icon?: LucideIcon            // 仅一个 16px 描边图标
  accent?: string              // 1px 左侧色线,默认 ink
  live?: boolean               // 显示绿色呼吸点
}

<MetricCard
  label="累计完成任务"
  value={12510}
  delta={2.4}
  suffix="次"
  sub="本季度"
  icon={TrendingUp}
  accent="#C97B8A"
/>
```

**结构**(从外到内):
1. 1px 左边强调线(`border-l`,3px 宽,颜色用 `accent`)
2. 顶部:`label` 12px mono + tracking-widest,墨色
3. 中部:`value` 48px display 衬线 + delta 徽章(sage 绿底)
4. 底部:`sub` 12px ink-faint
5. `live` 模式:右上角呼吸点(2s 周期,scale 1→1.4→1,opacity 0.6→1→0.6)

**反 AI 关键**:
- ❌ 不要 `bg-gradient-to-br` 背景
- ❌ 不要 `shadow-2xl`
- ❌ 不要 `rounded-3xl`
- ✅ 卡片是 `bg-white border border-rule rounded-md`,**没有阴影**
- ✅ hover 只改 `border-rule-strong` 这一条

### 4.2 `<NumberedSection />` —— 章节标号(品牌记忆点)

```tsx
<header className="mb-12">
  <div className="font-mono text-xs text-ink-faint tracking-widest mb-2">
    / 01 — Hero
  </div>
  <h1 className="font-display text-6xl text-ink leading-[0.95]">
    Build agents that <em class="italic">say</em> things.
  </h1>
</header>
```

**反 AI 关键**:
- 章节标题用 `/01`、`/02` 这种短横线 + 编号,而**不是** `Section 01`、`Chapter 1`。
- 中文环境用 `/01 — ` 或 `/壹、` 都可以,统一就好。

### 4.3 `<DataRow />` —— 表格行(列表页主力)

**不要用 `<table>`,用 `div + grid`** —— 表格在响应式下必崩。

```tsx
<div className="grid grid-cols-[1fr_120px_80px_40px] items-center
                py-3 px-4 border-b border-rule hover:bg-paper-soft
                transition-colors cursor-pointer">
  <div>
    <div className="text-sm text-ink">{name}</div>
    <div className="text-xs text-ink-faint">{desc}</div>
  </div>
  <div className="font-mono text-xs text-ink-soft">12.4K tokens</div>
  <div className="font-mono text-xs text-accent">+2.4%</div>
  <ChevronRight className="w-4 h-4 text-ink-muted" />
</div>
```

**反 AI 关键**:
- 没有"卡片化"的行,行间距靠 padding,边框靠 1px 横线
- hover 是 `bg-paper-soft`(几乎看不出来的浅色),**不是阴影**

### 4.4 `<Tab />` —— 选项卡(顶部分类)

```tsx
<div className="flex gap-1 border-b border-rule">
  {tabs.map(t => (
    <button className={cx(
      'px-4 py-2 text-sm border-b-2 -mb-px transition-colors',
      active === t.id
        ? 'border-ink text-ink'      // 选中:墨色下划线 + 墨色字
        : 'border-transparent text-ink-faint hover:text-ink'
    )}>
      {t.label}
    </button>
  ))}
</div>
```

**反 AI 关键**:
- 不要圆角药丸状 `rounded-full`
- 不要渐变背景
- 用 **2px 下划线 + -mb-px 顶到 border 上** 这种"老派"做法

### 4.5 `<CodeChip />` —— 代码片段标签(品牌符号)

```tsx
<span className="font-mono text-xs px-1.5 py-0.5
                 bg-paper-warm border border-rule rounded
                 text-ink-soft">
  sakura chat
</span>
```

`paper-warm` 是比 `paper-soft` 再深一档的米色 —— 用来装代码标识,让眼睛立刻定位。

### 4.6 `<StatusDot />` —— 状态点(实时信号)

```tsx
<span className="relative inline-flex">
  <span className="w-2 h-2 rounded-full bg-accent" />
  {live && (
    <span className="absolute inset-0 w-2 h-2 rounded-full
                     bg-accent animate-ping opacity-75" />
  )}
</span>
```

放在数字、状态、计数器旁边,2-3 个一组就有 opendesign 那种"服务器还活着"的实感。

### 4.7 `<BigStat />` —— 巨型数字(首屏 Hero)

```tsx
<div className="font-display text-[120px] leading-none text-ink
                tracking-tightest tabular-nums">
  {formatNum(12510)}
</div>
```

**关键**:`tabular-nums` —— 数字等宽,CountUp 滚动时**不会左右抖动**。
**关键**:`tracking-tightest`(-0.04em) —— 大数字字间距收紧,像杂志封面。

### 4.8 `<Hero />` —— 首屏(opendesign 的招牌)

```tsx
<section className="max-w-[1400px] mx-auto px-12 pt-24 pb-32">
  <div className="grid grid-cols-12 gap-8">
    {/* 左 7 列 — 文案 */}
    <div className="col-span-7">
      <NumberedSection num="01" title="Hero" />
      <h1 className="font-display text-7xl leading-[0.95] text-ink mt-8">
        Build agents that <em>say</em> things,<br />
        not agents that <em>render</em> things.
      </h1>
      <p className="text-lg text-ink-soft mt-8 max-w-xl leading-relaxed">
        SakuraAgentTeam is a 100-agent platform...
      </p>
      <div className="flex gap-3 mt-12">
        <button className="px-5 py-3 bg-ink text-paper text-sm">
          开始使用 →
        </button>
        <button className="px-5 py-3 border border-ink text-ink text-sm">
          查看 GitHub
        </button>
      </div>
    </div>
    {/* 右 5 列 — 实时指标卡堆 */}
    <div className="col-span-5 space-y-3">
      <BigStat label="活跃智能体" value={5} sub="持续运行中" live />
      <BigStat label="累计任务" value={12510} sub="本季度" delta={2.4} />
      <BigStat label="节省工时" value={38540} suffix="小时" sub="vs 人工" delta={18} />
    </div>
  </div>
</section>
```

**反 AI 关键**:
- ❌ 不要居中堆叠 + 大背景图 + 模糊圆
- ✅ 12 栅格不对称布局,左 7 右 5,文字左对齐
- ✅ 按钮是 **方角墨底**(`bg-ink text-paper`),**没有圆角没有渐变**
- ✅ 标题用 `font-display`,`leading-[0.95]` 紧凑
- ✅ "say" 用 italic(opendesign 的招牌动作)

---

## 5. 关键页面 mockup

### 5.1 HomePage

```
┌──────────────────────────────────────────────────────────┐
│  [Sakura]      产品   文档   价格          登录  开始使用 → │
├──────────────────────────────────────────────────────────┤
│  /01 — Hero                                              │
│                                                          │
│  Build agents that say things,             ┌──────────┐  │
│  not agents that render things.            │ ● 5  活跃 │  │
│                                            ├──────────┤  │
│  SakuraAgentTeam 是一个 100-agent 平台…    │ 12,510 +2.4%│
│                                            ├──────────┤  │
│  [开始使用 →]  [查看 GitHub]                │ 38,540 +18% │
│                                            └──────────┘  │
├──────────────────────────────────────────────────────────┤
│  /02 — 100% 免费                                         │
│  ··· 四列特性 ···                                        │
├──────────────────────────────────────────────────────────┤
│  /03 — Squad                                             │
│  9 个预设团队 + 100 个专家的横滑列表                      │
├──────────────────────────────────────────────────────────┤
│  /04 — 12 套剧本                                         │
│  研究 / 设计 / 工程 / 写作 4 列卡片                       │
├──────────────────────────────────────────────────────────┤
│  /05 — Live Metrics  ← CountUp + 增量徽章                │
│  [5 卡] 12510 / 5 / 38540 / 100+ / 254+                   │
├──────────────────────────────────────────────────────────┤
│  /06 — Why Zhihui                                        │
│  对比表(我们 vs ChatGPT vs CrewAI vs AG2)                │
├──────────────────────────────────────────────────────────┤
│  /07 — Agent Library                                     │
│  30 分类 / 100 智能体的 DataRow 列表                      │
├──────────────────────────────────────────────────────────┤
│  [footer] 友站 GitHub · Discord · Docs · Blog            │
└──────────────────────────────────────────────────────────┘
```

### 5.2 ProvidersPage

```
┌──────────────────────────────────────────────────────────┐
│  / LLM Providers                                         │
│                                                          │
│  上手 3 步:                                              │
│  [01 选厂商] → [02 填 Key] → [03 用起来]                │
│                                                          │
│  🔍 搜索 254 个供应商...                                 │
│  [全部] [OpenAI] [Anthropic] [DeepSeek] [国产] [开源]   │
│                                                          │
│  ┌─ OpenAI ────────────────────────────────────── → ┐  │
│  │ 美国 · 旗舰模型 · 自带 Function Calling   [点击配置]│  │
│  ├─ Anthropic ──────────────────────────────────── → ┤  │
│  │ 美国 · Claude 3.5 · 长上下文            [点击配置]│  │
│  ├─ DeepSeek ────────────────────────────────────── → ┤  │
│  │ 中国 · 国产之光 · 价格屠夫               [点击配置]│  │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

**结构要点**:
- 顶部分类用 `<Tab />`(2px 下划线),**不是药丸**
- 搜索框是单行 input + 1px 边框,**没有圆角没有图标按钮**
- 供应商用 `<DataRow />`,**没有图标**(这是 opendesign 的硬要求 —— "字比图更高级")

### 5.3 WorkspacePage(chat)

```
┌──────────────────────────────────────────────────────────┐
│  ← back  [Dev Mode] [Squad: 3 agents] [12,510] [Export]  │
├─────────────────┬────────────────────────────────────────┤
│ [research] 5    │  ┌─ user ────────────────────────────┐ │
│ [design]   3    │  │ 帮我做一份 LLM provider 调研       │ │
│ [dev]      4    │  └────────────────────────────────────┘ │
│ [+ 新建]        │                                        │
│                 │  ┌─ research(2.3s) ───────────────┐    │
│                 │  │  找到 254 个供应商,推荐 5 个... │    │
│                 │  └─────────────────────────────────┘    │
│                 │  ┌─ design(4.1s) ─────────────────┐    │
│                 │  │  [thinking…]                    │    │
│                 │  └─────────────────────────────────┘    │
│                 │                                        │
│                 │  ┌──────────────────────────────[Send]┐ │
│                 │  │ 输入消息…                       │    │
│                 │  └────────────────────────────────────┘ │
└─────────────────┴────────────────────────────────────────┘
```

**结构要点**:
- 左侧 240px 固定栏,1px 右边线
- 右侧聊天区,最大宽度 720px 居中
- 消息气泡:用户 `bg-ink text-paper`,智能体 `bg-white border border-rule`(无气泡形状,用 padding 区分)
- agent 消息上方一行 mono:`research(2.3s)` —— 时间永远显示

### 5.4 AgentLibraryPage(详情弹窗)

```
┌─ / Agent · Frontend Engineer ──────────────────  [×] ─┐
│                                                         │
│  FRONTEND                                              │
│  资深前端工程师 · 8 年经验 · 复刻 opendesign 这种事   │
│                                                         │
│  ─────────────────────────────────────────────────     │
│                                                         │
│  / 借鉴成熟框架                                         │
│  - Anthropic Prompt Caching   (省 50% token)            │
│  - OpenAI Swarm               (轻量编排)                │
│  - AG2 GroupChat              (动态角色)                │
│  - MetaGPT                    (SOP 化)                  │
│  - CrewAI                     (角色 + 任务)             │
│  - LangGraph                  (状态机)                  │
│                                                         │
│  / 工具集                                               │
│  [file_edit] [shell] [grep] [glob] [web_search]         │
│                                                         │
│  [添加到团队]    [查看 YAML]                             │
└─────────────────────────────────────────────────────────┘
```

**反 AI 关键**:
- 右上角关闭是 `×`(U+00D7)或 lucide `<X />`,**不是** emoji `❌`
- 弹窗是 `rounded-md`(不是 `rounded-2xl`)
- 没有背景模糊

---

## 6. 动画契约

### 6.1 CountUp(必须)

```ts
const easeOutQuart = (t: number) => 1 - Math.pow(1 - t, 4)

useEffect(() => {
  const obs = new IntersectionObserver(([e]) => {
    if (e.isIntersecting) {
      const start = performance.now()
      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / 1800)
        const v = Math.floor(start + (end - start) * easeOutQuart(t))
        setValue(v)
        if (t < 1) requestAnimationFrame(tick)
      }
      requestAnimationFrame(tick)
      obs.disconnect()
    }
  }, { threshold: 0.3 })
  if (ref.current) obs.observe(ref.current)
  return () => obs.disconnect()
}, [end])
```

### 6.2 数字进场(可选)

```css
@keyframes slideUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.tabular-nums { font-variant-numeric: tabular-nums; }
```

### 6.3 Hover(温柔)

- 过渡时间 **200ms**(`transition-colors duration-200`)
- 只改 `border` 颜色或 `bg` 颜色,**不**改 `transform / shadow / scale`

### 6.4 樱花(可选,慎用)

SakuraAgentTeam 本身有樱花飘落,但 opendesign 风格里**强烈建议去掉** —— 这是一个非常强的"Sakura 品牌信号",会破坏 Editorial Dashboard 的克制感。
如果一定要保留,**只用纯 CSS 圆点**(直径 4-8px,4 种暖色,`filter: blur(0.3px)`),禁止 emoji 字符(Windows 字体回退会黑块)。

---

## 7. 暗色模式(opendesign 是亮色派,暗色谨慎)

opendesign 自己**不做暗色**,但 Vercel / Linear 都有。
**做法**:
- 暗色背景 `oklch(15% 0.01 80)`(暖墨,不是纯黑)
- 暗色卡片 `oklch(20% 0.01 80)`
- 主文字 `oklch(95% 0.01 80)`(暖白,不是纯白)
- 强调色保留 signal 绿(对比度足够)

**禁用**:`#000` / `#FFF` —— 在暗色模式里也用 OKLCh 暖色阶。

---

## 8. 与现有 🌸 高级感的关系

| 维度 | 🌸 高级感(V0) | OpenDesign 风格(V1,本文) |
|------|---------------|---------------------------|
| 配色 | 暖纸白 + 樱花粉 + sage | 暖纸米 + signal 绿 + 墨黑 |
| 字体 | Fraunces + Noto Sans SC + JetBrains Mono | Fraunces + Geist + JetBrains Mono |
| 适用场景 | 品牌 / 营销 / 个人作品 | Dashboard / 数据 / 后台 |
| 圆角 | rounded-xl | rounded-md(更克制) |
| 阴影 | 几乎无 | 完全无 |
| 渐变 | 极少 | 完全没有 |
| 数字 | 静态 | CountUp 滚动 |
| 反 AI | ✅ | ✅✅✅ |

**建议**:V0 用于 HomePage / AuthPage / AccountPage(品牌向),V1 用于 WorkspacePage / ProvidersPage / HistoryPage(数据向)。**不要混**。

---

## 9. 落地清单(从这份文档到代码的步骤)

1. ✅ 把 `tailwind.config.ts` 里的 `paper / card / accent / ink / rule` 5 组 token 改成本文档 §2 的值
2. ✅ 把 `frontend/src/index.css` 的字体导入换成 §3 的 preload 链接
3. ✅ 抽出 `<MetricCard />` / `<NumberedSection />` / `<DataRow />` / `<Tab />` / `<CodeChip />` / `<StatusDot />` / `<BigStat />` 7 个组件
4. ✅ 重写 HomePage.Hero 用 §4.8 的 12 栅格不对称布局
5. ✅ 重写 ProvidersPage 用 `<DataRow />`(去图标)
6. ✅ 重写 AgentLibraryPage 详情弹窗,加 `/01` `/02` 编号章节
7. ✅ 所有指标数字套 CountUp(1800ms,IntersectionObserver 触发)
8. ✅ 删除所有 `backdrop-blur` / `blur-3xl` / `bg-gradient-to-*` / `rounded-full` / `rounded-3xl`
9. ✅ 全局搜索 `lucide-react` 的 `X` / `TrendingUp` / `Bot` / `Server` / `Sparkles` / `Users` 替代所有 emoji
10. ✅ Vite build 验证:`CSS < 30KB`,`JS < 350KB`

---

## 10. 一句话自检

> "如果把这个页面截图发给一位《Monocle》杂志的艺术总监,他会觉得这是出自他们排版工作室的设计,还是 AI 模板?"

**答案:是前者,就对了。**

---

## 附:参考资料

- [opendesign](https://github.com/yourname/opendesign) — 本文档的设计参考原型
- [Linear](https://linear.app) — `<DataRow />` 的灵感来源
- [Vercel Dashboard](https://vercel.com/dashboard) — 实时指标卡 + CountUp
- [FT.com](https://ft.com) — Editorial Dashboard 的字体策略
- [Stripe Atlas](https://stripe.com/atlas) — 配色 60-30-10 + 极少色相
- [Geist Font](https://vercel.com/font) — 未来感的无衬线
- [Fraunces](https://github.com/undercasetype/Fraunces) — 衬线大标题
- [JetBrains Mono](https://www.jetbrains.com/lp/mono/) — 等宽元数据
- [Stripe Sessions 2024](https://stripe.com/sessions) — 反 AI 排版范例

---

> 文档结束。开始重设计之前,**通读 §1 五原则 + §4.1 指标卡契约 + §6 动画契约**,这三节占 80% 的视觉决定。
