# Design System: Inspire (Enterprise Tech)

这是通过 UI UX Pro Max 引擎并结合 Inspire 核心品牌资产 (`pptstyle.json`) 生成的全局 UI 设计系统 (Source of Truth)。

## Pattern (布局与架构模式)
- **Name:** Enterprise Gateway
- **Conversion Focus:** Path selection (我是.../按行业/按角色). 强调可信赖程度与大型企业调性。
- **CTA Placement:** Contact Sales (Primary 位于 Header 右侧及底部) + 申请演示 / 登录 (Secondary)
- **Sections (标准落地页参考结构):** 
  1. Hero (核心理念 + 视频背景或品牌插画)
  2. Solutions by Industry (按行业划分的解决方案卡片)
  3. Core Capabilities (核心业务能力图谱)
  4. Client Logos (信任背书，配合横向滚动)
  5. Contact Sales (尾部转化区)

## Style (视觉设计风格)
- **Name:** Trust & Authority / Modern Enterprise
- **Mode Support:** 面向企业端，以白昼模式 (Light) 为主，局部深色背景 (搭配 Starry Blues 深蓝进行色块反转)
- **Keywords:** 现代扁平、结构化卡片、微弱投影(增加层级)、硬朗与柔和结合(大圆角配合锐利信息)、行业资质露出
- **Best For:** B2B SaaS, 企服平台, Tech Business Landing Pages
- **Performance:** ⚡ Excellent | **Accessibility:** ✓ WCAG AA 达标

## Colors (品牌独占色彩系统)

配色严格遵循 Inspire `pptstyle.json` 定义的品牌标量。

| Role | Hex | Name | CSS Variable | Usage |
|------|-----|------|--------------|-------|
| **Primary** | `#10213E` | Starry Blues | `--color-primary` | 主品牌色，用于章节背景、关键标题、大面积品牌色快 |
| **Accent/CTA** | `#5DB2E2` | Creative Blue | `--color-accent` | 侧重标识、跳转链接、按钮强化、图表高亮 (用量 5-10%) |
| **Secondary** | `#625D9C` | Amethyst | `--color-secondary` | 辅助信息、图表辅助色、创新标签 |
| **Success** | `#00524C` | Myrtle Deep Green | `--color-success` | 成功状态、正向数据增加、环保/合规状态 |
| **Info / Sub**| `#6FB1C8` | Cerulean Frost | `--color-info` | 浅蓝辅助色，用作轻量背景或次要图表色 |
| **Warning** | `#F59E0B` | Warning | `--color-warning` | 风险提示、关注状态 |
| **Destructive**| `#EF4444` | Danger | `--color-destructive` | 删除操作、阻断性错误提示 |
| **Background** | `#FFFFFF` | Pure White | `--color-background` | 工作区主背景、卡片容器底色 |
| **Background Alt**| `#F5F5F6` | Tech Gray | `--color-bg-alt` | 底层柔和过渡背景色，或用于区分不同模块区间 |
| **Foreground / Text** | `#10213E` | Primary Text | `--color-foreground` | 替代纯黑带来更温暖的科技感文本主色 |
| **Muted Text** | `#64748B` | Text Secondary| `--color-text-muted`| 次要说明、日期、辅助类图例文案 |
| **Border** | `#E2E8F0` | Border/Line | `--color-border` | 卡片描边、分割线、表格网格 |

*Brand Logic: 纯净大方，深渊蓝做底，创想蓝点睛。摒弃绝对纯黑。*

## Gradients (渐变与遮罩)
- **Section Background (`135deg`):** `#1B2B47` (0%) -> `#4A9FD8` (100%) - 用于封面和醒目章节背景。
- **Dark Overlay (to bottom):** `rgba(27, 43, 71, 0.8)` -> `rgba(27, 43, 71, 0.4)` - 用于大图片上方叠加，保证白色文字（如封面题解）高对比度。

## Typography (企业规范字体)

- **字体家族:** **MiSans** (优先), 备用字体 `Microsoft YaHei`, `Inter`, `Arial`
- **Mood:** enterprise, professional, clear, geometric, legible

**版式层级系统 (Hierarchy):**
- **Cover Title (英雄区大字):** 48pt, SemiBold (`#FFFFFF`), `line-height: 1.2`, 字间距 `-0.02em`
- **H1 (一级标题):** 28pt, SemiBold (`#10213E`), 底部间距 `24pt`
- **H2 (二级标题):** 22pt, Medium (`#10213E`), 底部间距 `16pt`
- **H3 (三级标题 / 卡片头):** 18pt, Medium (`#1B2B47`), 底部间距 `12pt`
- **Body (正文):** 12pt (移动端基础 16px), Regular (`#10213E`), `line-height: 1.5`, 容器最宽控制 `max-width: 80%` (针对宽屏阅读)
- **Label / Accent (标签与强调词):** 11pt, SemiBold (`#4A9FD8`), 全大写 `uppercase`, 字间距加宽 `0.05em`
- **Caption (注释及小字):** 12pt, Light (`#64748B`), 斜体 `Italic`

## Key Effects (动效与交互质感)
- **微互动:** 卡片采用轻微上浮（Transform translateY）及柔和拉长阴影扩散以响应 Hover。
- **信任透出:** 数据指标（Metrics）优先采用数字滚动 Reveal 动效；证书、Logo 采用无缝循环水平轮播。

## Avoid (Anti-patterns / 品牌禁区)
- ❌ 不要过度追求年轻化/娱乐化的强弹簧感 (Spring bounce) 动效。
- ❌ 绝对禁止使用 AI 紫色/粉色高饱和赛博朋克渐变，破坏信任感。
- ❌ 禁止混搭阴影：投影必须使用系统内收敛的、带蓝色相 (`rgba(16, 33, 62, 0.08)`) 的阴影，不使用粗糙的黑/灰阴影。
- ❌ 不要出现低对比度正文（浅灰叠白），`#10213E` 具备极好的阅读锐度。

## Pre-Delivery Checklist
- [ ] 所有 LOGO 图标挂载 `assets/logo.png` (深色文字版) / `assets/logo white.png` (白昼版)
- [ ] 禁止使用 Emoji 充当严肃按钮/导航图标 (均需使用线条或实体 SVG icon)
- [ ] 确保 `cursor-pointer` 添加到所有可点击交互区域
- [ ] 所有交互状态 (hover/focus/active) 保证平滑过渡 (150-250ms ease-out)
- [ ] Form / Input focus 轮廓保持明显的 Inspire Blue `#5DB2E2`
- [ ] 键盘导航（Tab）的 Focus ring 清晰可见
- [ ] 响应式折点匹配 (375px / 768px / 1024px / 1440px)
