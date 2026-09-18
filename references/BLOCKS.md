# 积木库 —— 24 类区块的 HTML 签名

> 所有 class 都已写进 `assets/shell.html`，**直接复制骨架改文字即可，不需要额外加 CSS**。
> 骨架里的 `{{…}}` 是占位说明，不是模板语法 —— 手写时整段替换成真实内容。
> `esc()` 不存在：报告是手写 HTML，**不转义**。所以要写字面尖括号请用 `&lt;` `&gt;`。

## 目录

| # | 区块 | 主要用在 |
|---|---|---|
| [1](#1-结论摘要lead--维度表) | 结论摘要（lead + 维度表） | 首屏 |
| [2](#2-kgrid--kpi-指标卡) | `kgrid` KPI 指标卡 | 摘要 / 压力线 |
| [3](#3-chartgrid--图表) | `chartgrid` 图表 | 全篇 |
| [4](#4-tablewrap--数据表) | `tablewrap` 数据表 | 全篇 |
| [5](#5-stepper--生命周期步骤条) | `stepper` 生命周期步骤条 | 规模与生命周期 |
| [6](#6-tl--创意时间线) | `tl` 创意时间线 | 创意要素全解 |
| [7](#7-filterbar--fpanel-交互筛选) | `filterbar` 交互筛选 | 按 Hook / 媒体 / 语言下钻 |
| [8](#8-pmx--发行策略矩阵) | `pmx` 发行策略矩阵 | 发行商 / 竞品 |
| [9](#9-aud--三受众建议) | `aud` 三受众建议 | 策略建议 |
| [10](#10-mmtree--创意体系脑图) | `mmtree` 创意体系脑图 | 静态层级（旧版收口，仍可用） |
| [11](#11-fam--mgrid--mcard-素材画廊) | `fam` 素材画廊 | 全量素材 |
| [12](#12-gal--可仿拍大卡) | `gal` 可仿拍大卡 | 可借鉴素材 |
| [13](#13-detailsrev--逆向提示词) | `details.rev` 逆向提示词 | 可仿拍素材内 |
| [14](#14-detailssc--标准脚本卡) | `details.sc` 标准脚本卡 | 脚本拆解 |
| [15](#15-tplgrid--玩法模板库) | `tplgrid` 玩法模板库 | 可批量迭代模板 |
| [16](#16-hookrow--hook-缩略图行) | `hookrow` Hook 缩略图行 | 筛选面板内 |
| [17](#17-newsbtn--资讯按钮) | `newsbtn` 资讯按钮 | 资讯扫描表 |
| [18](#18-cardnote--提示条) | `cardnote` 提示条 | 全篇 |
| [19](#19-blockquote--三态引用) | `blockquote` 三态引用 | 全篇（收口句主力） |
| [20](#20-flow--线性承接图) | `flow` 线性承接图 | **迭代脑图前半**（阶段承接） |
| [21](#21-chip--chip2--标签) | `chip` / `chip2` 标签 | hero、卡片 |
| [22](#22-结论摘要表的列变体) | 结论摘要表的列变体 | 首屏 |
| [23](#23-图表函数速查) | 图表函数速查 | —— |
| [24](#24-raw--一次性区块) | `raw` 一次性区块 | 专项拆解 |
| [25](#25-mmk--markmap-交互脑图) | `mmk` Markmap 交互脑图 | 收口（可缩放/折叠） |

---

## 1. 结论摘要（`blockquote.lead` + 维度表）

**用途**：报告首屏。**一句话结论压在 `blockquote.lead` 上，下面一张维度表把结论拆开。**
**总-分-总结构里的第一个「总」。**

```html
<h2 id="sec-1">🧭 结论摘要</h2>
  <blockquote class="lead">{{一句话核心结论，关键词用 <strong> 加粗}}</blockquote>
  <div class="chips">
    <span class="chip">素材 {{n}} 条</span><span class="chip">广告 {{n}} 个</span><span class="chip">{{国数}} 国</span>
  </div>
  <div class="tablewrap">
    <table>
      <thead>
        <tr><th>维度</th><th>结论</th><th>关键数据</th></tr>
      </thead>
      <tbody>
        <tr><td>投放量级</td><td>{{一句话说清}}</td><td class="num">{{数字}}</td></tr>
        <tr><td>素材节奏</td><td>…</td><td class="num">…</td></tr>
        <tr><td>地区结构</td><td>…</td><td class="num">…</td></tr>
        <tr><td>媒体结构</td><td>…</td><td class="num">…</td></tr>
        <tr><td>创意方向</td><td>…</td><td class="num">…</td></tr>
      </tbody>
    </table>
  </div>
```

- `blockquote.lead` 是 `blockquote` 的高亮变体，**每份报告只在首屏用一条**
- 维度行**按本次报告真正有话说的地方定** —— 上面五行只是骨架，没结论的维度直接删
- 表 **≤7 行**：首屏读不完的表等于没写
- 关键数据列用 `.num`（金色加粗、等宽数字）；列怎么定见 [§22](#22-结论摘要表的列变体)
- 这一节含表，必须在同节内给 `blockquote` 结论 —— `blockquote.lead` 就是它，别删

---

## 2. `kgrid` KPI 指标卡

**用途**：一屏扫完的关键数字。也可当「三条压力线」这类并列论点用（此时 k-v 写词不写数）。

```html
<div class="kgrid">
    <div class="kpi"><div class="k-l">{{指标名}}</div><div class="k-v">{{值}}</div><div class="k-d">{{注释}}</div></div>
    <div class="kpi danger"><div class="k-l">{{指标名}}</div><div class="k-v">{{值}}</div><div class="k-d">{{注释}}</div></div>
    <div class="kpi good"><div class="k-l">{{指标名}}</div><div class="k-v">{{值}}</div><div class="k-d">{{注释}}</div></div>
  </div>
```

**注意**：`danger` = 红条，`good` = 青条，不加 = 主题渐变条。**4 个一屏最舒服**，超过会自动换行。
真实样例：COC `sec-anx`（4 个，2 红 2 默认）。

---

## 3. `chartgrid` 图表

**用途**：放 canvas 图。**副标题 `.cs` 写读图结论，不要写图例。**

```html
<div class="chartgrid">
    <div class="chartbox"><div class="ct">{{图标题}}</div><div class="cs">{{一句话读图结论}}</div><canvas id="cvXxx" height="300"></canvas></div>
    <div class="chartbox">…</div>
  </div>
```

`<div class="chartgrid single">` = 单栏铺满。`height` 建议：横向条形 260–330，折线 230，矩阵 300。

> 有 `.chartgrid.single`、`.chartbox`、`.ct`、`.cs`、`.chartbox canvas` 的样式。

**必须配合 §23 在 `CHART_DRAW` 里画出来**，否则是空白框。

---

## 4. `tablewrap` 数据表

```html
<div class="tablewrap"><table>
    <thead><tr><th>{{列名}}</th><th>{{列名}}</th></tr></thead>
    <tbody>
      <tr><td>{{行首（自动加粗）}}</td><td class="num">{{数字列用 num，金色等宽}}</td><td>{{说明}}</td></tr>
    </tbody>
  </table></div>
```

**行内可用的强调**：
- `class="num"` → 金色 + 数字对齐（**所有数字列都该加**）
- `<span class="lv lv-h">高</span>` / `lv-m` / `lv-l` → 红 / 金 / 灰 三档标签
- `<strong>` → 白色加粗（`strong` 已设为 `color:#fff`）
- 涨跌色内联：`style="color:#3fbf9f;font-weight:800"`（涨）／ `#ff8fa3`（跌）
- `.keep`（青）/ `.borrow`（橙）→ 应该保持 / 应该借鉴

**注意**：表窄于 520px 会横向滚动，正常。**每张表都要有 `.cs` 或下方 `blockquote` 给出结论**，不要裸表。
真实样例：COC `sec-5`（周表）、`sec-region`（地区表）。

---

## 5. `stepper` 生命周期步骤条

```html
<div class="stepper">
    <div class="step"><span class="s-ico">🚀</span><b>{{阶段名}}</b><i>{{时间}}</i><em>{{关键数字}}</em><u>{{备注}}</u></div>
    <div class="s-arrow">→</div>
    <div class="step"><span class="s-ico">📊</span><b>{{阶段名}}</b><i>{{时间}}</i><em>{{关键数字}}</em><u>{{备注}}</u></div>
    <div class="s-arrow">→</div>
    <div class="step"><span class="s-ico">🤼</span><b>{{阶段名}}</b><i>{{时间}}</i><em>{{关键数字}}</em><u>{{备注}}</u></div>
  </div>
```

**注意**：`em` 是强调数字（主题色），`u` 是灰色的补充说明。**3–5 个阶段**，超出会横向滚动。
真实样例：COC `sec-6`（3 段：长线运营期 → 稳态投放 → 联动放量）。

---

## 6. `tl` 创意时间线

**用途**：把一条素材按播放时间轴切开，讲每个窗口承担什么功能。**这是「创意要素全解」的核心块。**

```html
<div class="tl">
    <div class="tl-item">
      <div class="tl-t"><span class="tl-ts">0.0–3.0s</span><b>① {{阶段名}}</b></div>
      <div class="tl-d">{{描述，关键数字用 <strong>，话术原文用 … }}</div>
      <div class="tl-tags"><span class="chip2">{{画面元素}}</span></div>
    </div>
    <div class="tl-item">
      <div class="tl-t"><span class="tl-ts">3.0–8.0s</span><b>② {{阶段名}}</b></div>
      …
    </div>
  </div>
```

**注意**：时间点必须是**真实测得的**（关键帧脚本抽出来的），不要臆造。左侧竖线由 `.tl::before` 自动画。
真实样例：COC `sec-tl`（0–3s Hook / 3–8s 玩法与爽点 / …）。

---

## 7. `filterbar` + `fpanel` 交互筛选

**用途**：点击切换，下钻到某一类。**这是报告里唯一的交互式区块。**

```html
<div class="filterbar">
    <span class="fb-lab">选择 {{维度}} →</span>
    <button class="fbtn hookbtn on" data-t="key1">{{标签}} {{占比}}%</button>
    <button class="fbtn hookbtn" data-t="key2">{{标签}} {{占比}}%</button>
  </div>
  <div class="fpanel hookpanel on" data-p="key1">
    <div class="fcard">
      <div class="fc-h"><b>{{标题}}</b><span class="lv lv-h">占比 {{n}}%</span><span class="lv lv-l">触发情绪：{{…}}</span></div>
      <div class="fc-sub">{{副标题}}</div>
      <div class="fgrid">
        <div class="fcell"><div class="fl">{{字段名}}</div><div class="fv">{{内容}}</div></div>
        <div class="fcell"><div class="fl">{{字段名}}</div><div class="fv">{{内容}}</div></div>
      </div>
      <div class="fcell" style="margin-top:12px;background:linear-gradient(90deg,rgba(200,137,42,.14),rgba(63,191,159,.06));border-color:rgba(240,180,81,.3)">
        <div class="fl">策略解读</div><div class="fv">{{深入解读}}</div>
      </div>
      <div class="hookrow">…{{§16 缩略图}}…</div>
    </div>
  </div>
  <div class="fpanel hookpanel" data-p="key2">…</div>
```

**接线规则（shell 已内置）**：
- 按钮 `data-t` 必须与面板 `data-p` **完全相等**
- **第一个**按钮和**第一个**面板加 `on`
- 类名可用：`hookbtn/hookpanel`、`langbtn/langpanel`、`mediabtn/mediapanel`、`dirbtn/dirpanel`，或通用 `fbtn[data-t]` + `fpanel`

**注意**：面板**必须全部写在 HTML 里**（不是 JS 生成），所以文件会大 —— 这是有意的，保证离线可看。
真实样例：COC `sec-filter-hook` / `sec-filter-media`。

---

## 8. `pmx` 发行策略矩阵

**用途**：发行商 / 竞品的产品矩阵 + 生命周期。

```html
<div class="pmx">
    <div class="pcard hl">
      <div class="pc-n">{{发行商}}</div>
      <div class="pc-e">{{主体全称 / 地区 / 股权}}</div>
      <div class="pc-row"><span>{{字段}}</span><span>{{值}}</span></div>
      <div class="pc-pl">产品矩阵明细</div>
        <div class="pc-p"><b>{{产品}}</b><span>{{品类}} · 在投</span></div>
        <div class="pc-p dead"><b>{{产品}}</b><span>{{品类}} · 已停投 {{YYYY-MM}}</span></div>
    </div>
  </div>
```

**注意**：`.hl` = 主角高亮（金条 + 金边）；`.pc-p.dead` 自动降透明度 50%。产品矩阵**按广告量降序排**。
真实样例：COC `sec-pub`（Supercell 12 款产品）。

---

## 9. `aud` 三受众建议

**用途**：**总-分-总里最后的「总」**。按受众分栏给可执行动作。

```html
<div class="aud">
    <div class="aud-c">
      <div class="ac-h"><span class="ac-i">🎨</span><b>对设计师</b><i>创意执行</i></div>
      <div class="aud-i"><b>{{动作标题}}</b><span>{{依据 + 具体数字 + 怎么做}}</span></div>
    </div>
    <div class="aud-c">
      <div class="ac-h"><span class="ac-i">🎯</span><b>对优化师</b><i>投放策略</i></div>
      …
    </div>
    <div class="aud-c">
      <div class="ac-h"><span class="ac-i">🚀</span><b>对产品 / 市场团队</b><i>战略决策</i></div>
      …
    </div>
  </div>
```

**注意**：三栏边框色由 `:nth-child` 自动分配（主题/紫/青）。**每栏 5–6 条**。每条 `<b>` 是祈使句动作，`<span>` 必须是「数据依据 + 具体怎么做」，不能只有结论。
真实样例：COC `sec-20`。

---

## 10. `mmtree` 创意体系脑图

**用途**：报告收尾，把全篇压缩成一棵树。**必须是最后一个内容块。**

```html
<div class="mmtree">
    <ul>
      <li><span class="mm-root">{{产品}} 素材策略体系</span>
        <ul>
          <li><span class="mm-l1">{{层名}}</span>
            <ul>
              <li><span class="mm-l2">{{要点}} <b>{{关键数字}}</b></span></li>
              <li><span class="mm-l3">{{补充细节}}</span></li>
            </ul>
          </li>
        </ul>
      </li>
    </ul>
  </div>
```

**注意**：`mm-l1` 是层（6–8 个），`mm-l2` 是事实，`mm-l3` 是补充。**每个 mm-l1 下 2–3 条**，全树不超过 8 层。
**`.mmtree li::after` 的横线固定在 `top:16px`** —— 所以 `mm-l2/l3` 的文字**不要长到换行**，否则横线会落在文字中间。宁可多写几条短的。
真实样例：COC `sec-mindmap`（7 层）。

---

## 11. `fam` + `mgrid` + `mcard` 素材画廊

**用途**：全量素材，按创意方向分族展示。**每张卡片可在线播放。**

```html
<div class="fam">
    <div class="famhead"><span class="fam-ico">⚔️</span><h4>{{族名}}</h4><span class="fam-cnt">{{n}}</span></div>
    <div class="famdesc">{{该族共性一句话}}（≈{{占比}}%）。</div>
    <div class="mgrid">
      <div class="mcard">
        <div class="mcover">
          <video controls preload="metadata" playsinline poster="{{封面 base64}}"><source src="{{视频 base64}}" type="video/mp4"></video>
          <span class="badge b-type">视频</span><span class="b-lang">{{短ID 7位}}</span>
        </div>
        <div class="mbody"><div class="mrow"><span class="mchip">{{n}} 剪切点</span></div></div>
      </div>
    </div>
  </div>
```

**字段**：
- `poster` → `data:image/jpeg;base64,…`（压制过的，宽 360 / q72）
- `<source src>` → `data:video/mp4;base64,…`（**必须 <2MB**，否则文件爆）
- `.b-type` = 左上紫色「视频」标；`.b-dur` = 右上时长；`.b-lang` = 左下**短 ID**（前 7 位，可对照详情页）
- `.mchip` 放剪切点数 / 素材类型 / 语言

**封面兜底**：视频超预算时把 `<video>` 换成 `<img src="封面">`，并把 `.b-type` 改成
`<span class="badge b-cover">封面</span>`（橙标，与「视频」区分），`.mchip` 写「视频 >2MB，见详情页」。
**口径里必须说明有多少条走了兜底。**

> 容器（`.mcover` / `.gal-thumb` / `.hookthumb` / `.tplthumb` / `.sc-thumb`）**同时支持 `<video>` 和 `<img>`**，
> 两者的 `object-fit:cover` 规则都已写在 shell 里。**不要只给 video 写样式** ——
> 这是冷启动验收时踩到的坑：img 没有规则会溢出容器，封面显示成被裁切的一大块。

**注意**：族数 ≤7，每族卡片 5–12 张。
真实样例：COC `sec-cards`（6 族 41 张）。

---

## 12. `gal` 可仿拍大卡

**用途**：逐条拆解「可借鉴」素材。比 §11 详细得多。

```html
<div class="gal">
  <div class="gal-row">
    <div class="gal-thumb">
      <video controls preload="metadata" playsinline poster="{{封面}}"><source src="{{视频}}" type="video/mp4"></video>
      <button class="gt-zoom" type="button" data-title="{{标题}}" data-sub="{{一句话结论}}">⤢ 放大</button>
    </div>
    <div class="gal-main">
      <div class="gal-hd">
        <span class="gal-no">01</span>
        <span class="gal-tag">可仿拍 · {{方向}}</span>
        <span class="gal-name">{{标题}}</span>
        <span class="gal-lang">{{语言}} · {{n}} 个剪切点</span>
      </div>
      <div class="gal-verdict">{{一句话判断}}</div>
      <div class="g-rows">
        <dl class="g-row"><dt>借鉴点</dt><dd>{{…}}</dd></dl>
        <dl class="g-row kf"><dt>关键帧</dt><dd>{{…}}</dd></dl>
        <dl class="g-row why"><dt>为什么有效</dt><dd>{{…}}</dd></dl>
      </div>
      <div class="kfstrip"><span class="kf-label">关键帧</span><div class="kf-f"><img src="{{帧}}" alt="{{t}}s" loading="lazy"><i>{{t}}s</i></div></div>
      <div class="g-chips"><span class="chip2">{{标签}}</span></div>
      {{可选：§13 逆向提示词}}
    </div>
  </div>
</div>
```

**注意**：
- `data-title` / `data-sub` 是灯箱里显示的文案，**必须填**
- `.gt-zoom` **只在有 `<video>` 时才有意义**（灯箱读的是 `video source` 的 src）
- `.g-row` 的 `dt` 颜色靠类名：默认=`借鉴点`(主题色)、`.kf`=`关键帧`(金)、`.why`=`为什么有效`(青)
- `.gal-tag` 默认主题色，加 `.t2` 变紫
- 关键帧 `.kf-f` 建议 3–6 张，**必须是真实抽帧**，不是封面重复
真实样例：COC `sec-gal-a`（8 条）。

---

## 13. `details.rev` 逆向提示词

**用途**：把一条素材反写成 AI 视频提示词，供设计快速迭代变体。**放在 §12 卡片内。**

```html
<details class="rev">
        <summary>AI 变体提示词 ▾</summary>
        <pre>{{提示词正文，分段写：主体 / 场景 / 运镜 / 节奏 / 文字}}</pre>
        <div class="rev-note">逆向重构 · 非原始提示词；生成后请抽帧人工复核。</div>
      </details>
```

**注意**：台词**只能用素材里真实出现过的句子**（来自 ASR 转写），不能自创。`.rev-note` 那句免责声明**必须保留**。
真实样例：DramaBox 报告 `sec-gal-a`。

---

## 14. `details.sc` 标准脚本卡

**用途**：把洞察推到「可直接投产」。**字段最全的块。**

```html
<details class="sc">
    <summary>
      <span class="sc-no">01</span>
      <span class="sc-id">{{短ID}}</span>
      <span class="sc-meta">投放 {{n}} 天 · 关联 {{n}} 条 · 曝光 {{n}} · 时长约 {{n}}s</span>
      <span class="sc-open">展开脚本 ▾</span>
    </summary>
    <div class="sc-body">
      <div class="sc-thumb"><video controls preload="metadata" playsinline poster="{{封面}}"><source src="{{视频}}" type="video/mp4"></video></div>
      <div class="sc-rows">
        <div class="sc-row sc-kf"><dt>开头黄金三秒</dt><dd>{{画面 + 台词原文 + 为什么这样开头}}</dd></div>
        <div class="sc-row "><dt>中间吸引</dt><dd>{{承接方式}}</dd></div>
        <div class="sc-row sc-kf"><dt>最后转化逻辑</dt><dd>{{收口 + CTA 话术原文}}</dd></div>
        <div class="sc-row "><dt>痛点需求</dt><dd>{{① … ② …}}</dd></div>
        <div class="sc-row "><dt>视角</dt><dd>{{…}}</dd></div>
        <div class="sc-row "><dt>音效</dt><dd>{{…}}</dd></div>
        <div class="sc-row "><dt>剪辑</dt><dd>{{…}}</dd></div>
        <div class="sc-row "><dt>分镜</dt><dd>{{…}}</dd></div>
        <div class="sc-row "><dt>目标受众</dt><dd>{{…}}</dd></div>
        <div class="sc-row sc-live"><dt>真人识别</dt><dd>{{出现时段 + 人物特征，或「无真人出镜」}}</dd></div>
      </div>
    </div>
  </details>
```

**注意**：
- `dt` 颜色：`.sc-kf` = 主题色、`.sc-live` = 青、默认 = 白
- **提取不到的字段一律写「不可得」，绝不自创**。这是本报告可信度的底线。
- `sc-meta` 的数字来自接口字段，别手算
真实样例：COC `sec-scripts`（20 张）。

---

## 15. `tplgrid` 玩法模板库

**用途**：回答「下一个能批量复制的玩法在哪」。

```html
<div class="tplgrid">
    <div class="tplcard">
      <div class="tpl-hd"><span class="tpl-ico">⚡</span><b>{{模板名}}</b></div>
      <div class="tpl-meta">
        <span class="lv lv-h">制作成本 {{低/中/高}}</span>
        <span class="lv lv-m">可迭代性 {{低/中/极高}}</span>
      </div>
      <div class="tpl-row"><b>典型元素</b>{{…}}</div>
      <div class="tpl-row"><b>机制</b>{{…}}</div>
      <div class="tpl-note">{{投产建议，说明能否 100% 由现有客户端产出}}</div>
      <div class="tplthumbs"><div class="tplthumb"><video controls preload="metadata" playsinline poster="{{封面}}"><source src="{{视频}}" type="video/mp4"></video><i>{{短ID}}</i></div></div>
    </div>
  </div>
```

**注意**：`tpl-note` 是金底提示框，**必须回答「要花什么成本、能不能规模化」**，不能空泛。
真实样例：COC `sec-tpl`（6 个模板）。

---

## 16. `hookrow` Hook 缩略图行

**用途**：在筛选面板 / 模板卡里放一排**小尺寸**素材缩略图。

```html
<div class="hookrow"><div class="hookthumb"><video controls preload="metadata" playsinline poster="{{封面}}"><source src="{{视频}}" type="video/mp4"></video><i>{{短ID}}</i></div></div>
```

**注意**：只有 74px 宽，**建议 3–6 个**。和 §11 的 `.mcard` 共用同一批 base64，不用重复下载。
真实样例：COC `sec-filter-hook`、`sec-tpl`。

---

## 17. `newsbtn` 资讯按钮

```html
<tr><td>09-09</td><td>{{信源}}</td><td>{{标题}}</td><td>{{维度}}</td><td><span class="lv lv-h">高</span></td><td><a class="newsbtn" href="{{Google News url}}" target="_blank" rel="noopener">查看详情 ↗</a></td></tr>
```

**注意**：Google News 聚合页是**前端跳转**，离线 HTML **无法预解析最终地址** —— 按钮只能指向上游聚合入口。这一点**必须在 `.cardnote` 里向读者说明**，否则会被当成「链接坏了」。
影响等级：`lv-h` 高（直接改变投放约束）/ `lv-m` 中 / `lv-l` 低。
真实样例：COC `sec-news`（20 条）。

**提要变体**（结论摘要章节用，1–2 条）：

```html
<li>{{信源}}：<a class="newsbtn" href="{{Google News url}}" target="_blank" rel="noopener">{{标题摘要}} ↗</a></li>
```

**两处呈现**（铁律 11）：结论摘要章节放 1–2 条提要（`<li>` + `newsbtn`），
外部环境章放完整清单（`<tr>` + `newsbtn`）。**完整清单 ≥3 条**，不足 `validate.py` 判 FAIL。

> **`newsbtn` 这个类名不只是样式，它是个标记位。** 三处都依赖它：
> ① `validate.py` 按「含 newsbtn 的行/项」数资讯条数（<3 判 FAIL）；
> ② `fidelity.py` 按它做**资讯数字豁免**（引用的是他人标题原文，不该走保真通道）；
> ③ 主题 CSS 里 `.newsbtn` 的配色。
> **所以资讯条目一律用 `<a class="newsbtn">` 承载链接** —— 换成别的类名，
> 保真校验会把资讯标题里的日期金额当成「自创数字」判 FAIL，而计数会变成 0。
> 反过来，这个标记也是**边界**：豁免只覆盖带 newsbtn 的行/项与 `#sec-news` 整章，
> 正文里陈述的数字照旧要能溯源。

---

## 18. `cardnote` 提示条

```html
<p class="cardnote"><strong>{{为什么要看这些内容}}</strong>{{方法论 + 数据来源说明}}</p>
```

**用途**：在读者开始读之前，先说清「为什么是这些条目 / 怎么筛的 / 有什么坑」。
**注意**：橙色左边框，适合放**方法论与免责说明**。全篇 2–4 处即可，多了变噪音。

---

## 19. `blockquote` 三态引用

**收口句的主力块。每个数据章节末尾都该有一段。**

```html
<blockquote>{{普通结论，默认主题色左边框}}</blockquote>
  <blockquote class="warn"><strong>{{警示结论}}</strong><br>{{风险说明}}</blockquote>
  <blockquote class="fix"><strong>{{对策结论}}</strong><br>{{建议说明}}</blockquote>
```

| 类名 | 颜色 | 用于 |
|---|---|---|
| 无 | 主题色 | 结论、读数 |
| `warn` | 红 | 风险、警示、坏消息 |
| `fix` | 青 | 对策、机会点、可操作建议 |

**注意**：`blockquote strong` 是金色。**段落里用 `<br><br>` 分段**（不是多个 blockquote）。
真实样例：全篇。COC `sec-region` 末尾那段「扁平到极致的地区结构」是标准写法。

---

## 20. `flow` 线性承接图

**用途**：展示转化链路 / 时间上的承接关系。

```html
<div class="flow">
    <div class="flow-row">
      <div class="flow-cell"><div class="fc-t">{{阶段}}</div><div class="fc-d">{{该阶段做什么}}</div><div class="fc-bar" style="width:{{%}}"></div></div>
      <div class="flow-cell">…</div>
    </div>
  </div>
```

**注意**：`.flow-row` 有 `min-width:660px`，窄屏横向滚动。`.fc-bar` 是主题色渐变条，宽度用内联 style 给。

---

## 21. `chip` / `chip2` 标签

```html
<span class="chip">{{hero 里的灰底胶囊}}</span>
  <span class="chip2">{{卡片里的小紫标签}}</span>
```

- `.chip` → hero 的 `.chips` 容器里用，5 个左右
- `.chip2` → `.g-chips` / `.tl-tags` 里用，每个卡片 3–8 个

---

## 22. 结论摘要表的列变体

**用途**：首屏那张维度表，列不是写死的 —— 按报告类型换列。

```html
<!-- 单产品深拆（默认）-->
<tr><th>维度</th><th>结论</th><th>关键数据</th></tr>

<!-- 竞品对标（competitor 预设）-->
<tr><th>维度</th><th>本产品</th><th>参照产品</th><th>含义</th></tr>

<!-- 素材/广告双量纲并列时，量纲务必分列，不可合并 -->
<tr><th>维度</th><th>素材数</th><th>广告数</th><th>结论</th></tr>
```

**注意**：
- `.tablewrap` 自带圆角、阴影与横向滚动，**不要再加 CSS**
- 首屏表 **最多 6–7 行**，否则首屏读不完
- 「素材数」与「广告数」是两个量纲（铁律 5），**必须分列**，不要写成一个「投放量」
真实样例：COC `sec-1`（8 行「维度 / 本产品 / 参照 / 含义」）。

---

## 23. 图表函数速查

`shell.html` 已内置 4 个函数，全部**运行时从 CSS 变量取色** —— 换主题时图表自动跟着变。
唯一要改的是 `CHART_DRAW` 里那段 demo。

### `bars(id, rows, opt)` —— 横向条形

```js
bars('cvMedia',[
    ['AppLovin',15.54,C.brand],['Vungle',12.30,C.brand],['TikTok',5.32,C.ember]
  ],{fmt:function(v){return v.toFixed(2)+'%'},max:18,padL:120});
```
- `rows` = `[[标签, 数值, 颜色], …]`，颜色可省（默认 `C.brand`）
- `opt.fmt(v)` 格式化右侧数字标签；`opt.max` 固定轴上限（**不给会自动取最大值，跨图对比时会误导，建议明确给**）
- `opt.padL` 左侧留白，按最长标签调（中文约 `字数×13`）；标签超 12 字会被截断成 `…`

### `grouped(id, labels, series, max)` —— 分组柱状

```js
grouped('cvWeekNew',['W1','W2','W3','W4'],[
    {n:'日均在投',c:C.brand,v:[869,894,953,1191]},
    {n:'新素材',c:C.teal,v:[217,116,192,528]}
  ],1300);
```
- `labels` 超 6 字会被截断，**建议给短标签**（W1 / A 组）
- 图例自动排顶部

### `line(id, labels, vals)` —— 折线

```js
line('cvDaily',['08-11','08-15','08-19','08-23'],[865,863,886,886]);
```
- 轴范围自动留 30% 余量；数据点数量决定标签密度，**超过 12 个点会挤**，必要时隔点给标签

### `matrix(id, opt)` —— 四象限散点

```js
matrix('cvMatrix',{
    xLabel:'制作成本 低 → 高', yLabel:'可迭代性 低 → 高',
    pts:[['即时反馈',0.12,0.92,C.brand],['真人实拍',0.86,0.14,C.danger]]
  });
```
- `pts` = `[[名称, x, y, 颜色]]`，**x/y 都是 0~1 归一化坐标**（左下 = 0,0）
- 适合「成本 × 可迭代性」这类二维取舍分析

### 可选色板变量

`C.brand`（主题色）· `C.brandL` · `C.violet` · `C.ember` · `C.gold` · `C.teal` · `C.danger` · `C.dim`

**约定**：主角 / 本产品用 `C.brand` 或 `C.teal`，竞品一律 `C.violet`，其他 `C.dim`。同一张图里**颜色不超过 4 种**。

---

## 24. `raw` 一次性区块

有些分析是这份产品独有的（COC 的「WWE 联动专项拆解」、DramaBox 的「变现模式 × 素材形态」）。**不要为了套积木而削掉它**。

做法：
1. 优先用现有积木**组合**（COC 的联动专项 = `blockquote.warn` 概述 + 两张 `tablewrap` + `tl` 时间线）
2. 确实需要新样式时，**在正文 `<style>` 槽之后追加一个 `<style>` 块**（放在 head 里，见 shell 注释），类名加产品前缀避免冲突
3. 写完后跑 `scripts/validate.py`，它会检查 CSS 是否落在 `<style>` 内

> ⚠️ **最容易犯的错**：`html.replace('</head>', CSS)` 会把 CSS 落到 `</style>` **外面**，浏览器把样式表当正文渲染，报告顶部出现一大段裸 CSS 文本。
> **正确做法**：`html.replace('</style>', CSS + '</style>')`，或 `rfind('</style>')` 后插入。

---

## 25. `mmk` Markmap 交互脑图

**用途**：报告收口。和 §20 `flow`、§10 `mmtree` 是**三件不同的东西**，别混：

| 区块 | 形态 | 说什么 |
|---|---|---|
| §20 `flow` | 纯 CSS 横向承接图 | **线性**：阶段一 → 二 → 三，有先后顺序 |
| §10 `mmtree` | 纯 DOM 树（CSS 画横线） | **层级**：静态展示，读者只能看 |
| §25 `mmk` | Markmap 交互图（SVG） | **层级 + 可交互**：能缩放、拖拽、点节点折叠 |

> **「迭代脑图」= §20 `flow` + §25 `mmk`。** 前者讲承接顺序，后者讲体系全貌。
> §10 `mmtree` 是更早的静态版本，仍然可用，但**不要再把 `mmtree` 当成"脑图收尾"的唯一形态**。

### 作者手写的部分（照抄，只换内容）

```html
<div class="mmk">
    <div class="mmk-bar">
      <span class="mmk-t">{{标题}} · 可交互</span>
      <span class="mmk-tabs">
        <button class="mmk-tab on" type="button" data-mmk-lang="zh">中文</button>
        <button class="mmk-tab" type="button" data-mmk-lang="en">EN</button>
      </span>
      <span class="mmk-g">
        <button class="mmk-act" type="button" data-mmk-act="expand">全展开</button>
        <button class="mmk-act" type="button" data-mmk-act="collapse">收起到层</button>
        <button class="mmk-act" type="button" data-mmk-act="fit">适应画布</button>
      </span>
    </div>
    <div id="markmap"></div>
    <div class="mmk-hint">
      <span>滚轮 = 滚动页面</span>
      <span><kbd>Ctrl</kbd> + 滚轮 = 缩放</span>
      <span>拖动 = 平移</span>
      <span>点节点 = 折叠</span>
    </div>
  </div>

  <script type="text/markdown" id="mmk-md-zh">
# {{产品}} · 素材策略体系
## 卖点层
- **{{要点}}** · 占比 {{n}}%
  - {{支撑事实}}
## 投放层
- **{{要点}}**
## 风险层
- {{衰减最快的方向}}
  </script>
```

**要点**：

- `#markmap` 这个 **id 不能改**（`mmk-boot` 与 CSS 都按它找容器），也**只能有一个**
- 容器**必须带 `.mmk` 外壳**：高度、边框、渐变背景、print 样式都挂在 `.mmk` / `#markmap` 上
- **markdown 源是 `<script type="text/markdown">`，不是 `<pre>`** —— `mmk-boot` 按
  `script[type="text/markdown"][id^="mmk-md-"]` 收源。**多语言就多写一份**
  （`mmk-md-zh` / `mmk-md-en`），语言 tab 的 `data-mmk-lang` 要和 id 后缀**小写对齐**，
  对不上的 tab 会被静默隐藏
- 源里**必须有 `#` 标题或 `-` 列表**，否则只剩一个根节点（`validate.py` 会判 FAIL）
- 源是 markdown，不是 HTML：`**加粗**` 有效，`<b>` 会被当字面量

### 依赖必须内联（这一步不做，脑图就是一段死 markdown）

```bash
python scripts/mindmap.py <报告.html>          # 幂等，可重复跑
python scripts/mindmap.py <报告.html> --check  # 只体检、不写文件
```

`mindmap.py` 把 d3@7 + markmap-lib@0.18.12 + markmap-view@0.18.12 **内联**到
`shell.html` 里那处裸 `MARKMAP_VENDOR` 标记位（正文里那处，不是 CSS 注释里那处 ——
选错位置会把 1MB 依赖注进 `<style>`，脚本永不执行，而"依赖已内联"的断言照样全绿，
见 `pitfalls.md` #26）。三个 vendor 缓存落在 `<skill>/assets/vendor/`，可复用。

### 固定层不要改（在 `shell.html` 的 `mmk-boot` 里）

1. **禁用 `markmap-autoloader`** —— 它靠运行期动态 `import()` 拉 d3 / markmap-view，
   任一 CDN 失败就静默 reject，页面只剩没渲染的 markdown，控制台还不一定报错
2. **渲染失败必须降级**为样式化列表（`data-mmk-fallback="1"`），信息不丢
3. **语言切换必须重建容器**再 `transform` + `create` —— Markmap 实例和 DOM 强绑定，
   对旧容器重复 create 会残留 zoom / ResizeObserver 监听，图形**套娃叠影**
4. **语言切换必须串行**（`queue = queue.then(...)`）—— 连点两个语言按钮时，
   并发的 create 会互相覆盖 transform，最后谁赢看运气
5. **滚轮不劫持页面**（`scrollForPan:false` + `pan:false`）—— markmap 自带的 wheel
   处理器**无条件 `preventDefault()`**，不拆掉的话读者在报告里滚不动

### 交付前自检

```bash
python scripts/validate.py <报告.html> --dir <工作区>            # 静态：依赖备好了
python scripts/check_mindmap_render.py <报告.html> --dir <工作区> # 运行：真的渲染出来了
```

**两条都要跑。** 静态只能证明"准备好了"，这套设计的失效模式恰恰是**静态全绿、页面只剩没渲染的 markdown**。

