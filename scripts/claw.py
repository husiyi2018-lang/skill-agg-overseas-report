#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aggclaw 取数驱动:并行发起多路分析 + 拉素材清单。

用法(Windows 建议 PYTHONIOENCODING=utf-8):
  # 1) 跑一路或多路分析(lanes.json = [{tag, input, mode, lang}, ...])
  python claw.py analyze --lanes lanes.json --work ./work --conc 3
  # 2) 拉某个会话的素材清单
  python claw.py materials --session "<session_id>" --out work/materials.json
  # 3) 把所有 result_*.json 里的 session 一起拉
  python claw.py materials --scan raw/data --out raw/materials_all.json

设计要点(踩坑固化):
  - 并发 ≤3(默认):8 路同轰会触发网关 504。
  - 504 / HTTP200 但 body 极小且含“繁忙/请稍后/抱歉” => 假结果,当失败处理。
  - 重试 = 新会话(不带 session_id),天然独立样本,不破坏交叉验证;每路最多 1 次重试。
  - 单次调用常 1-8 分钟,必须后台跑。

落盘约定(**分析文本与元数据分开写**,别再把 output 塞回 JSON):

  <raw>/data/result_L{n}_{tag}.md    output 原文,corpus-ready —— 保真校验的语料
  <raw>/data/result_L{n}_{tag}.json  只留结构化字段(session_id / ok / error / ...)

  为什么必须分开:fidelity 抽语料时,对 .json 走 `_walk_scalars` + `_is_encoded()`,
  长文本会被判成编码串**整段丢弃**;而 .md 走纯文本分支,数字直接可抽。
  早期把整篇 output 塞在 JSON 里 → 语料大面积缺失,只能人工把 output 拆成
  .md 放进 raw/ 补救。别再退回去。
"""
import sys, os, io, json, re, time, argparse, threading
import urllib.request, urllib.parse, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

API = "https://ai-chat-global.youcloud.com"
BUSY_WORDS = ("系统繁忙", "请稍后", "抱歉", "busy", "try again")


def _key():
    k = os.environ.get("YOUCLOUD_API_KEY", "").strip()
    if not k:
        sys.exit("[ERR] 未设置 YOUCLOUD_API_KEY")
    return k


def call(input_text, chat_mode=8, language_code="zh", session_id="", timeout=600):
    """返回 dict: {ok, output, session_id, error, http}"""
    body = {"input": input_text, "chat_mode": chat_mode, "language_code": language_code}
    if session_id:
        body = {"input": input_text, "session_id": session_id}
    req = urllib.request.Request(
        API + "/aichat/claw",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + _key(), "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            code = r.getcode()
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": "HTTP %s" % e.code, "http": e.code}
    except Exception as e:
        return {"ok": False, "error": type(e).__name__ + ": " + str(e)[:200], "http": 0}

    try:
        j = json.loads(raw)
    except Exception:
        return {"ok": False, "error": "非 JSON 返回", "http": code}

    out = (j.get("output") or j.get("content") or "").strip()
    sid = j.get("session_id") or j.get("sessionId") or ""
    # 假成功:body 极小 + 繁忙词
    if len(out) < 200 and any(w in out for w in BUSY_WORDS):
        return {"ok": False, "error": "引擎繁忙占位(假成功)", "session_id": sid, "http": code}
    if not out:
        return {"ok": False, "error": "空结果", "session_id": sid, "http": code}
    return {"ok": True, "output": out, "session_id": sid, "http": code}


def _slug(tag, maxlen=40):
    """把 lane tag 洗成安全文件名片段(保留中文,其余非字母数字换 -)。"""
    s = re.sub(r"[^0-9A-Za-z一-鿿_-]+", "-", str(tag or "lane")).strip("-")
    return (s or "lane")[:maxlen]


def _save(raw, n, lane, r):
    """落盘两个文件到 <raw>/data/:

      result_L{n}_{tag}.md    output 原文 —— corpus-ready,保真语料的基线
      result_L{n}_{tag}.json  只留结构化字段,**不写 output**

    为什么 markdown 要单独落成 .md:见模块 docstring 的「落盘约定」。
    一句话:fidelity 对 .json 里的长文本会按编码串整段丢弃,对 .md 才会纯文本抽取。
    """
    d = os.path.join(raw, "data")
    os.makedirs(d, exist_ok=True)
    stem = "result_L%d_%s" % (n, _slug(lane.get("tag")))
    out = r.get("output") or ""

    md_p = ""
    if out:
        md_p = os.path.join(d, stem + ".md")
        with io.open(md_p, "w", encoding="utf-8") as f:
            f.write(out)

    meta = {
        "ok": bool(r.get("ok")),
        "tag": lane.get("tag"),
        "lane_index": n,
        "session_id": r.get("session_id", ""),
        "http": r.get("http"),
        "error": r.get("error", ""),
        "retried": bool(r.get("_retried")),
        "chars": len(out),
    }
    json_p = os.path.join(d, stem + ".json")
    with io.open(json_p, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    print("[save] L%-2d %-16s ok=%-5s chars=%-6d sess=%s\n       json=%s%s"
          % (n, lane.get("tag"), meta["ok"], meta["chars"], meta["session_id"],
             json_p, ("\n       md  =" + md_p) if md_p else " (无 output,未写 md)"),
          flush=True)


def run_lane(raw, n, lane, retry=True):
    """跑一路:失败(含假成功)时以新会话重试 1 次。"""
    tag = lane["tag"]
    arg = dict(chat_mode=int(lane.get("mode", 8)), language_code=lane.get("lang", "zh"))
    r = call(lane["input"], **arg)
    if not r["ok"] and retry:
        print("[retry] %s 首次失败(%s),以新会话重试" % (tag, r.get("error")), flush=True)
        time.sleep(5)
        r = call(lane["input"], **arg)  # 新会话:不带 session_id
        r["_retried"] = True
    r["_tag"] = tag
    r["_lane"] = n
    _save(raw, n, lane, r)
    return r


def cmd_analyze(a):
    if not os.path.isfile(a.lanes):
        sys.exit("[ERR] lanes 文件不存在: %s" % a.lanes)
    lanes = json.load(open(a.lanes, encoding="utf-8"))
    if isinstance(lanes, dict):
        lanes = lanes.get("lanes", [])
    # 语料落盘目录:默认与 work/ 同级(工作区约定 work/ + raw/ 并列)
    raw = a.raw or os.path.join(os.path.dirname(os.path.abspath(a.work)), "raw")
    conc = max(1, int(a.conc))
    indexed = list(enumerate(lanes, start=1))     # 1-based lane 序号 = L{n}
    print("=== 分析 %d 路,并发 ≤%d ===" % (len(lanes), conc), flush=True)
    print("=== 语料落盘目录: %s ===" % os.path.join(raw, "data"), flush=True)
    results, lock = [], threading.Lock()

    def worker(pair):
        n, ln = pair
        r = run_lane(raw, n, ln, retry=not a.no_retry)
        with lock:
            results.append(r)

    # 分批:每批 conc 路,批间等待(避免网关被打爆)
    for s in range(0, len(indexed), conc):
        batch = indexed[s:s + conc]
        ts = [threading.Thread(target=worker, args=(p,)) for p in batch]
        [t.start() for t in ts]
        [t.join() for t in ts]
        print("--- 批 %d/%d 完成 ---" % (s // conc + 1, (len(indexed) + conc - 1) // conc), flush=True)

    ok = sum(1 for r in results if r.get("ok"))
    print("=== 完成:%d/%d 成功 ===" % (ok, len(results)), flush=True)
    for r in sorted(results, key=lambda x: x.get("_lane") or 0):
        if not r.get("ok"):
            print("  [未跑成] L%s %s: %s"
                  % (r.get("_lane"), r.get("_tag"), r.get("error")), flush=True)
    print("提示:未跑成的路在报告中标「未跑成」并由相邻路覆盖,禁虚标", flush=True)


def fetch_materials(session_id, timeout=120):
    enc = urllib.parse.quote(session_id, safe="~")
    req = urllib.request.Request(
        API + "/aichat/sessions/%s/materials" % enc,
        headers={"Authorization": "Bearer " + _key()}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def cmd_materials(a):
    sessions = {}
    if a.session:
        sessions["manual"] = a.session
    if a.scan:
        for fn in sorted(os.listdir(a.scan)):
            if fn.startswith("result_") and fn.endswith(".json"):
                j = json.load(open(os.path.join(a.scan, fn), encoding="utf-8"))
                if j.get("session_id"):
                    sessions[fn[:-5]] = j["session_id"]
    all_mats = {}
    for tag, sid in sessions.items():
        try:
            mats = fetch_materials(sid)
        except Exception as e:
            print("[warn] %s 拉取失败: %s" % (tag, e), flush=True)
            continue
        for m in mats:
            mid = m.get("id")
            if mid and mid not in all_mats:
                all_mats[mid] = m
        print("[materials] %s: %d 条(累计 %d 去重)" % (tag, len(mats), len(all_mats)), flush=True)
    out = a.out or os.path.join(a.scan or ".", "materials_all.json")
    od = os.path.dirname(os.path.abspath(out))
    if od:
        os.makedirs(od, exist_ok=True)          # --out raw/... 时目录可能还不存在
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump(list(all_mats.values()), f, ensure_ascii=False, indent=1)
    print("[done] -> %s (%d 条去重素材)" % (out, len(all_mats)), flush=True)


def _require_key_early():
    if not os.environ.get("YOUCLOUD_API_KEY", "").strip():
        sys.exit("[ERR] 未设置 YOUCLOUD_API_KEY(AppGrowing Global → Profile → Enterprise Info)")


def main():
    ap = argparse.ArgumentParser(description="aggclaw 取数驱动")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("analyze"); p.add_argument("--lanes", required=True)
    p.add_argument("--work", default="./work"); p.add_argument("--conc", type=int, default=3)
    p.add_argument("--raw", default="", help="语料落盘目录(默认 <work>/../raw)")
    p.add_argument("--no-retry", action="store_true")
    p = sub.add_parser("materials"); p.add_argument("--session", default="")
    p.add_argument("--scan", default="", help="扫哪个目录下的 result_*.json 取 session_id(现为 raw/data)")
    p.add_argument("--out", default="")
    a = ap.parse_args()
    if a.cmd == "analyze":
        _require_key_early()
        cmd_analyze(a)
    else:
        _require_key_early()
        cmd_materials(a)


if __name__ == "__main__":
    main()
