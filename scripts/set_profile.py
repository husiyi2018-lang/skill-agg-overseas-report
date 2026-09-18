#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""写入/查看本机使用者档案 profile.json —— 每个销售只填一次。

为什么需要它：报告右上角的注册按钮、PDF 页眉的注册地址都是**销售本人的邀请
注册链接**,一人一条、彼此不同。这条链接不能硬编码进技能里(否则所有人分享出去
的报告都算在同一个人的邀请额度上),所以要在技能根目录存一份只属于本机的
profile.json,生成报告时自动填进 INVITE_URL 槽位。

用法:
  python set_profile.py --invite-url "https://s.ymapp.com/abcd"     # 设置/更新
  python set_profile.py --invite-url "https://..." --pagepub-name "出海素材报告"
  python set_profile.py --show                                      # 看当前存的什么
  python set_profile.py --get                                       # 只打印链接(给脚本用)
  python set_profile.py --fill <报告.html>                          # 把 {{INVITE_URL}} 填进报告
  python set_profile.py --clear                                     # 清空(换人用时)

优先级: 环境变量 AGG_INVITE_URL > profile.json > 无(自检会报缺失)
profile.json 已在 .gitignore 里,不会被推到公开仓库 —— 别把它删掉。
"""
import argparse, io, json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
PROFILE = os.path.join(SKILL, "profile.json")

ENV_KEY = "AGG_INVITE_URL"
SLOT = "{{INVITE_URL}}"


def load(path=PROFILE):
    """读 profile.json;文件不存在或坏了都返回 {}（不抛异常,自检要能容错）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save(d, path=PROFILE):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)          # 原子替换,中途断电不会留半个文件


def invite_url(d=None):
    """取邀请注册链接:环境变量优先,其次 profile.json。返回 (值, 来源)。"""
    v = (os.environ.get(ENV_KEY) or "").strip()
    if v:
        return v, "环境变量 %s" % ENV_KEY
    v = ((d if d is not None else load()).get("invite_url") or "").strip()
    if v:
        return v, "profile.json"
    return "", ""


def check_url(u):
    if not u.lower().startswith(("http://", "https://")):
        return "邀请链接必须以 http:// 或 https:// 开头,当前是:%s" % u[:60]
    if " " in u:
        return "邀请链接里不能有空格"
    return ""


def fill(files, url, slot=SLOT):
    """把报告里的 {{INVITE_URL}} 槽位一次性换成本人的邀请链接。

    为什么要单独有这个:这个链接在报告里出现**两处**(右上角按钮 href、PDF 页眉
    的 href + 可见文本),手工替换极易只改一处 —— 那处漏改的会指向别人的注册页。
    统一走这个函数,一处不漏。

    返回 (改动文件数, 总替换次数)。
    """
    nfile = nsub = 0
    for p in files:
        with io.open(p, "r", encoding="utf-8") as f:
            s = f.read()
        if slot not in s:
            continue
        cnt = s.count(slot)
        s = s.replace(slot, url)
        with io.open(p, "w", encoding="utf-8") as f:
            f.write(s)
        nfile += 1
        nsub += cnt
        print("  %s —— 替换 %d 处" % (p, cnt))
    return nfile, nsub


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--invite-url", dest="invite_url", default=None,
                    help="销售本人的邀请注册链接(完整 URL)")
    ap.add_argument("--pagepub-name", dest="pagepub_name", default=None,
                    help="发布到 pagepub 时用的站名(可留空,默认取报告标题)")
    ap.add_argument("--show", action="store_true", help="只显示当前档案")
    ap.add_argument("--get", action="store_true",
                    help="只打印邀请链接本身(给脚本/管道用),没有则退出码 1")
    ap.add_argument("--fill", nargs="+", default=None, metavar="HTML",
                    help="把这些报告 HTML 里的 {{INVITE_URL}} 就地替换成本人链接")
    ap.add_argument("--clear", action="store_true", help="清空档案(换人使用时)")
    ap.add_argument("--path", default=PROFILE, help="profile.json 路径(默认技能根目录)")
    a = ap.parse_args()

    cur, src = invite_url(load(a.path))

    if a.get:
        if not cur:
            sys.stderr.write("邀请链接未设置,先跑: python set_profile.py "
                             "--invite-url \"<你的邀请链接>\"\n")
            return 1
        sys.stdout.write(cur + "\n")
        return 0

    if a.fill:
        if not cur:
            print("[错误] 邀请链接未设置,先跑: python set_profile.py "
                  "--invite-url \"<你的邀请链接>\"")
            return 1
        nfile, nsub = fill(a.fill, cur)
        if not nfile:
            print("这些文件里没有 %s 槽位(可能已经填过了)。" % SLOT)
            return 0
        print("已把 %d 个文件里的 %d 处 %s 替换为: %s"
              % (nfile, nsub, SLOT, cur))
        print("来源: %s" % src)
        return 0

    if a.clear:
        if os.path.exists(a.path):
            os.remove(a.path)
            print("已清空: %s" % a.path)
        else:
            print("本来就没有: %s" % a.path)
        return 0

    if a.show or (a.invite_url is None and a.pagepub_name is None):
        d = load(a.path)
        cur, src = invite_url(d)
        print("档案文件: %s  (%s)" % (a.path, "存在" if d else "还没建"))
        print("邀请注册链接: %s" % (cur or "(未设置)"))
        if src:
            print("  来源: %s" % src)
        print("pagepub 站名: %s" % (d.get("pagepub_name") or "(未设置,默认用报告标题)"))
        if not cur:
            print("")
            print("设置方法: python \"%s\" --invite-url \"<你的邀请注册链接>\""
                  % os.path.abspath(__file__))
        return 0

    d = load(a.path)
    if a.invite_url is not None:
        u = a.invite_url.strip()
        if not u:
            print("邀请链接为空,没有改动。")
            return 1
        bad = check_url(u)
        if bad:
            print("[错误] %s" % bad)
            return 1
        d["invite_url"] = u
        d["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if a.pagepub_name is not None:
        d["pagepub_name"] = a.pagepub_name.strip()

    try:
        save(d, a.path)
    except Exception as e:
        print("[错误] 写入失败: %s" % e)
        return 1

    print("已写入 %s" % a.path)
    print("  邀请注册链接: %s" % d.get("invite_url", "(未设置)"))
    print("  pagepub 站名: %s" % (d.get("pagepub_name") or "(未设置,默认用报告标题)"))
    print("")
    print("后续所有报告会自动把这条链接填进右上角按钮和 PDF 页眉,无需再问。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
