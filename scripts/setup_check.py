#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境自检 —— 换机器 / 第一次拿到这个技能时,先跑这个。

用法:
  python setup_check.py

检查 7 项:
  1. Python 版本(≥3.8)
  2. YOUCLOUD_API_KEY 环境变量(取数必需)
  3. ffmpeg(封面、关键帧必需)
  4. Pillow(封面压缩;缺了报告会胀到 20MB+)
  5. Edge / Chrome(只有导 PDF 用;缺了不影响 HTML 报告)
  6. 邀请注册链接(每人不同!报告右上角按钮与 PDF 页眉都挂它)
  7. pagepub(把做好的报告发布成公开链接,发给客户就能点开)

第 6、7 项问的**不是技术依赖,是使用者本人的两样东西**:
  - 邀请注册链接:一人一条,不能共用,所以必须本人提供一次;
    存起来后用 setup_check 同一目录下的 set_profile.py 随时改。
  - pagepub API 密钥:在 https://pagepub.net 控制台自己创建。

缺东西时,除了逐项说明,还会打印一段**兜底提示词** ——
整段复制给 Claude,它会自己把依赖装好配好,使用者不需要懂命令行。

退出码:0 = 必需项齐全;1 = 有必需项缺失
"""
import io, json, os, sys, shutil, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
PROFILE = os.path.join(SKILL, "profile.json")

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


def invite_url():
    """邀请注册链接:环境变量优先,其次本机 profile.json。返回 (值, 来源)。"""
    v = (os.environ.get("AGG_INVITE_URL") or "").strip()
    if v:
        return v, "环境变量 AGG_INVITE_URL"
    try:
        with open(PROFILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        v = (d.get("invite_url") or "").strip() if isinstance(d, dict) else ""
    except Exception:
        v = ""
    return (v, "profile.json") if v else ("", "")


def find_pagepub():
    """pagepub CLI:先查 PATH,再查几个常见安装位(多数安装方式不写进 PATH)。"""
    p = shutil.which("pagepub") or shutil.which("pagepub.exe")
    if p:
        return p
    home = os.path.expanduser("~")
    cands = [os.path.join(home, ".local", "bin", "pagepub"),
             os.path.join(home, ".local", "bin", "pagepub.exe"),
             os.path.join(home, "bin", "pagepub"),
             os.path.join(home, ".pagepub", "pagepub.exe")]
    for env, sub in (("LOCALAPPDATA", "pagepub/pagepub.exe"),
                     ("ProgramFiles", "pagepub/pagepub.exe"),
                     ("ProgramFiles", "PagePub/pagepub.exe")):
        base = os.environ.get(env)
        if base:
            cands.append(os.path.join(base, *sub.split("/")))
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return ""


def pagepub_cred():
    """pagepub 凭据:环境变量优先,其次 ~/.pagepub/config.json（login 写的）。"""
    if (os.environ.get("PAGEPUB_API_KEY") or "").strip():
        return "环境变量 PAGEPUB_API_KEY"
    cfg = os.path.join(os.path.expanduser("~"), ".pagepub", "config.json")
    try:
        with open(cfg, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return ""
    if isinstance(d, dict) and (d.get("api_key") or "").strip():
        return cfg
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
    print("  agg-creative-report 环境自检")
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

    # 6. 邀请注册链接 —— 每人不同,只有使用者本人能提供
    inv, src = invite_url()
    if inv:
        print(OK + "邀请注册链接已设置(%s): %s" % (src, inv))
    else:
        print(MISS + "邀请注册链接未设置 —— 报告右上角注册按钮和 PDF 页眉都会留空")
        missing.append((
            "邀请注册链接(每人不同)",
            "报告是发给客户看的,右上角按钮与 PDF 页眉都挂**你自己的**邀请注册链接;"
            "不填的话,报告转发再多也导不回你的账号",
            "登录 AppGrowing Global → 邀请/推广 页面复制属于你的邀请注册链接,"
            "然后一条命令存进本机档案(以后所有报告自动用它,不用再填):\n"
            "      python \"%s\" --invite-url \"<你的邀请链接>\""
            % os.path.join(HERE, "set_profile.py")))

    # 7. pagepub —— 把做好的报告变成一个能直接发给客户的公开链接
    pp = find_pagepub()
    if pp:
        print(OK + "pagepub CLI  %s" % pp)
    else:
        print(MISS + "pagepub CLI 未找到 —— 报告做完了发不出去公开链接")
        missing.append((
            "pagepub 命令行工具",
            "报告最后一步是把 HTML 目录发布成一个公开网址,客户点开就能看,"
            "不用下载几十 MB 的附件;这一步靠 pagepub 完成",
            "装法: " + install_hint(
                "Windows: 在 Git Bash 里执行 curl -fsSL https://pagepub.net/cli/install.sh | sh;"
                "若提示不支持,去 https://pagepub.net 下载 Windows 版压缩包,解压后把 "
                "pagepub.exe 放到 C:\\Users\\<你>\\.local\\bin 下(这个目录不用写进 PATH,脚本会自己找到)",
                "macOS: curl -fsSL https://pagepub.net/cli/install.sh | sh",
                "Linux: curl -fsSL https://pagepub.net/cli/install.sh | sh")))

    cred = pagepub_cred()
    if cred:
        print(OK + "pagepub 凭据已配置(%s)" % cred)
    else:
        print(MISS + "pagepub API 密钥未配置 —— 发布时会被拒")
        missing.append((
            "pagepub API 密钥",
            "pagepub 用密钥认证你的账号;没有它发布命令会报「未配置服务器地址/API 密钥」",
            "这是**你自己的账号凭据**(pp_ 开头):打开 https://pagepub.net 登录 → "
            "控制台「API 密钥」→ 新建密钥 → 把它给我,我执行 "
            "pagepub login --api-key <密钥> 存好(凭据只存在你本机 ~/.pagepub/config.json,"
            "**不要写进技能目录,更不要提交到仓库**)"))

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
    print("我用的是 agg-creative-report 技能(做海外广告素材投放报告),位置在:")
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
    print("- 需要我自己提供的凭据,请**一次性问全**,别反复来问:")
    print("    a) YOUCLOUD_API_KEY(AppGrowing 取数用)")
    print("    b) 我的邀请注册链接(每人不同,要挂在我分享出去的每份报告上)")
    print("    c) pagepub API 密钥(把报告发布成公开链接用)")
    print("  请告诉我每样从哪个页面复制、复制后贴给你就行;能代我设就代我设")
    print("  (Windows 环境变量可用 setx,设完提醒我重开终端)。")
    print("  b 请用 set_profile.py 存进本机档案,c 请用 pagepub login 存好 —— ")
    print("  两者都只落在我本机,不要写进技能目录,更不要提交到 git。")
    print("- 遇到任何选择你替我决定,不要反问我技术细节。")
    print("- 全部就绪后,再问我:要分析哪个产品、哪个时间段;按 SKILL.md 的流程做完报告,")
    print("  最后用 pagepub 发布成公开链接发给我。")
    print("=" * 66)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
