#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""素材内嵌(视频主路径):下载 → probe → **一律重编码** → 判体积 → base64。

用法:
  python media_embed.py --dir <工作区> --ids id1,id2 [--max-mb 2.5] [--total-mb 14.0]
  python media_embed.py --dir <工作区> --all
  python media_embed.py --dir <工作区> --all --force

输入:  <工作区>/raw/materials_all.json   (claw.py materials 的落盘结果)
产出:  <工作区>/work/videos.json
       { "<全量素材ID>": {"kind":"video|image", "data_uri":"data:video/mp4;base64,...",
                          "size":int, "orig":int, "dur":float, "w":int, "h":int} }

为什么"一律重编码"而不是"先探体积、超了就不要":
  实测里超预算的恰恰是**最有代表性的头部素材** —— 按原片体积分档会一刀砍掉证据链。
  标定: 原片 15MB → 重编码后 1.05MB(约 15:1)。
  所以「原片多大」和「能不能内嵌」基本无关,关键只在重编码参数。

为什么这个脚本必须存在:
  SKILL.md 第 2 步「素材实体化」把视频内嵌列为主路径,而 videos.py(Range 探体积分档)
  的 ≤2MB 判据会把头部素材全砍掉,只是备用。少了本脚本,卡片就只能退化成封面兜底 ——
  而卡片退化**不会报错**,只会被读者发现(pointers.md #21)。

降级规则:
  ffprobe 查不到视频流(实拍到的 …-102 后缀其实是 JPEG)→ kind="image",
  原图直接当封面,不做抽帧。
  重编码后仍 > --max-mb,或累计超出 --total-mb → **不写入** videos.json,
  该素材由 covers.py 的封面兜底,口径里必须说明有多少条走了兜底。

依赖 ffmpeg / ffprobe(需在 PATH 里);缺失时明确报错,不静默产出空结果。
"""
import io, os, sys, json, base64, argparse, subprocess, tempfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

EMBED_MAX_MB = 2.5     # 单条内嵌上限
TOTAL_MAX_MB = 14.0    # 全报告内嵌累计上限
SCALE_W = 270          # 重编码目标宽度(竖屏素材)

# 重编码参数:窄宽度 + 高 CRF + baseline profile。
# baseline 是为了老浏览器也能硬解;aac 48k 单声道让音频几乎不占体积;
# faststart 让播放器边下边播。
VCODEC = ["-vf", "scale=%d:-2" % SCALE_W,
          "-c:v", "libx264", "-crf", "32", "-preset", "veryfast",
          "-pix_fmt", "yuv420p", "-profile:v", "baseline",
          "-c:a", "aac", "-b:a", "48k", "-ac", "1",
          "-movflags", "+faststart"]


def have_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
        subprocess.run(["ffprobe", "-version"], stdout=subprocess.DEVNULL,
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


def download(url, dst, timeout=600):
    with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r, \
            open(dst, "wb") as f:
        while True:
            c = r.read(1 << 16)
            if not c:
                break
            f.write(c)


def is_still(path):
    """按文件头判静态图。**必须排在 ffprobe 前面** —— ffprobe 对 JPEG/PNG 会报出一条
    MJPEG/PNG 视频流且 duration=0,于是「有视频流」为真,静态图会被当成视频转成
    **只有一帧的 mp4**(实测 58KB 的 JPEG → 4KB 的假视频)。那种卡片点开是张静止图,
    却顶着「视频」徽标,比走封面兜底更误导。判据:magic bytes + duration≈0 双保险。"""
    try:
        with open(path, "rb") as f:
            head = f.read(12)
    except OSError:
        return False
    if head[:2] == b"\xff\xd8":          # JPEG
        return True
    if head[:8] == b"\x89PNG\r\n\x1a\n":  # PNG
        return True
    if head[:3] == b"GIF":
        return True
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return True
    return False


def probe(path):
    """返回 (w, h, dur) 或 None(静态图 / 无视频流)。"""
    if is_still(path):
        return None
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height", "-show_entries",
                        "format=duration", "-of", "json", path],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        return None
    try:
        j = json.loads(r.stdout.decode("utf-8", "replace"))
    except Exception:
        return None
    streams = j.get("streams") or []
    if not streams:
        return None
    w = int(streams[0].get("width") or 0)
    h = int(streams[0].get("height") or 0)
    try:
        dur = float((j.get("format") or {}).get("duration") or 0)
    except Exception:
        dur = 0.0
    if not w or not h:
        return None
    if dur and dur < 1.0:
        # 单帧/极短:当静态图处理,不要转成 1 帧 mp4
        return None
    return w, h, dur


def transcode(src, dst, scale=SCALE_W, crf=32):
    vc = list(VCODEC)
    vc[1] = "scale=%d:-2" % scale          # -vf 的参数
    vc[vc.index("-crf") + 1] = str(crf)
    cmd = ["ffmpeg", "-y", "-i", src] + vc + ["-loglevel", "error", dst]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return r.returncode == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 0


def main():
    ap = argparse.ArgumentParser(description="素材视频重编码内嵌")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--ids", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--max-mb", type=float, default=EMBED_MAX_MB)
    ap.add_argument("--total-mb", type=float, default=TOTAL_MAX_MB)
    ap.add_argument("--scale", type=int, default=SCALE_W,
                    help="重编码目标宽(默认 %d);素材偏长时可调小以塞进预算" % SCALE_W)
    ap.add_argument("--crf", type=int, default=32, help="x264 CRF,越大越小越糊(默认 32)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    if not have_ffmpeg():
        sys.exit("[ERR] 找不到 ffmpeg / ffprobe —— 视频内嵌做不出来。\n"
                 "      最省事:跑 python scripts/setup_check.py,\n"
                 "      把打印出来的那段提示词整段发给 Claude,它会帮你装好。\n"
                 "      (装完要重开终端;详见 references/setup.md)")

    mats_p = os.path.join(a.dir, "raw", "materials_all.json")
    if not os.path.isfile(mats_p):
        alt = os.path.join(a.dir, "work", "materials_all.json")
        if os.path.isfile(alt):
            mats_p = alt
    mats_list = load_json(mats_p)
    if not mats_list:
        sys.exit("[ERR] 找不到素材清单: %s\n      先跑 claw.py materials 拉会话素材" % mats_p)
    if isinstance(mats_list, dict):
        mats_list = mats_list.get("data") or list(mats_list.values())
    by_id = {}
    for e in mats_list:
        m = e.get("material") if isinstance(e, dict) and "material" in e else e
        if isinstance(m, dict) and m.get("id"):
            by_id[m["id"]] = m

    vp = os.path.join(a.dir, "work", "videos.json")
    videos = load_json(vp, {}) or {}
    # 累计已用 = 已写进 videos.json 的 data_uri 长度（base64），与下面新增项的
    # payload 同量纲。旧版这里 *3//4 折回原始字节，跟前面按原始字节判的闸门"自洽"，
    # 但两者一起偏离了真实产物大小 —— 双错互证，所以一直没被发现。
    used = sum(len(v.get("data_uri") or "") for v in videos.values())

    if a.ids:
        want = [x.strip() for x in a.ids.split(",") if x.strip()]
    elif a.all:
        want = list(by_id.keys())
    else:
        sys.exit("[ERR] 需要 --ids 或 --all")

    todo = [i for i in want if a.force or i not in videos]
    if a.force:
        # --force 重跑时必须先把旧条目摘掉、并把它们占的额度退回 used。
        # 不摘的话起点就是「旧总量」，任何新条目都会撞预算闸门被拒 ——
        # 实测表现为 **0 条内嵌、全部走封面兜底**,而日志只说"累计将超总额度",看不出是自撞。
        for i in todo:
            v = videos.pop(i, None)
            if isinstance(v, dict):
                used -= len(v.get("data_uri") or "")
        used = max(used, 0)
    cap_bytes = int(a.max_mb * 1024 * 1024)
    tot_bytes = int(a.total_mb * 1024 * 1024)
    print("请求 %d 个,待处理 %d 个(清单内 %d);已内嵌 %d 条 / %.1fMB"
          % (len(want), len(todo), len(by_id), len(videos), used / 1048576.0))

    tmpd = tempfile.mkdtemp(prefix="embed_")
    ok = img = big = fail = 0
    for mid in todo:
        x = by_id.get(mid)
        if not x:
            print("  [skip] 不在素材清单: %s" % mid[:12])
            fail += 1
            continue
        u = (x.get("download_url") or "").strip()
        if not u:
            print("  [skip] 无视频直链: %s" % mid[:12])
            fail += 1
            continue
        local = os.path.join(tmpd, mid + ".bin")
        try:
            download(u, local)
        except Exception as e:
            print("  [FAIL] %s 下载失败: %s" % (mid[:12], e))
            fail += 1
            continue
        orig = os.path.getsize(local)

        pr = probe(local)
        if pr is None:
            # 不是视频(实测有 …-102 后缀其实是 JPEG) → 原图直接当封面
            raw = open(local, "rb").read()
            mime = "image/png" if raw[:4] == b"\x89PNG" else "image/jpeg"
            if len(raw) > cap_bytes:
                print("  [BIG ] %s 图片 %dKB 超单条上限,走封面兜底" % (mid[:12], len(raw) // 1024))
                big += 1
                os.remove(local)
                continue
            img_uri = "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode())
            videos[mid] = {"kind": "image", "data_uri": img_uri,
                           "size": len(raw), "payload": len(img_uri),
                           "orig": orig, "dur": 0, "w": 0, "h": 0}
            used += len(img_uri)        # 同视频分支:预算按写进 HTML 的长度算
            img += 1
            print("  [img ] %s 非视频流,原图 %dKB 内嵌" % (mid[:12], len(raw) // 1024))
            os.remove(local)
            continue

        w, h, dur = pr
        out = os.path.join(tmpd, mid + ".mp4")
        if not transcode(local, out, a.scale, a.crf):
            print("  [FAIL] %s 重编码失败" % mid[:12])
            fail += 1
            os.remove(local)
            continue
        size = os.path.getsize(out)
        b64 = "data:video/mp4;base64," + base64.b64encode(open(out, "rb").read()).decode()
        # ★ 预算必须按**写进 HTML 的长度**算,不能按重编码后文件的原始字节算。
        # base64 比原始字节大约 1.37 倍,拿原始字节当闸门会让「14MB 预算」的产物
        # 实际带上 ~19MB 载荷 —— 实测 Magic Sort! 那份报告就是这样胀到 23MB 的,
        # 而脚本自报的「base64 合计约 13.8MB」看着完全合规,不查根本发现不了。
        payload = len(b64)
        if payload > cap_bytes:
            print("  [BIG ] %s 重编码后载荷 %dKB 超上限 %.1fMB,走封面兜底"
                  % (mid[:12], payload // 1024, a.max_mb))
            big += 1
        elif used + payload > tot_bytes:
            print("  [BIG ] %s 累计将超总额度 %.1fMB,走封面兜底" % (mid[:12], a.total_mb))
            big += 1
        else:
            videos[mid] = {"kind": "video", "data_uri": b64, "size": size,
                           "payload": payload, "orig": orig,
                           "dur": round(dur, 1), "w": w, "h": h}
            used += payload
            ok += 1
            print("  [ok  ] %s %5dKB -> %5dKB 原文件 / %5dKB 内嵌 (%dx%d %.1fs)"
                  % (mid[:12], orig // 1024, size // 1024, payload // 1024, w, h, dur))
        for p in (local, out):
            try:
                os.remove(p)
            except OSError:
                pass

    try:
        os.remove(os.path.join(tmpd, "*.bin"))
    except Exception:
        pass
    import shutil
    shutil.rmtree(tmpd, ignore_errors=True)

    save_json(vp, videos)
    print("\n[done] 视频内嵌 %d / 图片 %d / 超预算走兜底 %d / 失败 %d"
          % (ok, img, big, fail))
    print("       videos.json 共 %d 条,写进 HTML 的载荷合计约 %.1fMB(预算 %.1fMB) -> %s"
          % (len(videos), used / 1048576.0, a.total_mb, vp))
    print("[铁律] 走了封面兜底的条数必须在报告口径里写明,否则读者会以为卡片坏了")


if __name__ == "__main__":
    main()
