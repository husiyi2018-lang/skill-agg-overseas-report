#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""素材封面:从素材视频抽首帧 + 压缩 + base64 化。

用法:
  python covers.py --dir <工作区> --ids id1,id2,...     # 补指定素材
  python covers.py --dir <工作区> --all                  # 补清单里全部
  python covers.py --dir <工作区> --all --force          # 已存在的也重做
      [--t 0.6] [--width 360] [--quality 72]

输入:  <工作区>/raw/materials_all.json   (claw.py materials 的落盘结果)
产出:  <工作区>/covers/<id>.jpg          压缩后的封面(视频首帧)
       <工作区>/work/covers.json         {id: {"data_uri": "data:image/jpeg;base64,..."}}

为什么是抽首帧:
  aggclaw 的会话素材接口只回 {id, detail_url, download_url},**没有封面图字段**,
  所以封面一律取**视频第 0.6 秒那一帧**(与 frames.py 的 Hook 帧同一时间点,画面口径一致)。

为什么必须压缩:
  原图直嵌会让单文件到 20MB+(实测 60 张 17MB)。
  压到**宽 360px / JPEG q72** → 60 张约 3.35MB base64,报告落在 2MB 出头,可离线看。

依赖 ffmpeg(需在 PATH 里)。没有 ffmpeg 会明确报错,不会静默产出空结果。

注意:
  - download_url 是**有时效性**的链接,过期后重跑 claw.py materials 换新链接
  - 长片不要整条下载:先让 ffmpeg 直接在 URL 上抽帧(HTTP 按需读),
    失败才回落到「下载到临时文件再抽」
"""
import io, os, sys, json, time, base64, shutil, argparse, subprocess, tempfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

WIDTH = 360       # 压缩目标宽度
QUALITY = 72      # JPEG 质量
FRAME_T = 0.6     # 抽帧时间点(秒)
GRAB_WIDTH = 720  # 抽帧宽度(再压到 WIDTH,留点余量)


def have_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


def load_json(p, default=None):
    if not os.path.isfile(p):
        return default
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def grab(src, t, out, width):
    """从本地文件或 URL 抽第 t 秒的一帧;失败返回 False。"""
    cmd = ["ffmpeg", "-y", "-ss", "%.2f" % t, "-i", src, "-frames:v", "1",
           "-vf", "scale=%d:-2" % width, "-q:v", "4", out]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return r.returncode == 0 and os.path.isfile(out) and os.path.getsize(out) > 0


def download(url, dst, timeout=300):
    with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r, \
            open(dst, "wb") as f:
        while True:
            c = r.read(1 << 16)
            if not c:
                break
            f.write(c)


def compress(raw, width=WIDTH, quality=QUALITY):
    """压到指定宽度 / JPEG 质量,返回 (bytes, mime)。PIL 缺失时原样返回。"""
    try:
        from PIL import Image
    except ImportError:
        print("    [WARN] 未装 Pillow,跳过压缩(报告会胀到 20MB+) —— "
              "pip install Pillow,或跑 scripts/setup_check.py 让 Claude 装")
        ext = ".png" if raw[:4] == b"\x89PNG" else ".jpg"
        return raw, ("image/png" if ext == ".png" else "image/jpeg")
    try:
        im = Image.open(io.BytesIO(raw))
        im = im.convert("RGB")
        if im.width > width:
            im = im.resize((width, max(1, int(im.height * width / im.width))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        print("    [WARN] 压缩失败,用原图: %s" % e)
        return raw, "image/jpeg"


def main():
    ap = argparse.ArgumentParser(description="封面抽帧 + 压缩 + base64")
    ap.add_argument("--dir", required=True, help="工作区目录")
    ap.add_argument("--ids", default="", help="逗号分隔;不给则配 --all")
    ap.add_argument("--all", action="store_true", help="处理清单里全部素材")
    ap.add_argument("--t", type=float, default=FRAME_T, help="抽帧时间点(秒),默认 0.6")
    ap.add_argument("--width", type=int, default=WIDTH)
    ap.add_argument("--quality", type=int, default=QUALITY)
    ap.add_argument("--force", action="store_true", help="已存在的也重做")
    a = ap.parse_args()

    if not have_ffmpeg():
        sys.exit("[ERR] 找不到 ffmpeg —— 封面是从视频首帧抽的,没有它做不出来。\n"
                 "      最省事:跑 python scripts/setup_check.py,\n"
                 "      把打印出来的那段提示词整段发给 Claude,它会帮你装好。\n"
                 "      (装完 ffmpeg 要重开终端;详见 references/setup.md)")

    raw_dir = os.path.join(a.dir, "raw")
    cov_dir = os.path.join(a.dir, "covers")
    work_dir = os.path.join(a.dir, "work")
    os.makedirs(cov_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)

    mats_p = os.path.join(raw_dir, "materials_all.json")
    if not os.path.isfile(mats_p):                  # 兼容落在 work/ 的旧工作区
        alt = os.path.join(work_dir, "materials_all.json")
        if os.path.isfile(alt):
            mats_p = alt
    mats_list = load_json(mats_p)
    if not mats_list:
        sys.exit("[ERR] 找不到素材清单: %s\n      先跑 claw.py materials 拉会话素材" % mats_p)
    if isinstance(mats_list, dict):
        mats_list = mats_list.get("data") or list(mats_list.values())
    # 兼容 [{material:{...}}] 与 [{...}] 两种形状
    by_id = {}
    for e in mats_list:
        m = e.get("material") if isinstance(e, dict) and "material" in e else e
        if isinstance(m, dict) and m.get("id"):
            by_id[m["id"]] = m

    covers_p = os.path.join(work_dir, "covers.json")
    covers = load_json(covers_p, {}) or {}

    if a.ids:
        want = [x.strip() for x in a.ids.split(",") if x.strip()]
    elif a.all:
        want = list(by_id.keys())
    else:
        sys.exit("[ERR] 需要 --ids 或 --all")

    todo = [i for i in want if a.force or i not in covers]
    print("请求 %d 个,待处理 %d 个(清单内 %d)" % (len(want), len(todo), len(by_id)))

    tmpd = tempfile.mkdtemp(prefix="covers_")
    ok = fail = bytes_in = bytes_out = 0
    for mid in todo:
        x = by_id.get(mid)
        if not x:
            print("  [skip] 不在素材清单: %s" % mid)
            fail += 1
            continue
        u = (x.get("download_url") or "").strip()
        if not u:
            print("  [skip] 无视频直链: %s" % mid)
            fail += 1
            continue
        fr = os.path.join(tmpd, mid + ".jpg")
        if os.path.isfile(fr):
            os.remove(fr)
        how = "URL直抽"
        if not grab(u, a.t, fr, GRAB_WIDTH):
            how = "下载后抽帧"
            local = os.path.join(tmpd, mid + ".mp4")
            try:
                download(u, local)
            except Exception as e:
                print("  [FAIL] %s 下载失败: %s" % (mid[:12], e))
                fail += 1
                continue
            got = grab(local, a.t, fr, GRAB_WIDTH)
            try:
                os.remove(local)
            except OSError:
                pass
            if not got:
                print("  [FAIL] %s 抽帧失败(视频可能损坏或时长为 0)" % mid[:12])
                fail += 1
                continue
        try:
            raw = open(fr, "rb").read()
        except OSError as e:
            print("  [FAIL] %s 读帧失败: %s" % (mid[:12], e))
            fail += 1
            continue
        comp, mime = compress(raw, a.width, a.quality)
        ext = ".png" if mime == "image/png" else ".jpg"
        with open(os.path.join(cov_dir, mid + ext), "wb") as f:
            f.write(comp)
        covers[mid] = {"data_uri": "data:%s;base64,%s" % (mime, base64.b64encode(comp).decode())}
        ok += 1
        bytes_in += len(raw)
        bytes_out += len(comp)
        print("  [ok] %s  %4dKB -> %4dKB (%s)" % (mid[:12], len(raw) // 1024, len(comp) // 1024, how))
        time.sleep(0.4)

    shutil.rmtree(tmpd, ignore_errors=True)
    save_json(covers_p, covers)
    print("\n[done] 成功 %d / 失败 %d | 压缩 %dKB -> %dKB (%.0f%%)"
          % (ok, fail, bytes_in // 1024, bytes_out // 1024,
             (100.0 * bytes_out / bytes_in) if bytes_in else 0))
    print("       covers.json 共 %d 条 -> %s" % (len(covers), covers_p))
    print("[提示] 抽帧失败的素材要在报告口径里说明其卡片只有文字")


if __name__ == "__main__":
    main()
