#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境自检 —— 换机器 / 第一次拿到这个技能时,先跑这个。

用法:
  python setup_check.py

检查 5 项:
  1. Python 版本(≥3.8)
  2. YOUCLOUD_API_KEY 环境变量(取数必需)
  3. ffmpeg(封面、关键帧必需)
  4. Pillow(封面压缩;缺了报告会胀到 20MB+)
  5. Edge / Chrome(只有导 PDF 用;缺了不影响 HTML 报告)

缺东西时,除了逐项说明,还会打印一段**兜底提示词** ——
整段复制给 Claude,它会自己把依赖装好配好,使用者不需要懂命令行。

退出码:0 = 必需项齐全;1 = 有必需项缺失
"""
import io, os, sys, shutil, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)

OK, MISS, OPT = "  [OK]  ", "  [缺失] ", "  [可选] "


def has_env_key():
    for n in ("YOUCLOUD_API_KEY", "COZE_YOUCLOUD_API_KEY"):
        if (os.environ.get(n) or "").strip():
            return n
    return ""


def has_ffmpeg():
    p = shutil.which("ffmpeg")
    if not p:
        return ""
    try:
        subprocess.run([p, "-version"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
        return p
    except Exception:
        return ""


def has_pillow():
    try:
        import PIL
        return getattr(PIL, "__version__", "?")
    except ImportError:
        return ""


def find_browser():
    sys.path.insert(0, HERE)
    try:
        import topdf
        return topdf.find_browser("auto")
    except Exception:
        return None, None


def install_hint(win, mac, linux):
    if sys.platform.startswith("win"):
        return win
    if sys.platform == "darwin":
        return mac
    return linux


def main():
    print("=" * 66)
    print("  agg-overseas-report 环境自检")
    print("  技能位置: %s" % SKILL)
    print("=" * 66)

    missing = []      # 必需
    optional = []     # 可选

    # 1. Python
    v = sys.version_info
    if v >= (3, 8):
        print(OK + "Python %d.%d.%d" % (v[0], v[1], v[2]))
    else:
        print(MISS + "Python %d.%d.%d —— 需要 ≥3.8" % (v[0], v[1], v[2]))
        missing.append(("Python 版本过低", "脚本语法需要 Python 3.8 以上",
                        "装一个 3.8+ 的 Python: https://www.python.org/downloads/"))

    # 2. API Key
    k = has_env_key()
    if k:
        print(OK + "环境变量 %s 已设置" % k)
    else:
        print(MISS + "YOUCLOUD_API_KEY 未设置 —— 取数(aggclaw 分析 + 素材清单)会直接失败")
        missing.append((
            "YOUCLOUD_API_KEY 环境变量",
            "没有它 aggclaw 取数会直接报错退出,报告做不出来",
            "这个 Key 是**你自己的账号凭据**,别人给不了:"
            "登录 AppGrowing Global → 个人中心 / 企业信息 里复制 API Key。"
            "拿到后设为环境变量 —— "
            "Windows: 开始菜单搜「环境变量」→ 用户变量新增 YOUCLOUD_API_KEY;"
            "或用命令 setx YOUCLOUD_API_KEY \"<你的key>\"(设完要重开终端);"
            "macOS/Linux: 在 ~/.zshrc 或 ~/.bashrc 里加 export YOUCLOUD_API_KEY=\"<你的key>\""))

    # 3. ffmpeg
    ff = has_ffmpeg()
    if ff:
        print(OK + "ffmpeg  %s" % ff)
    else:
        print(MISS + "ffmpeg 未找到 —— 封面(视频抽帧)和关键帧都做不出来")
        missing.append((
            "ffmpeg",
            "报告里的素材封面是从视频首帧抽出来的,关键帧也要它,缺了这两步直接失败",
            "装法: " + install_hint(
                "Windows: winget install --id Gyan.FFmpeg -e(或 choco install ffmpeg);装完**重开终端**",
                "macOS: brew install ffmpeg(没装 brew 先装 brew)",
                "Linux: sudo apt install ffmpeg(或 dnf install ffmpeg)")))

    # 4. Pillow
    pl = has_pillow()
    if pl:
        print(OK + "Pillow %s" % pl)
    else:
        print(OPT + "Pillow 未安装 —— 封面不会被压缩,单文件可能胀到 20MB+")
        optional.append((
            "Pillow(PIL)",
            "封面压缩用;缺了不是不能跑,但报告会大到不好发",
            "装法: %s -m pip install Pillow" % sys.executable))

    # 5. 浏览器
    bname, bexe = find_browser()
    if bexe:
        print(OK + "Edge/Chrome(%s)%s" % (bname, bexe))
    else:
        print(OPT + "没找到 Edge / Chrome —— **只影响导 PDF,不影响 HTML 报告**")
        optional.append((
            "Edge 或 Chrome",
            "只有最后一步「导出 PDF」用它;HTML 报告是自包含单文件,双击就能看,不需要浏览器",
            "想同时要 PDF 就装一个: " + install_hint(
                "Windows: Edge 系统自带,若被卸了用 winget install Microsoft.Edge",
                "macOS: 装 Chrome 或 Edge(brew install --cask google-chrome)",
                "Linux: sudo apt install chromium(或 google-chrome)")))

    # ---- 结论 ----
    print("-" * 66)
    if not missing and not optional:
        print("  全部就绪,可以开工了。")
        return 0

    if missing:
        print("  有 %d 项**必需**依赖缺失,现在跑不出报告。" % len(missing))
    if optional:
        print("  另有 %d 项可选依赖没装(不影响主流程)。" % len(optional))

    print("""
最省事的做法:**不用自己装** —— 把下面整段复制给 Claude,它会全部搞定。
(复制范围:从下面那条横线开始,到结束横线为止)
""")
    print("=" * 66)
    print("我用的是 agg-overseas-report 技能(做海外广告素材投放报告),位置在:")
    print("  %s" % SKILL)
    print("刚跑了环境自检,下面这些没准备好。请你**直接帮我装好、配好**,不要让我自己动手:")
    print("")
    n = 1
    for name, why, how in (missing + optional):
        print("%d) %s —— %s" % (n, name, why))
        print("   建议做法: %s" % how)
        n += 1
    print("")
    print("要求:")
    print("- 装完请重新运行: python \"%s\"" % os.path.join(HERE, "setup_check.py"))
    print("  确认必需项都变成 [OK]。")
    print("- 需要我自己提供的凭据(比如 YOUCLOUD_API_KEY),请明确告诉我从哪个页面拿、拿到后怎么设,")
    print("  能代我设就代我设(Windows 可用 setx,设完提醒我重开终端)。")
    print("- 遇到任何选择你替我决定,不要反问我技术细节。")
    print("- 全部就绪后,再问我:要分析哪个产品、哪个时间段,然后按 SKILL.md 的流程开始。")
    print("=" * 66)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
