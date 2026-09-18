#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Markmap 依赖内联进报告单文件 —— 交互脑图离线自包含。

用法:
  python scripts/mindmap.py <报告.html> [--dir <工作区>] [--vendor-dir <目录>] [--force]
  python scripts/mindmap.py <报告.html> --check        # 只体检,不写文件

它做三件事:

  1. **找依赖**:`--vendor-dir` → `$AGG_MARKMAP_VENDOR` → `<skill>/assets/vendor/`
     → `<--dir>/build/vendor` → `<报告所在目录>/build/vendor`
     依次找 d3 / markmap-lib / markmap-view 三个 js。找不到才联网下载
     (版本写死,不追 latest)。

     ⚠️ **缓存只认 `<skill>/assets/vendor/`**。它是候选表里第一个「必然存在」的目录,
     所以 `write_to` 永远落在那里;`<--dir>/build/vendor` 只在**显式传 `--dir`** 时
     才进候选(见 `resolve_cache_dirs` 的 `if args.dir:` 守卫),且排在 `assets/vendor`
     之后 —— 即它只读不写、且被前面命中后根本轮不到。
     **不要在 skill 根目录手工造 `build/vendor`**:那是历史版本遗留(曾按「工作区」处理
     skill 自身),990K×2 纯冗余,已在 2026-09-15 清理。清理后回归全绿。
  2. **校验内容**:下载到的内容必须命中指纹(版本字符串 + 导出符号)且体积达标 ——
     防止 CDN 返回 HTML 错误页 / 版本被换掉后被静默内联。
  3. **幂等注入**:把三个 `<script id="mmk-*">` 塞进 `<!--MARKMAP_VENDOR-->` 标记位。
     第 N 次跑的结果和第 1 次完全一样(整体替换 BEGIN…END 之间的内容)。

## 为什么不用 markmap-autoloader

autoloader 全靠运行期动态 `import()` 去拉 d3 / markmap-view / toolbar,
**任一 CDN 失败就静默 reject** —— 页面上只剩一段没渲染的 markdown,
控制台连红字都不一定有;无头导出时它还会跟封面图片抢网络。报告是离线交付物,
外链本来就是铁律禁区,所以依赖只能内联。

## 为什么必须自己注入,而不是写在 shell.html 里

vendor 有 1MB 量级,塞进 `assets/shell.html` 会让模板没法读、diff 全是噪音;
而且**报告是不是要脑图**只有正文知道。所以模板里只留一个标记位,
由本脚本在「脑图确实存在」时才注入。

## CDN 路径的两个坑(实测)

  - `markmap-lib` 的浏览器构建叫 `dist/browser/index.iife.js`;
    写 `index.js` 是 **404**(而 `markmap-view` 的 `index.js` 恰好是 200),
    两个包命名规则不一致,别凭直觉类推。
  - 三个文件**加载顺序必须是 d3 → lib → view**:lib / view 的 IIFE 尾参分别是
    `window.katex` 和全局 `d3`,d3 不在前面就是 ReferenceError。
    注入顺序即数组顺序,别改。
"""
from __future__ import print_function

import argparse
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BEGIN = "<!--MARKMAP_VENDOR:BEGIN"
END = "<!--MARKMAP_VENDOR:END-->"
BARE = "<!--MARKMAP_VENDOR-->"

# id, 缓存文件名, 版本, CDN 地址, 指纹(必须全部命中), 体积下限(KB)
# ⚠️ 顺序 = 注入顺序 = 浏览器加载顺序: d3 → lib → view
VENDOR = [
    dict(id="mmk-d3", fn="d3.min.js", ver="d3@7.9.0",
         url="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js",
         marks=["d3js.org v7.9.0"], min_kb=200),
    dict(id="mmk-lib", fn="markmap-lib.iife.js", ver="markmap-lib@0.18.12",
         url="https://cdn.jsdelivr.net/npm/markmap-lib@0.18.12/dist/browser/index.iife.js",
         marks=['"markmap-lib": "0.18.12"', "exports.Transformer"], min_kb=400),
    dict(id="mmk-view", fn="markmap-view.js", ver="markmap-view@0.18.12",
         url="https://cdn.jsdelivr.net/npm/markmap-view@0.18.12/dist/browser/index.js",
         marks=["exports.Markmap", "defaultOptions"], min_kb=30),
]

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


def save(p, s):
    d = os.path.dirname(os.path.abspath(p))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def style_spans(h):
    """所有 <style>…</style> 的 (start, end) 区间。"""
    out = []
    for m in re.finditer(r"<style[^>]*>", h, re.I):
        e = h.find("</style>", m.end())
        if e > 0:
            out.append((m.end(), e))
    return out


def hazard_spans(h):
    """**不能**被注入的区间:<style> 内部 与 <!-- --> 注释内部。

    为什么必须有这个判定(实测踩到,后果很重):
    `shell.html` 里 "<!--MARKMAP_VENDOR-->" 这串字出现在 **3 处** ——
    两处是注释里的说明文字,只有一处是正文里的真标记位,而**排在文件最前面
    的那处恰好在 CSS 注释里**。早期实现用 `h.replace(BARE, blk, 1)` 替换
    第一处,于是 1MB 依赖被注进了 `<style>` —— 脚本不执行、`markmap` 未定义、
    脑图永远渲染不出来,而 `validate.py` 的静态检查(全文搜 `<script id="mmk-d3">`)
    **照样判绿**。这是最难发现的一类失效:静态全绿、运行全崩。
    """
    spans = list(style_spans(h))
    for m in re.finditer(r"<!--.*?-->", h, re.S):
        spans.append((m.start(), m.end()))
    return spans


def find_bare(h):
    """返回**可安全注入**的裸标记位置列表(已排除注释与 <style> 内部)。

    ⚠️ 计算危险区间时要**把标记自身那个注释区间摘掉** —— 标记的写法
    就是一个 HTML 注释(`<!--MARKMAP_VENDOR-->`),不摘的话它会把自己判成
    「位于注释内」,于是所有候选都被排除、一个可用位置都找不到(实测踩到)。
    区分「标记本身的注释」与「恰好也写着这串字的说明注释」靠的是文本相等:
    前者整段就等于 BARE,后者是包着这串字的长句。
    """
    haz = [(a, b) for a, b in hazard_spans(h) if h[a:b] != BARE]
    return [m.start() for m in re.finditer(re.escape(BARE), h)
            if not any(a <= m.start() < b for a, b in haz)]


def check_js(item, txt):
    """内容指纹校验。返回 (ok, 说明)。"""
    if len(txt) < item["min_kb"] * 1024:
        return False, "只有 %d KB,小于下限 %d KB" % (len(txt) // 1024, item["min_kb"])
    head = txt[:400].lower()
    if "<!doctype" in head or "<html" in head or "<script src=" in head:
        return False, "内容是 HTML 而不是 JS(CDN 大概率返回了错误页)"
    for mk in item["marks"]:
        if mk not in txt:
            return False, "指纹缺失: %r(版本对不上或文件被换过)" % mk
    return True, "%d KB" % (len(txt) // 1024)


def download(item, dest_dir, verbose=True):
    """下载到 dest_dir,校验通过才落盘。返回 (path, 说明) 或 (None, 失败原因)。"""
    import urllib.request           # 本模块只有这一处发请求,就近导入即可
    dest = os.path.join(dest_dir, item["fn"])
    try:
        if verbose:
            print("  ↓ %s  (%s)" % (item["ver"], item["url"]))
        r = urllib.request.urlopen(item["url"], timeout=90)
        raw = r.read()
    except Exception as e:
        return None, "下载失败: %s: %s" % (type(e).__name__, e)
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError:
        txt = raw.decode("utf-8", "replace")
    ok, why = check_js(item, txt)
    if not ok:
        return None, "内容校验不通过: %s" % why
    # `</script` 会提前闭合内联脚本;实测这 3 个包里没有,当真出现时做最小转义
    if "</script" in txt.lower():
        txt = re.sub(r"</(script)", r"<\\/\1", txt, flags=re.I)
        print("  ! %s 里含 </script,已转义" % item["fn"])
    save(dest, txt)
    return dest, why


def resolve_cache_dirs(args, report_path):
    """按优先级返回 (可读目录列表, 写盘目录)。"""
    rep_dir = os.path.dirname(os.path.abspath(report_path))
    cands = []
    if args.vendor_dir:
        cands.append(os.path.abspath(args.vendor_dir))
    env = (os.environ.get("AGG_MARKMAP_VENDOR") or "").strip()
    if env:
        cands.append(os.path.abspath(env))
    cands.append(os.path.join(SKILL_ROOT, "assets", "vendor"))
    if args.dir:
        cands.append(os.path.join(os.path.abspath(args.dir), "build", "vendor"))
    cands.append(os.path.join(rep_dir, "build", "vendor"))
    write_to = None
    for c in cands:
        try:
            if not os.path.isdir(c):
                os.makedirs(c)
            write_to = c
            break
        except OSError:
            continue
    return cands, (write_to or cands[0])


def get_vendor(args, report_path):
    """返回 {id: js 文本},失败抛 SystemExit。"""
    dirs, write_to = resolve_cache_dirs(args, report_path)
    out, notes = {}, []
    for item in VENDOR:
        txt, src = None, ""
        if not args.force:
            for d in dirs:
                p = os.path.join(d, item["fn"])
                if os.path.isfile(p):
                    t = load(p)
                    ok, why = check_js(item, t)
                    if ok:
                        txt, src = t, "缓存 " + p
                        break
                    notes.append("缓存 %s 不合格(%s),忽略" % (p, why))
        if txt is None:
            p, why = download(item, write_to)
            if p is None:
                sys.exit("[ERR] %s 取不到依赖 —— %s\n"
                         "      手工修法: 自己下载 %s 存成 %s/%s"
                         % (item["id"], why, item["url"], write_to, item["fn"]))
            txt, src = load(p), "下载 " + p + "(" + why + ")"
        notes.append("%-9s %s ← %s" % (item["id"], item["ver"], src))
        out[item["id"]] = txt
    for n in notes:
        print("  · " + n)
    return out


def build_block(vendor):
    head = (BEGIN + "  " + " + ".join(v["ver"] for v in VENDOR)
            + "  由 scripts/mindmap.py 内联,勿手改 -->")
    parts = [head]
    for item in VENDOR:
        parts.append('<script id="%s">\n%s\n</script>' % (item["id"], vendor[item["id"]]))
    parts.append(END)
    return "\n".join(parts)


def has_mindmap(h):
    """页面里有没有真的脑图容器。

    ⚠️ 必须锚在**开标签**上,不能直接搜 `id="markmap"` —— boot 脚本里写着
    `getElementById('markmap')` / `d.id='markmap'`,那是 JS 文本,不是 DOM 属性。
    (用双引号的正则 + 标签前缀双重收紧;否则 shell 一定带 boot 脚本 → 永远为真。)
    """
    return bool(re.search(r'<[a-zA-Z][^>]*\bid\s*=\s*["\']markmap["\'][^>]*>', h))


# 「用了 autoloader」= 真的把它引进来(src=/href= 或动态 import()/require())。
# ⚠️ 不要写成全文搜 `markmap-autoloader`:shell.html 的注释里**本来就在讲**
#    「刻意不用 markmap-autoloader」,全文搜必然把这段说明当成违规(实测踩到)。
#    判「用法」而不是判「提及」,这条才立得住。
AUTO_USE = re.compile(
    r"""(?:src|href)\s*=\s*["'][^"']*markmap-autoloader"""
    r"""|(?:import|require)\s*\(\s*["'][^"']*markmap-autoloader""", re.I)


def injected(h):
    m = re.search(re.escape(BEGIN) + r".*?" + re.escape(END), h, re.S)
    return m.group(0) if m else None


def check_mode(h, path):
    print("体检: %s" % path)
    bad = 0
    if not has_mindmap(h):
        print("[  OK  ] 报告没有 #markmap 脑图 —— 本脚本不需要做任何事")
        return 0
    blk = injected(h)
    if not blk:
        print("[ FAIL ] 有 #markmap 但依赖未内联(标记位还是空的或已被删)"
              " → 跑 python scripts/mindmap.py %s" % os.path.basename(path))
        return 1
    for item in VENDOR:
        m = re.search(r'<script id="%s">(.*?)</script>' % re.escape(item["id"]), h, re.S)
        if not m:
            print("[ FAIL ] 缺少内联脚本 %s" % item["id"]); bad += 1
            continue
        ok, why = check_js(item, m.group(1))
        print("[%s] %-9s %s" % ("  OK  " if ok else " FAIL ", item["id"], why))
        if not ok:
            bad += 1
    if AUTO_USE.search(h):
        print("[ FAIL ] 出现 markmap-autoloader —— 本技能明令禁用(CDN 失败即静默不渲染)")
        bad += 1
    print("")
    print("  %d error" % bad)
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description="把 Markmap 依赖内联进报告单文件")
    ap.add_argument("html")
    ap.add_argument("--dir", default="", help="工作区目录(缓存兜底位置 build/vendor)")
    ap.add_argument("--vendor-dir", default="", help="指定 vendor 缓存目录(最高优先级)")
    ap.add_argument("--force", action="store_true", help="忽略缓存,重新下载")
    ap.add_argument("--check", action="store_true", help="只体检不写文件")
    a = ap.parse_args()

    if not os.path.isfile(a.html):
        sys.exit("[ERR] 文件不存在: %s" % a.html)
    h = load(a.html)
    print("脑图内联: %s  (%.2f MB)" % (a.html, len(h.encode("utf-8")) / 1048576.0))

    if a.check:
        sys.exit(check_mode(h, a.html))

    if not has_mindmap(h):
        if injected(h):
            h2 = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), BARE, h, flags=re.S)
            save(a.html, h2)
            print("  · 报告没有 #markmap → 已把 1MB 依赖摘掉(省体积)")
        else:
            print("  · 报告没有 #markmap → 跳过(没动文件)")
        return

    if injected(h) is None and not find_bare(h):
        sys.exit("[ERR] 找不到可注入的标记位 <!--MARKMAP_VENDOR--> —— "
                 "要么 shell.html 版本太旧,要么正文把标记位删了,"
                 "要么仅存的那处落在 <style>/注释里(那种位置注入后脚本不执行)")

    vendor = get_vendor(a, a.html)
    blk = build_block(vendor)
    if injected(h) is not None:
        h2 = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda m: blk, h, count=1, flags=re.S)
        how = "替换"
    else:
        spots = find_bare(h)
        if len(spots) != 1:
            sys.exit("[ERR] 可注入的裸标记位有 %d 处(期望恰好 1 处,位于正文、"
                     "不在 <style> 或注释内)。请在 shell.html 里只保留一处。"
                     % len(spots))
        i = spots[0]
        h2 = h[:i] + blk + h[i + len(BARE):]
        how = "首次注入"
    # 注入后自证:块头必须不在 <style> 内 —— 注进 CSS 的话脚本不会执行,
    # 脑图必然渲染失败,而所有静态检查(靠全文搜 <script id="mmk-d3">)都会是绿的。
    _bi = h2.find(BEGIN)
    if _bi >= 0 and any(s <= _bi < e for s, e in style_spans(h2)):
        sys.exit("[ERR] 依赖块被注进了 <style> 里(标记位选错了)—— "
                 "脚本不会执行,脑图必然渲染失败。检查 shell.html 的标记位位置。")
    if h2 == h:
        print("  · 已是目标状态,文件未变(幂等)")
    else:
        save(a.html, h2)
        print("  · %s三个 <script>(d3 / markmap-lib / markmap-view)" % how)
    print("  完成: %.2f MB → %.2f MB"
          % (len(h.encode("utf-8")) / 1048576.0, len(h2.encode("utf-8")) / 1048576.0))


if __name__ == "__main__":
    main()
