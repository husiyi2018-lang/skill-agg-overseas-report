#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML → PDF(Edge/Chrome headless,跨平台)。

用法:
  python topdf.py <报告.html> [--out <输出.pdf>] [--browser auto|edge|chrome]
                  [--browser-exe <浏览器可执行文件路径>] [--timeout 240]

关键坑(必读):
  **Edge headless 会把 PDF 写到它自己的安装目录(cwd),而不是 --print-to-pdf 里给的路径。**
  所以本脚本转完之后会在几个候选位置找一遍,找到就 cp 回目标目录。

其它注意:
  - 报告里的图表是 canvas,靠 `beforeprint` 事件重绘。
    headless 下要用 `--virtual-time-budget` 给足时间,否则图表会是空白。
  - 侧栏/按钮的隐藏由 shell.html 的 @media print 负责,不要删那段 CSS。
  - 浏览器自动找:Windows / macOS / Linux 的常见安装位置都查过,再兜底查 PATH。
    装在绿色版目录等非标准位置的,用 `--browser-exe` 指过去即可,不用改代码。
  - **没有浏览器不影响出 HTML 报告** —— 报告本身就是自包含单文件,双击就能看。
"""
import io, os, re, sys, glob, shutil, argparse, subprocess, time

CANDIDATES = {
    "edge": [
        # Windows(系统级 + 用户级安装)
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        # macOS
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        # Linux
        "/usr/bin/microsoft-edge",
        "/usr/bin/microsoft-edge-stable",
        "/opt/microsoft/msedge/msedge",
    ],
    "chrome": [
        # Windows
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        # macOS
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        # Linux
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ],
}

# 上面都没命中时,再按可执行名去 PATH 里找(覆盖非标准安装位置)
WHICH_NAMES = {
    "edge": ["msedge", "microsoft-edge", "microsoft-edge-stable"],
    "chrome": ["google-chrome", "google-chrome-stable", "chromium",
               "chromium-browser", "chrome"],
}


def find_browser(pref="auto", exe=""):
    """返回 (名字, 可执行文件路径);找不到返回 (None, None)。

    exe 非空时直接用它(绿色版 / 非默认安装位置)。
    """
    if exe:
        if os.path.isfile(exe):
            return "custom", exe
        return None, None
    order = ["edge", "chrome"] if pref == "auto" else [pref]
    for name in order:
        for p in CANDIDATES.get(name, []):
            if p and os.path.isfile(p):
                return name, p
        for cmd in WHICH_NAMES.get(name, []):
            p = shutil.which(cmd)
            if p:
                return name, p
    return None, None


def file_url(path):
    p = os.path.abspath(path).replace("\\", "/")
    return "file:///" + p.lstrip("/") if not p.startswith("/") else "file://" + p


def hunt_pdf(target_name, since, extra_dirs):
    """在浏览器安装目录 / cwd / 目标目录里找刚生成的 PDF。"""
    dirs = list(extra_dirs)
    for grp in CANDIDATES.values():
        for exe in grp:
            if os.path.isfile(exe):
                dirs.append(os.path.dirname(exe))
    dirs += [os.getcwd(), os.path.expanduser("~"), os.path.expanduser("~/Desktop")]
    seen = set()
    for d in dirs:
        if not d or d in seen or not os.path.isdir(d):
            continue
        seen.add(d)
        for pat in (target_name, "output.pdf", "*.pdf"):
            for f in glob.glob(os.path.join(d, pat)):
                try:
                    if os.path.getmtime(f) >= since:
                        return f
                except OSError:
                    pass
    return None


def main():
    ap = argparse.ArgumentParser(description="HTML → PDF")
    ap.add_argument("html")
    ap.add_argument("--out", default="", help="默认与 html 同目录同名 .pdf")
    ap.add_argument("--browser", default="auto", choices=["auto", "edge", "chrome"])
    ap.add_argument("--browser-exe", default="",
                    help="浏览器可执行文件路径(绿色版/非默认安装位置时用)")
    ap.add_argument("--timeout", type=int, default=240)
    a = ap.parse_args()

    src = os.path.abspath(a.html)
    if not os.path.isfile(src):
        sys.exit("[ERR] 文件不存在: %s" % src)
    out = os.path.abspath(a.out) if a.out else os.path.splitext(src)[0] + ".pdf"
    os.makedirs(os.path.dirname(out), exist_ok=True)

    name, exe = find_browser(a.browser, a.browser_exe)
    if not exe:
        sys.exit("[ERR] 找不到 Edge / Chrome,导不了 PDF。\n"
                 "  注意:**这不影响 HTML 报告** —— 报告是自包含单文件,双击就能看。\n"
                 "  想同时要 PDF 的话,二选一:\n"
                 "    1) 装个 Edge 或 Chrome(装完重跑本脚本即可,它会自己找到);\n"
                 "    2) 已经装了但没找到(绿色版/非默认路径):\n"
                 "       python topdf.py <报告.html> --browser-exe \"<浏览器exe完整路径>\"")
    print("[browser] %s -> %s" % (name, exe))

    # 先清掉旧的,免得误判
    if os.path.isfile(out):
        try:
            os.remove(out)
        except OSError:
            pass
    since = time.time() - 5

    # 注意:--print-to-pdf 给的路径 Edge 可能不遵守,所以同时记录它的 cwd
    cmd = [exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
           "--no-sandbox", "--virtual-time-budget=20000",
           "--run-all-compositor-stages-before-draw",
           "--print-to-pdf-no-header",
           "--print-to-pdf=" + out.replace("\\", "/"),
           file_url(src)]
    print("[cmd] %s" % " ".join('"%s"' % c if " " in c else c for c in cmd))
    try:
        subprocess.run(cmd, timeout=a.timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       cwd=os.path.dirname(out))
    except subprocess.TimeoutExpired:
        print("[WARN] 浏览器超时(%ds),继续找产出文件" % a.timeout)

    if not os.path.isfile(out):
        print("[info] 目标路径没有文件,去浏览器安装目录找…")
        found = hunt_pdf(os.path.basename(out), since, [os.path.dirname(out)])
        if found and os.path.abspath(found) != out:
            shutil.copy2(found, out)
            try:
                os.remove(found)
            except OSError:
                pass
            print("[fixed] 从 %s 拷回目标路径" % found)

    if not os.path.isfile(out):
        sys.exit("[ERR] PDF 未生成。检查:报告里是否 JS 报错 / 是否用了需要联网的资源")

    size = os.path.getsize(out)
    print("[done] %s  (%.1f MB)" % (out, size / 1048576.0))
    if size < 20 * 1024:
        print("[WARN] PDF 小于 20KB,可能是空白页 —— 检查图表 canvas 是否在 beforeprint 里重绘")

    # 顺手提示:确认 PDF 页数
    try:
        with io.open(out, "rb") as f:
            blob = f.read()
        pages = len(re.findall(rb"/Type\s*/Page[^s]", blob))
        if pages:
            print("[info] 约 %d 页" % pages)
    except Exception:
        pass


if __name__ == "__main__":
    main()
