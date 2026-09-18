#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
手游榜单追踪 + 选品 —— 回答「本周有哪些值得分析的游戏」。

这条流程跑在报告之前（SKILL.md 的「入口 B」）。它解决的是**分析谁**的问题：
榜单里几百个游戏，不能全做，也不能只挑排名高的（排名高 ≠ 值得分析）。

    快照(什么在火) -> 品类(哪些品类在换血) -> 选品打分(哪些值得分析)
        -> 简报 -> 选定标的 -> 进原报告流程

数据源：iTunes RSS（App Store 官方榜单，免费、无鉴权、服务端直接返回 JSON）
    https://itunes.apple.com/{market}/rss/{chart}/limit=100/genre={genre}/json
选它而不是抓 Google Play 的原因：GP 榜单页是 JS 渲染，抓下来拿不到应用名（实测）。

用法：
    python game_rank.py snapshot --pick     # 抓快照 + 出选品（最常用）
    python game_rank.py pick --top 30       # 读最新快照 -> 选品 -> 简报
    python game_rank.py compare             # 与上一次快照做真环比
    python game_rank.py categories          # 只看品类换血榜

    --dir PATH        工作区，默认 reports/_rank
    --markets a,b,c   覆盖默认的 12 个市场

耗时：单次 RSS 请求实测约 1.2s。默认 12市场×3榜=36 + 品类归因 lookup 约 15 次
      ≈ 51 次请求，6 线程并发下约 20–40 秒。**timeout 请给 ≥300s**。
      （旧文档写的「约 5 分钟」是那台机器网络慢，不是接口的问题。）

落盘：
    <工作区>/daily_YYYYMMDD.json    榜单快照（环比的历史基线）
    <工作区>/picks_YYYYMMDD.json    选品结果
    <工作区>/brief_YYYYMMDD.md      可直接贴飞书/邮件的选品简报
"""
import argparse
import glob
import json
import os
import sys
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Windows 控制台默认 GBK，商标字符(™ ®)会让 print 直接 UnicodeEncodeError 崩掉整个脚本。
# 必须在任何输出之前改掉，否则跑完 50 次网络请求才死在最后一行打印上。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 市场：覆盖超休闲买量最猛的盘子。in/pk/ng/vn/id/ph/th 是新兴市场（素材本地化需求最强），
# us/br/mx/tr/ru 是主力盘与土耳其系发行商大本营。
MARKETS = ["in", "us", "br", "id", "ph", "vn", "th", "mx", "pk", "ng", "ru", "tr"]

# 三榜分工：免费榜=当前热度，畅销榜=变现能力，新上架榜=起量窗口(信号最强)
CHARTS = ["topfreeapplications", "topgrossingapplications", "newfreeapplications"]

GAMES_GENRE = "6014"  # Games 总品类

# ⚠️ 哪些榜真的认 genre 参数 —— 实测出来的，别想当然。
# topfree / topgrossing 认（genre=6014 返回 100% 是 Games）。
# **newfreeapplications 完全不认** —— genre 传 6014/7012/7003/7006 拿回的是**同一张榜**
# （两两重合 100%），而且那是**全品类**新上架榜（美国前 25 名里只有 2 款是游戏）。
# 所以游戏新上架榜只能「抓全品类 + 按条目自带的 category 字段客户端过滤」得到。
# 源文档没发现这一点：它的「新上架榜」一直是全品类榜，据此得出的起量结论有一半是假的。
CHART_META = {
    "topfreeapplications":     {"games_only_via_genre": True,  "label": "免费榜"},
    "topgrossingapplications": {"games_only_via_genre": True,  "label": "畅销榜"},
    "newfreeapplications":     {"games_only_via_genre": False, "label": "新上架榜"},
}

# ★ 权威 genre ID -> 子品类名映射（只收游戏子品类）。
# 这张表是**实测核对出来的**，不是猜的：拿每个 genre 榜的榜首 app 去 lookup API
# 读它的 genreIds/genres，取与该 feed 命中的那一项。
# 猜错的代价很高 —— 初版凭印象写成 7003=Arcade / 7011=Puzzle / 7014=Simulation，全错。
# 真实是 7003=Casual / 7011=Music / 7012=Puzzle / 7014=Roleplaying / 7015=Simulation。
# 核对方法见 references/game-pick.md。
GENRES = {
    7001: "Action", 7002: "Adventure", 7003: "Casual", 7004: "Board",
    7005: "Card", 7006: "Casino", 7009: "Family", 7011: "Music",
    7012: "Puzzle", 7013: "Racing", 7014: "Roleplaying", 7015: "Simulation",
    7016: "Sports", 7017: "Strategy", 7018: "Trivia", 7019: "Word",
}
# 7007 Dice / 7008 Educational 实测返回空数组；7010 及 7020+ 是**非法 ID**，
# 传了会静默回退到全品类榜（榜首变成 ChatGPT）。这些一律不要收进本表。

# ---------------------------------------------------------------------------
# 选品打分模型 —— 「从广告素材情报平台视角，什么样的手游值得做分析」
#
# 五个维度，缺一不可：
#   1. 正在买量（否则没素材可分析）        -> 跨市场覆盖 + 新上架榜
#   2. 变现能力强（有收入才能持续买量）    -> 畅销榜表现
#   3. 素材迭代快（量大、变动频繁）        -> 休闲品类
#   4. 情报需求强（大厂已有成熟情报体系）  -> 中小发行商加权、大厂长青降权
#   5. 买量窗口期（刚起量，正是切入时机）  -> 新上架榜+免费榜双榜
# ---------------------------------------------------------------------------
SCORE = {
    "market_cover":   5.0,   # 每覆盖 1 个市场（全球买量力度）
    "free_top50":     8.0,   # 免费榜进前 50
    "free_top10":    15.0,   # 免费榜进前 10（额外加成）
    "grossing_hit":  15.0,   # 进畅销榜 = 强变现信号
    "grossing_top50": 10.0,  # 畅销榜进前 50（额外加成）
    "new_rising":    30.0,   # 新上架榜 + 免费榜同时出现（起量窗口，最高权重）
    "new_app_rank":  12.0,   # 新上架榜前 10（刚上架就冲榜）
    "casual_genre":   8.0,   # 休闲品类（素材迭代最快）
    "sme_bonus":     10.0,   # 中小发行商（更缺素材情报工具）
    "big_malus":    -25.0,   # 大厂长青老游戏降权
    "rank_rise":      6.0,   # 有历史快照时，跨市场平均排名上升（每 5 名折算，封顶 2×）
    "cat_rising":     8.0,   # 所属品类本周在换血（品类榜得出的信号）
}

# ⚠️ 长青老游戏必须降权 —— 这是本模型最重要的一条，踩过坑。
# 不加降权时 Top5 是 Candy Crush / Royal Match / 8 Ball Pool / Roblox / PUBG，
# 全是上榜十年的游戏：数据好看但毫无分析价值（素材体系早已成熟稳定，没有新东西可分析；
# 大厂有成熟情报采购流程，不需要外部工具；报告写出来也没人看）。
# 降权后 Top 才是真正值得分析的标的。
# 维护：发现某游戏长期霸榜且行业已充分研究，就加进来（小写子串匹配）。
EVERGREEN = [
    "candy crush", "royal match", "roblox", "pubg", "8 ball pool",
    "subway surfers", "clash of clans", "coin master", "gardenscapes",
    "homescapes", "township", "fishdom", "toon blast", "mobile legends",
    "free fire", "efootball", "clash royale", "hay day", "brawl stars",
    "monopoly go", "block blast", "ludo king", "carrom pool", "among us",
    "minecraft", "pokemon go", "call of duty", "garena", "honkai", "genshin",
]

# 商店品类里算「休闲/超休闲」的那些 —— **权威口径，优先于关键词**。
CASUAL_GENRES = {"Casual", "Puzzle", "Board", "Card", "Trivia", "Word",
                 "Family", "Music", "Simulation"}

# 休闲品类关键词 —— 只在 lookup 拿不到该游戏品类时兜底。
# 有 genre 就一定用 genre：那是商店官方分类、可引用；关键词是我们自己猜的，
# 按铁律 4 出现在正文里得标「手工编码」。两者不一致时以 genre 为准。
CASUAL_KW = [
    "puzzle", "match", "merge", "sort", "color", "block", "tile", "arrow",
    "cube", "ball", "idle", "clicker", "runner", "hyper", "casual", "word",
    "mahjong", "solitaire", "sudoku", "jigsaw", "connect", "draw", "pop",
    "bubble", "blast", "crush", "escape", "brain", "trivia", "quiz",
    "farm", "city", "tycoon", "simulator", "sim", "life", "party",
    "carrom", "ludo", "card", "domino",
]

# 大厂（素材需求相对稳定、已有成熟情报体系）—— 不降权，但也拿不到中小厂商加成
BIG_PUBLISHERS = [
    "voodoo", "playrix", "king", "supercell", "zynga", "ea ", "electronic arts",
    "tencent", "netmarble", "activision", "ubisoft", "roblox", "mojang",
    "miniclip", "dream games", "peak games", "moon active", "sybo",
    "hungry studio", "century games", "kayac", "saygames", "homa",
]


# ---------------------------------------------------------------------------
# 抓取
# ---------------------------------------------------------------------------

def http_get(url, timeout=25, retries=3):
    """带重试的 GET。个别市场偶发 WinError 10060，重试即可；连续失败返回 None，不中断整轮。"""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as f:
                return f.read()
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(1.2 * (attempt + 1))
    return None


def entries(payload):
    """把 feed.entry 归一成 list。

    坑：limit=1 时 iTunes 返回的是**单个 dict 而不是长度 1 的数组**，
    直接 [0] 会 KeyError: 0。所有取 entry 的地方都要走这里。
    """
    if not payload:
        return []
    try:
        d = json.loads(payload.decode("utf-8", "replace"))
    except Exception:
        return []
    e = d.get("feed", {}).get("entry", [])
    if e == []:
        return []
    return e if isinstance(e, list) else [e]


def chart_url(market, chart, genre=None, limit=100):
    g = f"/genre={genre}" if genre else ""
    return f"https://itunes.apple.com/{market}/rss/{chart}/limit={limit}{g}/json"


def fetch_chart(market, chart, genre=None, limit=100, games_only=False):
    """抓一个榜，返回 [{rank,name,dev,appid,cat}, ...]。失败返回 []。

    genre 与 games_only 是**两件独立的事**，调用方必须显式区分：
      - `genre=6014`      -> 服务器端筛游戏（topfree / topgrossing 认）
      - `genre=None`      -> 完全不过滤，拿全品类榜（**新上架榜**要的就是这个）
      - `games_only=True` -> 客户端按条目自带的 category 字段筛 Games，
                             专供不认 genre 的新上架榜

    第一版让 genre 由 games_only 反推（`genre = 6014 if not games_only else None`），
    结果哨兵取 `genre=None` 时被悄悄改写成 `genre=6014`，哨兵变成「游戏榜 Top20」，
    于是 48 个合法品类榜全被判成回退。**别再把这两个概念耦合起来。**
    """
    rows = entries(http_get(chart_url(market, chart, genre, limit)))
    out = []
    for e in rows:
        cat = e.get("category", {}).get("attributes", {}).get("label", "")
        name = e.get("im:name", {}).get("label", "")
        if not name:
            continue
        if games_only and cat != "Games":
            continue
        out.append({
            "rank": len(out) + 1,          # 过滤后重排名，否则名次会跳号(1,2,12,13…)
            "name": name,
            "dev": e.get("im:artist", {}).get("label", ""),
            "appid": e.get("id", {}).get("attributes", {}).get("im:id", ""),
            "cat": cat,
        })
    return out


def fetch_names(market, chart, genre=None):
    return [r["name"] for r in fetch_chart(market, chart, genre)]


def run_parallel(tasks, workers=6):
    """tasks = [(key, callable), ...] -> {key: result}。并发 ≤6，再多会被限流。"""
    out = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn): k for k, fn in tasks}
        for fu, k in futs.items():
            try:
                out[k] = fu.result()
            except Exception:
                out[k] = []
    return out


def lookup_genres(appids, verbose=False):
    """批量 lookup，拿每个 App 的**权威子品类集合**（从 genreIds/genres 里只留游戏子品类）。

    为什么非要有这一步：RSS 自带的 `category` 字段只有大类("Games")，拿不到子品类；
    而「逐品类免费榜」只能覆盖**已经进过某子品类 Top100** 的游戏 —— 刚上架的新品
    一个都不在里面，用它去数「品类新品数」会全得 0（第一版就是这样，换血率恒为 0）。

    lookup 支持逗号分隔多 id（分批 50），几百款游戏只要十几次请求。
    它是苹果自己的接口，给出的品类可引用，比我们自己按名字猜关键词硬得多。

    ⚠️ 覆盖不到全部：实测 591 款里只有 491 款（83%）能拿到子品类，剩下 100 款分两类 ——
    一类 lookup 只回大类（`genreIds=['6014']`，苹果没给这些 App 挂子品类，实测含 Smash Fest!、
    DAVE THE DIVER），一类连 genres 字段都没有。这不是请求失败（分块 50/20 都验过，无失败块）。
    所以品类席位是**已归因游戏的子集**，是个下界；简报必须把覆盖率一并写出。
    """
    out = {}
    ids = [str(a) for a in appids if a]
    if not ids:
        return out, 0
    for i in range(0, len(ids), 50):
        raw = http_get("https://itunes.apple.com/lookup?id=" + ",".join(ids[i:i + 50]))
        if not raw:
            continue
        try:
            d = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            continue
        for r in d.get("results", []):
            gids, gns = r.get("genreIds", []), r.get("genres", [])
            got = {gn for gi, gn in zip(gids, gns)
                   if str(gi).isdigit() and int(gi) in GENRES}
            if got:
                out[str(r.get("trackId"))] = got
    if verbose:
        pct = round(len(out) / len(ids) * 100) if ids else 0
        print(f"      命中 {len(out)}/{len(ids)} 款（{pct}%）"
              + ("　其余苹果未挂子品类，按未分类处理" if len(out) < len(ids) else ""))
    return out, len(ids)


def snapshot_chart(market, chart):
    """按榜各自的取法抓游戏榜 —— 三个榜的游戏化路径并不一样，见 CHART_META。"""
    if CHART_META[chart]["games_only_via_genre"]:
        return fetch_chart(market, chart, GAMES_GENRE)          # 服务端按 genre 筛
    return fetch_chart(market, chart, None, games_only=True)    # 全品类榜 + 客户端筛


def snapshot(markets, workers=6, verbose=True):
    """12 市场 × 3 榜 × Top100 + 一次全量品类归因 lookup。

    返回 (data, appid_genres, n_classified, n_total)。
    品类归因**单独返回、不塞进 data** —— data 的键是 `{market}_{chart}`，
    build_index 会按 "_" 切，混进一个别的键会让它切出 market="_game"，
    然后拿 dict 当 list 迭代而崩。
    """
    tasks = [(f"{m}|{c}", (lambda m=m, c=c: snapshot_chart(m, c)))
             for m in markets for c in CHARTS]
    if verbose:
        print(f"[1/3] 抓榜单快照：{len(markets)} 市场 × {len(CHARTS)} 榜 = {len(tasks)} 次请求 ...")
    res = run_parallel(tasks, workers)
    data = {k.replace("|", "_"): v for k, v in res.items()}
    empty = [k for k, v in data.items() if not v]
    if verbose:
        print(f"      完成，非空榜 {len(data) - len(empty)}/{len(data)}")
        if empty:
            # 报出具体是哪些，而不是笼统一句「本次超时」——
            # 实测 br/mx/ru 的 newfree 榜空是**数据如此**（那两个市场的新上架榜
            # 前 100 名里一款游戏都没有），不是网络失败，不该让人去重试。
            print(f"      空榜：{', '.join(empty)}"
                  + ("　（这三个市场的新上架榜实测本就没有游戏，非网络问题）"
                     if len(empty) == 3 else ""))

    # 品类归因：免费榜 + 新上架榜里出现过的所有游戏，一次性 lookup 拿子品类。
    # 存进快照，后续 pick 不必再联网。
    ids, seen = [], set()
    for chart in ("topfreeapplications", "newfreeapplications"):
        for m in markets:
            for r in data.get(f"{m}_{chart}", []):
                if r["appid"] and r["appid"] not in seen:
                    seen.add(r["appid"])
                    ids.append(r["appid"])
    if verbose:
        print(f"[2/3] 品类归因：对 {len(ids)} 款游戏做 lookup ...")
    gmap, total = lookup_genres(ids, verbose)
    return data, {k: sorted(v) for k, v in gmap.items()}, len(gmap), total


# ---------------------------------------------------------------------------
# 索引与品类
# ---------------------------------------------------------------------------

def build_index(snap):
    """{游戏名: {market: {chart: rank}}}

    只认 `{market}_{chart}` 且值是非空 list of dict 的键 —— 快照里还躺着别的结构
    （以及 `_` 前缀的内部键），不设这道闸就会拿 dict 当 list 迭代而崩。
    """
    idx = defaultdict(lambda: defaultdict(dict))
    for key, rows in snap.get("data", {}).items():
        if not rows or not isinstance(rows, list) or key.startswith("_"):
            continue
        parts = key.split("_", 1)
        if len(parts) != 2:
            continue
        market, chart = parts
        if not isinstance(rows[0], dict) or "name" not in rows[0]:
            continue
        for r in rows:
            idx[r["name"]][market][chart] = r["rank"]
    return idx


def dev_of(snap, name):
    for rows in snap.get("data", {}).values():
        if not isinstance(rows, list) or not rows:
            continue
        for r in rows:
            if isinstance(r, dict) and r.get("name") == name:
                return r.get("dev", "")
    return ""


def build_genre_map(snap):
    """{游戏名: set(品类名)} —— 源是快照里的 `game_genres`（appid -> 子品类，lookup 权威给出）。

    它覆盖**每一款**上榜游戏，包括刚上架、还没进任何子品类榜的新品。
    这里不用「逐品类榜反推」：那只能覆盖「已进某子品类 Top100」的游戏，
    对「品类新品数」这个指标完全无效（新品一条都不在里面）。

    ⚠️ 一款游戏会同时属于多个子品类（Apple 品类是多标签的，实测 Meowdoku! 同时在
    Casual 与 Puzzle 下）。所以「品类席位」是**带重复的归属**，不是互斥划分 ——
    各品类席位相加必然大于候选总数，简报里必须写明，否则看起来像统计错误。
    """
    out = defaultdict(set)
    by_appid = snap.get("game_genres", {})
    if not by_appid:
        return out
    for key, rows in snap.get("data", {}).items():
        if not isinstance(rows, list) or key.startswith("_"):
            continue
        for r in rows:
            if not isinstance(r, dict):
                continue
            g = by_appid.get(str(r.get("appid", "")))
            if g:
                out[r["name"]] |= set(g)
    return out


def category_stats(snap, markets=None):
    """品类两个因子：**席位**（体量）与**新品数**（换血 = 飙升信号）。

    - `seats` 席位：该品类有多少款进了总免费榜 Top100 = 榜上体量/存量。
    - `fresh` 新品：该品类本周有多少款出现在**游戏新上架榜**上 = 换血强度。
    - `rate` 换血率 = fresh/(fresh+seats)：新品在该品类可见供给里的占比。
      只看 `seats` 会把长青盘（占着一堆席位但全是老游戏）误判成热门；
      只看 `fresh` 样本太小会噪声主导。两个一起看。

    为什么新品数**不能**定义成「新上架榜 ∩ 总免费榜」：实测交集恒为 0。
    刚上架的游戏本来就进不了总榜 Top100（正是文档说的「尚未进免费榜」），
    交集为空是常态 —— 第一版就是这么写的，结果 16 个品类的换血数全是 0，
    指标彻底退化。改成「新上架榜里属于该品类的款数」才有区分度。

    ⚠️ n 小，须按铁律 4 标注：12 个市场的游戏新上架榜合计约 140 款，
    摊到 16 个品类上多是 0–20，属**方向性信号，不可外推为比例、不可精确排序**。
    """
    markets = markets or snap.get("markets", [])
    gmap = build_genre_map(snap)
    agg = defaultdict(lambda: {"seats": 0, "fresh": 0})
    for m in markets:
        for r in snap.get("data", {}).get(f"{m}_topfreeapplications", []):
            for g in gmap.get(r.get("name", ""), ()):
                agg[g]["seats"] += 1
        for r in snap.get("data", {}).get(f"{m}_newfreeapplications", []):
            for g in gmap.get(r.get("name", ""), ()):
                agg[g]["fresh"] += 1
    rows = []
    for g, a in agg.items():
        tot = a["seats"] + a["fresh"]
        if not tot:
            continue
        rows.append({"genre": g, "seats": a["seats"], "fresh": a["fresh"],
                     "rate": round(a["fresh"] / tot * 100, 1)})
    rows.sort(key=lambda x: (-x["fresh"], -x["rate"], -x["seats"]))
    return rows


def new_sample_n(snap, markets=None):
    """游戏新上架榜的可用样本量（品类新品数的 n，必须随结论一起给出）。"""
    return sum(len(snap.get("data", {}).get(f"{m}_newfreeapplications", []))
               for m in (markets or snap.get("markets", [])))


# ---------------------------------------------------------------------------
# 选品打分
# ---------------------------------------------------------------------------

def is_casual(name, gset):
    """有商店品类就用商店品类（可引用），没有才退到关键词（手工编码，需标注）。"""
    if gset:
        return bool(gset & CASUAL_GENRES), "商店品类"
    n = name.lower()
    return any(k in n for k in CASUAL_KW), "关键词"


def is_big(dev):
    d = (dev or "").lower()
    return any(b in d for b in BIG_PUBLISHERS)


def is_evergreen(name):
    n = name.lower()
    return any(e in n for e in EVERGREEN)


def score_game(name, markets, prev_ranks=None, rising_genres=None, gmap=None):
    s, reasons = 0.0, []
    gset = (gmap or {}).get(name, set())

    # 1) 跨市场覆盖 = 全球买量力度
    cover = len(markets)
    if cover >= 2:
        s += cover * SCORE["market_cover"]
        reasons.append(f"覆盖{cover}市场")

    # 2) 免费榜 = 当前热度
    free = [c["topfreeapplications"] for c in markets.values()
            if "topfreeapplications" in c]
    if free:
        bf = min(free)
        if bf <= 10:
            s += SCORE["free_top10"] + SCORE["free_top50"]
            reasons.append(f"免费榜Top10(#{bf})")
        elif bf <= 50:
            s += SCORE["free_top50"]
            reasons.append(f"免费榜Top50(#{bf})")

    # 3) 畅销榜 = 变现能力（有收入才能持续买量）
    gross = [c["topgrossingapplications"] for c in markets.values()
             if "topgrossingapplications" in c]
    if gross:
        bg = min(gross)
        s += SCORE["grossing_hit"]
        reasons.append(f"进畅销榜(#{bg})")
        if bg <= 50:
            s += SCORE["grossing_top50"]

    # 4) 起量窗口（最高权重）：新上架榜 + 免费榜同时出现
    new = [c["newfreeapplications"] for c in markets.values()
           if "newfreeapplications" in c]
    if new and free:
        s += SCORE["new_rising"]
        reasons.append("⭐新上架+免费榜双榜(起量窗口)")
        if min(new) <= 10:
            s += SCORE["new_app_rank"]
            reasons.append(f"新上架榜Top10(#{min(new)})")
    elif new:
        s += SCORE["new_rising"] * 0.5
        reasons.append("新上架榜(早期起量,尚未冲进免费榜)")

    # 5) 品类
    casual, src = is_casual(name, gset)
    if casual:
        s += SCORE["casual_genre"]
        reasons.append("休闲品类" + ("" if src == "商店品类" else "(关键词判定)"))

    # 6) 真环比：与上一份快照比，跨市场平均排名上升
    if prev_ranks:
        deltas = []
        for mk, ch in markets.items():
            for chart, rk in ch.items():
                old = prev_ranks.get(mk, {}).get(chart)
                if old:
                    deltas.append(old - rk)          # 正数 = 名次上升
        if deltas:
            avg = sum(deltas) / len(deltas)
            if avg >= 1:
                s += min(SCORE["rank_rise"] * (avg / 5), SCORE["rank_rise"] * 2)
                reasons.append(f"环比上升(平均+{avg:.0f}名)")

    # 7) 所属品类在本周换血
    if rising_genres and (gset & rising_genres):
        s += SCORE["cat_rising"]
        reasons.append(f"品类换血({'/'.join(sorted(gset & rising_genres))})")

    return round(s, 1), reasons, gset


def snapshot_index_from(snap):
    """把 defaultdict 索引拍平成普通 dict（好落盘、好比较）。"""
    return {k: dict(v) for k, v in build_index(snap).items()}


def pick(snap, prev=None, top_n=30, min_score=0):
    idx = build_index(snap)
    gmap = build_genre_map(snap)
    markets = snap.get("markets", [])
    cats = category_stats(snap, markets)

    # 「在换血」的品类 = 新品数排前 40% 且真的换过血(fresh>0)的那些。
    # 不取全量，否则每个品类都算换血，第 7 项加成退化成常数、失去区分度。
    rising_genres = set()
    if cats:
        cut = max(1, int(len(cats) * 0.4))
        rising_genres = {c["genre"] for c in cats[:cut] if c["fresh"] > 0}

    pidx = snapshot_index_from(prev) if prev else {}
    picks = []
    for name, mks in idx.items():
        sc, reasons, gset = score_game(name, mks, pidx.get(name),
                                       rising_genres, gmap)
        dev = dev_of(snap, name)
        ever, big = is_evergreen(name), is_big(dev)
        if ever:
            sc = round(sc + SCORE["big_malus"], 1)
            reasons.append("⚠️长青老游戏(降权)")
        elif not big:
            sc = round(sc + SCORE["sme_bonus"], 1)
            reasons.append("中小厂商(情报需求强)")
        if sc < min_score:
            continue
        af = {}
        for mk, ch in mks.items():
            for chart, rk in ch.items():
                af[f"{mk}_{chart}"] = rk
        casual, _ = is_casual(name, gset)
        picks.append({
            "name": name, "dev": dev, "score": sc, "reasons": reasons,
            "market_count": len(mks), "genres": sorted(gset),
            "is_casual": casual, "is_big": big, "is_evergreen": ever,
            "ranks": af,
            "best_free": min([v for k, v in af.items() if "topfree" in k], default=None),
            "best_gross": min([v for k, v in af.items() if "grossing" in k], default=None),
            "best_new": min([v for k, v in af.items() if "newfree" in k], default=None),
        })
    picks.sort(key=lambda x: -x["score"])
    return picks[:top_n], cats, rising_genres


def compare(cur, prev, top_n=15):
    """真环比。榜更新是小时/天级，短间隔两次快照会得到 0 条变动 —— 那是正常的，不是 bug。"""
    a, b = build_index(prev), build_index(cur)
    rows = []
    for name, mks in b.items():
        ds = []
        for mk, ch in mks.items():
            for chart, rk in ch.items():
                old = a.get(name, {}).get(mk, {}).get(chart)
                if old:
                    ds.append((old - rk, mk, chart, old, rk))
        if not ds:
            continue
        avg = sum(d[0] for d in ds) / len(ds)
        best = max(ds, key=lambda d: d[0])
        rows.append({"name": name, "avg": round(avg, 1),
                     "best_move": f"{best[1]}/{best[2]} #{best[3]}→#{best[4]}",
                     "points": len(ds), "new": False, "gone": False})
    for name in a:
        if name not in b:
            rows.append({"name": name, "avg": -999, "best_move": "跌出榜单",
                         "points": 0, "new": False, "gone": True})
    up = sorted([r for r in rows if not r["gone"] and r["avg"] > 0],
                key=lambda x: -x["avg"])[:top_n]
    down = sorted([r for r in rows if r["gone"] or r["avg"] < 0],
                  key=lambda x: x["avg"])[:top_n]
    return up, down, len(rows)


# ---------------------------------------------------------------------------
# 落盘与呈现
# ---------------------------------------------------------------------------

def latest(dirpath, pat="daily_*.json"):
    fs = sorted(glob.glob(os.path.join(dirpath, pat)))
    return fs[-1] if fs else None


def previous(dirpath, cur_path):
    """文件名是 daily_YYYYMMDD.json，字典序 = 时间序，sorted 取最后一个即上一份。"""
    fs = [f for f in sorted(glob.glob(os.path.join(dirpath, "daily_*.json")))
          if f != cur_path]
    return fs[-1] if fs else None


def tag_of(p):
    if p["is_evergreen"]:
        return "⚠️长青"
    return "🏢大厂" if p["is_big"] else "🔥中小"


def print_picks(picks, cats, window, newn=None, cov=None):
    W = 112
    print("=" * W)
    print(f"🎯 值得深入分析的手游产品（{window}）")
    print("=" * W)
    if cats:
        print("📈 品类榜　席位=进总榜款数(体量)　新品=上架即上榜款数(换血=飙升信号)")
        print(f"  {'品类':<12}{'新品':>6}{'席位':>6}{'换血率':>8}  判读")
        for c in cats[:8]:
            if c["fresh"] == 0:
                note = "存量盘（席位靠长青游戏占着，无新品）"
            elif c["rate"] >= 15:
                note = "⭐换血快"
            else:
                note = "有新品但换血一般"
            print(f"  {c['genre']:<12}{c['fresh']:>6}{c['seats']:>6}"
                  f"{str(c['rate'])+'%':>8}  {note}")
        if cov and cov.get("total"):
            print(f"  ℹ️ 品类归因覆盖 {cov['classified']}/{cov['total']} 款"
                  f"（{round(cov['classified']/cov['total']*100)}%）；"
                  f"未覆盖的苹果未挂子品类，席位是**下界**")
        if newn:
            print(f"  ⚠️ n：游戏新上架榜共 {newn} 款，样本小，新品数为**方向性信号**，"
                  f"不可外推为比例")
        print("-" * W)
    print(f"{'#':<3}{'游戏':<34}{'分':>6}{'市场':>5}{'免费':>5}{'畅销':>5}{'新品':>5}  "
          f"{'品类':<14}{'发行商':<22}分析理由")
    print("-" * W)
    for i, p in enumerate(picks, 1):
        f = f"#{p['best_free']}" if p["best_free"] else "-"
        g = f"#{p['best_gross']}" if p["best_gross"] else "-"
        n = f"#{p['best_new']}" if p["best_new"] else "-"
        genre = "/".join(p["genres"])[:13] or "-"
        print(f"{i:<3}{p['name'][:33]:<34}{p['score']:>6}{p['market_count']:>5}"
              f"{f:>5}{g:>5}{n:>5}  {genre:<14}{(p['dev'] or '')[:21]:<22}"
              f"{tag_of(p)} {' + '.join(p['reasons'][:3])}")
    print("-" * W)
    print("标签含义：🔥中小=优先（更缺素材情报工具）｜🏢大厂=有成熟情报体系｜"
          "⚠️长青=上榜久、素材体系成熟，已降权")
    print("品类来自 App Store 官方分类，**一款游戏可同时属于多个品类**（多标签），"
          "故各品类席位相加会大于候选总数。")


def write_brief(path, picks, cats, snap, wo, up=None, down=None, prev_ts=None,
                newn=None):
    ts = snap.get("ts", "")[:19].replace("T", " ")
    cov = snap.get("genre_coverage") or {}
    L = []
    # 章节号必须**动态生成**：环比那一段没有历史快照时整段不写，
    # 写死编号会让简报从「三、发行商信号」直接跳到「五、下一步」，看着像漏了一章。
    _sec = [0]
    _CN = "一二三四五六七八"

    def H(title):
        _sec[0] += 1
        L.append(f"## {_CN[_sec[0] - 1]}、{title}")
        L.append("")

    L.append("# 本周值得分析的手游 · 选品简报")
    L.append("")
    L.append(f"- **快照时间**：{ts}　**窗口**：{wo}")
    L.append(f"- **覆盖**：{len(snap.get('markets', []))} 市场 × {len(CHARTS)} 榜 × Top100"
             f"（App Store 官方榜单 · iTunes RSS）")
    if cov.get("total"):
        L.append(f"- **品类归因**：对免费榜与新上架榜出现过的 {cov['total']} 款游戏逐个取"
                 f"商店官方子品类，命中 {cov['classified']} 款"
                 f"（{round(cov['classified']/cov['total']*100)}%）。"
                 f"其余 {cov['total']-cov['classified']} 款苹果未挂子品类，按未分类处理")
    L.append("")

    H("飙升品类")
    L.append("两个因子一起看，缺一个都会看错：")
    L.append("")
    L.append("- **新品** = 该品类本周有多少款**上架即上榜**。新品能冲上来 = "
             "这个品类在换血、有新钱进来买量 —— 这才是「飙升」。")
    L.append("- **席位** = 该品类进总免费榜 Top100 的款数 = 榜上体量。"
             "只看席位会把长青盘（一堆老游戏占着位子）误判成热门。")
    if cov.get("total") and cov["classified"] < cov["total"]:
        L.append(f"- ⚠️ 席位与新品都只统计**已归因的 {cov['classified']} 款**"
                 f"（另 {cov['total']-cov['classified']} 款苹果未挂子品类）。"
                 f"所以席位是**下界**，不是该品类的完整体量。")
    L.append("")
    L.append("| 品类 | 新品 | 席位 | 换血率 | 判读 |")
    L.append("|:---|---:|---:|---:|:--|")
    for c in (cats or [])[:8]:
        if c["fresh"] == 0:
            j = "存量盘：席位靠长青游戏占着，无新品"
        elif c["rate"] >= 15:
            j = "⭐ 换血快，值得优先看"
        else:
            j = "有新品但换血一般"
        L.append(f"| {c['genre']} | **{c['fresh']}** | {c['seats']} | {c['rate']}% | {j} |")
    L.append("")
    if newn:
        L.append(f"> ⚠️ **样本量 n={newn}**（全部市场的游戏新上架榜款数总和）。这个 n 很小，"
                 f"「新品」是**方向性信号，不能外推成比例**，也不要在品类之间做精确排序。"
                 f"要更硬的品类结论，得回到 aggclaw 查该品类的广告数与素材数。")
        L.append("")

    H(f"值得分析的候选（Top {min(10, len(picks))}）")
    L.append("| # | 游戏 | 分数 | 市场 | 免费 | 畅销 | 品类 | 发行商 | 标签 | 分析理由 |")
    L.append("|:--|:--|--:|--:|--:|--:|:--|:--|:--|:--|")
    for i, p in enumerate(picks[:10], 1):
        f = f"#{p['best_free']}" if p["best_free"] else "-"
        g = f"#{p['best_gross']}" if p["best_gross"] else "-"
        L.append(f"| {i} | {p['name']} | {p['score']} | {p['market_count']} | {f} | {g} "
                 f"| {'/'.join(p['genres']) or '-'} | {p['dev'] or '-'} | {tag_of(p)} "
                 f"| {' + '.join(p['reasons'][:3])} |")
    L.append("")

    pubs = defaultdict(list)
    for p in picks[:30]:
        if p["dev"] and not p["is_evergreen"]:
            pubs[p["dev"]].append(p)
    multi = sorted([(d, v) for d, v in pubs.items() if len(v) >= 2],
                   key=lambda x: -len(x[1]))[:8]
    if multi:
        H("发行商信号（多产品同时在投 = 素材需求最大的客户）")
        L.append("| 发行商 | 在投产品数 | 代表产品 |")
        L.append("|:--|--:|:--|")
        for d, v in multi:
            tops = "、".join(x["name"] for x in sorted(v, key=lambda y: -y["score"])[:3])
            L.append(f"| {d} | {len(v)} | {tops} |")
        L.append("")

    if up or down:
        H("真环比" + (f"（对比 {prev_ts}）" if prev_ts else ""))
        if up:
            L.append("**上升**")
            L.append("")
            for r in up[:8]:
                L.append(f"- {r['name']}　平均 +{r['avg']} 名　{r['best_move']}")
            L.append("")
        if down:
            L.append("**掉队**")
            L.append("")
            for r in down[:8]:
                mv = r["best_move"] if r["gone"] else f"平均 {r['avg']} 名"
                L.append(f"- {r['name']}　{mv}")
            L.append("")

    H("下一步")
    L.append("选定标的直接进 `agg-overseas-report` 原报告流程"
             "（第 0 步判意图 → 第 1 步 aggclaw 取数 → …）。")
    if not prev_ts:
        L.append("")
        L.append("> ℹ️ 本期**没有历史快照，因此没有环比**。排行榜更新是小时/天级，"
                 "隔天再跑一次 `game_rank.py snapshot --pick` 就会出现"
                 "「上升 / 掉队」两节，选品打分里的「环比上升」加成也会生效。")
    L.append("")
    L.append("### 口径与边界")
    L.append("")
    L.append("- 榜单数据来自 **App Store 官方榜单（iTunes RSS）**，与报告正身的 "
             "AppGrowing 口径**不是同一个来源**，两边数字不可混用、不可互相验证。")
    L.append("- 本简报的数字**不进报告正文**；报告正文的数字仍须能追到 aggclaw 返回，"
             "或登记进 `work/derived.json`（铁律 2）。")
    L.append("- 品类是 App Store 官方分类，**多标签**：一款游戏可同时属于多个品类，"
             "所以各品类席位相加会大于总款数。")
    L.append("- 「新上架榜」在 Apple 的接口里**不认品类参数**，返回的是**全品类**新上架榜，"
             "本脚本按条目自带的 category 字段过滤出 Games（美国榜 100 款里只有约 10 款是游戏），"
             "所以它样本量天生很小。")
    L.append("- 榜单名次是**当日快照**，不是区间累计 —— 它回答「此刻谁在榜上」，"
             "不回答「这一周涨了多少」。排行榜更新为小时/天级，短间隔两次快照环比必然为 0 条。")
    L.append("- 榜单只反映「谁在榜上」，**不等于「谁在买量」** —— 起量是间接推断，"
             "买量的直接证据要回到 aggclaw 的广告数与素材数。")
    L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="手游榜单追踪 + 选品")
    ap.add_argument("cmd", nargs="?", default="pick",
                    choices=["snapshot", "pick", "compare", "categories", "all"])
    ap.add_argument("--dir", default=os.path.join("reports", "_rank"))
    ap.add_argument("--markets", default=None)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--pick", action="store_true", help="snapshot 后直接出选品")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    markets = (args.markets.split(",") if args.markets else MARKETS)
    os.makedirs(args.dir, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    wo = datetime.now().strftime("%Y-%m-%d")

    if args.cmd in ("snapshot", "all"):
        data, genres, n_cls, n_tot = snapshot(markets, args.workers)
        snap = {"ts": datetime.now().isoformat(), "window": wo,
                "markets": markets, "charts": CHARTS,
                "data": data, "game_genres": genres,
                "genre_coverage": {"classified": n_cls, "total": n_tot}}
        fn = os.path.join(args.dir, f"daily_{today}.json")
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)
        print(f"[3/3] 快照已落盘：{fn}  ({os.path.getsize(fn)//1024} KB)")
        if not args.pick and args.cmd == "snapshot":
            return

    fn = latest(args.dir, "daily_*.json")
    if not fn:
        print(f"[X] 没有快照。先跑：python scripts/game_rank.py snapshot --dir {args.dir}")
        sys.exit(1)
    with open(fn, encoding="utf-8") as f:
        snap = json.load(f)
    snap.setdefault("markets", markets)

    if args.cmd == "categories":
        cats = category_stats(snap)
        newn = new_sample_n(snap)
        print(f"{'品类':<14}{'新品':>6}{'席位':>6}{'换血率':>8}")
        for c in cats:
            print(f"{c['genre']:<14}{c['fresh']:>6}{c['seats']:>6}{str(c['rate'])+'%':>8}")
        if newn:
            print(f"\n⚠️ 游戏新上架榜样本 n={newn}，新品数为方向性信号，不可外推为比例。")
        return

    if args.cmd == "compare":
        pf = previous(args.dir, fn)
        if not pf:
            print(f"[!] 只有一份快照（{os.path.basename(fn)}），无法做环比。")
            print("    排行榜更新是小时/天级，需积累 2 份以上 —— 隔天再跑一次 snapshot 即可。")
            return
        with open(pf, encoding="utf-8") as f:
            prev = json.load(f)
        up, down, n = compare(snap, prev)
        print(f"环比：{os.path.basename(pf)} → {os.path.basename(fn)}　可比对 {n} 款\n")
        print("📈 上升")
        for r in up:
            print(f"  +{r['avg']:<5} {r['name'][:44]:<46}{r['best_move']}")
        print("\n📉 掉队")
        for r in down:
            print(f"  {r['best_move'][:52]:<54}{r['name'][:40]}")
        return

    # pick / all
    pf = previous(args.dir, fn)
    prev = None
    if pf:
        with open(pf, encoding="utf-8") as f:
            prev = json.load(f)
    picks, cats, rising = pick(snap, prev, top_n=args.top)
    newn = new_sample_n(snap)
    print(f"快照：{os.path.basename(fn)}　时间：{snap.get('ts','?')[:19].replace('T',' ')}"
          + (f"　环比基线：{os.path.basename(pf)}" if prev else
             "　（无历史快照，本次不含环比信号）"))
    print()
    print_picks(picks, cats, wo, newn, snap.get("genre_coverage"))

    pj = os.path.join(args.dir, f"picks_{today}.json")
    with open(pj, "w", encoding="utf-8") as f:
        json.dump({"ts": snap.get("ts"), "rise_genres": sorted(rising),
                   "new_sample_n": newn, "categories": cats, "picks": picks}, f,
                  ensure_ascii=False, indent=2)
    bf = os.path.join(args.dir, f"brief_{today}.md")
    up = down = None
    if prev:
        up, down, _ = compare(snap, prev)
    write_brief(bf, picks, cats, snap, wo, up, down,
                prev.get("ts", "")[:10] if prev else None, newn)
    print(f"\n选品结果：{pj}")
    print(f"选品简报：{bf}   ← 可直接贴飞书/邮件")
    if not prev:
        print("\n提示：这次没有历史快照，所以没有环比信号。明天同一条命令再跑一次，"
              "第 6 项「环比上升」加成就会生效。")


if __name__ == "__main__":
    main()
