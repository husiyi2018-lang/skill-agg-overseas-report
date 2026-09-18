#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频分档:≤阈值内嵌(base64)、>阈值走封面+跳转。

用法:
  python videos.py raw/materials_all.json --out work
      [--max-mb 2] [--max-total-mb 20] [--ids id1,id2] [--all]

产出:
  work/videos.json  {id: {"kind":"embed","data_uri":"data:video/mp4;base64,...","size":n}}
                    {id: {"kind":"cover","size":n,"too_big":true}}
  内嵌素材的封面仍由 covers.py 产出(视频抽的首帧,可选)。

规则:
  - 体积用 HTTP Range 探测(Content-Range 总长),不整段下载。
  - ≤max-mb 且累计不超 max-total-mb → 下载转 base64 内嵌。
  - 超单条阈值 或 超总额度 → 走封面+跳转(避免单文件过大)。
"""
import sys, os, io, json, base64, argparse, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_MAX_MB = 2.0
DEFAULT_TOTAL_MB = 20.0


def probe_size(url, timeout=30):
    """返回字节数;探测失败返回 None。先 Range 0-0 读 Content-Range,失败再 HEAD。"""
    try:
        req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            cr = r.headers.get("Content-Range")  # bytes 0-0/1234567
            if cr and "/" in cr:
                total = cr.split("/")[-1].strip()
                if total.isdigit():
                    return int(total)
            cl = r.headers.get("Content-Length")
            if r.getcode() == 206 and cl:
                return int(cl)
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            cl = r.headers.get("Content-Length")
            if cl:
                return int(cl)
    except Exception:
        pass
    return None


def download(url, timeout=300):
    buf = io.BytesIO()
    with urllib.request.urlopen(url, timeout=timeout) as r:
        while True:
            c = r.read(1 << 16)
            if not c:
                break
            buf.write(c)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("materials")
    ap.add_argument("--out", default="work")
    ap.add_argument("--max-mb", type=float, default=DEFAULT_MAX_MB)
    ap.add_argument("--max-total-mb", type=float, default=DEFAULT_TOTAL_MB)
    ap.add_argument("--ids", default="")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()

    if not os.path.isfile(a.materials):
        sys.exit("[ERR] 素材清单不存在: %s(先跑 claw.py materials)" % a.materials)
    mats = json.load(io.open(a.materials, encoding="utf-8"))
    if isinstance(mats, dict):
        mats = list(mats.values())
    if a.ids:
        want = set(x.strip() for x in a.ids.split(",") if x.strip())
    else:
        want = set(m["id"] for m in mats if a.all or m.get("is_mentioned"))

    max_b = a.max_mb * 1024 * 1024
    total_cap = a.max_total_mb * 1024 * 1024
    out, used, n_embed, n_cover, n_unknown = {}, 0, 0, 0, 0
    for m in mats:
        mid = m.get("id")
        if mid not in want:
            continue
        url = m.get("download_url")
        if not url:
            out[mid] = {"kind": "cover", "reason": "无直链"}; n_cover += 1; continue
        size = probe_size(url)
        if size is None:
            out[mid] = {"kind": "cover", "reason": "体积未知(探测失败)"}; n_cover += 1; n_unknown += 1
            print("[video] %s 体积未知 -> 封面" % mid[:12], flush=True); continue
        if size > max_b:
            out[mid] = {"kind": "cover", "size": size, "too_big": True}; n_cover += 1
            print("[video] %s %.1fMB > %sMB -> 封面+跳转" % (mid[:12], size / 1048576, a.max_mb), flush=True); continue
        if used + size > total_cap:
            out[mid] = {"kind": "cover", "size": size, "over_budget": True}; n_cover += 1
            print("[video] %s 内嵌超总额度 -> 封面" % mid[:12], flush=True); continue
        try:
            data = download(url)
        except Exception as e:
            out[mid] = {"kind": "cover", "size": size, "reason": "下载失败:%s" % type(e).__name__}
            n_cover += 1
            print("[video] %s 下载失败 -> 封面" % mid[:12], flush=True); continue
        out[mid] = {"kind": "embed", "size": size,
                    "data_uri": "data:video/mp4;base64," + base64.b64encode(data).decode()}
        used += size; n_embed += 1
        print("[video] %s %.1fMB -> 内嵌(累计 %.1fMB)" % (mid[:12], size / 1048576, used / 1048576), flush=True)

    vj = os.path.join(a.out, "videos.json")
    os.makedirs(a.out, exist_ok=True)
    with io.open(vj, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n[done] 内嵌 %d / 封面 %d(其中体积未知 %d)/ 内嵌合计 %.1fMB -> %s"
          % (n_embed, n_cover, n_unknown, used / 1048576, vj), flush=True)
    if n_unknown:
        print("[提示] 体积未知的素材已按封面处理,须在报告口径注明", flush=True)


if __name__ == "__main__":
    main()
