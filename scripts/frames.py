#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""关键帧抽取 —— 供「真实剪切点」与「开场故事板」使用。

用法:
  python frames.py --dir <工作区> --ids id1,id2 [--times 0.6,2.6,5.4,8.6]
      [--width 180] [--storyboard]

产出:
  <工作区>/frames/<id>_<t>s.jpg
  <工作区>/work/frames.json
      {id: [{"t": 0.6, "data_uri": "data:image/jpeg;base64,..."}, ...]}

为什么要真实抽帧:
  报告里的「关键帧」必须是**真的从视频里切出来的**,
  不能用封面重复充数 —— 那等于把同一张图贴五遍,读者一看就穿帮。

抽帧时间点约定:
  - 通用关键帧:0.6 / 2.6 / 5.4 / 8.6 秒(对应 0-3s Hook / 3-8s 玩法 / 收口)
  - 开场故事板(sb):同上,用于 `takeaway` 块的 sb/sbT 字段

依赖 ffmpeg(需在 PATH 里)。没有 ffmpeg 会明确报错,不会静默产出空结果。

注意:
  - 素材若是**完整长片**(几十 MB),只抽前 10 秒,不要整片下载抽帧
  - 视频链接有时效性,过期后从 work/videos.json 或 raw/ 里换新链接
"""
import io, os, re, sys, json, base64, argparse, subprocess, tempfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
DEFAULT_TIMES = [0.6, 2.6, 5.4, 8.6]


def load_json(p, default=None):
    if not os.path.isfile(p):
        return default
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def have_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


def download(url, dst, timeout=300):
    with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r, \
            open(dst, "wb") as f:
        while True:
            c = r.read(1 << 16)
            if not c:
                break
            f.write(c)


def grab(video, t, out, width):
    """抽第 t 秒的一帧;失败返回 False。"""
    cmd = ["ffmpeg", "-y", "-ss", "%.2f" % t, "-i", video, "-frames:v", "1",
           "-vf", "scale=%d:-2" % width, "-q:v", "4", out]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return r.returncode == 0 and os.path.isfile(out) and os.path.getsize(out) > 0


def main():
    ap = argparse.ArgumentParser(description="关键帧抽取")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--ids", default="", help="逗号分隔素材 ID")
    ap.add_argument("--ids-file", default="", help="从文件读 ID,每行一个")
    ap.add_argument("--times", default=",".join(str(x) for x in DEFAULT_TIMES))
    ap.add_argument("--width", type=int, default=180)
    ap.add_argument("--storyboard", action="store_true",
                    help="标记为故事板用途(写进 frames.json 的 kind 字段)")
    a = ap.parse_args()

    if not have_ffmpeg():
        sys.exit("[ERR] 找不到 ffmpeg —— 关键帧抽不出来。\n"
                 "      最省事:跑 python scripts/setup_check.py,\n"
                 "      把打印出来的那段提示词整段发给 Claude,它会帮你装好。\n"
                 "      (装完要重开终端;详见 references/setup.md)")

    ids = []
    if a.ids:
        ids = [x.strip() for x in a.ids.split(",") if x.strip()]
    if a.ids_file and os.path.isfile(a.ids_file):
        with io.open(a.ids_file, encoding="utf-8") as f:
            ids += [l.strip() for l in f if l.strip()]
    if not ids:
        sys.exit("[ERR] 需要 --ids 或 --ids-file")

    times = [float(x) for x in a.times.split(",") if x.strip()]

    # 素材来源:优先 raw/material_src.json({id: {url: ...}}),其次 raw/materials_all.json
    src = load_json(os.path.join(a.dir, "raw", "material_src.json"), {}) or {}
    mats = load_json(os.path.join(a.dir, "raw", "materials_all.json"), []) or []
    if isinstance(mats, dict):
        mats = mats.get("data") or list(mats.values())
    for e in mats:
        m = e.get("material") if isinstance(e, dict) and "material" in e else e
        if isinstance(m, dict) and m.get("id") and m.get("download_url"):
            src.setdefault(m["id"], {"url": m["download_url"]})

    fr_dir = os.path.join(a.dir, "frames")
    os.makedirs(fr_dir, exist_ok=True)
    work_dir = os.path.join(a.dir, "work")
    out_p = os.path.join(work_dir, "frames.json")
    frames = load_json(out_p, {}) or {}

    tmpd = tempfile.mkdtemp(prefix="frames_")
    ok_ids = 0
    for mid in ids:
        u = (src.get(mid) or {}).get("url")
        if not u:
            print("  [skip] %s 无视频直链" % mid[:12])
            continue
        local = os.path.join(tmpd, mid + ".mp4")
        try:
            download(u, local)
        except Exception as e:
            print("  [FAIL] %s 下载失败: %s" % (mid[:12], e))
            continue
        got = []
        for t in times:
            out = os.path.join(fr_dir, "%s_%.1fs.jpg" % (mid, t))
            if not grab(local, t, out, a.width):
                continue
            raw = open(out, "rb").read()
            got.append({"t": t,
                        "kind": "storyboard" if a.storyboard else "keyframe",
                        "data_uri": "data:image/jpeg;base64," + base64.b64encode(raw).decode()})
        if got:
            frames[mid] = got
            ok_ids += 1
            print("  [ok] %s  抽到 %d/%d 帧" % (mid[:12], len(got), len(times)))
        else:
            print("  [FAIL] %s 一帧都没抽到(视频可能损坏或时长为 0)" % mid[:12])
        try:
            os.remove(local)
        except OSError:
            pass

    save_json(out_p, frames)
    print("\n[done] %d 个素材有帧 -> %s" % (ok_ids, out_p))
    print("[铁律] 报告里的关键帧必须来自这里,不能用封面重复充数")


if __name__ == "__main__":
    main()
