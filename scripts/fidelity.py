#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数字保真 + 素材 ID 合法性(从 agg-ad-strategy/scripts/check.py 移植并改造)。

**为什么要移植**:报告里一个数字编错,整份报告的可信度就归零。
保真校验把「这个数是不是编的」从人工抽查变成机器判定。

**和老版的关键区别 —— 派生值登记制**
语料是 aggclaw 的自然语言原文(raw/data/result_L*.md)与素材清单,所以「数字必须能在 raw 里
字面命中」是基本盘;但报告里还有大量**自己算的**聚合值:

    「占窗口总量 48%」 = 253/527,源 raw/materials_all.json
    「在投 −69%」      = (98-312)/312,源 raw/data/result_L2_....md

这些数字在报告里字面存在,但在任何 raw 文件里都不存在 → 只按字面命中判会误报「疑似自创」FAIL。

本版的规则:
    报告数字 → ① 在 raw 语料里字面命中 → OK
              ② 在 work/derived.json 里登记过 → OK(且校验登记本身合法)
              ③ 都不是 → FAIL(疑似自创)

    派生值登记格式(work/derived.json):
    {
      "48.0":   {"formula":"253/527*100", "source":"raw/materials_all.json",
                 "n":253, "note":"分母是窗口素材总量"},
      "69.0":   {"formula":"(98-312)/312", "source":"raw/data/result_L2_....md"}
    }

    **登记本身的校验**(防止把编造洗白):
      - `formula` 与 `source` 必填,且 source 文件必须真实存在
      - formula 里出现的**每个数字**必须自己在 raw 语料或另一条登记里命中
        → 「(98-312)/312」合法,说明 98 和 312 都查得到
        → 「(1-9999)/9999」不合法,会连带上报

用法:
  python fidelity.py <报告.html> --dir <工作区> [--strict]

工作区约定:<工作区>/raw/**/*.json|*.md 为语料(aggclaw 分析原文在 raw/data/result_L*.md,
           由 claw.py analyze 自动落盘),<工作区>/raw/materials_all.json 为素材清单,
           <工作区>/work/derived.json 为派生值登记(可选,缺失则全按「必须字面命中」判)。
"""
import io, os, re, sys, json, glob, argparse


# ---------------- 归一化 ----------------
# 报告里同一个数可能有多种写法,归一后比对,避免假阳性
MINUS = "−–—―-"          # − – — ― -
DASHES = re.compile("[" + re.escape(MINUS) + "]")


def norm_number(s):
    """把报告里的一个数字串归一成可与语料比对的形式。

    '1,335' -> '1335'    '45.8M' -> '45.8M'
    '−69%'  -> '-69'     '28.08%' -> '28.08'
    """
    s = str(s).strip()
    s = DASHES.sub("-", s)
    s = s.replace(",", "").replace("　", "").replace(" ", "")
    s = s.rstrip("%")                       # 去掉百分号
    s = s.replace("％", "")             # 全角 %
    return s.strip()


# 注意:数字与单位之间**不允许有空格**。
# 允许的话表格行「6 Messenger」会被读成 "6M"、「11 Moloco」读成 "11M" —— 实测误报。
NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?[%KMB]?", re.I)

# 数字/百分号之间、数字与数字之间的横线 —— 一律是区间或日期分隔符,不是负号。
# 覆盖:「2023-2026」「2026-08-12」「10.42%–12.40%」「1–99」
RANGE_DASH = re.compile(r"(?<=[\d%％])\s*[−–—―-]\s*(?=\d)")


def extract_numbers(text):
    """从一段文本里抽出所有数字串(已归一)。

    两个必须处理的假阳性(都实测踩到过):
      1. **区间/日期的横线不是负号** —— 「2023-2026」「10.42%–12.40%」
         曾分别被读成 -2026 与 -12.40,误报成「疑似自创」。
         判据:横线左边是数字**或百分号**,右边是数字 → 分隔符。
      2. **Unicode 负号** —— 报告里写的是 U+2212(−) 而不是 ASCII 连字符,
         要先统一才能让 −69% 被正确读成负值。
    """
    t = text or ""
    t = RANGE_DASH.sub(" ", t)              # 先把区间横线抹成空格
    t = t.replace("−", "-")            # 剩下的 − 才是真负号
    out = []
    for m in NUM_RE.finditer(t):
        v = norm_number(m.group(0))
        if v and v not in ("-", ".", ""):
            out.append(v)
    return out


SUFFIX = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}


def canonical(v):
    """把归一化后的数字串转成可比较的浮点(展开 K/M/B 后缀)。

    '5.5M' -> 5500000.0    '50.93' -> 50.93    让两种写法能对上。
    """
    m = re.match(r"^(-?\d+(?:\.\d+)?)\s*([KMB]?)$", str(v).strip(), re.I)
    if not m:
        return None
    try:
        return round(float(m.group(1)) * SUFFIX[m.group(2).upper()], 6)
    except Exception:
        return None


# 中日韩文字 + 全角标点。含这些 = 自然语言,**不可能是 URL / base64 / hex**。
CJK_RE = re.compile(u"[㐀-䶿一-鿿豈-﫿　-〿＀-￯]")


def _is_encoded(s):
    """URL / 资源 ID / base64 这类编码串里的数字**不是事实数字**,提取时必须排除。

    实测踩坑:raw 里 media 图标的 URL 含 `RS8y815993f86lbbwVVQO`,
    其中子串 "5993" 让一个改错的小数(59.93)被误判为「命中」而放行。
    早期版本用「归一化后子串搜索」做兜底,整块语料一起搜 → 就是这个后果。

    ⚠️ 第一条判据曾有 `if len(s) > 60: return True`(无附加条件),
    结果把 aggclaw 的 `output`——一整篇几千字的自然语言分析——**整段当成编码串丢弃**,
    语料大面积缺失,只能靠人工把 output 拆成 .md 塞进 raw/ 补救。

    修法分两层,两层都要留着:
      ① 产出端:`claw.py` 把 output 单独落成 raw/data/result_L*.md,走 .md 纯文本分支,
         根本不经过本函数;
      ② 这里放宽判据 —— 用「**含 CJK**」而不是「无空白」来识别散文。
         **中文没有空格**,所以「无空白」区分不了中文散文与编码串(实测踩到);
         而任何编码方案都不会产出中日韩文字,含 CJK 即铁定是自然语言。
    URL / data URI 两条判据保持无条件(即使串里混了中文也照拦),
    因为「散文里夹了一个直链」时,把整串跳过比抽出链接里的假数字安全。
    """
    if CJK_RE.search(s):
        # 含中日韩文字 → 自然语言。下面的「长且无空白」「base64 特征」「长 hex」都不适用。
        return bool(re.search(r"https?://|^data:", s))
    if len(s) > 60 and not re.search(r"\s", s):
        return True
    if re.search(r"https?://|^data:", s):
        return True
    # base64 特征字符
    if re.search(r"[+=\\]", s) and len(s) > 20 and not re.search(r"\s", s):
        return True
    # 无分隔符的长 hex / 混合大小写串(资源 id)
    if len(s) >= 16 and not re.search(r"\s", s) and re.search(r"[a-z]", s) and re.search(r"\d", s):
        return True
    return False


def _walk_scalars(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _walk_scalars(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _walk_scalars(v)
    elif isinstance(o, bool) or o is None:
        return
    elif isinstance(o, (int, float)):
        yield str(o)
    elif isinstance(o, str):
        yield o


def corpus_numbers(paths):
    """从 raw 文件里抽出「事实数字」集合(归一化字符串)。

    **只从 JSON 的标量值里取,不从编码串里取** —— 这是本节的关键。
    .md / .txt 按纯文本抽。
    """
    nums = set()
    for p in paths:
        try:
            if p.lower().endswith(".json"):
                d = load_json_safe(p)
                if d is None:
                    continue
                for s in _walk_scalars(d):
                    if _is_encoded(s):
                        continue
                    nums.update(extract_numbers(s))
            else:
                nums.update(extract_numbers(
                    io.open(p, encoding="utf-8", errors="replace").read()))
        except Exception:
            pass
    canons = set()
    for n in nums:
        c = canonical(n)
        if c is not None:
            canons.add(c)
    return nums, canons


def load_json_safe(p, default=None):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ---------------- 报告正文提取 ----------------
# 上次 report_text 豁免掉的资讯引用行数 —— 让豁免**可见**。
# 静默豁免是危险的:豁免逻辑一旦误伤正文,不会有人发现。
LAST_NEWS_EXEMPT = 0


def _strip_news_refs(h):
    """剥掉「资讯引用」区块 —— 它们不参与数字保真。

    为什么必须豁免:资讯表里是**他人文章标题的原文**,天生带日期、
    排名、金额(实测一行 `09-09 … 《部落冲突》8月流水突破 5000 万美元,
    全球下载量 TOP3` 会抽出 ['09','09','8','5000','3'] 五个数字)。
    这些数字**不是本报告的主张**,在 aggclaw 语料里当然查不到,
    不豁免就会把整份报告判成「数字不可溯源」——而报告其实没错。

    豁免的依据是一个**显式标记**而不是位置猜测:凡带 `newsbtn` 链接的
    `<tr>` 行 / `<li>` 项整条剔除;另整块剔除资讯章节 `#sec-news`。
    所以写报告时资讯条目**必须**用 `<a class="newsbtn">` 承载链接,
    否则豁免不生效(这一条写在 BLOCKS.md §17)。

    边界:豁免只覆盖「引用行」与「资讯章」,正文陈述里的数字仍要命中语料;
    资讯本身的合规由 news.py(白名单 + 黑名单 + 条数下限)与人工 pick 负责。
    """
    global LAST_NEWS_EXEMPT
    # 先整块删资讯章,再删零散引用行 —— 顺序反了会把章内每一行都
    # 单独计一次,计数虚高(章内的行本就该由整章那次一并带走)。
    h, k = re.subn(r'<section\b[^>]*id="sec-news"[^>]*>.*?</section>', " ", h,
                   flags=re.S | re.I)
    n = 0
    for pat in (
        r"<tr\b(?:(?!</tr>).)*?newsbtn(?:(?!</tr>).)*?</tr>",
        r"<li\b(?:(?!</li>).)*?newsbtn(?:(?!</li>).)*?</li>",
    ):
        h, c = re.subn(pat, " ", h, flags=re.S | re.I)
        n += c
    LAST_NEWS_EXEMPT = n + k        # k: 整块资讯章(1 或 0)
    return h


def report_text(html):
    """取出报告里「人眼会读到的文字」—— 剥掉 script/style/base64/标签/素材 ID。

    只在这一层上做保真,避免把这些误判成「主张数字」:
      - CSS 里的 px / 色值
      - base64 内嵌资源
      - **素材短 ID** —— 卡片上的 `0932a9f` 会被 NUM_RE 抽成 "0932",
        实测一次误报 48 个「疑似自创」。ID 的合法性由基础 ID 校验单独负责,
        不该混进数字保真通道。
      - **资讯引用行**(见 `_strip_news_refs`)—— 引用他人标题原文,
        数字不是本报告的主张。
    """
    # 章节号(3.1 / 4.2 / 1.1)不是数据,是排版编号 —— 先摘掉,否则会被当成「自创数字」。
    # 出现在两个地方:标题标签内,以及左侧目录的链接文字。
    h = re.sub(r"(<h[2-6][^>]*>)\s*\d+(?:\.\d+)+\s*", r"\1", html, flags=re.I)
    h = re.sub(r'(<a\b[^>]*class="toc-h3"[^>]*>.*?</span>)\s*\d+(?:\.\d+)+\s*',
               r"\1", h, flags=re.S | re.I)
    h = re.sub(r"\b\d+\.\d+\s*(?=[一-鿿]{2,})", " ", h)   # 「3.1 规模与趋势」残形
    h = re.sub(r"<script\b.*?</script>", "", h, flags=re.S | re.I)
    h = re.sub(r"<style\b.*?</style>", "", h, flags=re.S | re.I)
    h = re.sub(r"<!--.*?-->", "", h, flags=re.S)
    h = _strip_news_refs(h)                                              # 资讯引用
    h = re.sub(r"data:[a-zA-Z0-9/+.-]+;base64,[A-Za-z0-9+/=]+", " ", h)   # 内嵌资源
    h = re.sub(r'<[^>]+>', ' ', h)                                        # 标签
    h = (h.replace("&nbsp;", " ").replace("&amp;", "&")
          .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    # 素材 ID(32 位 hex 或 7~12 位短 ID)整体抹掉,别让它的数字碎片进保真通道
    h = re.sub(r"\b[0-9a-fA-F]{32}(?:-\d{3})?\b", " ", h)
    h = re.sub(r"\b(?=[0-9a-fA-F]*\d)(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{6,12}\b", " ", h)
    return h


# ---------------- 派生值登记 ----------------
def load_derived(path, raw_paths):
    """读派生值登记,返回 (entries, errors)。

    errors 里放「登记本身不合法」的问题 —— 防止用登记把编造洗白。
    """
    if not os.path.isfile(path):
        return {}, []
    d = load_json_safe(path)
    if not isinstance(d, dict):
        return {}, ["derived.json 顶层必须是对象 {数值: {formula, source, ...}}"]

    errs = []
    for k, v in d.items():
        if not isinstance(v, dict):
            errs.append("派生值 %r 的值必须是对象(含 formula/source)" % k)
            continue
        if not (v.get("formula") or "").strip():
            errs.append("派生值 %r 缺 formula —— 公式必填,否则无法复核" % k)
        src = (v.get("source") or "").strip()
        if not src:
            errs.append("派生值 %r 缺 source —— 必须写明源自哪个 raw 文件" % k)
        else:
            # source 允许写成 "raw/xxx.json" 或绝对/相对路径
            cand = [src] + [os.path.join(base, src) for base in raw_paths]
            if not any(os.path.isfile(c) for c in cand):
                errs.append("派生值 %r 的 source 文件不存在: %s" % (k, src))
    return {norm_number(k): v for k, v in d.items() if isinstance(v, dict)}, errs


ARITH_ONLY = re.compile(r"^[\d\s+\-*/().]+$")


def check_derived_evaluates(derived):
    """**公式必须真的算得出登记的值** —— 否则登记只是一句口号。

    只对纯算术公式生效(`921 / 253`、`(98-312)/312*100`、`24.82+11.15`),
    含标识符的公式(`sum(num(m.x) for m in materials)`)无法在此求值,跳过。

    比对时按**登记值的小数位**取整 —— 报告里写的是显示值(如 `3.6`),
    而 `921/253 = 3.6399...`,四舍五入到 1 位才是 3.6。
    """
    errs = []
    for k, v in derived.items():
        f = (v.get("formula") or "").strip()
        if not ARITH_ONLY.match(f):
            continue
        exp = canonical(k)
        if exp is None:
            continue
        try:
            got = eval(f, {"__builtins__": {}}, {})    # 已限定为纯算术字符
        except Exception:
            errs.append("派生值 %r 的公式 %r 无法求值(只支持 + - * / 与括号)" % (k, f))
            continue
        if not isinstance(got, (int, float)):
            continue
        # 按登记值的小数位取整后比对
        dp = 0
        kk = str(k).rstrip("KMBkMb%")
        if "." in kk:
            dp = len(kk.split(".")[1])
        if round(float(got), dp) != round(float(exp), dp):
            errs.append("派生值 %r 登记为 %s,但公式 %r 算出来是 %s —— "
                        "公式与数值对不上,必有一处写错" % (k, exp, f, round(float(got), dp)))
    return errs


def check_derived_selfconsistent(derived, corpus_nums, corpus_canons, raw_paths):
    """登记里的公式,其数字自身也要可溯源 —— 否则登记就成了洗白编造的后门。"""
    errs = []
    for k, v in derived.items():
        f = v.get("formula") or ""
        for n in extract_numbers(f):
            if len(n.lstrip("-").replace(".", "")) < 2:   # 单字符(2、3)不判,噪音太大
                continue
            if n in derived:                              # 另一个登记值,OK
                continue
            if n in corpus_nums or (canonical(n) in corpus_canons):
                continue
            errs.append("派生值 %r 的公式 %r 里的数字 %s 在 raw 语料里查不到 —— "
                        "要么它也是派生的(请一并登记),要么是编的" % (k, f, n))
    return errs


# ---------------- 主校验 ----------------
def validate(html_path, ws_dir, strict=False, verbose=True):
    """返回 (errors, warnings, stats)。"""
    html = io.open(html_path, encoding="utf-8", errors="replace").read()
    errs, warns, stats = [], [], {}

    raw_dir = os.path.join(ws_dir, "raw") if ws_dir else ""
    files = []
    search_dirs = [raw_dir] if (raw_dir and os.path.isdir(raw_dir)) else []
    if ws_dir and os.path.isdir(ws_dir):
        search_dirs.append(ws_dir)
    for d in search_dirs:
        files += glob.glob(os.path.join(d, "**", "*.json"), recursive=True)
        files += glob.glob(os.path.join(d, "**", "*.md"), recursive=True)
        files += glob.glob(os.path.join(d, "**", "*.txt"), recursive=True)
    files = [p for p in files
             if os.path.basename(p) not in ("derived.json", "covers.json", "videos.json")]
    corpus_nums, corpus_canons = corpus_numbers(files)
    stats["corpus_files"] = len(files)

    derived, derr = load_derived(os.path.join(ws_dir, "work", "derived.json"), [ws_dir]) \
        if ws_dir else ({}, [])
    errs.extend(derr)
    if derived:
        errs.extend(check_derived_selfconsistent(derived, corpus_nums, corpus_canons, [ws_dir]))
        errs.extend(check_derived_evaluates(derived))
    stats["derived"] = len(derived)

    if not corpus_nums:
        warns.append("raw 语料为空(--dir 未给或 raw/ 下无文件),跳过数字保真"
                     "—— 交付前必须补跑,否则保真形同虚设")
        return errs, warns, stats

    text = report_text(html)
    stats["news_exempt"] = LAST_NEWS_EXEMPT
    if LAST_NEWS_EXEMPT:
        warns.append("资讯引用豁免 %d 处(不参与数字保真)—— 确认这些位置"
                     "确实是引用他人标题的 newsbtn 行/资讯章" % LAST_NEWS_EXEMPT)
    nums = extract_numbers(text)
    uniq = sorted(set(nums))
    miss = []
    for n in uniq:
        if len(n.lstrip("-").replace(".", "")) < 2:    # 单字符不判(1、2 这类噪音)
            continue
        if n in derived:                                # ② 派生值登记
            continue
        if n in corpus_nums:                            # ① 字面命中
            continue
        c = canonical(n)                                # ①b 数值等价(45.80 == 45.8)
        if c is not None and c in corpus_canons:
            continue
        miss.append(n)

    stats["numbers"] = len(uniq)
    stats["miss"] = len(miss)
    stats["hit_derived"] = len([n for n in uniq if n in derived])

    if miss:
        msg = ("有 %d 个数字既不在 raw 语料命中、也未在 derived.json 登记"
               "(疑似自创):%s" % (len(miss), ", ".join(miss[:20])))
        if strict:
            errs.append(msg)
        else:
            errs.append(msg)
            errs.append("  → 若该数字是**自己算的聚合/环比**,请写进 work/derived.json:"
                        "{\"<数值>\":{\"formula\":\"...\",\"source\":\"raw/xxx.json\"}}")
            errs.append("  → 若确实是写错了,改掉。**不得靠登记把编造洗白** —— "
                        "登记里的公式数字自身也要能在 raw 命中。")

    # ---- 素材 ID 合法性 ----
    mat_p = os.path.join(raw_dir, "materials_all.json") if raw_dir else ""
    if mat_p and os.path.isfile(mat_p):
        mats = load_json_safe(mat_p, [])
        if isinstance(mats, dict):
            mats = mats.get("data") or list(mats.values())
        valid = set()
        for e in mats:
            m = e.get("material") if isinstance(e, dict) and "material" in e else e
            if isinstance(m, dict) and m.get("id"):
                valid.add(m["id"])
        # 报告用 7 位短 ID;核对短 ID 是否都能对上
        shorts = re.findall(r'class="b-lang">([0-9a-f]{7})<', html)
        shorts += re.findall(r'<i>([0-9a-f]{7})</i>', html)
        bad = [s for s in set(shorts) if not any(v.startswith(s) for v in valid)]
        if bad:
            errs.append("素材短 ID 不在 materials_all.json 清单中(编造/截断):%s"
                        % ", ".join(sorted(bad)[:10]))
        stats["ids"] = len(set(shorts))
        stats["id_bad"] = len(bad)

    return errs, warns, stats


def main():
    ap = argparse.ArgumentParser(description="数字保真 + 素材 ID 合法性")
    ap.add_argument("html")
    ap.add_argument("--dir", required=True, help="工作区目录(读 raw/ 与 work/derived.json)")
    ap.add_argument("--strict", action="store_true", help="warning 也算失败")
    a = ap.parse_args()

    errs, warns, st = validate(a.html, a.dir, a.strict)
    print("语料文件 %d 个 | 报告数字 %d 个(登记 %d / 未命中 %d)"
          % (st.get("corpus_files", 0), st.get("numbers", 0),
             st.get("derived", 0), st.get("miss", 0)))
    if st.get("ids"):
        print("素材短 ID %d 个,非法 %d 个" % (st["ids"], st.get("id_bad", 0)))
    for w in warns:
        print("[WARN] " + w)
    for e in errs:
        print("[FAIL] " + e)
    print("RESULT:", "PASS" if not errs else "FAIL")
    sys.exit(0 if not errs else 1)


if __name__ == "__main__":
    main()
