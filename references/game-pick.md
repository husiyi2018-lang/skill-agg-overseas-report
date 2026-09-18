# 手游榜单选品 —— 「本周有哪些值得分析的游戏」

> **这一步在报告之前，解决的是「分析谁」。** 榜单里几百个游戏，不能全做，
> 也不能只挑排名高的 —— **排名高 ≠ 值得分析**。
> 脚本：`scripts/game_rank.py`　触发词：哪些游戏值得分析 / 什么游戏在火 /
> 榜单变化 / 选品 / 找竞品 / 本周有什么新游戏。

---

## 0. 它和报告的关系（先读，别搞混口径）

```
选品（本文件，App Store 榜单口径）
    -> 选定 1 款标的
        -> 报告正身（aggclaw / AppGrowing 口径）
```

两条口径**不同源、不可互验、不可混用**：

| | 选品阶段 | 报告正身 |
|---|---|---|
| 数据源 | App Store 官方榜单（iTunes RSS） | AppGrowing 全球广告 AI 策略分析平台 |
| 回答 | 谁在榜上、谁在换血 | 谁在买量、买什么素材 |
| 产物 | `brief_*.md` 简报 | 自包含 HTML 报告 |

**铁律**：简报里的数字**不许搬进报告正文**。报告正文的数字照旧要能追到 aggclaw 返回，
或登记进 `work/derived.json`（SKILL.md 铁律 2）。选品简报是**决策辅助**，不是报告论据。

**署名**：选品简报里写明「App Store 官方榜单 · iTunes RSS」。这不违反铁律 1 ——
铁律 1 禁的是写有米有数 / youclaw，以及引 Sensor Tower / AppMagic / data.ai 等**竞品平台**。
App Store 官方榜单是商店自有数据，不是竞品平台。但**报告 HTML 的署名仍只有一种写法**。

---

## 1. 执行

```bash
python scripts/game_rank.py snapshot --pick     # 最常用：抓快照 + 出选品（约 20–40 秒）
python scripts/game_rank.py pick --top 30       # 复用已有快照重跑选品
python scripts/game_rank.py compare             # 与上一次快照的真环比
python scripts/game_rank.py categories          # 只看品类换血榜
```

- **`timeout` 给 ≥300s**。单次 RSS 请求实测约 1.2s，默认共约 51 次请求，并发 6。
  （旧文档写「约 5 分钟」是那台机器网络慢，不是接口的问题。）
- `--dir` 默认 `reports/_rank`。**落盘必须保留** —— 它是环比的唯一历史基线。
- 选完标的后，把 `brief_*.md` 给用户看，同时按用户选的流程开跑报告。

### 产出

| 文件 | 内容 |
|---|---|
| `daily_YYYYMMDD.json` | 榜单快照 + 品类归因（**环比的历史基线，别删**） |
| `picks_YYYYMMDD.json` | 选品打分结果 |
| `brief_YYYYMMDD.md` | 可直接贴飞书/邮件的简报 |

---

## 2. 数据源：iTunes RSS

```
https://itunes.apple.com/{market}/rss/{chart}/limit=100/genre={genre}/json
```

- `{market}`：`in us br id ph vn th mx pk ng ru tr`（12 个，实测可用）
- `{chart}`：`topfreeapplications` 免费榜 / `topgrossingapplications` 畅销榜 /
  `newfreeapplications` 新上架榜
- `{genre}`：`6014` = Games 总品类；子品类见下方映射表
- 免费、无鉴权、服务端直接返回 JSON —— 比抓 Google Play 可靠得多

### ⚠️ 哪些榜真的认 `genre`（实测，别想当然）

| 榜 | 认 genre? | 取法 |
|---|:---:|---|
| `topfreeapplications` | ✅ | 带 `genre=6014`，返回 100% 是 Games |
| `topgrossingapplications` | ✅ | 同上 |
| `newfreeapplications` | ❌ | **完全不认**，见下 |

**`newfreeapplications` 会忽略 genre 参数**：传 `6014 / 7012 / 7003 / 7006` 拿回的是
**同一张榜**（两两重合 100%），而且那是**全品类**新上架榜 ——
美国榜前 25 名里只有 2 款是游戏（榜首常是全品类第一的 `ChatGPT` 之类）。
所以游戏新上架榜只能「抓全品类 + 按条目自带的 `category` 字段客户端过滤」得到。

> 源文档没发现这一点，它的「新上架榜」一直是全品类榜，据此得出的起量结论有一半是假的。

过滤后样本很小：美国 100 款里约 10 款是 Games，`br / mx / ru` 三个市场**是 0**
（那两个市场的新上架榜前 100 名里一款游戏都没有，不是网络问题）。

### `category` 字段只有大类

条目的 `category.attributes.label` 给的是 `Games` / `Business` / `Productivity` 这种**大类**，
**拿不到子品类**。但它足以把全品类新上架榜过滤成游戏榜 —— 这是它唯一的用途。

---

## 3. 子品类：用 lookup API，别用 genre 榜反推

子品类来自 **`https://itunes.apple.com/lookup?id=a,b,c`**（逗号分隔多 id，分批 50）
返回的 `genreIds` / `genres` 数组 —— 这是苹果自己的分类，**可引用**。

**为什么不用「逐品类榜反推」**：那只能覆盖「已进过某子品类 Top100」的游戏，
刚上架的新品一条都不在里面，用它数「品类新品数」会**全得 0**。实测踩过。

### 权威 genre ID 映射（实测核对，不要凭印象改）

| ID | 子品类 | ID | 子品类 |
|---|---|---|---|
| 7001 | Action | 7012 | **Puzzle** |
| 7002 | Adventure | 7013 | Racing |
| 7003 | **Casual** | 7014 | Roleplaying |
| 7004 | Board | 7015 | **Simulation** |
| 7005 | Card | 7016 | Sports |
| 7006 | Casino | 7017 | Strategy |
| 7009 | Family | 7018 | Trivia |
| 7011 | **Music** | 7019 | Word |

**复核方法**（别猜）：取该 genre 榜的榜首 app id → `lookup?id=<id>` →
在它返回的 `genreIds`/`genres` 里找与该 feed 命中的那一项。

初版凭印象写成 `7003=Arcade / 7011=Puzzle / 7014=Simulation`，**全错**。
`7007 Dice` / `7008 Educational` 实测返回空数组；
`7010` 及 `7020+` 是**非法 ID** —— 传了会**静默回退**到全品类榜（榜首变成 `ChatGPT`）。
**非法 genre 不报错**，这是本流程最容易悄悄污染结论的一处。

### ⚠️ 归因覆盖率不是 100%

实测 591 款里只有 491 款（**83%**）能拿到子品类。剩下 100 款分两类：
lookup 只回大类（`genreIds=['6014']`，苹果没给这些 App 挂子品类 ——
实测含 `Smash Fest!`、`DAVE THE DIVER`），以及连 `genres` 字段都没有。

**不是请求失败**（分块 50 / 20 都验过，无失败块）。所以
**品类席位是「已归因游戏」的子集，是个下界**。简报里必须把覆盖率写出来。

---

## 4. 选品打分模型

**从「广告素材情报平台」的视角，什么样的手游值得做产品分析？**

| 维度 | 信号 | 为什么 |
|:---|:---|:---|
| 1️⃣ 正在买量 | 跨市场覆盖数 | 没买量就没素材可分析 |
| 2️⃣ 变现能力强 | 进畅销榜 | 有收入才能持续买量 |
| 3️⃣ 素材迭代快 | 休闲品类 | 每周数十套素材，最需要情报工具 |
| 4️⃣ 情报需求强 | **中小发行商** | 大厂已有成熟情报体系，不是好客户 |
| 5️⃣ 买量窗口期 | **新上架榜 + 免费榜双榜** ⭐ | 刚起量，正是切入时机 |

```python
SCORE = {
    "market_cover":   5.0,   # 每覆盖 1 个市场（全球买量力度）
    "free_top50":     8.0,   # 免费榜进前 50
    "free_top10":    15.0,   # 免费榜进前 10（额外加成）
    "grossing_hit":  15.0,   # 进畅销榜 = 强变现信号
    "grossing_top50": 10.0,  # 畅销榜进前 50（额外）
    "new_rising":    30.0,   # ⭐ 新上架+免费双榜（最高权重）
    "new_app_rank":  12.0,   # 新上架榜前 10（刚上架就冲榜）
    "casual_genre":   8.0,   # 休闲品类
    "sme_bonus":     10.0,   # 中小发行商加成
    "big_malus":    -25.0,   # ⚠️ 长青老游戏降权
    "rank_rise":      6.0,   # 有历史快照时，跨市场平均排名上升（每 5 名折算，封顶 2×）
    "cat_rising":     8.0,   # 所属品类本周在换血
}
```

### ⚠️ 长青老游戏必须降权 —— 这是本模型最重要的一条，踩过坑

不加降权时 Top5 是 `Candy Crush` / `Royal Match` / `8 Ball Pool` / `Roblox` / `PUBG`。
它们**数据好看但毫无分析价值**：

- 素材体系早已成熟稳定，没有新东西可分析
- 大厂有成熟的情报采购流程，不需要外部工具
- 报告写出来也没人看（行业都知道它们怎么做）

加 `EVERGREEN` 名单 + `big_malus` 降权后，Top 才是真正值得分析的标的。
**维护**：发现某游戏长期霸榜且行业已充分研究，就加进 `EVERGREEN`（小写子串匹配）。
注意大厂的**新品**（如 `Kingshot`）仍应保留 —— 所以只对「上榜久 + 品类成熟」的组合降权。

### 品类判定：优先商店品类，关键词只做兜底

有 lookup 拿到的商店品类就一定用它（**可引用**）；没有才退到 `CASUAL_KW` 关键词 ——
那是我们自己猜的，按铁律 4 出现在正文里得标「**手工编码**」。
脚本会在理由里自动标注 `(关键词判定)`，两者不一致时**以商店品类为准**。

### 标签

`🔥中小` = 优先（更缺素材情报工具）｜`🏢大厂` = 有成熟情报体系｜
`⚠️长青` = 上榜久、素材体系成熟，已降权

---

## 5. 品类：两个因子一起看

| 因子 | 定义 | 看它回答什么 |
|:---|:---|:---|
| **席位** | 该品类进总免费榜 Top100 的款数 | 榜上体量（存量结构） |
| **新品** | 该品类本周出现在**游戏新上架榜**的款数 | **换血强度 —— 这才是「飙升」** |
| **换血率** | 新品 ÷ (新品 + 席位) | 新品在可见供给里的占比 |

- **只看席位**会把长青盘误判成热门（一堆老游戏占着位子，没有新钱进来）
- **只看新品**样本太小会噪声主导

**两个都必须标注 n**。游戏新上架榜合计约 140 款，摊到 16 个品类上多是 0–20，
属**方向性信号，不可外推为比例、不可在品类间精确排序**（铁律 4）。
要更硬的品类结论，回到 aggclaw 查该品类的广告数与素材数。

**品类是多标签的**：一款游戏可同时属于多个子品类（实测 `Meowdoku!` 同时在
Casual 与 Puzzle 下）。所以各品类席位相加**必然大于**总款数 ——
简报里必须写明，否则看起来像统计错误。

---

## 6. 环比（需要历史快照）

- 每次 `snapshot` 落盘 `daily_YYYYMMDD.json`，`compare` 自动拿**上一份**做对比
- `old_rank - new_rank > 0` 即上升；跨市场取平均，`avg ≥ 1` 才给 `rank_rise` 加分
- **排行榜更新是小时/天级**。短间隔两次快照会得到 **0 条变动** ——
  实测间隔 3 分钟两次快照 → 0 条变动。那是正常的，不是 bug，别去修。
  积累 2–3 天才有意义。

---

## 7. 已知坑（写脚本/改脚本前扫一遍）

| 坑 | 现象 | 处置 |
|:---|:---|:---|
| Windows 控制台 GBK | `print` 遇 `™`/`®` 直接 `UnicodeEncodeError` **崩掉整个脚本**（跑完几十次请求才死在最后一行输出上） | 开头 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` |
| `newfreeapplications` 忽略 genre | 四个不同 genre 返回同一张榜；那是**全品类**榜 | 抓全品类 + 按 `category` 过滤 Games |
| 非法 genre 静默回退 | 传 `7010`/`7020+` 不报错，返回全品类榜（榜首 `ChatGPT`） | 只收实测核对过的 16 个 ID |
| `limit=1` 返回 dict 不是 list | `feed.entry[0]` → `KeyError: 0` | 统一的 `entries()` 归一化 |
| 归因覆盖 83% | 100/591 款无子品类 | 简报写明覆盖率、席位标为**下界** |
| 品类多标签 | 各品类席位相加 > 总款数 | 简报写明，不要「修正」 |
| 品类席位靠「新品 ∩ 总榜」 | 交集恒为 0，指标退化成常数 | 改用「新上架榜里属于该品类的款数」 |
| 哨兵要对齐市场 | 拿 us 的名单比 in/tr 的榜 → 一半假数据放行 | 逐市场取哨兵 |
| `genre` 与 `games_only` 耦合 | 哨兵取 `genre=None` 被改写成 `genre=6014`，48 个合法榜全判为回退 | 两个参数**各管各**，调用方显式传 |
| Google Trends | 直连 `/trends/api/explore` 返回 **429** | 有 Clash 代理（`127.0.0.1:7897`）可重试，否则退回榜单数据 |
| Google Play 榜单页 | JS 渲染，抓下来 940KB 但 `aria-label` 里没有应用名，**抓不到** | 用 iTunes RSS 替代 |
| 第三方站（appbrain 等） | 404 / 429 | 别花时间 |

---

## 8. 实测基线（2026-09-17，12 市场 × 3 榜 × Top100）

**品类（换血 = 新品数，席位 = 进总榜款数，换血率）**：

| 品类 | 新品 | 席位 | 换血率 |
|:---|---:|---:|---:|
| Casual | 44 | 527 | 7.7% |
| Puzzle | 43 | 420 | 9.3% |
| Action | 23 | 239 | 8.8% |
| Strategy | 21 | 131 | 13.8% |
| Simulation | 15 | 234 | 6.0% |
| Board | 9 | 83 | 9.8% |
| Trivia | 8 | 12 | **40.0%** ⭐ |
| Racing | 7 | 63 | 10.0% |

**Top 10 值得分析的标的**：

| 游戏 | 发行商 | 关键信号 |
|:---|:---|:---|
| Block Out! - Color Sort Puzzle | Grand Games 🇹🇷 | 11市场，免费#2，畅销#19 |
| Magic Sort! | Grand Games 🇹🇷 | 10市场，免费#7，畅销#32 |
| Bus Traffic Fever! | GOODROID | 10市场，免费#8，畅销#36 |
| Tasty Travels: Merge Game | Century Games | 11市场，免费#6，畅销#8 |
| Colony Flow! | ABI GLOBAL | 9市场，免费#6，畅销#29 |
| Hollywood Merge | VoyagerOne | 9市场，免费#10，畅销#16 |
| Food Hunt: Pixel Puzzle | FUNFINITY | 11市场，免费#12，畅销#37 |
| Whiteout Survival | Century Games | 10市场，免费#9，畅销#7 |
| Castle Busters | Voodoo | 11市场，免费#5，畅销#19 |
| Mob Control | Voodoo | 11市场，免费#2，畅销#61 |

**品类集中度**：Top 10 里 7 款是 Casual/Puzzle 休闲品类 —— 素材迭代最快，
是素材情报工具的核心目标市场。

**发行商信号**：`Grand Games`、`Century Games`、`Voodoo`、`Lumi Games`、`Flow Games`、
`Microfun`、`ABI GLOBAL`、`FUNFINITY`、`Oakever Games` 多产品同时在投。

> ⚠️ 这是**单日快照**，不是趋势。环比要等历史快照积累。
