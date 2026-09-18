#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google News 聚合 —— 「近 7 天资讯扫描」章节的数据源。

用法:
  python news.py fetch --dir <工作区> --queries "Clash of Clans,Supercell,手游买量" \
      [--days 7] [--lang en-US] [--max-per-query 100]
  python news.py list  --dir <工作区> [--top 30]
  python news.py pick  --dir <工作区> --idx 3,7,12,19

产出:
  <工作区>/raw/news_all.json    全部原始条目(去重后)
  <工作区>/raw/news_dropped.json 被剔除的条目(命中信源黑名单)
  <工作区>/work/news.json       人工挑出并补了 grade/dim 的条目(报告直接消费)

为什么单独一个脚本:
  投放数据的保真由 validate.py 对着接口返回来校验;资讯是**另一个来源**,
  不能混进那条通道,否则「保真」二字失效。本文件是资讯侧的独立规则集。

踩坑(必读):
  1. Google News 是**前端跳转**,离线 HTML 无法预解析最终地址 →
     报告里的按钮只能指向上游聚合入口,并必须在 cardnote 里向读者说明。
  2. 用**产品中文名**搜时,中文源的信源质量参差 →
     游戏类优先保留英文行业源;命中 BLACKLIST 的信源直接剔除。
  3. 报告**必须**含 ≥3 条外部资讯(下限 MIN_KEEP),且应尽量有优选白名单
     信源 —— 数量不足时先放宽检索词,仍不足才降级到厂商/品类层面,
     并必须在 cardnote 里显式写明「暂无该产品直接报道」。
"""
import io, os, re, sys, json, argparse, datetime
import urllib.request, urllib.parse
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# 第三方数据平台黑名单:其数据/排名/结论一律不得进入报告。命中即剔除。
BLACKLIST = (
    "sensortower.com", "appmagic.rocks", "appmagic.ai", "data.ai",
    "chanmama.com", "feigua.cn", "feigua.com", "kaogujia.com",
    "dataeye.com", "dataeye.cn", "diandian.com", "diandianzhibo.com",
    "reyun.com", "talkingdata.com",
)

# 优选信源白名单(53 家):命中即打 tier="优选"。
# **与上面的 BLACKLIST 不重叠** —— 白名单原本是 62 家行业媒体,剔除 9 家
# 第三方数据平台(SensorTower / QuestMobile / 七麦研究院 / DataEye 游戏观察 /
# DataEye 短剧观察 / 广大大出海笔记 / 广大大短剧笔记 / AI 产品榜 / AI 新榜)后剩 53 家。
# 剔除理由:它们是竞品数据平台,SKILL.md 铁律 #1 明令"禁引 Sensor Tower /
# AppMagic / data.ai 等竞品平台"——白名单不该与铁律自相矛盾。
WHITELIST = (
    # 游戏行业媒体(28)
    "GameLook", "GameLook 快讯", "GameRes 游资网", "游戏葡萄", "游戏陀螺", "游戏茶馆", "游戏日报",
    "游戏干线", "游戏新知", "游戏智库", "游戏研究社", "游戏联合体", "游戏价值论",
    "游戏客栈", "游戏寿司", "游戏那点事", "游戏吃瓜人", "游戏产业报告", "游戏财经汇",
    "游戏马可听", "竞核", "触乐", "罗斯基", "游鲨游戏圈", "游桃 Factory",
    "GameCentral", "GameFind", "GameQuest",
    # 出海与全球化(10)
    "白鲸出海", "扬帆出海", "独立出海联合体", "Enjoy 出海开发者服务平台",
    "Meetgames 游戏出海", "Android GO 出海", "出海观察", "点点出海",
    "E 哥带你去出海", "WaveGlocal",
    # 营销与商业媒体(10)
    "Morketing", "TopMarketing", "Fmarketing", "36 氪游戏", "极客公园",
    "硅星人", "娱乐资本论", "互联网怪盗团", "预言家游报", "天天开柒",
    # 短剧 / 微短剧(1)
    "短剧自习室",
    # 协会与官方(4)
    "中国音数协游戏工委", "广东省游戏产业协会", "ChinaJoy", "微信公开课",
)

# 直连可达的行业媒体 RSS —— **Google News 不可达时的兜底**。
# 实测(2026-09-17,本机):news.google.com 超时(WinError 10060),Clash 7897 未开,
# 而下面这几家直连可达。没有这层兜底,「外部媒体文章 ≥3 条」(铁律 11)在无代理的
# 机器上必然过不了,validate.py 会在交付前判 error。
#
# 与 Google News 的关键差别:这些是**主题 feed 不是搜索 feed**,拿回来的是一整个
# 站点的最新文章流,所以必须客户端按关键词过滤(见 _fetch_direct),而且命中的
# 多是**行业/品类层面**报道而非该产品直接报道 —— 按 SKILL「搜不到时的降级」
# 必须在 .cardnote 里显式写明「暂无该产品直接报道」。
FEEDS = (
    ("游戏陀螺",   "https://www.youxituoluo.com/feed"),
    ("白鲸出海",   "https://www.baijing.cn/feed"),
    ("游戏茶馆",   "https://www.youxichaguan.com/feed"),
    ("游戏研究社", "https://www.yystv.cn/rss/feed"),
    ("触乐",       "https://www.chuapp.com/feed"),
)

# 直连 feed 的缺省过滤词。产品名(如 Magic Sort)在中文行业媒体里基本搜不到,
# 所以真正起作用的是**品类/赛道词**。这批词是**实测挑出来的**(2026-09-17):
# 五家 feed 不限窗口合计命中 17 条,集中在 出海/买量/小游戏/IAA/变现/广告 上,
# 「休闲」「素材」这类词在这些站点里几乎不出现,别指望。
DEFAULT_TOPICS = ("出海,买量,休闲,超休闲,小游戏,IAA,变现,广告,投放,素材,"
                  "手游,海外,营销,留存")

# 直连 feed 的缺省窗口(天)。**必须比 Google News 的 7 天宽得多** ——
# 这些是低频站点 feed(游戏陀螺一个月才 3 条相关,白鲸出海已停更到 8/21),
# 套 7 天窗口实测只有 1 条,凑不满「≥3 条」这条硬闸门。
DIRECT_DAYS = 30

GRADES = ("高", "中", "低")
DIMS = ("IP 联动", "竞品动态", "平台政策", "成本趋势", "产品更新", "资本市场", "行业趋势")

# 资讯条数上限:服从「任何清单 ≤7」的结构铁律
CAP = 7
# 资讯条数**下限**:报告必须含外部媒体文章(见 SKILL.md 第 2 步硬闸门)。
# 这条下限是"必须有"的量化形式 —— 降到 0 条的报告不具备外部视角。
MIN_KEEP = 3


def _host(url):
    m = re.match(r"https?://([^/?#]+)", url or "", re.I)
    return (m.group(1).lower() if m else "")


def _clean_title(t):
    """Google News 标题尾部常带 ' - 媒体名',剥掉。"""
    return re.sub(r"\s*-\s*[^-]{2,40}$", "", (t or "").strip()).strip()


def _blocked(url):
    if any(b in _host(url) for b in BLACKLIST):
        return "黑名单信源"
    return ""


def _norm_src(s):
    """信源名归一:去空格/连字符/大小写,用于与白名单比对。"""
    return re.sub(r"[\s\-_·]+", "", (s or "").lower())


_WL_NORM = [(_norm_src(n), n) for n in WHITELIST]


def _tier(src):
    """信源分级:命中白名单 → "优选",否则空串。

    **双向包含**匹配 —— Google News 回的信源名粒度不一,同一家媒体
    可能回 "GameLook" 也可能回 "GameLook 快讯",单向包含会漏掉后者。
    """
    s = _norm_src(src)
    if len(s) < 2:
        return ""
    for norm, _ in _WL_NORM:
        if s in norm or norm in s:
            return "优选"
    return ""


def _locale_for(query, lang):
    """**关键**:hl/gl/ceid 必须与查询语言匹配。

    实测:用 hl=en-US 搜中文词「部落冲突」只回 1 条;换 hl=zh-CN&gl=CN&ceid=CN:zh 回 100 条。
    """
    if lang and lang != "auto":
        return lang, "US", "US:en"
    if re.search(r"[一-鿿]", query or ""):
        return "zh-CN", "CN", "CN:zh"
    return "en-US", "US", "US:en"


def _fetch_feed(query, lang="auto", days=7, max_items=100):
    """拉一个 Google News RSS,返回近 N 天内条目。"""
    hl, gl, ceid = _locale_for(query, lang)
    url = ("https://news.google.com/rss/search?q=%s&hl=%s&gl=%s&ceid=%s"
           % (urllib.parse.quote(query), hl, gl, ceid))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read()
    root = ET.fromstring(raw)
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        src_el = item.find("source")
        src = (src_el.text or "").strip() if src_el is not None else ""
        dt = None
        for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S GMT"):
            try:
                dt = datetime.datetime.strptime(pub, fmt).replace(tzinfo=datetime.timezone.utc)
                break
            except Exception:
                continue
        if dt and dt < cutoff:
            continue
        if not src:
            m = re.search(r"\s+-\s+([^-]{2,40})$", title)
            src = m.group(1).strip() if m else ""
        out.append({
            "dt": dt.isoformat() if dt else pub,
            "src": src,
            "title": title,
            "link": link,
            "query": query,
            "recent": True,
        })
        if len(out) >= max_items:
            break
    return out


def _parse_pub(pub):
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S GMT",
                "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.datetime.strptime(pub.strip(), fmt).replace(
                tzinfo=datetime.timezone.utc)
        except Exception:
            continue
    return None


def _fetch_direct(topics, days=7, max_items=60):
    """从 FEEDS 直连 RSS 里按关键词过滤。

    这些是主题 feed,不是搜索 feed:拿回来的是站点最新文章流,命中与否完全取决于
    关键词。所以过滤词要用**品类/赛道词**(休闲/买量/素材…),用产品名一条也捞不到。
    """
    kws = [k.strip().lower() for k in topics if k.strip()]
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    out, failed = [], []
    for name, url in FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                raw = r.read()
            root = ET.fromstring(raw)
        except Exception as e:
            failed.append("%s(%s)" % (name, type(e).__name__))
            continue
        for item in root.iter("item"):
            title = _clean_title((item.findtext("title") or "").strip())
            if not title:
                continue
            if kws and not any(k in title.lower() for k in kws):
                continue
            dt = _parse_pub(item.findtext("pubDate") or "")
            if dt and dt < cutoff:
                continue
            out.append({
                "dt": dt.isoformat() if dt else (item.findtext("pubDate") or ""),
                "src": name,
                "title": title,
                "link": (item.findtext("link") or "").strip(),
                "query": "直连RSS",
                "recent": True,
            })
            if len(out) >= max_items:
                return out, failed
    return out, failed


def cmd_fetch(a):
    raw_dir = os.path.join(a.dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    queries = [q.strip() for q in a.queries.split(",") if q.strip()]
    if not queries:
        sys.exit("[ERR] --queries 为空")

    seen, all_items, dropped = set(), [], []
    for q in queries:
        try:
            items = _fetch_feed(q, lang=a.lang, days=a.days, max_items=a.max_per_query)
        except Exception as e:
            print("  [WARN] %-28s 拉取失败: %s" % (q, e))
            continue
        kept = 0
        for it in items:
            why = _blocked(it["link"])
            if why:
                dropped.append(dict(it, drop=why))
                continue
            key = re.sub(r"[^a-z0-9一-鿿]", "", (it["title"] or "").lower())[:70]
            if key in seen:
                continue
            seen.add(key)
            it["title"] = _clean_title(it["title"])
            it["tier"] = _tier(it["src"])       # 优选白名单标记
            all_items.append(it)
            kept += 1
        print("  %-28s -> %d 条入池(原始 %d)" % (q, kept, len(items)))

    # Google News 一条没中(被墙/超时最常见) -> 走直连行业 RSS 兜底。
    # 不兜底就等于「无代理的机器永远交不出合规报告」。
    if not all_items:
        print("  [降级] Google News 未取到任何条目(被墙或超时),改用直连行业 RSS ...")
        topics = [t.strip() for t in (a.topics or DEFAULT_TOPICS).split(",") if t.strip()]
        items, failed = _fetch_direct(topics, days=a.direct_days,
                                      max_items=a.max_per_query)
        kept = 0
        for it in items:
            why = _blocked(it["link"])
            if why:
                dropped.append(dict(it, drop=why))
                continue
            key = re.sub(r"[^a-z0-9一-鿿]", "", (it["title"] or "").lower())[:70]
            if key in seen:
                continue
            seen.add(key)
            it["tier"] = _tier(it["src"])
            all_items.append(it)
            kept += 1
        print("  %-28s -> %d 条入池(原始 %d;过滤词 %s)"
              % ("直连RSS", kept, len(items), "/".join(topics)))
        if failed:
            print("  [WARN] 直连不可达: %s" % ", ".join(failed))

    # 稳定排序:先按时间倒序,再把优选源整段提到前面。
    # (Python 的 sort 是稳定的,所以第二次排序不会打乱组内的时间序)
    all_items.sort(key=lambda x: x.get("dt", ""), reverse=True)
    all_items.sort(key=lambda x: x.get("tier") != "优选")
    p = os.path.join(raw_dir, "news_all.json")
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=1)
    n_pref = sum(1 for it in all_items if it.get("tier") == "优选")
    print("\n[done] 入池 %d 条(其中优选信源 %d 条),剔除 %d 条 -> %s"
          % (len(all_items), n_pref, len(dropped), p))
    if n_pref == 0:
        print("[WARN] 本轮没有命中任何优选白名单信源 —— 挑条目时要靠人工判断信源质量,"
              "并在报告 .cardnote 里说明")

    if dropped:
        pd = os.path.join(raw_dir, "news_dropped.json")
        with io.open(pd, "w", encoding="utf-8") as f:
            json.dump(dropped, f, ensure_ascii=False, indent=1)
        from collections import Counter
        c = Counter(d["drop"] for d in dropped)
        print("[剔除] " + " / ".join("%s %d" % kv for kv in c.items()) + " -> " + pd)
        print("[提示] 剔除项均为第三方数据平台信源(铁律 1),不进入报告")


def cmd_list(a):
    p = os.path.join(a.dir, "raw", "news_all.json")
    items = json.load(io.open(p, encoding="utf-8"))
    n_pref = sum(1 for it in items if it.get("tier") == "优选")
    print("共 %d 条(优选 %d 条)\n" % (len(items), n_pref))
    for i, it in enumerate(items[:a.top]):
        mark = "[优选]" if it.get("tier") == "优选" else "      "
        print("[%3d]%s %s  %-22s  %s" % (
            i, mark, (it.get("dt") or "")[:10], (it.get("src") or "")[:22],
            (it.get("title") or "")[:78]))
    print("\n用 `python news.py pick --dir %s --idx 0,5,9,...` 挑出入报告的条目" % a.dir)


def cmd_pick(a):
    src = os.path.join(a.dir, "raw", "news_all.json")
    items = json.load(io.open(src, encoding="utf-8"))
    idxs = [int(x) for x in a.idx.split(",") if x.strip()]
    picked = []
    for i in idxs:
        if i < 0 or i >= len(items):
            print("  [skip] 越界索引 %d" % i)
            continue
        it = items[i]
        picked.append({
            "t": it.get("title", ""),          # 标题
            "date": (it.get("dt") or "")[:10],
            "src": it.get("src", ""),
            "tier": it.get("tier", ""),         # 优选 / 空
            "url": it.get("link", ""),
            "grade": "",                        # 人工填:高/中/低
            "dim": "",                          # 人工填:见 DIMS
            "d": "",                            # 人工填:一句话影响说明
        })
    wdir = os.path.join(a.dir, "work")
    os.makedirs(wdir, exist_ok=True)
    out = os.path.join(wdir, "news.json")
    if os.path.isfile(out) and not a.force:
        old = json.load(io.open(out, encoding="utf-8"))
        have = {(x.get("t") or "")[:50] for x in old}
        picked = old + [p for p in picked if (p.get("t") or "")[:50] not in have]
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump(picked, f, ensure_ascii=False, indent=1)
    print("[done] %d 条 -> %s" % (len(picked), out))
    n_pref = sum(1 for x in picked if x.get("tier") == "优选")
    print("[信源] 其中优选白名单信源 %d 条" % n_pref)
    if len(picked) < MIN_KEEP:
        print("[BLOCK] 只挑了 %d 条,低于下限 %d —— 报告必须含外部媒体文章。"
              % (len(picked), MIN_KEEP))
        print("        先放宽检索词(厂商名 / 品类买量 / 手游营销)重跑 fetch;")
        print("        确实搜不到该产品的直接报道时,可放宽到厂商/品类层面,"
              "但必须在报告 .cardnote 里显式写明「暂无该产品直接报道」。")
    elif n_pref == 0:
        print("[WARN] 没有一条来自优选白名单 —— 请在 .cardnote 里说明信源筛选取向")
    print("[下一步] 手工补 grade(高/中/低)、dim(维度)、d(一句话影响),然后才能进报告")
    # 只断言下限:上限在两处文档里口径不一(本文件 CAP=7,而 data-pipeline.md
    # 写「只留 15-20 条」、BLOCKS.md 的真实样例是 20 条),未擅自统一。
    print("[铁律] 条数**下限 %d**(报告必须有外部媒体文章);上限见 data-pipeline.md,"
          "不要全塞进报告" % MIN_KEEP)


def main():
    ap = argparse.ArgumentParser(description="Google News 聚合")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="拉取并去重")
    f.add_argument("--dir", required=True)
    f.add_argument("--queries", required=True, help="逗号分隔,建议 4 个主题词")
    f.add_argument("--days", type=int, default=7)
    f.add_argument("--lang", default="auto",
                   help="auto(默认,按查询语言自动选)= 推荐;也可强制 en-US / zh-CN")
    f.add_argument("--max-per-query", type=int, default=100)
    f.add_argument("--topics", default="",
                   help="直连RSS兜底的过滤词(逗号分隔);留空用 DEFAULT_TOPICS(%s)。"
                        "这是主题 feed,只有品类/赛道词有用,产品名捞不到东西"
                        % DEFAULT_TOPICS)
    f.add_argument("--direct-days", type=int, default=DIRECT_DAYS,
                   help="直连RSS兜底的窗口(天),默认 %d。这些是低频站点 feed,"
                        "窗口要比 Google News 的 7 天宽得多" % DIRECT_DAYS)
    f.set_defaults(func=cmd_fetch)

    l = sub.add_parser("list", help="列出去重后的条目")
    l.add_argument("--dir", required=True)
    l.add_argument("--top", type=int, default=30)
    l.set_defaults(func=cmd_list)

    p = sub.add_parser("pick", help="挑出入报告的条目")
    p.add_argument("--dir", required=True)
    p.add_argument("--idx", required=True)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_pick)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
