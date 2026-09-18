---
name: agg-overseas-report
description: 海外产品「素材投放与创意策略综合报告」生成器。基于 AppGrowing Global（aggclaw 分析引擎），产出**自包含单文件 HTML**：零外部依赖、可离线、素材可在线播放、四种手写 canvas 图表、四套深色主题可选。内置**数字保真校验**（报告里每个数字都要能溯源或登记公式）与**派生值登记制**。适用于出海游戏 / 短剧 App / 工具金融 App 的单产品深拆与竞品对标。**也支持「先选品再分析」**：用户问「本周有哪些值得分析的游戏」时，先用 App Store 榜单跑选品（飙升品类 + 值得分析的标的），定下标的再进报告流程。当用户要求分析某款海外产品的素材策略、广告投放、创意方向。触发词：素材报告、素材策略、创意策略报告、投放分析、竞品素材对比、哪些游戏值得分析、什么游戏在火、榜单变化、选品、找竞品。
---

---

## 开工前（必做）：环境自检

**换机器 / 第一次拿到这个技能，先跑这一条** —— 它会告诉你缺什么：

```bash
python scripts/setup_check.py
```

缺东西时，它会在结尾打印一段**兜底提示词**，整段复制给 Claude等Agent，Claude等Agent 会自己把
ffmpeg / Pillow / 浏览器 / API Key 装好配好 —— **使用者不需要懂命令行**。

| 依赖 | 少了会怎样 | 必需? |
|---|---|---|
| Python ≥3.8 | 脚本跑不起来 | ✅ |
| `YOUCLOUD_API_KEY` 环境变量 | 取数直接失败 | ✅ |
| ffmpeg | 封面（视频抽帧）与关键帧做不出来 | ✅ |
| Pillow | 封面不压缩 → 报告胀到 20MB+ | ⭕ 建议 |
| Edge / Chrome | 只影响导 PDF，**HTML 报告照出** | ⚪ 可选 |

装完 ffmpeg 要**重开终端**才认得到。详见 `references/setup.md`。

---

## 两个入口

| 用户说的 | 从哪进 |
|---|---|
| 「分析 XX 的素材策略」「拆解这条素材」「和 YY 对比」 | → **直接进下面第 0 步** |
| 「**本周有哪些值得分析的游戏**」「什么游戏在火」「榜单变化」「选品」 | → **先走「入口 B：选品」**，定下标的再回来从第 0 步走 |

---

## 入口 B：选品（用户没点名产品时，先定「分析谁」）

**榜单里几百个游戏，不能全做，也不能只挑排名高的 —— 排名高 ≠ 值得分析。**

读 `references/game-pick.md`，然后：

```bash
python scripts/game_rank.py snapshot --pick    # 抓快照 + 出选品（约 20-40 秒，timeout ≥300s）
```

产出 `<工作区>/brief_YYYYMMDD.md` 选品简报（飙升品类 + 值得分析的标的 + 发行商信号 + 环比），
`daily_YYYYMMDD.json` 是**环比的历史基线，别删**。

**流程**：出简报 → **同时**开跑 Top1 的报告流程（第 0 步起）→ 用户若换标的，前面的取数作废。

**四条不能破的边界**：

1. **口径隔离** —— 选品用 App Store 官方榜单（iTunes RSS）口径，报告正身是 AppGrowing 口径，
   **两个数字不可混用、不可互验**。简报里的数字**不许搬进报告正文**；
   正文数字照旧要能追到 aggclaw 返回或登记进 `work/derived.json`（铁律 2）。
2. **榜单 ≠ 买量** —— 榜单只说明「谁在榜上」，起量是间接推断。
   买量的直接证据（广告数 / 素材数）仍要回 aggclaw 查。
3. **小样本必须标 n** —— 品类「新品数」的 n 只有约 140（游戏新上架榜天生样本小），
   属方向性信号，按铁律 4 标注，**不可外推为比例、不可在品类间精确排序**。
4. **作者署名不因此放宽** —— 简报里写「App Store 官方榜单 · iTunes RSS」（商店自有数据），
   **报告 HTML 的署名仍只有一种写法**（铁律 1，`validate.py` 会校验）。

> 品类归因只覆盖 83%（591 款里 491 款；其余苹果未挂子品类），所以品类席位是**下界**，
> 简报必须写明覆盖率。非法 genre ID 会**静默回退**到全品类榜，别往 `GENRES` 表里加没核对过的 ID ——
> 实测坑与复核方法见 `references/game-pick.md`。

---

## 工作流（7 步，每步带验收）

### 0. 判定意图与档位

读 `references/intent-presets.md`：
- 判定**意图预设**：`game-strategy` / `short-drama` / `app-tool` / `competitor` / `single-creative`
- 用 aggclaw 量级问答（或去重后的素材清单总量）拿窗口素材总数，定**档位**：A ≥5万 / B 1千–5万 / C <1千

**先判定再动手** —— 判错会导致「取了一堆用不上的数」或「写到一半发现缺数」。

### 1. 取数

读 `references/data-pipeline.md`。aggclaw 一条路走到底 —— 分析文本给洞察与数字，会话素材接口给素材清单：

```bash
# 1) 多路分析(A 档走多路交叉,见 references/a-tier.md)
#    分析原文与元数据分开落盘:raw/data/result_L{n}_{tag}.md + 同名 .json
python scripts/claw.py analyze --lanes work/lanes.json --work work --conc 3
# 2) 拉各会话引用的素材清单,落盘到 raw/(保真校验的语料基线)
python scripts/claw.py materials --scan raw/data --out raw/materials_all.json
```

- **分析原文落成 `.md`,不要塞回 JSON** —— 保真校验抽语料时,`.json` 里的长文本会被
  判成编码串整段丢弃,`.md` 才走纯文本分支。`claw.py` 已按此落盘,别再手工拆分补救。
- `--raw` 默认取 `<work>/../raw`(工作区约定里 `work/` 与 `raw/` 同级),要换落点再显式传。

- **A 档必须多路交叉**：≤8 路独立会话，≥2 路同结论才算高置信度（详见 `references/a-tier.md`）
- **★★ 越轻越稳** —— 实测同一窗口下：6 子问题的重问法 **4 次全挂**（每次 600s 超时 + 新会话重试
  = 烧掉 20 分钟），3 子问题的轻问法 **一次就中**，6 路轻问并发 **6/6 全成**。
  **把重问题拆成 2–3 个轻问题并行，是这份技能里性价比最高的一条操作。** 详见 `pitfalls.md` #35
- **并发 ≤3**，8 路同时 POST 会网关 504
- **口径冲突（差异 >20%）严禁取平均**，正文用主口径 + 口径说明里注明分歧
- **超时必须 ≥600 秒**（单次 1–8 分钟，提前中断返回空结果）
- **素材清单落盘后别读进上下文** —— 只在磁盘上聚合
- **有一条提问是结构性取不到的**：「XX 品类素材量前 N 的产品及各自素材数」——
  接口为素材级数据、无产品归属字段，问了要么超时要么被引擎明确拒绝。
  要做产品级对比就**点名指定产品、每款一路、自行汇总**。详见 `pitfalls.md` #36
- **脚本别叫 `select.py`/`json.py`/`types.py`** —— 与标准库同名会让 `urllib.request` 在 Windows 上循环导入报错，改叫 `pick.py` 之类

### 2. 素材实体化 ⛔ **这一步是硬闸门，没跑不得进第 3 步**

> **为什么单列一条警告**：这一步**跳过了不会报错**。曾经交付过一份「代表素材区块
> 排版整齐、ID 徽标齐全、validate 全绿」的报告，但卡片是裸 `<div>` + 手绘 SVG 占位，
> **读者点不动也播不了**。根因就是这一步没跑。详见 `pitfalls.md` #21。
>
> **判断依据**：`ls work/`。`covers.json` / `videos.json` 是空的或不存在 = 没跑。
> **空的中间产物本身就是最强信号。**

> **开工先探活，30 秒。** 取数脚本遇服务端宕机会**静默挂死**（`0 字节无响应`），
> 最坏耗 100 分钟才抛一句「已重试 10 次」，极易被误判成 Key 失效。
> 动手前先跑这三条 curl 定性（放行 `--noproxy '*'`）：
>
> ```bash
> BASE=https://ai-chat-global.youcloud.com
> curl -sS --noproxy '*' -m 12 -o /dev/null -w "root   %{http_code} %{time_total}s\n" $BASE/
> curl -sS --noproxy '*' -m 12 -o /dev/null -w "midw   %{http_code} %{time_total}s\n" $BASE/aichat/foobar
> curl -sS --noproxy '*' -m 12 -o /dev/null -w "biz    %{http_code} %{time_total}s\n" \
>   -X POST -H "Content-Type: application/json" -d '{"input":"hi"}' $BASE/aichat/claw
> ```
>
> `root=200` + `foobar=401 秒回` + `biz=0 字节超时` ⇒ **服务端 upstream 宕机，不是你的问题**，
> 直接报故障别空转。完整指纹对照表见 `pitfalls.md` #22b。

```bash
# ① 先把素材清单拉全（download_url 会中途变 401，别等写正文时才补）
python scripts/claw.py materials --scan raw/data --out raw/materials_all.json

# ② 封面：视频抽首帧 → 宽360/q72 → base64（依赖 ffmpeg）
python scripts/covers.py --dir <工作区> --all

# ③ 视频内嵌：一律重编码（不限原片大小）→ 判体积 → base64
python scripts/media_embed.py --dir <工作区>

# ④ 关键帧
python scripts/frames.py --dir <工作区> --ids id1,id2

# ⑤ 外部媒体资讯（**有下限，见下**）
python scripts/news.py fetch --dir <工作区> --queries "<产品名>,<开发商>,<品类>买量,手游营销"
python scripts/news.py list  --dir <工作区> --top 40      # 看 [优选] 标记再挑
python scripts/news.py pick  --dir <工作区> --idx 0,3,7,12
```

**⑤ 资讯有硬下限：报告必须含 ≥3 条外部媒体文章。** 这是产品要求，不是加分项 ——
纯平台数据回答不了「这游戏最近发生了什么」这类归因问题。三条纪律：

- **条数 ≥3**。`list` 里带 `[优选]` 的是白名单信源（53 家行业媒体，名单在 `news.py`）。
  `pick` 不足 3 条会直接 `[BLOCK]`，而且 `validate.py` 在交付前还会再拦一次（error）。
- **搜不到的降级**：先放宽检索词（厂商名 / 品类买量 / 手游营销）；确实没有该产品的直接报道，
  可放宽到**厂商层面 / 同赛道品类层面**，但数量仍须 ≥3，且**必须在 `.cardnote` 里显式写明
  「暂无该产品直接报道」**。拿泛行业文章冒充该产品报道，比留空更伤信任。
- **媒体文中的数字不进正文陈述**。资讯表引用的是他人文章标题原文（带日期、排名、金额），
  这些数字不是本报告的主张 —— `fidelity.py` 对资讯行做**豁免**（判据是行内含 `newsbtn` 链接），
  但它们也不得被搬进正文当论据。正文里的数字照旧要能追到接口字段或登记进 `derived.json`。

**两处呈现**：结论摘要章节放 1-2 条关键动态（`<li>` + `newsbtn`），外部环境章放完整清单（表格行 + `newsbtn`）。

- **`media_embed.py` 才是视频主路径**：原片 15MB → 重编码后 1.05MB（约 15:1），
  所以「原片多大」和「能不能内嵌」基本无关（`videos.py` 的 `≤2MB` 分档会把头部素材全砍掉）
- 封面与关键帧**都依赖 ffmpeg** —— 素材清单只有视频直链、没有封面图字段，封面一律从视频首帧来
- 封面**必须压缩**（原图直嵌 → 单文件 20MB+）
- 内嵌视频必须 `IntersectionObserver` 进视口才播 + `.mplay` 手动暂停（14 条齐播会卡死）
- 关键帧**必须真抽**，不能用封面重复充数
- 少数 ID 是**图片不是视频**（实测 `…-102` 是 JPEG）→ 无视频流时降级 `kind="image"`

### 3. 组装 HTML

从 `assets/shell.html` 复制一份，按注释替换槽位（`{{TITLE}}` / `{{FAVICON}}` / `{{THEME_CSS}}` / `{{NAV}}` / hero 各槽 / `{{SCOPE_BAR}}`），
正文按 `references/BLOCKS.md` 手写。

- 主题从 `references/themes.md` 整套复制（4 套：base 粉紫 / gold 部落金 / teal 青金 / indigo 深蓝）
- **文风硬约束见 `references/writing-style.md`（2026-09 起默认生效）**：判断句小标题、
  结论前置（hero 第一段即核心判断）、引子三段式、主动给反例、跨行业类比、术语裸用、
  口径声明固定句式。它管「怎么写」，与 `report-craft.md`（管结构与口径）叠加生效
- 写作规则与证据链格式见 `references/report-craft.md`
- **资讯放两处**：结论摘要章节 1-2 条提要（`<li>` + `newsbtn`）+ 外部环境章完整清单（表格行 + `newsbtn`）。
  资讯条目**必须**用 `<a class="newsbtn">` 承载原文链接 —— 这个标记同时是
  `validate.py` 的计数依据与 `fidelity.py` 的豁免依据，漏了就两边都失效。写法见 `BLOCKS.md` §17
- **静态 `<title>` 要单独同步** —— 导出 PDF、书签读的是它
- **素材卡必须是 `<a href="…/material/<全量ID>">`，不是裸 `<div>`**（铁律：可点可播）
- **小标题不要出现「摘要 / 分析 / 应保持 / 可借鉴」这类版式词** ——
  要写这一章真正的判断（如「这三件事，头部已经跑通了」）。
  版式词是模板泄漏到内容里的痕迹，读者一眼看出是填空。详见 `pitfalls.md` #23
- **正文不要写编码参数**（转码宽度、抽帧秒数）—— 保真校验会判 FAIL，读者也不需要知道。
  详见 `pitfalls.md` #24

### 3b. 迭代脑图（写 `#markmap` 块 → 内联依赖）

「迭代脑图」= **线性承接图**（阶段一→二→三，纯 CSS，用 `flow`，见 `BLOCKS.md` §20）
\+ **Markmap 交互脑图**（可缩放/展开，用 `mmk`，见 `BLOCKS.md` §25）。两者分工不同，都要有。
（旧版只用 `mmtree` 静态层级树收尾，即 `BLOCKS.md` §10 —— 仍可用，但**不是**「迭代脑图」的全部。）

```bash
# ① 正文里写 .mmk 块 + markdown 数据源（骨架见 BLOCKS.md §25）
# ② 内联三依赖（幂等，可重复跑；报告没有 #markmap 时它会自动把 1MB 摘掉）
python scripts/mindmap.py <报告.html>
# ③ 只体检不写文件
python scripts/mindmap.py <报告.html> --check
```

- **禁用 `markmap-autoloader`**：它靠运行期动态 `import()` 拉 d3 / markmap-view / toolbar，
  **任一 CDN 失败就静默 reject** —— 页面只剩一段没渲染的 markdown，控制台还不一定报错。
  依赖必须由 `mindmap.py` **内联**进单文件（离线自包含，约 1MB）
- 依赖顺序 **d3 → markmap-lib → markmap-view** 不可调换；`markmap-lib` 的浏览器包是
  `index.iife.js`（写 `index.js` 是 404）
- 渲染失败**必须降级**为样式化列表（信息不丢），语言切换**必须重建容器 + 串行**——
  这些都在 `shell.html` 的 `mmk-boot` 固定层里，别改
- 铁律：脑图是**渲染出来的**才算数 —— 静态校验只能证明"依赖备好了"，
  交付前必须跑第 5 步末尾的**运行时自检**

### 4. 登记派生值

**这一步是新增的，也是本技能和「看起来专业」的区别所在。**

报告里凡是**自己算出来**的数字（合计、环比、占比、集中度），都要写进 `work/derived.json`：

```json
{
  "253":   {"formula":"137+116", "source":"raw/materials_all.json", "n":253,
            "note":"iOS 段 + Android 段素材数相加"},
  "-69":   {"formula":"(98-312)/312*100", "source":"raw/data/result_L2_....md"}
}
```

- `formula` 与 `source` **必填**，source 文件必须真实存在
- 纯算术公式（`921/253`）会**被求值并比对**，算不对就报错
- 公式里出现的数字**自身也要能溯源**（在 raw 里命中，或本身也是登记值）→ 防止用登记洗白编造

### 5. 自检（必过）

```bash
python scripts/validate.py <报告.html> --dir <工作区>
```

检查：占位符残留 / CSS 是否落在 `<style>` 内 / 导航锚点一一对应 / 一级导航 ≤7 /
卡片 ID 是否在清单内 / canvas 是否都画了 / 灯箱按钮是否配对 / 裸表裸图 / CDN 外链 /
**数字保真（命不中又没登记的判 FAIL）** / **外部媒体资讯 ≥3 条（不足判 FAIL）** /
**容器标签配平（总数相等 + 深度全程非负）**。

> **最后那条是唯一一类「其余闸门全绿也拦不住」的失效。** 实测事故：组装脚本在素材族循环里
> 多吐一个 `</div>`，把 `.layout` 提前闭合，正文渲染到弹性布局之外 —— 侧栏消失、正文占满屏幕、
> 崩点落在页面中段，**而当时 13 项检查全部是绿的**（数字保真过了、卡片全对、锚点全通）。
> 数字错会被 `fidelity` 拦，**结构崩坏不会**。详见 `pitfalls.md` #32。

**0 error 才算过。** 详见 `references/pitfalls.md`。

报告里有交互脑图（`#markmap`）时，**再跑一次运行时自检**：

```bash
python scripts/check_mindmap_render.py <报告.html> --dir <工作区>
```

- **为什么必须单有这一步**：`validate.py` 是**静态**分析，它只能证明脑图"**准备好**渲染了"
  （依赖内联、指纹体积达标、boot 逻辑在、CSS 覆盖到），证明不了"**渲染成功**"。
  而本技能这套设计的失效模式恰恰是：**静态全绿、运行全崩，页面只剩一段没渲染的 markdown**。
  所以必须真的用无头浏览器跑一遍，断言 `#markmap` 里出现了 `<svg class="markmap">` 且有节点。
- 断言链：容器非空 → 未出现降级标记 → svg 已挂载 → `.markmap-node` > 0；
  再跑**深度运行时**四条（默认就做，加 `--quick` 才退回只验基础渲染）：⑤ 依赖缺失时是否降级 → ⑥ 语言切换是否**重建**
  （不是叠加套影）→ ⑦a 同一 tick 连点 4 次后**末态是否干净** → ⑦b **并发渲染峰值是否 ≤1**。
  渲染失败会**把降级原因原样打出来**（如"内联依赖缺失"），直接指向根因。
- 它先剥掉 base64 载荷再渲染 —— 排除内嵌封面/视频与脑图抢主线程造成的**假失败**。
- **它会给自检副本装一个 rAF 垫片**（`install_raf_shim`，插在 `</head>` 之前）。
  无头 `--virtual-time-budget` 下浏览器**会停发 rAF 帧**，而 markmap-view 的 `renderData`
  里是 `await new Promise(requestAnimationFrame)` ⇒ 渲染永不恢复，正确报告也会偶发
  假红"末态节点 8 ≠ 点击前 13"。垫片把帧调度换成语义等价的 `setTimeout(fn,16)`，
  虚拟时间即可可靠推进。**它必须早于 d3**（d3-timer 在**加载时**就把 rAF 抓进变量，
  晚于 d3 打补丁等于白装），所以插在 `</head>` 之前而非 `</body>`。垫片**只进副本、永不进产物**。
- 垫片**不会把真 bug 一起盖掉**：装垫片后把同一批判据打到变异体上，⑦b 仍稳定报峰值 **4**，
  正确实现稳定报 **1**，各 3/3 复现 —— 判据区分度一分没少。
- ⑦a/⑦b 都会回填**环境供帧计数**（`--virtual-time-budget` 到底供了几帧）。读不到（`<0`）说明
  垫片没装上，此时"末态不收敛"**降级为 WARN 并说明原因，不判红** —— 分不清是"报告卡在半渲染"
  还是"环境不供帧"，就不该诬告被测对象。启动日志 `[1/3]` 那行会显式打出「rAF 垫片已装 / **未装**」，
  看到"未装"就知道后面若出现 ⑦a 红要按环境问题看。
- 找不到 Edge / Chrome 时**只 WARN 跳过、不阻断**（这是加分自检，不该让合格报告交付不了）。
- 报告没有 `#markmap` 时直接 SKIP（不是错）。
- 踩坑全过程见 `references/pitfalls.md` #30（queue 空串行化）与 #31（无头 rAF 停发）。

### 6. 目视复核

- 左导航点击跳转 + 滚动高亮
- **四种图表全部渲染**（`matrix` 最容易漏 —— 没画过的 canvas 没有 `width` 属性）
- 素材卡片封面可见、视频可播、`⤢ 放大` 开灯箱
- **脑图能拖能缩**：滚轮缩放、拖拽平移、`适应/展开/收起` 三个按钮有效；
  有第二语言时切 tab 后图形**重建**（不是叠加套影）；把 `mmk-lib` 临时删掉再看一次，
  应降级成**结构化列表**而不是空白
- 打印预览（Ctrl+P）下侧栏隐藏、卡片不跨页断裂

### 7. 出 PDF

```bash
python scripts/topdf.py <报告.html>
```

---

## 铁律（违反即返工）

1. **数据源署名只有一种写法**：`AppGrowing全球广告 AI 策略分析平台`，链接
   https://appgrowing.ai —— 禁写有米有数 / youclaw，
   禁引 Sensor Tower / AppMagic / data.ai 等竞品平台
   （`shell.html` 的 `side-foot` 已内置这句与链接，别改成别的写法；
     `validate.py` 会校验署名与链接，缺任一即 error）
2. **不动不写** —— 正文每个数字都要能追到接口字段，或已登记进 `work/derived.json`
3. **不臆造** —— 取不到就写「不可得」「本轮未探测」，并在数据边界章节列明
4. **手工编码的占比必须标注 n 与误差**（如「n=200 样本，误差 ±10pp，属方向性结论」）
5. **「素材数」与「广告数」是两个量纲，不可互推** —— 表格必须分列
6. **素材 ID 只能来自 materials 清单**，不得推断 / 截断 / 跨对象挪用
7. **追加 CSS 必须插在 `</style>` 之内** —— `replace('</head>', CSS)` 会让浏览器把样式当正文渲染
8. **一级导航 ≤7，任何清单 ≤7**
9. **合规/违规素材与创意方向分开统计** —— 违规素材常与合规头部素材同母版
10. **素材卡必须可点可播** —— 是 `<a href="…/material/<全量ID>">`，封面容器里有
    `<video>`/`<img>`、不得用 SVG 占位。**卡片退化不会报错，只会被读者发现**
11. **外部媒体文章 ≥3 条** —— 报告必须含外部资讯：完整清单 ≥3 条（`<tr>` + `newsbtn`）
    + 结论摘要 1-2 条提要（`<li>` + `newsbtn`）。不足先放宽检索词，再降级到厂商/品类层面
    （数量仍须 ≥3）并在 `.cardnote` 显式标注「暂无该产品直接报道」。
    **资讯引用行不参与数字保真**（引用他人标题原文），但正文陈述里的数字照旧要能溯源 —— 
    两者以 `newsbtn` 为界，不得把媒体数字搬进正文当论据
12. **脑图必须内联、必须降级、必须真的渲染出来** —— 禁 `markmap-autoloader`（静默失效）；
    三依赖由 `mindmap.py` 内联且**不许落在 `<style>` 里**；渲染失败降级为列表；
    交付前 `check_mindmap_render.py` 必须 OK（静态校验绿 ≠ 渲染成功）

---

## 文件导航

| 文件 | 什么时候读 |
|---|---|
| `assets/shell.html` | **每次必用** —— 复制它开工 |
| `references/BLOCKS.md` | **写正文时全程对照** —— 24 类区块的骨架 |
| `references/game-pick.md` | **入口 B（用户没点名产品时）** —— 榜单选品模型 / 权威子品类映射 / 口径隔离 / 选品的坑 |
| `references/intent-presets.md` | **第 0 步** —— 判定意图 / 档位 / 章节骨架 |
| `references/report-craft.md` | 第 3 步 —— 结构铁律 / 口径区块 / **数据口径陷阱** / 证据链 / 四层标注 / 质检红线 |
| `references/writing-style.md` | **第 3 步，必读** —— 文风硬约束（判断句标题 / 结论前置 / 引子三段式 / 反例段 / 跨行业类比 / 术语裸用 / 固定句式模板 / 保真边界） |
| `references/themes.md` | 第 3 步 —— 选配色 + favicon |
| `references/data-pipeline.md` | 第 1 步 —— 取数口径与铁律 |
| `references/a-tier.md` | 判为 A 档时 —— ≤8 路交叉采样 / 并发分批 / 假结果识别 / 置信度汇聚 |
| `references/setup.md` | **开工前** —— 环境自检 / 缺依赖怎么办 / 兜底提示词 |
| `references/pitfalls.md` | 遇到怪问题时 / 开工前扫一遍 —— HTML·PDF·体积类**工程坑** + 验证流程（数据口径已移至 report-craft） |

## 脚本速查

| 脚本 | 作用 |
|---|---|
| `setup_check.py` | **环境自检**（缺依赖时打印兜底提示词） |
| `game_rank.py` | **入口 B 选品**：App Store 榜单快照 + 品类换血 + 选品打分 + 环比 + 简报（纯 stdlib，不需 Key） |
| `claw.py` | **aggclaw 多路取数驱动**（lanes 并行、504/假成功重试、拉素材清单） |
| `aggclaw.py` | aggclaw 单次调用（chat_mode 7=游戏 / 8=非游戏短剧 / 9=灵感） |
| `covers.py` | 视频首帧 → 压缩 → base64（需 ffmpeg） |
| `media_embed.py` | **视频内嵌主路径**：下载 → ffprobe → 一律重编码 → 判体积 → base64 |
| `videos.py` | 视频分档：Range 探体积（旧路径，会砍掉头部素材，仅备用） |
| `frames.py` | 真实关键帧抽取（需 ffmpeg） |
| `news.py` | Google News 聚合 + 信源白/黑名单过滤 |
| `mindmap.py` | **Markmap 依赖内联**（幂等注入；`--check` 只体检）—— d3 / markmap-lib / markmap-view → 单文件 |
| `check_mindmap_render.py` | **脑图运行时自检**（无头浏览器断言 `#markmap` 里真有 svg 与节点；失败打出降级原因） |
| `fidelity.py` | **数字保真 + 派生值登记校验 + 素材 ID 合法性** |
| `validate.py` | 交付前自检（含调用 fidelity） |
| `topdf.py` | HTML → PDF（处理 Edge 写错目录的坑） |

## 工作区约定

```
reports/{product}_{YYYYMMDD}/
    raw/          # 接口原始返回，全部落盘 —— **保真校验的语料基线**
        data/     # ★ aggclaw 分析原文: result_L{n}_{tag}.md(语料) + 同名 .json(仅元数据)
        materials_all.json / news_all.json
    covers/       # 封面(视频首帧抽出来的,压缩后)
    frames/       # 关键帧
    work/
        derived.json     # ★ 派生值登记（自己算出来的数字都在这）
        covers.json / videos.json / news.json
        build_report.py  # 组装脚本（可选，但推荐留档）
    *.html / *.pdf

reports/_rank/            # ★ 入口 B 选品的工作区（不属于任何单个产品）
    daily_YYYYMMDD.json   # 榜单快照 + 品类归因 —— **环比的历史基线，别删**
    picks_YYYYMMDD.json   # 选品打分结果
    brief_YYYYMMDD.md     # 可直接贴飞书/邮件的选品简报
```

所有脚本统一 `--dir <工作区>`；`game_rank.py` 默认 `--dir reports/_rank`。
