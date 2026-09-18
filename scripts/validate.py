#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""报告交付前自检。

用法:
  python validate.py <报告.html> --dir <工作区> [--strict]

  ⚠️ `--dir` 是**必给**的:不给就等于跳过数字保真与素材 ID 校验,那两项现在是 error,
  不是 warning。pitfalls #19 里记的旧命令没带 --dir,已同步修正。

检查项(每条都是踩过的坑,详见 references/pitfalls.md):
  [err] 1. 无 {{占位符}} 残留
  [err] 2. 所有 CSS 落在 <style> 块内        ← pitfall #1,最容易犯
  [err] 3. 导航锚点 ↔ 正文 id 一一对应(无死链)
  [err] 4. 素材卡片有 ID 徽标、7 位 hex、全站不重复
  [err] 4b. **素材卡可点可播**(是 <a href="…/material/全量ID">、封面有 video/img、
          无手绘 SVG 占位)—— 等价于「第 2 步素材实体化真的跑过」,见 pitfalls #21
  [err] 5. 每个 <canvas> 都有对应 id 且被 CHART_DRAW 引用
  [err] 6. 灯箱按钮 .gt-zoom 所在的 .gal-thumb 里有 <video>
  [err] 7. 含表/图的章节无 CDN 外链(离线自包含)
  [err] 8. 静态 <title> 已设置
  [err] 9. 容器同时有 video / img 规则(封面兜底不溢出)
  [err] 10. **数字保真**(命不中又没登记的判 FAIL)
  [err] 11. **数据源署名**统一且链接到 appgrowing.ai(铁律 1)
  [err] 12. **交互脑图自检**(有 #markmap 时):禁 autoloader、禁外链 <script src=…>、
          三个 mmk-* 依赖已内联且体积达标、mmk-md-* markdown 源在、boot 逻辑完整、
          pan:false + scrollForPan:true、CSS 覆盖 --markmap-* (暗色可读)。
          没有 #markmap → warn(不是错,可能本次确实不需要脑图)
          ⚠️ 本项按标签计数时**必须排掉假标签**(JS 注释 / HTML 注释里的示例),
          见下面 dead_spans 一节 —— 否则 boot 注释里的示例 md 源会被算成一份。
  [err] 14. **容器标签配平**(div/main/nav…):总数相等且深度全程非负。
          结构崩坏是唯一一类「其余闸门全绿也拦不住」的失效 —— 见 pitfalls #32
  [err] 13. **外部媒体文章 ≥3 条**(newsbtn 行/项计数)—— 「必须有外部媒体文章」
          的量化闸门;不足时先放宽检索词,再降级到厂商/品类层面但数量仍须 ≥3。
          资讯提要(结论摘要里的 newsbtn 列表项)缺失 → warn
  [warn]  一级导航 >7 / 孤儿章节 / 裸表裸图 / 体积 / 白名单外域名 …

退出码: 0 = 通过; 1 = 有 error

## 卡住(而不是报错)时的自救

报告内联了三块 1MB 级依赖后,`strip_vendor` 会把它换成**等长空白块**;在这块空白上
一个 `(?m)^\s*…` 形状的正则就能让整条命令**零输出挂死**(pitfall #28)。

所以本脚本自带看门狗:整轮超过 `--hang-timeout`(默认 90s)就**打印当前调用栈并退出**。
看到 `Timeout (0:01:30)!` + 栈里停在某个 `check_*` 函数,就说明那个函数里有回溯正则 ——
去把行首 `\s` 改成 `[ \t]`(`\s` 含 `\n`,是这类事故的固定配方)。

**为什么关键项必须是 error 而不是 warning**:本技能的整套可信度叙事
(「正文每个数字都要能追到接口字段或已登记」)建立在数字保真上。它一旦
掉在 warning 里,报告就能在**没跑过保真校验**的情况下拿到 "0 error" 并交付。
「0 error 才算过」这条验收标准,只有把关键项都设成 error 才成立。
"""
import io, os, re, sys, json, argparse

OK, WARN, ERR = "  OK  ", " WARN ", " FAIL "

# 铁律 1 的唯一合法数据源署名(措辞固定,shell.html 的 side-foot 已写死,别各处自行发挥)
SRC_NAME = "AppGrowing全球广告 AI 策略分析平台"
SRC_URL_RE = re.compile(r'href\s*=\s*["\']https?://(?:www\.)?appgrowing\.ai[/"\']', re.I)

# 外部媒体文章条数下限 —— 「每份报告必须有外部媒体文章」的量化形式。
# 与 news.py 的 MIN_KEEP 同值;改一处要改两处(两个脚本各自独立,不互相 import)。
MIN_NEWS = 3


class Report(object):
    def __init__(self):
        self.items = []
        self.n_err = 0
        self.n_warn = 0

    def ok(self, m):
        self.items.append((OK, m))

    def warn(self, m):
        self.items.append((WARN, m)); self.n_warn += 1

    def err(self, m):
        self.items.append((ERR, m)); self.n_err += 1

    def dump(self):
        print("")
        for lvl, m in self.items:
            print("[%s] %s" % (lvl, m))
        print("")
        print("=" * 62)
        print("  %d error / %d warning" % (self.n_err, self.n_warn))
        print("=" * 62)


def load(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


def style_spans(h):
    """返回所有 <style>...</style> 的 (start, end) 区间。"""
    out = []
    for m in re.finditer(r"<style[^>]*>", h):
        e = h.find("</style>", m.end())
        if e > 0:
            out.append((m.end(), e))
    return out


def in_spans(pos, spans):
    return any(s <= pos < e for s, e in spans)


# ---------------------------------------------------------------- 假标签排除
# 报告里「长得像标签、但其实只是文本」的地方有两类,凡按标签计数都得先排掉:
#
#   1. **脚本体**:shell.html 的 mmk-boot 里有一段 JS 块注释,举例写了
#      `<script type="text/markdown" id="mmk-md-zh">`(line 788)。裸扫标签会把
#      这段示例当成第 3 份 markdown 源 —— 实测「2 份(en/zh)」被判成「3 份」。
#   2. **HTML 注释**:同理,注释里贴的老代码 / 示例标签不该算数。
#
# 注意这和 mindmap.py 里 `has_mindmap` 收紧正则是**同一类问题的两种形态**:
# 那边是「JS 字符串 getElementById('markmap') 冒充 DOM 属性」,这边是
# 「JS 注释里的示例标签冒充真标签」。共同教训:HTML 是文本,搜标签必须带上下文。


def script_body_spans(h):
    """返回所有 <script> 的**体**区间 (body_start, close_tag_start)。

    `pos = c + 9` 直接跳到 `</script` 之后,所以体内再套多少层假标签都会被跳过,
    不会因为「外层没闭合又找到一个内层」而错乱。
    """
    out, pos, low = [], 0, h.lower()
    tag = re.compile(r"<script\b[^>]*>", re.I)
    while True:
        m = tag.search(h, pos)
        if not m:
            break
        c = low.find("</script", m.end())
        if c < 0:
            break
        out.append((m.end(), c))
        pos = c + 9
    return out


def dead_spans(h):
    """不该参与标签计数的区间:HTML 注释 + 脚本体。"""
    dead = script_body_spans(h)
    i = 0
    while True:
        s = h.find("<!--", i)
        if s < 0:
            break
        e = h.find("-->", s + 4)
        if e < 0:
            break
        dead.append((s, e + 3))
        i = e + 3
    return dead


def real_tags(h, pat):
    """按 pat 扫标签,但跳过 dead_spans 里的「假标签」。返回匹配列表。"""
    dead = dead_spans(h)
    return [m for m in re.finditer(pat, h, re.I) if not in_spans(m.start(), dead)]


# ---------------------------------------------------------------- JS 代码净化
def js_code(js):
    """剔掉 JS 注释,只留真会跑的 token(字符串字面量**保留**)。

    用途:判「引导脚本到底调了哪个 API」。反面例子(实测踩到):mmk-boot 的注释
    里为了说明「别用静态工厂 Markmap.create」,把那个调用原样写了一遍 ——
    裸搜 `Markmap.create(` 会把这段说明当成违规。这是 pitfall #29
    「判用法不判提及」在 JS 层的翻版:HTML 层有 dead_spans 兜着,JS 层没有。

    ⚠️ 为什么不用 `re.sub(r'//.*$')` 一刀切:boot 里有
    `createElementNS('http://www.w3.org/2000/svg',…)`,串里的 `//` 会被当注释,
    把那一行后半截**真代码**一起吃掉(实测)。所以这里是个小状态机。
    ⚠️ 字符串**不剔除**:要留的 token 里有 `data-mmk-fallback` 这种就长在串里。
    ⚠️ 正则字面量必须单独处理(这是实测踩到的第二个坑):boot 里有
    `.replace(/`([^`]+)`/g,'<code>…')` —— 这个正则里长着**反引号**。若把反引号
    一律当模板串引号,第 1 个反引号开串、第 2 个(在字符类 `[^`]` 里)就把它关了、
    第 3 个又开一次,而后面再无反引号可关 → **从此卡在字符串态**,
    后面所有注释都不再被剔除(那条"不许用 Markmap.create"的反向断言于是永远误报)。
    """
    # 正则 vs 除号:标准启发式 —— `/` 前面是这些字符(或什么也没有)时是正则开头。
    REGEX_PREV = "(,=:[!&|?{};+-*%~^"
    out, i, n, q, prev = [], 0, len(js), None, ""
    while i < n:
        c = js[i]
        nxt = js[i + 1] if i + 1 < n else ""
        if q:                                   # 串内:原样保留,只认转义与闭合
            out.append(c)
            if c == "\\":
                out.append(nxt); i += 2; continue
            if c == q:
                q = None
            i += 1; continue
        if c == "/" and nxt == "/":             # 行注释
            j = js.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and nxt == "*":             # 块注释
            j = js.find("*/", i + 2)
            i = n if j < 0 else j + 2
            out.append(" ")                     # 防 `a/*x*/b` 粘成 `ab`
            continue
        if c == "/" and (prev == "" or prev in REGEX_PREV):   # 正则字面量
            j, in_cls = i + 1, False
            while j < n:
                d = js[j]
                if d == "\\":
                    j += 2; continue
                if d == "\n":
                    break                       # 正则不跨行 → 防跑飞
                if d == "[":
                    in_cls = True
                elif d == "]":
                    in_cls = False
                elif d == "/" and not in_cls:
                    break
                j += 1
            end = min(j + 1, n)
            out.append(js[i:end]); i = end; prev = "/"
            continue
        if c in "\"'`":
            q = c; out.append(c); i += 1; continue
        out.append(c)
        if not c.isspace():
            prev = c
        i += 1
    return "".join(out)


# ---------------------------------------------------------------- vendor 中和
# 为什么要这层:报告现在把 d3 / markmap-lib / markmap-view 三个 vendor **内联**进
# 单文件(离线自包含,由 scripts/mindmap.py 注入在两个标记之间)。这些 JS 里天然
# 含有「看起来像我们的产物、其实只是库的字符串」的片段。
#
# ⚠️ 下面两条是**实测确认**的真误报(数字来自 report-good.html 实测,见 pitfall #27):
#
#   - `check_canvas` 调色板断言:**ERR 级真误报**。vendor 里天然有 7 处
#     `function v(` —— 不中和就必报「调色板函数名叫 v,会被告遮蔽」,中和后归 0。
#   - `check_offline` **WARN 级噪声**。vendor 里 `markmap-lib` 带一行
#     `jsdelivr: (path) => \`https://cdn.jsdelivr.net/npm/${path}\``(unpkg 同理),
#     它**不是** `src=`/`href=` 形态,所以 ERR 那条正则抓不到;但会落进下面
#     「白名单外域名」的兜底扫描 —— 不中和多出 7 个域名(cdn.jsdelivr.net /
#     unpkg.com / d3js.org / *.spec.whatwg.org / mathiasbynens.be / test1),
#     中和后归 0。
#
# ⚠️ 另外两点**别写错**(实测推翻过旧说法):
#
#   - `check_css_placement`:**实测两态都是 0 处**,vendor 里并没有「行首 `.x…{`」
#     形状(三个 vendor 文件该正则命中数均为 0)。它这里调 strip_vendor 纯属
#     **防御性**保留 —— 换 vendor 版本时可能变,但当前不是因为有误报才加的。
#   - autoloader 检查:**与 vendor 无关**。三个 vendor 文件里 `markmap-autoloader`
#     出现 **0 次**;全页仅 1 处,在 `shell.html` 的**注释**里(块外),中和 vendor
#     对它毫无作用。它属 pitfall #29(判「用法」不判「提及」),不属本条。
#
# 对策:校验前把 **BEGIN…END 之间的整块** 等长替换成空格(保留 \n,不改变 `(?m)^`
# 锚点行为与 offset)。只中和这一块、不抹全部脚本体,是刻意的 ——
# 正文里其它内联脚本仍参与扫描,真把 CSS 写进 <script> 或真引了 CDN 照样抓得到。
# `<!--MARKMAP_VENDOR:BEGIN…` / `:END-->` 两个常量与 scripts/mindmap.py 是同一条
# 协议;万一那边改了名,check_mindmap 会立刻报「依赖未内联」,不会静默漏检。
MKBEGIN = "<!--MARKMAP_VENDOR:BEGIN"
MKEND = "<!--MARKMAP_VENDOR:END-->"


def strip_vendor(h):
    """把注入的 vendor 块整体抹成等长空格(仅保留换行),长度与输入一致。"""
    m = re.search(re.escape(MKBEGIN) + r".*?" + re.escape(MKEND), h, re.S)
    if not m:
        return h
    blank = re.sub(r"[^\n]", " ", m.group(0))
    return h[:m.start()] + blank + h[m.end():]


def check_css_placement(h, r):
    """坑 #1:CSS 落到 </style> 外面 → 浏览器当正文渲染。

    ⚠️ 这里的 `strip_vendor` 是**防御性**的,不是因为有实测误报:三个 vendor 文件用
    下面这条正则实测命中均为 0(见 pitfall #27),换 vendor 版本时可能变,故保留。

    ⚠️⚠️ 行首缩进只许用 `[ \\t]`,**绝对不要写 `\\s`**(pitfall #28)。
    `\\s` 包含 `\\n`,于是 `^\\s*` 从任意行首起就能一路吃穿后面所有空行;
    而 strip_vendor 恰好把 1MB 依赖换成了**等长空白块** —— 在那上面这个正则
    不会报错、不会抛异常,只会**永远算不完**(灾难性回溯)。症状是整条命令
    零输出挂死,看着像崩溃,实际是永不返回。
    """
    h = strip_vendor(h)
    spans = style_spans(h)
    if not spans:
        r.err("找不到任何 <style> 块")
        return
    # 在 body 里找像 CSS 规则的东西
    body_at = h.find("<body")
    leaks = []
    for m in re.finditer(r"(?m)^[ \t]*([.#][-A-Za-z0-9_.#> \t,:\[\]=\"'()-]{2,80})[ \t]*\{", h):
        pos = m.start()
        if body_at > 0 and pos > body_at:
            leaks.append((pos, m.group(1).strip()[:60]))
    if leaks:
        r.err("CSS 规则落在 <body> 里(会被当正文渲染)—— %d 处,首个: %r"
              % (len(leaks), leaks[0][1]))
        r.items.append((ERR, "  修法: html.replace('</style>', CSS + '</style>'),不要 replace('</head>')"))
    else:
        r.ok("CSS 全部落在 <style> 块内(%d 块)" % len(spans))


def check_placeholders(h, r):
    ph = re.findall(r"\{\{[A-Za-z_ ]+\}\}", h)
    if ph:
        uniq = sorted(set(ph))
        r.err("残留占位符 %d 处: %s" % (len(ph), ", ".join(uniq[:8])))
    else:
        r.ok("无占位符残留")


def check_nav(h, r):
    nav_m = re.search(r'<nav class="side"[^>]*>(.*?)</nav>', h, re.S)
    if not nav_m:
        r.err("找不到 <nav class=\"side\">")
        return
    nav = nav_m.group(1)
    links = re.findall(r'<a class="toc-(h2|h3)" href="#([^"]+)"', nav)
    hrefs = [x[1] for x in links]
    h2s = [x[1] for x in links if x[0] == "h2"]

    ids = set(re.findall(r'<h[2-6][^>]*\bid="([^"]+)"', h))
    ids |= set(re.findall(r'\bid="([^"]+)"', h))

    dead = [x for x in hrefs if x not in ids]
    if dead:
        r.err("导航死链 %d 个: %s" % (len(dead), ", ".join(dead[:6])))
    else:
        r.ok("导航 %d 个锚点全部有效(%d 个一级)" % (len(hrefs), len(h2s)))

    if len(h2s) > 7:
        r.warn("一级导航 %d 章 > 7 —— 结构铁律要求 ≤7,建议合并" % len(h2s))

    # 孤儿章节:有 id 的 h2 不在导航里
    body_h2 = re.findall(r'<h2[^>]*\bid="([^"]+)"', h)
    orphan = [x for x in body_h2 if x not in hrefs]
    if orphan:
        r.warn("正文有 h2 未进导航 %d 个: %s" % (len(orphan), ", ".join(orphan[:6])))
    else:
        r.ok("无孤儿章节")


def check_gallery_ids(h, r, dir_):
    """每张素材卡片都该有 ID 徽标;有 --dir 时核对 ID 是否在取数清单内。"""
    badges = re.findall(r'<span class="b-lang">([^<]+)</span>', h)
    if badges:
        bad = [b for b in badges if not re.fullmatch(r"[0-9a-f]{7}", b.strip())]
        if bad:
            r.err("有 %d 个卡片 ID 徽标不是 7 位 hex: %s"
                  % (len(bad), ", ".join(sorted(set(bad))[:5])))
        else:
            r.ok("素材卡片 %d 张,ID 徽标格式正确(7 位 hex)" % len(badges))
        dup = len(badges) - len(set(badges))
        if dup:
            r.err("卡片 ID 有 %d 个重复(违反铁律 6:全站素材只出现一次)" % dup)
    else:
        r.err("没找到任何素材卡片 ID 徽标(.b-lang)—— 证据链要求每张卡片可点回素材")

    # 与取数清单核对
    if dir_:
        cj = os.path.join(dir_, "work", "covers.json")
        if os.path.isfile(cj):
            covers = json.load(io.open(cj, encoding="utf-8"))
            short = {k[:7]: k for k in covers}
            miss = [b for b in badges if b.strip() not in short]
            if miss:
                r.err("有 %d 张卡片的 ID 不在 covers.json 里: %s"
                      % (len(miss), ", ".join(sorted(set(miss))[:5])))
            else:
                r.ok("全部卡片 ID 都能在 covers.json 对上")
        else:
            r.err("未找到 %s,ID 核对被跳过 —— 不得在未核对的情况下交付" % cj)


def check_videos(h, r):
    """gt-zoom 灯箱按钮所在的 gal-thumb 里必须有 <video>,否则点了没反应。"""
    bad = 0
    for m in re.finditer(r'<div class="gal-thumb">(.*?)</div>\s*<div class="gal-main">', h, re.S):
        blk = m.group(1)
        if "gt-zoom" in blk and "<video" not in blk:
            bad += 1
    if bad:
        r.err("有 %d 个 .gt-zoom 灯箱按钮所在容器里没有 <video> —— 点击会打不开" % bad)
    else:
        r.ok("灯箱按钮与视频配对正确")

    nv = h.count("<video")
    if nv:
        r.ok("内嵌视频 %d 个" % nv)


def check_img_rules(h, r):
    """封面兜底时卡片里放的是 <img>,容器必须同时有 img 规则,否则图片溢出。"""
    css = "".join(h[s:e] for s, e in style_spans(h))
    # 容器 = 任何「.cls video」出现在选择器里的类,兼容 `X video{` 与 `X video,...{`
    containers = set(m.group(1) for m in re.finditer(r"\.(\w[\w-]*)\s+video\s*[,{]", css))
    bad = [c for c in sorted(containers)
           if not re.search(r"\.%s\s+img\s*[,{]" % re.escape(c), css)]
    if bad:
        r.items.append((ERR, "容器 %s 只有 video 规则、没有 img 规则 —— 封面兜底时 <img> 会溢出"
                             % ", ".join("." + c for c in bad)))
        r.items.append((ERR, "  修法: 补 .xxx img{width:100%;height:100%;object-fit:cover}"))
        r.n_err += 1
    else:
        r.ok("封面容器 video / img 规则齐备(%d 个)" % len(containers))

    n_img = len(re.findall(r'class="mcover"><img', h))
    n_vid = len(re.findall(r'class="mcover"><video', h))
    if n_img or n_vid:
        r.items.append((OK, "素材卡:内嵌视频 %d 张 / 封面兜底 %d 张" % (n_vid, n_img)))


def check_material_cards(h, r):
    """素材卡片必须是**可点、可播**的实体,不能退化成裸 <div>。

    **为什么要单列这一条**:曾经交付过一份「代表素材区块看起来很正常」的报告 ——
    14 张卡片排版整齐、ID 徽标齐全、validate 全绿 —— 但读者点不动、也播不了。
    根因是两件事同时发生:

      1. 卡片写成了 `<div class="mcard">`(裸 div),**没有 href** → 无跳转;
         写法是「手绘 SVG 占位图」而不是真封面 → 无 <video>、无 <img>。
      2. 第 2 步「素材实体化」根本没跑 —— 没跑就不会报错,卡片就静默退化了。

    旧校验只查了「ID 徽标在不在 covers.json 里」,于是**退化的卡片照样全绿通过**。
    所以这里补上三条**只有真跑过媒体步骤才可能满足**的结构断言:

      - 每张 .mcard 都是 <a href="…/material/{full_id}">,不是 div
      - href 里的 ID 是**全量 ID**(32 位 hex + 可选 -201/-202 后缀),不是 7 位截断
      - 每张 .mcard 的封面容器里有 <video> 或 <img>,且**不含 <svg>**

    这三条合起来等价于「媒体步骤真的跑过」,把第 2 步从「文档里的建议」变成硬闸门。
    """
    # 卡片总数以 .mcard 为准(比 .b-lang 更准:徽标可能被误写在别处)
    n_card = len(re.findall(r'class="mcard"', h))
    if not n_card:
        r.err("没找到任何 .mcard 素材卡片 —— 代表素材区块缺失(证据链要求卡片可点可播)")
        return

    # ① 必须是 <a ...> 且带 material 详情页链接
    opens = re.findall(r'<(a|div)[^>]*class="mcard"[^>]*>', h)
    n_div = sum(1 for t in opens if t == "div")
    hrefs = re.findall(
        r'<a[^>]*class="mcard"[^>]*href="([^"]+)"', h)
    if n_div:
        r.err("有 %d 张素材卡是裸 <div> 而不是 <a> —— 读者点不动(必须包一层 "
              "<a href=\"…/material/<全量ID>\">)" % n_div)
    bad_href = [u for u in hrefs
                if not re.search(r"/material/[0-9a-f]{32}(?:-\d+)?$", u)]
    if bad_href:
        r.err("有 %d 张素材卡的跳转链接格式不对(要求 …/material/<32位hex>[-201/-202]): %s"
              % (len(bad_href), ", ".join(sorted(set(bad_href))[:3])))
    if hrefs and not n_div and not bad_href:
        r.ok("素材卡全部可点: %d 张卡都带 material 详情页全量 ID 链接" % len(hrefs))

    # ② 封面容器里必须有真媒体,且不能是手绘 SVG
    blocks = re.findall(r'class="mcard".*?(?=class="mcard"|\Z)', h, re.S)
    n_media = n_svg = 0
    for b in blocks:
        cov = re.search(r'class="mcover">(.*?)</div>', b, re.S)
        seg = cov.group(1) if cov else b
        if "<video" in seg or "<img" in seg:
            n_media += 1
        if "<svg" in seg:
            n_svg += 1
    if n_svg:
        r.err("有 %d 张素材卡的封面是手绘 <svg> 占位图 —— 说明第 2 步「素材实体化」"
              "没跑成,卡片会退化" % n_svg)
    if n_media < n_card:
        r.err("有 %d 张素材卡封面里没有 <video> / <img> —— 卡片是空壳"
              % (n_card - n_media))
    elif not n_svg:
        r.ok("素材卡全部可播: %d 张卡封面容器都有真媒体(video/img),无 SVG 占位"
             % n_media)


def check_canvas(h, r):
    ids = re.findall(r'<canvas[^>]*\bid="([^"]+)"', h)
    if not ids:
        r.warn("报告里没有 <canvas>")
        return
    draw_m = re.search(r"window\.CHART_DRAW\s*=\s*function\s*\(\)\s*\{(.*?)\n\};", h, re.S)
    body = draw_m.group(1) if draw_m else h
    missing = [i for i in ids if ("'%s'" % i) not in body and ('"%s"' % i) not in body]
    if missing:
        r.err("<canvas> 定义了但 CHART_DRAW 没画 %d 个: %s" % (len(missing), ", ".join(missing)))
    else:
        r.ok("<canvas> %d 个,全部在 CHART_DRAW 里有对应绘制" % len(ids))

    # 调色板辅助函数别被 forEach 的回调变量 v 遮蔽。
    #   ⚠️ 这条断言**必须先中和 vendor**(pitfall #27 第二次踩到)。内联的 d3 /
    #   markmap bundle 里天然含有 `function v(`(实测全页 7 处,**全部来自 vendor**,
    #   正文 0 处),不中和就是每份报告必报的假 FAIL,而它指向的"罪名"极具体
    #   (调色板函数重名),人很容易照着去改一份本来就正确的报告。
    #   注意这里**不能**用 real_tags:调色板函数本身写在正文内联 <script> 里,
    #   real_tags 会连脚本体一起跳过 → 变成永不报错的假阴性。
    #   中和 vendor 才同时满足"不去掉正文脚本"和"不误报依赖"两点。
    hp = strip_vendor(h)
    if re.search(r"function\s+v\s*\(", hp) and re.search(r"forEach\(function\s*\(\s*v\s*,", hp):
        r.err("调色板辅助函数名叫 v,会被 forEach(function(v,...)) 遮蔽 → 运行时 TypeError")
    else:
        r.ok("调色板辅助函数命名无遮蔽风险")


def check_blockquotes(h, r):
    """每个数据章节末尾该有 blockquote 结论,不要裸表裸图。"""
    secs = re.split(r'(?=<h2[^>]*\bid=")', h)
    naked = []
    for s in secs:
        if not re.match(r'<h2[^>]*\bid="', s):
            continue
        title = re.search(r"<h2[^>]*>(.*?)</h2>", s, re.S)
        t = re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else "?"
        if "<table" in s or "<canvas" in s:
            if "<blockquote" not in s:
                naked.append(t[:30])
    if naked:
        r.warn("有 %d 个含表/图的章节没有 blockquote 结论: %s"
               % (len(naked), " | ".join(naked[:4])))
    else:
        r.ok("所有含表/图的章节都有 blockquote 结论")


def check_size(h, r):
    n = len(h.encode("utf-8"))
    mb = n / 1048576.0
    b64 = sum(len(m) for m in re.findall(r"base64,[A-Za-z0-9+/=]+", h))
    r.items.append((OK, "文件 %.1f MB(base64 占 %.1f MB)" % (mb, b64 / 1048576.0)))
    if mb > 40:
        r.warn("文件 >40MB,离线打开会卡。考虑压缩封面或减少内嵌视频")
    if "<img" in h and "loading=" not in h:
        r.warn("有 <img> 未加 loading=\"lazy\" —— 大图会让滚动卡顿")


def check_news(h, r):
    """外部媒体文章闸门 —— 报告必须含 ≥3 条资讯。

    判据是 **`newsbtn` 链接所在的行/项** —— 刻意与 fidelity 的资讯豁免
    用同一个标记,这样「被计入条数的」和「被豁免保真的」是同一批元素,
    不会出现两边各算各的。

    条数下限对应产品要求「每份报告必须有外部媒体文章」。搜不到该产品的
    直接报道时可以降级到厂商/品类层面,但**数量仍须 ≥3**,且必须显式标注
    (标注是文字判断,脚本管不了,列在 SKILL.md 的交付清单里人工确认)。
    """
    rows = re.findall(r"<tr\b(?:(?!</tr>).)*?newsbtn(?:(?!</tr>).)*?</tr>",
                      h, re.S | re.I)
    lis = re.findall(r"<li\b(?:(?!</li>).)*?newsbtn(?:(?!</li>).)*?</li>",
                     h, re.S | re.I)
    n = len(rows) + len(lis)
    if n == 0:
        r.err("报告里没有任何外部媒体资讯(newsbtn)—— 违反「必须有外部媒体文章」。"
              "先跑 `python scripts/news.py fetch/pick` 取资讯,再放进报告")
    elif len(rows) < MIN_NEWS:
        r.err("外部媒体资讯完整清单只有 %d 条(<%d)—— 先放宽检索词补数"
              "(厂商名 / 品类买量 / 手游营销);确实没有该产品的直接报道时,"
              "可降级到厂商或品类层面,但**数量仍须 ≥%d**"
              % (len(rows), MIN_NEWS, MIN_NEWS))
    else:
        r.ok("外部媒体资讯 %d 条(清单 %d / 提要 %d,下限 %d)"
             % (n, len(rows), len(lis), MIN_NEWS))
    if not lis:
        r.warn("资讯提要缺失 —— 结论摘要章节应放 1-2 条关键动态(newsbtn 列表项),"
               "与外部环境章的完整清单形成「两处」呈现")


def check_offline(h, r):
    r"""离线自包含硬约束:CDN 外链属交付缺陷(移植自 check.py §2c)。

    ⚠️ 先中和 vendor 块:内联 vendor(`markmap-lib`)的 `npm2url` 里带一行
    ``jsdelivr: (path) => `https://cdn.jsdelivr.net/npm/${path}` ``(unpkg 同理)。
    注意它**不是** `src=`/`href=` 形态 —— 所以上面那条 ERR 正则本来就抓不到它;
    真正被它污染的是下面「白名单外域名」的**兜底 WARN** 扫描:不中和会多报 7 个
    域名(cdn.jsdelivr.net / unpkg.com / d3js.org / *.spec.whatwg.org /
    mathiasbynens.be / test1),中和后归 0(实测,见 pitfall #27)。
    中和的只是 vendor 那一块,`<script src=…>` / `<link href=…>` 这些**标签属性**
    仍在,所以真的引了外链照样抓得到。
    """
    m = strip_vendor(h)
    cdn = re.compile(r"""(?:src|href)\s*=\s*["'][^"']*"""
                     r"""(?:jsdelivr|unpkg|cdnjs|googleapis|gstatic|bootstrapcdn)[^"']*""")
    hits = set(cdn.findall(m))
    if hits:
        r.err("产物含 CDN 外链(违反离线自包含):%s" % ", ".join(sorted(hits)[:5]))
    else:
        hosts = set(re.findall(r"https?://([a-z0-9.-]+)", m))
        hosts -= {"appgrowing.ai", "www.appgrowing.ai",
                  "appgrowing-global.youcloud.com", "news.google.com",
                  "www.w3.org",
                  "s.ymapp.com"}          # 官方注册短链(历史写法,仍在白名单)
        # 邀请注册链接由每个销售自带,域名不固定 —— 动态剔掉,免得每次多报一条
        # 无意义的「白名单外域名」,把真正需要看的被引链接淹掉。
        m_inv = re.search(r'class="[^"]*\bregcta\b[^"]*"[^>]*href="https?://([^"/?#]+)',
                          m)
        if m_inv:
            hosts.discard(m_inv.group(1))
        hosts = {d for d in hosts if not d.endswith(".appgrowing.ai")}
        r.ok("CDN 外链 = 0")
        if hosts:
            r.warn("出现白名单外的域名(资讯信源/被引链接属正常,确认无运行时依赖):%s"
                   % ", ".join(sorted(hosts)[:8]))


def check_misc(h, r):
    if "<title>" in h:
        t = re.search(r"<title>(.*?)</title>", h, re.S).group(1).strip()
        if not t or "{{" in t:
            r.err("静态 <title> 未设置(导出 PDF / 书签读的是它)")
        else:
            r.ok("静态标题: %s" % t[:50])
    for pat, msg in [(r'<b></b>', "残留空 <b></b>"),
                     (r"{{THEME_CSS}}", "主题槽未替换"),
                     (r"var DATA=", "混入了 report-full.html 的 DATA 驱动壳(本技能不用)")]:
        if re.search(pat, h):
            r.warn(msg)


def check_brand(h, r):
    """品牌与注册入口必须**整段照抄** shell.html,不许删改(2026-09 起)。

    为什么是 err 而不是 warn:报告是对外交付物 —— 左上角 AppGrowing 标识、
    网页标签图标、右上角注册引导按钮、PDF 页脚品牌条,这四件是报告被分享出去后
    唯一能把客户导回 AppGrowing 的入口。少任何一件,商业闭环就断了,而
    **其余所有检查都会是绿的**(它们只关心报告本身完不完整)。

    判定口径:只认真实元素与真实链接,注释里提一句不算
    (沿用 pitfall #29「判用法不判提及」)。
    """
    body = h
    m = re.search(r'<body\b[^>]*>(.*)', h, re.S | re.I)
    if m:
        body = m.group(1)
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)

    misses = []
    # 注册邀请链接:每个销售填自己那条(见 references/setup.md),所以**不能**查固定短链,
    # 只能查「有没有填上」+「两处是不是同一条」。
    reg = re.search(r'<a[^>]*class="[^"]*\bregcta\b[^"]*"[^>]*>', body)
    reg_href = ""
    if not reg:
        misses.append("右上角注册引导按钮 .regcta 缺失")
    else:
        m_href = re.search(r'href="([^"]*)"', reg.group(0))
        reg_href = (m_href.group(1) if m_href else "").strip()
        if not reg_href or reg_href.startswith("{{"):
            misses.append("右上角注册按钮 href 还是空槽位"
                          "—— 必须填销售本人的邀请注册链接 INVITE_URL")
        elif not re.match(r"https?://", reg_href):
            misses.append("注册按钮链接不是 http(s) 地址:%s" % reg_href[:40])

    pb = re.search(r'<a[^>]*class="[^"]*\bpb-cta\b[^"]*"[^>]*>', body)
    if not pb:
        misses.append("PDF 页眉品牌条里的注册链接 .pb-cta 缺失"
                      "(PDF 里按钮点不到,只能靠这行地址导流)")
    else:
        m_pb = re.search(r'href="([^"]*)"', pb.group(0))
        pb_href = (m_pb.group(1) if m_pb else "").strip()
        if not pb_href or pb_href.startswith("{{"):
            misses.append("PDF 页眉注册链接还是空槽位")
        elif not re.match(r"https?://", pb_href):
            misses.append("PDF 页眉链接不是 http(s) 地址:%s" % pb_href[:40])
        elif reg_href and pb_href != reg_href:
            misses.append("PDF 页眉链接与右上角按钮链接不一致(两处必须是同一条邀请链接)")

    if not re.search(r'class="[^"]*\bprintbar\b', body):
        misses.append("PDF 页脚品牌条 .printbar 缺失"
                      "(打印时 LOGO 与按钮会被 display:none,只剩它能露品牌)")
    if "--agg-logo" not in h:
        misses.append("品牌 LOGO 变量 --agg-logo 缺失(左上角标识会空白)")
    if not re.search(r'<link[^>]+rel="icon"', h):
        misses.append('网页标签图标 <link rel="icon"> 缺失')

    if misses:
        r.err("品牌/转化入口不完整:%s —— 整段照抄 shell.html,不要删改。"
              % ";".join(misses))
    else:
        r.ok("品牌与注册入口齐备(LOGO / favicon / .regcta / .printbar),"
             "邀请链接已填:%s" % reg_href)


def check_source_badge(h, r):
    """铁律 1:数据源署名必须统一,且可点回官网。

    以前这条只写在文档里、没有任何机械执行手段,而 shell 里也没有署名槽位 ——
    结果同一系列报告出现三种写法(「appgrowing.ai」/「AppGrowing Global 广告素材
    分析平台」/「AppGrowing全球广告 AI 策略分析平台」)。现在把它变成闸门,
    措辞由 shell.html 的 side-foot 统一提供,报告侧只需不删。
    """
    has_name = SRC_NAME in h
    has_link = bool(SRC_URL_RE.search(h))
    if not has_name:
        r.err("缺少数据源署名「%s」(铁律 1);shell.html 的 side-foot 已内置,不要删"
              % SRC_NAME)
    if not has_link:
        r.err("数据源署名没有链接到 appgrowing.ai(铁律 1)")
    if has_name and has_link:
        r.ok("数据源署名与官网链接齐备")


def md_sources(h):
    """取**真正的** markdown 数据源,返回 [(lang, body)](lang 已小写)。

    一律走 real_tags —— 跳过 HTML 注释与**所有**脚本体,只在正文里找。
    历史教训(pitfall #29):④ 和 ⑨ 起初各写一份正则、各自演化,结果 ④ 走
    real_tags 拿到了正确的 2 份,⑨ 用**裸** `re.finditer(r'<script…id="mmk-md-…">(.*?)</script>')`
    却先命中 boot 注释里那行示例文字 `<script type="text/markdown" id="mmk-md-zh">`,
    再一路 lazy 吃到下一个 `</script>` —— 于是**一份完全正常的报告**被判
    「mmk-md-zh 里没有 markdown 结构(缺 `# 标题` / `- 列表`)」。这个假 FAIL
    的罪名极具体,人会照着去改一份本来就正确的报告。

    中途曾给 ⑨ 单独打过 `md_source_hazards` 补丁(只排除 <style>/注释/boot 脚本体),
    那个方向是错的:它挡不住「写在**其它**内联脚本体里的示例标签」,而 ④ 用的
    real_tags 挡得住 —— 同一份文件里两套口径迟早再次分叉。所以此处收敛成一个函数,
    ④/⑨ 共用同一份结果,「几份源」「源里有没有结构」不可能再给出互相矛盾的答案。

    取 body 的办法:从真标签结尾到**其后第一个** `</script>`,与浏览器一致。
    """
    out = []
    for m in real_tags(h, r"<script\b[^>]*>"):
        tag = m.group(0)
        if not re.search(r'type\s*=\s*["\']text/markdown["\']', tag, re.I):
            continue
        lm = re.search(r'id\s*=\s*["\']mmk-md-([A-Za-z][A-Za-z-]{1,4})["\']', tag, re.I)
        if not lm:
            continue
        e = h.lower().find("</script", m.end())
        out.append((lm.group(1).lower(), h[m.end():e] if e > 0 else ""))
    return out


def check_mindmap(h, r):
    """交互脑图自检(pitfall #26 / #27 / #29)。

    本技能的「迭代脑图」= 线性承接图(阶段一→二→三)+ Markmap 交互脑图。
    后者走的是 shell.html 里那套**固定层**:自己 transform + create、自己降级、
    依赖由 scripts/mindmap.py 内联。这套设计有个静默失效模式 ——
    **漏跑注入**:页面上只剩一段没渲染的 markdown,而旧校验全绿照样交付。

    所以这里把它变成闸门。核心断言都是「只有真跑过 mindmap.py 才可能满足」:
      ① 没有 markmap-autoloader(它靠运行期 import 拉 CDN,失败即静默不渲染)
      ② 没有外链 <script src=…>(离线铁律)
      ③ mmk-d3 / mmk-lib / mmk-view 三个脚本已内联,且**内容指纹 + 体积**达标
      ④ mmk-md-* markdown 数据源存在
      ⑤ mmk-boot 引导脚本的关键逻辑在(实例化+setData 串行 / transform /
         replaceChild 重建 / degrade 降级 / 滚轮策略),且**没有**用回静态工厂
         Markmap.create(它丢 promise,会让 queue 空串行化)
      ⑥ CSS 覆盖了 --markmap-*(否则暗色主题下节点文字不可读)
    """
    # 指纹 / 判定函数一律从 mindmap.py 取,避免两处各写一份、改版本时失联。
    # ⚠️ 这个 import 必须是**纯离线**的:mindmap.py 的网络访问(urlopen 下载 vendor 包)
    #    被刻意关在 download() 函数体里,所以这里 `import mindmap` 只拿常量、不碰网络。
    #    谁要是把发请求的代码挪到模块顶部,这个纯离线校验器就会变成「可能挂在 DNS 上」。
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import mindmap
        vendor, check_js = mindmap.VENDOR, mindmap.check_js
        auto_use, has_mm = mindmap.AUTO_USE, mindmap.has_mindmap
    except ImportError:
        vendor = [dict(id="mmk-d3", min_kb=200),
                  dict(id="mmk-lib", min_kb=400),
                  dict(id="mmk-view", min_kb=30)]
        check_js = lambda it, t: (len(t) >= it["min_kb"] * 1024,
                                  "%d KB(< %d KB)" % (len(t) // 1024, it["min_kb"]))
        auto_use = re.compile(
            r"""(?:src|href)\s*=\s*["'][^"']*markmap-autoloader"""
            r"""|(?:import|require)\s*\(\s*["'][^"']*markmap-autoloader""", re.I)
        has_mm = lambda x: bool(
            re.search(r'<[a-zA-Z][^>]*\bid\s*=\s*["\']markmap["\'][^>]*>', x))

    # ⚠️ 判定用 has_mindmap 而不是裸搜 `id="markmap"`:boot 脚本里写着
    # `getElementById('markmap')`,裸搜会让**每份报告**都被当成有脑图。
    # 本函数里凡是"判用法"的地方都是这个道理(判「用法」不判「提及」,pitfall #29)。
    if not has_mm(h):
        r.warn("报告没有交互脑图(#markmap)—— 若本次应含「迭代脑图」,"
               "检查正文是否漏了 .mmk 块")
        return

    n0 = r.n_err

    # ① autoloader 禁用
    # ⚠️ 判「用法」而不是判「提及」:shell.html 的注释里本来就写着
    # 「刻意不用 markmap-autoloader」,全文搜会把这段说明当成违规(实测踩到)。
    # 注意 `auto_use` 只认 src=/href=/import()/require() 这些**真会加载**的形态
    # (pitfall #29)。补充实测口径:三个 vendor 文件里这个字符串出现 **0 次** ——
    # 所以这里跟 vendor 中和无关,别写成「靠 strip_vendor 中和」(那是旧说法,已推翻)。
    if auto_use.search(h):
        r.err("真的引进了 markmap-autoloader —— 明令禁用:它靠运行期动态 import "
              "去拉 d3 / markmap-view / toolbar,任一 CDN 失败就静默 reject,"
              "页面只剩没渲染的 markdown")

    # ② 脑图依赖不许外链
    #    走 real_tags:注释里贴的 `<script src=…>` 示例不算真外链(pitfall #29:
    #    判「用法」不判「提及」—— 反面例子就是 autoloader 那条,得判真加载形态)。
    ext = [m.group(1) for m in
           real_tags(h, r'<script\b[^>]*\bsrc\s*=\s*["\']([^"\']+)["\']')]
    if ext:
        r.err("出现外链 <script src>(违反离线自包含):%s" % ", ".join(ext[:3]))

    # ③ 三个依赖已内联 + 体积/指纹达标
    missing, thin = [], []
    for item in vendor:
        m = re.search(r'<script id="%s">(.*?)</script>' % re.escape(item["id"]), h, re.S)
        if not m:
            missing.append(item["id"]); continue
        ok, why = check_js(item, m.group(1))
        if not ok:
            thin.append("%s(%s)" % (item["id"], why))
    if missing:
        r.err("脑图依赖未内联: %s —— 跑 python scripts/mindmap.py <报告.html>"
              % ", ".join(missing))
    if thin:
        r.err("内联的脑图依赖内容不合格: %s" % ", ".join(thin))

    # ④ markdown 数据源(属性顺序不敏感)
    #    ⚠️ 必须走 real_tags(见 md_sources 的说明):shell.html 的 boot 注释里
    #    举例写了 `<script type="text/markdown" id="mmk-md-zh">`,裸扫会把它当第 3 份。
    #    结果在 ⑨ 复用,不再各扫一遍。
    mds = md_sources(h)
    if not mds:
        r.err('有 #markmap 但没有 markdown 数据源 —— 需要 '
              '<script type="text/markdown" id="mmk-md-zh">…</script>')
    else:
        langs = sorted({l for l, _ in mds})
        r.ok("脑图 markdown 源: %d 份(%s)" % (len(mds), "/".join(langs) or "?"))

    # ⑤ 引导脚本关键逻辑
    boot = re.search(r'<script id="mmk-boot">(.*?)</script>', h, re.S)
    if not boot:
        r.err('缺少 <script id="mmk-boot"> 引导脚本 —— 脑图固定层被删了')
    else:
        # ⚠️ 判 **code**(注释已剔除)而不是 boot 原文:下面那条"不许用静态工厂"
        #    是**反向**断言,而 boot 的注释里正为这件事写着说明 —— 不剔除注释
        #    就会拿说明当违规(pitfall #29 的 JS 层翻版,见 js_code 的说明)。
        code = js_code(boot.group(1))
        need = [("new window.markmap.Markmap(", "渲染器实例化"),
                ("mm.setData(", "串行化(queue 必须等得到渲染完成的 promise)"),
                ("Transformer", "markdown 解析"),
                ("replaceChild", "语言切换重建容器"),
                ("degrade", "渲染失败降级"),
                ("data-mmk-fallback", "降级标记"),
                ("scrollForPan:true", "滚轮不劫持页面"),
                ("pan:false", "拆掉自带的 wheel 平移")]
        lack = [n for n, _ in need if n not in code]
        if lack:
            r.err("脑图引导脚本缺少关键逻辑: %s(降级/重建/串行/滚轮策略任缺一项都会出问题)"
                  % ", ".join(lack))
        # 反向断言:静态工厂 Markmap.create(svg,opts,data) 内部是
        # `mm.setData(data).then(()=>mm.fit())` —— 那个 promise **没有被 return**,
        # 于是 queue 等不到渲染结束,"串行化"只剩同步那几行(空串行)。
        # 实测:连点 4 次语言标签,并发渲染峰值 4,末态由"谁最后画完谁赢"决定。
        # 这是**静态能拦、运行期也能量**的一条,两边都留了闸门。
        if "Markmap.create(" in code:
            r.err("引导脚本又用回了静态工厂 Markmap.create(…) —— 它内部的 "
                  "`mm.setData(data).then(()=>mm.fit())` 丢掉了 setData 的 promise,"
                  "queue 因此等不到渲染完成,串行化形同虚设。改成 "
                  "`mm=new Markmap(svg,opts)` + `return mm.setData(root)`"
                  "(见 pitfalls「queue 空串行化」)")

    # ⑥ 暗色可读:必须覆盖 markmap 自己的 CSS 变量
    css = "".join(h[s:e] for s, e in style_spans(h))
    if "#markmap" not in css:
        r.err("样式里没有 #markmap 容器规则(高度/背景会失控)")
    if "--markmap-text-color" not in css:
        r.err("没有覆盖 --markmap-text-color —— markmap 默认文字是 #333,"
              "在暗色主题下节点标签看不清")

    # ⑦ 依赖块**不许落在 <style> 里** —— 最隐蔽的一种失效,静态也能抓(pitfall #26)。
    #    实测事故:shell.html 的注释里也写着标记位那串字,而其中一处恰好在 CSS
    #    注释里、且排在文件最前面;早期 mindmap.py 替换「第一处」,于是 1MB 依赖
    #    被注进 <style>(脚本不执行 → 脑图永远渲染失败),而 ③ 的断言
    #    (全文搜 <script id="mmk-d3">)照样全绿。所以必须单列一条位置断言。
    #    教训:凡是"替换某标记位"的注入,都要加一条**位置断言** ——
    #    「内容存在」和「内容会执行」是两件事。
    blk = re.search(r"<!--MARKMAP_VENDOR:BEGIN", h)
    if blk and in_spans(blk.start(), style_spans(h)):
        r.err("脑图依赖块落在 <style> 里(标记位选错)—— 脚本不会执行,脑图必然"
              "渲染失败,而「依赖已内联」那条断言仍是绿的。修:重跑 "
              "`python scripts/mindmap.py <报告.html>`(它会挑正文里那处标记)")

    # ⑧ #markmap 必须声明高度 —— 没高度容器塌成 0,渲染了也看不见
    if not re.search(r"#markmap[^{]*\{[^}]*\bheight\s*:", css, re.I):
        r.err("#markmap 没有声明 height —— 容器会塌成 0 高,脑图渲染成功也看不见")

    # ⑨ markdown 源要有内容与结构,语言 tab 要与源对得上
    #    mds 来自 ④(同一个 md_sources),这里只判内容 —— 两边口径不可能再分叉。
    for lang, body in mds:
        if not body.strip():
            r.err("mmk-md-%s 是空的 —— 该语言下要么空白、要么直接降级" % lang)
        elif not re.search(r"^\s*(#{1,6}\s|[-*+]\s)", body, re.M):
            r.err("mmk-md-%s 里没有 markdown 结构(缺 `# 标题` / `- 列表`)—— "
                  "渲染出来会只有一个根节点" % lang)
    tab_langs = {x.lower() for x in
                 re.findall(r"data-mmk-lang\s*=\s*[\"']([a-zA-Z-]{2,5})[\"']", h)}
    md_langs = {x for x, _ in mds}
    orphan_tabs = tab_langs - md_langs
    if orphan_tabs:
        r.warn("语言 tab %s 没有对应的 mmk-md-%s 源 —— 该 tab 会被 syncUI 静默隐藏"
               % ("/".join(sorted(orphan_tabs)), "/".join(sorted(orphan_tabs))))

    if r.n_err == n0:
        r.ok("交互脑图齐备:三依赖已内联且不在 <style> 内、md 源有结构、"
             "boot 完整、样式覆盖到位")


def arm_watchdog(secs):
    """整轮校验超过 secs 秒 → 打印当前调用栈并退出(secs<=0 关闭)。

    为什么要这个:报告内联 d3 / markmap 三块 1MB 级依赖后,`strip_vendor` 会把它们
    换成**等长空白块**(保长度、保 `(?m)^` 锚点)。任何「行首 `\\s*` 之后还要个
    非空白字符」的正则在那块空白上会灾难性回溯 —— 表现是**命令挂死、零输出、
    没有 traceback**。排查时它看着像「脚本崩了 / 工具吞了输出」,实际是永不返回
    (pitfall #28 就是这么被揪出来的:最后靠逐函数子进程超时二分才定位)。

    faulthandler 的看门狗是 C 层的独立线程,**正则回溯占着 GIL 也能把栈 dump 出来**,
    所以它是这类「卡住」问题的正解(`-X faulthandler` 手动挂是等不到的)。
    """
    if secs <= 0:
        return False
    try:
        import faulthandler
    except ImportError:                                      # pragma: no cover
        return False
    faulthandler.dump_traceback_later(secs, exit=True)
    return True


def check_tag_balance(h, r):
    """容器标签配平:总数必须相等,且逐标签累计**深度不得跌到负值**。

    为什么是 err 而不是 warn:
      这一类失效**不会被别的检查发现** —— 数字保真 / 卡片 / 导航 / canvas 全都能是绿的,
      但 .layout 被提前闭合后,正文会渲染到弹性布局之外:
      侧栏消失、正文占满屏幕,且崩点在第一个多余闭合标签处(表现为「下半部分排版崩了」)。

    为什么还要查「深度跌负」而不只查总数:
      总数不等只能告诉你"有错",跌负能直接指出**第一个**多余闭合标签的位置,
      定位成本从"通读全文"降到"看一行上下文"。

    只统计结构性容器(div / main / nav / section / ul / ol / details / table),
    行内标签不在其列 —— 它们在 HTML5 里允许隐式闭合,查了会出假阳性。
    """
    body = h
    m = re.search(r"<body\b[^>]*>(.*)</body>", h, re.S | re.I)
    if m:
        body = m.group(1)

    # 先剔除不该参与计数的地方
    body = re.sub(r"<script\b.*?</script>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<style\b.*?</style>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    body = re.sub(r"data:[a-zA-Z0-9/+.-]+;base64,[A-Za-z0-9+/=]+", " ", body)

    CONTAINERS = ("div", "main", "nav", "section", "details", "table", "ul", "ol")
    pat = re.compile(r"<(%s)\b[^>]*?(/?)>|</(%s)\s*>" % ("|".join(CONTAINERS),
                                                          "|".join(CONTAINERS)),
                     re.I)

    opens, closes = 0, 0
    depth = 0
    first_neg = None
    counts = {}
    for m in pat.finditer(body):
        if m.group(1):                       # 开标签
            if m.group(2):                   # 自闭合 <div/>
                continue
            tag = m.group(1).lower()
            opens += 1
            depth += 1
            counts[tag] = counts.get(tag, 0) + 1
        else:                                # 闭标签
            tag = m.group(3).lower()
            closes += 1
            depth -= 1
            counts[tag] = counts.get(tag, 0) - 1
            if depth < 0 and first_neg is None:
                first_neg = (m.start(), tag)

    if opens == closes and first_neg is None:
        r.ok("容器标签配平:%d 开 / %d 闭,深度全程非负" % (opens, closes))
        return

    bad = sorted([(v, k) for k, v in counts.items() if v != 0], reverse=True)
    detail = "、".join("%s 差 %+d" % (k, v) for v, k in bad[:6]) or "无单项偏差记录"
    r.err("容器标签不配平:%d 开 / %d 闭(差 %+d);%s。"
          "这会让 .layout 提前闭合,正文渲染到弹性布局之外 —— "
          "表现为侧栏消失、正文占满屏幕,而**其余所有检查都会是绿的**。"
          % (opens, closes, closes - opens, detail))
    if first_neg:
        pos, tag = first_neg
        ctx = re.sub(r"\s+", " ", body[max(0, pos - 160):pos + 80])
        r.err("  第一个多余闭合标签位置:偏移 %d 处 </%s>,上文 …%s…"
              % (pos, tag, ctx[-170:]))


def main():
    ap = argparse.ArgumentParser(description="报告交付前自检")
    ap.add_argument("html")
    ap.add_argument("--dir", default="", help="工作区目录(用于核对素材 ID)")
    ap.add_argument("--strict", action="store_true", help="warning 也算失败")
    ap.add_argument("--hang-timeout", type=float, default=90.0,
                    help="整轮超时秒数,超时打印栈并退出(0=关闭;默认 90)")
    a = ap.parse_args()

    if not os.path.isfile(a.html):
        sys.exit("[ERR] 文件不存在: %s" % a.html)

    h = load(a.html)
    r = Report()
    print("校验: %s" % a.html)
    print("大小: %.1f MB" % (len(h.encode("utf-8")) / 1048576.0))

    armed = arm_watchdog(a.hang_timeout)
    check_placeholders(h, r)
    check_css_placement(h, r)
    check_nav(h, r)
    check_gallery_ids(h, r, a.dir)
    check_material_cards(h, r)
    check_videos(h, r)
    check_img_rules(h, r)
    check_canvas(h, r)
    check_blockquotes(h, r)
    check_tag_balance(h, r)
    check_misc(h, r)
    check_brand(h, r)
    check_source_badge(h, r)
    check_mindmap(h, r)
    check_news(h, r)
    check_offline(h, r)
    check_size(h, r)
    if armed:
        import faulthandler
        faulthandler.cancel_dump_traceback_later()

    # 数字保真 + 素材 ID 合法性(移植自 agg-ad-strategy/scripts/check.py)
    if a.dir:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import fidelity
            errs, warns, st = fidelity.validate(a.html, a.dir, a.strict)
            r.items.append((OK, "保真语料 %d 个文件 | 报告数字 %d 个"
                                "(派生登记 %d / 未命中 %d)"
                                % (st.get("corpus_files", 0), st.get("numbers", 0),
                                   st.get("derived", 0), st.get("miss", 0))))
            if st.get("ids"):
                r.items.append((OK, "素材短 ID %d 个,非法 %d 个"
                                    % (st["ids"], st.get("id_bad", 0))))
            for w in warns:
                r.warn(w)
            for e in errs:
                r.items.append((ERR, e))
                r.n_err += 1
        except ImportError as e:
            r.err("fidelity.py 不可用,数字保真未执行 → 不得交付: %s" % e)
    else:
        r.err("未传 --dir,数字保真与素材 ID 校验均未执行 → 不得交付。"
              "用法: validate.py <报告.html> --dir <工作区>")

    r.dump()
    if r.n_err or (a.strict and r.n_warn):
        sys.exit(1)


if __name__ == "__main__":
    main()
