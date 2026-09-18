#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交互脑图**运行时**自检 —— 证明脑图真的渲染出来了。

用法:
  python scripts/check_mindmap_render.py <报告.html> [--dir <工作区>]
      [--browser auto|edge|chrome] [--exe <浏览器路径>] [--keep] [--quick]

## 为什么需要它(与 validate.py 的 check_mindmap 分工)

`validate.check_mindmap` 是**静态**断言:依赖内联了没、指纹体积达标没、
boot 逻辑在不在、CSS 覆盖没。它证明的是「**准备好**渲染」,不是「**渲染成功**」。

而本技能这套设计的静默失效模式恰恰是:**依赖齐备、boot 在位、静态校验全绿,
运行期仍然崩掉** —— 页面只剩一段没渲染的 markdown,离线打开的人才会发现。
静态断言永远够不到这一层,所以必须有一步**真的用浏览器跑一遍**。

- 静态(HTML 里有没有)  → `validate.py`
- 运行时(跑起来对不对)  → 本脚本
两者不重叠,都要过。

## 它断言什么

**基础(每次)**:

  ① `#markmap` 容器存在(不存在 → SKIP,报告本来就没脑图,不是错)
  ② 没有 `data-mmk-fallback` 标记 —— 出现即渲染失败已降级,直接 FAIL 并把
     降级原因(如 "Transformer is not defined")原样打出来
  ③ `#markmap` 的直接子节点里有 `<svg class="markmap">`
  ④ 该 svg 里有 `.markmap-node`(节点数 > 0;树没画出来时会等于 0)

**深度(默认开;`--quick` 关)** —— 以下几条都是「渲染成功一次」看不见的:

  ⑤ **降级兜底真的能兜住**:故意把三个 `mmk-*` 脚本体抽空,制造**真阴性**。
     若降级没接上,这一步会看到空白容器而不是列表。同时断言降级列表条目数
     **等于**正常渲染的节点数 —— 逐条比对,防止"看着降级了、其实内容缺了几层"。
  ⑥ **语言切换是重建而非叠加**:切到第二语言再切回(走 `<html lang>` 属性那条
     通路,顺带验证 MutationObserver),全程 `#markmap` 容器与 svg **恒为 1 个**。
     叠加式实现的典型症状是切几次就多几个 svg,页面越切越高。
  ⑦a **连点末态干净**:同一 tick 内连点 4 次(1→0→1→0),**不装任何计量器**,
     末态必须 ①容器 1 个 ②svg 1 个(含游离 svg 计数)③节点数与点击前一致
     ④不含降级标记 ⑤高亮标签 = 最后一次入队的那一个。
  ⑦b **并发渲染峰值 ≤ 1**:装并发计量器,**只读点击后的第一个宏任务边界**。
     这一条才是"串行化"的本体,也是唯一能抓住「queue 空串行化」的断言。

## 为什么 ⑦ 拆成 (a)(b) 两个探针,而不是一个探针既量峰值又判末态

**理由只有一个,而且是决定性的:末态 DOM 分辨不出并发。**
`queue=queue.then(...)` 看起来天经地义,但**它串起来的只是 draw() 的同步部分** ——
只要 draw() 不把渲染完成的 promise 交回去,queue 就等不到真正渲染结束,连点 4 次
会让 4 个 renderData 并发跑。而这时 ⑦a 那几条**全是绿的**:最后一次 rebuild 已经把
容器换成新的,旧实例在**游离(已脱离 DOM)的** svg 上继续画,谁也看不见。

实测踩到的写法就是 markmap-view 的静态工厂:`Markmap.create(svg,opts,data)`
内部 `mm.setData(data).then(()=>mm.fit())`,**setData 的 promise 没被 return**。
所以 ⑦b 在 boot **之前**注入一个计量器(包一层 `Markmap.prototype.setData`,
记"同时在跑的渲染数"峰值)。变异测试里把 boot 改回 `Markmap.create` 而保留
queue:⑦a 依旧全绿、只有 ⑦b 报红。把同一批断言打到变异体上实测(H 组):
**末态 13 节点、容器/svg/游离 svg 全 1、高亮正确 —— 四项全绿,错误实现零暴露**。
这就是必须分开的证据,不是"顺手拆一下"。

**读数只能取第一个宏任务边界,不能取末态**:
`setTimeout(…,0)` 那一刻 4 次点击已全部入队,坏实现把 4 个渲染同时起跑
(实测峰值 **4**),好实现仍为 1(实测峰值 **1**),多次复现读数一致。
**不要在同一 tick 内同步读** —— 那时两个实现都还看不到渲染启动,无区分度。
(⑦a 不带计量器是"稳妥"而非"必须":早期以为是"装了计量器就读不到末态",
后来查明那不是计量器的性质,而是无头环境不供 rAF 帧被更长的 promise 链放大;
垫片修好后实测计量器在场也能读到干净末态。让末态读数里不掺仪器成分,
这个习惯保留。)

## 无头环境的 rAF 垫片(不装它,⑦a 会偶发假红)

`--virtual-time-budget` 下渲染器**会停止派发 requestAnimationFrame 帧**。
失败样本里打点计数冻结在 2,之后 40 次采样纹丝不动;而 markmap-view 的
`renderData` 里正是 `await new Promise(requestAnimationFrame)` —— 渲染永远等不到
恢复,页面卡在 **8 节点**的半渲染态。实测同一份**正确**报告连跑 3 次会有 1 次报
"末态节点 8 ≠ 点击前 13":那是**环境供帧问题**,不是报告的问题。

所以自检副本里会先装一个垫片(见 `install_raf_shim`):把帧调度换成语义等价的
`setTimeout(fn, 16)`,虚拟时间就可靠推进。垫片**必须早于 d3**(d3-timer 在加载时
就把 rAF 抓进变量),因此插在 `</head>` 之前。垫片只进自检副本,永不进产物。

**它不会把真 bug 一起盖掉**(这是我们专门验过的):装垫片后把同一批判据打到
变异体 mut-m1 上,⑦b 仍稳定报峰值 **4**、正确实现稳定报 **1**,各 3/3 复现 ——
判据的区分度一分没少。⑦a/⑦b 都会回填环境供帧计数 `raf`,读不到(<0)时降级为
WARN:垫片没装上,那两条结论不成立,但也不该诬告被测对象。

## 两个刻意的设计

- **先做"去资源副本"再测**:报告里塞着几十张 base64 封面和内嵌视频,
  无头浏览器解析它们要几百毫秒到几秒,会跟脑图的渲染抢主线程,
  把「其实能渲染」误判成超时(离线本机验证时尤其容易复现)。
  所以先剥掉 `data:*;base64,*` 载荷,再跑。`--keep` 可保留这份副本排查。
- **找不到浏览器 → WARN 跳过,不阻断**:本脚本是**加分自检**,不能因为它
  让一份本来合格的报告交付不了。这与 `topdf.py`(导 PDF 是主任务)策略不同。
"""
from __future__ import print_function

import argparse
import io
import json
import os
import re
import subprocess
import sys

# Windows 控制台默认 GBK。本脚本会打印 ⚠ / ✓ 这类符号,不先改掉输出编码的话
# 会**在自检全部通过之后**倒在最后一行 print 上 —— 实测:渲染 OK(24 节点)、
# 降级 OK,然后 UnicodeEncodeError 崩掉,看起来像自检失败,其实报告完全合格。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 浏览器发现复用 topdf.py,不在这里再写一份平台表 —— 两处各写一份,
# 以后加个浏览器路径就会漏改一处(与 validate 从 mindmap 取指纹同理)。
import topdf

FALLBACK_MARK = "data-mmk-fallback"
HOST_RE = re.compile(r'<div[^>]*\bid\s*=\s*["\']markmap["\'][^>]*>', re.I)
SVG_RE = re.compile(r'<svg[^>]*class\s*=\s*["\'][^"\']*\bmarkmap\b', re.I)
NODE_RE = re.compile(r'class\s*=\s*["\'][^"\']*\bmarkmap-node\b', re.I)
BASE64_RE = re.compile(r"data:[a-zA-Z0-9/+.-]+;base64,[A-Za-z0-9+/=]+")
# 三个内联依赖的脚本体(深度①要把它们抽空,制造"依赖缺失"真阴性)
VENDOR_BODY_RE = re.compile(
    r'(<script\s+id\s*=\s*["\']mmk-(?:d3|lib|view)["\'][^>]*>)(.*?)(</script>)',
    re.S | re.I)
MD_SRC_RE = re.compile(r'<script[^>]*type\s*=\s*["\']text/markdown["\']', re.I)
PROBE_ATTR = "data-mmk-probe"


# ── 深度探针的注入脚本(三份,共用一个小工具函数,判定面都限死在 #markmap 内) ──
_JS_HELPERS = """
function __mmkN(){return document.querySelectorAll('#markmap .markmap-node').length}
function __mmkHosts(){return document.querySelectorAll('#markmap').length}
function __mmkSvgs(){return document.querySelectorAll('#markmap svg').length}
function __mmkTabs(){return [].slice.call(document.querySelectorAll('.mmk-tab[data-mmk-lang]'))}
function __mmkOn(){var b=document.querySelector('.mmk-tab.on');return b?b.textContent.trim():''}
function __mmkPut(o){document.body.setAttribute('%(attr)s',JSON.stringify(o))}
function __mmkAll(){return document.querySelectorAll('svg.markmap').length}
function __mmkSnap(){return {n:__mmkN(),h:__mmkHosts(),s:__mmkSvgs(),all:__mmkAll()}}
/* 环境供帧计数:由 rAF 垫片维护。读不到(-1)说明垫片没装上,此时"末态不收敛"
   可能只是无头环境没供帧(见 install_raf_shim 的说明),不能算被测对象的错。 */
function __mmkRaf(){return (typeof window.__mmkRAF==='function')?window.__mmkRAF():-1}
/* 等末态收敛:必须**连续两次**采到期望形态才收尾。
   只采一帧是不可靠的 —— 实测 4 次点击后单次采样的节点数会在 8/13 之间跳
   (renderData 在建节点组的中途),采到 8 就成了假红。反过来只等"两帧相同"
   也不够:坏实现(rebuild 只追加)在中途也可能瞬时相同。判据直接写成
   "期望形态连续两次成立",两种偏差都盖住了。 */
function __mmkWait(n0, cb){
  var hits=0,i=0,seen=[];
  (function step(){
    var c=__mmkSnap();
    seen.push(c.n+'/'+c.h+'/'+c.s+'/'+c.all);
    if(c.n===n0&&c.h===1&&c.s===1&&c.all===1){hits++}else{hits=0}
    i++;
    if(hits>=2||i>=20){cb(c,seen,i,hits>=2);return}
    setTimeout(step,250);
  })();
}
""" % {"attr": PROBE_ATTR}

# ⑤ 降级:抽空 vendor 后必须落到结构化列表,且条目数与正常节点数一致
PROBE_FALLBACK = _JS_HELPERS + """
setTimeout(function(){
  var h=document.getElementById('markmap');
  __mmkPut({
    attr: h ? h.getAttribute('data-mmk-fallback') : null,
    items: document.querySelectorAll('.mmtree.mmk-fb li').length,
    note: (document.querySelector('.mmk-fb-note')||{}).textContent||'',
    svg: __mmkSvgs(),
    h: h ? h.style.height : ''
  });
}, 2600);
"""

# ⑥ 语言切换:en → (改 <html lang>) → 回;容器/svg 全程必须恒为 1
PROBE_LANG = _JS_HELPERS + """
setTimeout(function(){
  var t=__mmkTabs();
  var r={tabs:t.length, srcs:document.querySelectorAll('script[type="text/markdown"]').length,
         n0:__mmkN(), h0:__mmkHosts(), s0:__mmkSvgs()};
  if(t.length<2){__mmkPut(r);return}
  t[1].click();
  setTimeout(function(){
    r.n1=__mmkN(); r.h1=__mmkHosts(); r.s1=__mmkSvgs();
    /* 走报告级通路:改 <html lang>,应被 MutationObserver 接住 */
    var l0=(t[0].getAttribute('data-mmk-lang')||'').toLowerCase();
    document.documentElement.setAttribute('lang', l0.indexOf('zh')===0?'zh-CN':'en');
    setTimeout(function(){
      r.n2=__mmkN(); r.h2=__mmkHosts(); r.s2=__mmkSvgs();
      r.on=__mmkOn(); r.want=t[0].textContent.trim();
      __mmkPut(r);
    },1400);
  },1400);
}, 2600);
"""

# ⑦a 连点末态:**不装计量器**(装了会卡在半渲染态,见文件头说明)。
# 同一 tick 4 次点击,末态必须唯一、干净、与最后一次入队一致。
PROBE_RACE = _JS_HELPERS + """
setTimeout(function(){
  var t=__mmkTabs();
  var r={tabs:t.length};
  if(t.length<2){__mmkPut(r);return}
  r.n0=__mmkN();                          /* 点击前的节点数,末态应与之一致 */
  r.on0=__mmkOn();
  t[1].click(); t[0].click(); t[1].click(); t[0].click();
  __mmkWait(r.n0, function(c,seen,tries,converged){
    r.n=c.n; r.h=c.h; r.s=c.s; r.all=c.all;  /* all 含游离 svg */
    r.fb=!!document.querySelector('[data-mmk-fallback]');
    r.on=__mmkOn(); r.want=t[0].textContent.trim();
    r.tries=tries; r.converged=converged; r.seen=seen;
    r.raf=__mmkRaf();                       /* 环境供帧计数:判"红"前先确认环境供过帧 */
    __mmkPut(r);
  });
}, 2600);
"""

# ⑦b 并发峰值:**装计量器**,且只在点击后的第一个宏任务边界读数。
# 为什么读点不能是末态、也不能是同 tick 同步读 —— 见文件头的长说明,别随手改回去。
PROBE_CONC = _JS_HELPERS + """
var __c={mx:-9,cur:-9,seen:0,samples:[]};
function __cSample(tag){
  var m=(typeof window.__mmkMeter==='function')?window.__mmkMeter():null;
  if(!m){return}
  var s={tag:tag,mx:m.mx,cur:m.cur,n:__mmkN(),h:__mmkHosts(),v:__mmkSvgs()};
  __c.samples.push(s); __c.seen=1;
  if(m.mx>__c.mx)__c.mx=m.mx;
  __c.cur=m.cur;
}
setTimeout(function(){
  var t=__mmkTabs();
  var r={tabs:t.length};
  if(t.length<2){__mmkPut(r);return}
  __cSample('pre');
  t[1].click(); t[0].click(); t[1].click(); t[0].click();
  __cSample('same-tick');                 /* 无区分度,仅留档对比 */
  setTimeout(function(){
    __cSample('task+0');                  /* ← 主判据:4 次入队已发生 */
    setTimeout(function(){
      __cSample('task+1500');             /* 再采一帧兜底,取两次的最大值 */
      r.mx=__c.mx; r.cur=__c.cur; r.seen=__c.seen; r.samples=__c.samples;
      r.n=__mmkN(); r.h=__mmkHosts(); r.s=__mmkSvgs();
      r.raf=__mmkRaf();
      __mmkPut(r);
    },1500);
  },0);
}, 2600);
"""

# ⑦b 的并发计量器:**必须早于 boot 注入**(晚于三个 vendor 脚本)。
# 包一层 Markmap.prototype.setData 数"同时在跑的渲染"峰值 —— 这是唯一能证明
# queue 真在等渲染的证据。boot 用静态工厂 Markmap.create 时,工厂内部对实例
# 调用的 setData 也会落到这个原型方法上,所以两种写法都量得到。
# 量不到(window.markmap 缺失)时 mx=-1,由调用方降级为 WARN 而不是 FAIL:
# 探针自己装不上,不该诬告被测对象。
METER_JS = """
(function(){
  var M=window.markmap&&window.markmap.Markmap;
  if(!M||!M.prototype||!M.prototype.setData){window.__mmkMeter=function(){return {mx:-1,cur:-1}};return}
  var cur=0,mx=0,orig=M.prototype.setData;
  M.prototype.setData=function(){
    cur++; if(cur>mx)mx=cur;
    var p;
    try{p=orig.apply(this,arguments)}catch(e){cur--;throw e}
    return Promise.resolve(p).then(function(v){cur--;return v},
                                 function(e){cur--;throw e});
  };
  window.__mmkMeter=function(){return {mx:mx,cur:cur}};
})();
"""

# 计量器注入锚点:三个 vendor 脚本由 mindmap.py 打在 <!--MARKMAP_VENDOR--> 处,
# 正好紧邻 mmk-boot 之前 —— 所以"插到 mmk-boot 之前"就是"插在依赖之后"。
BOOT_ANCHOR_RE = re.compile(r'<script\s+id\s*=\s*["\']mmk-boot["\']', re.I)

# ── 无头环境的 rAF 垫片(只装进自检副本,永不进产物) ────────────────────
# **为什么必须有**:`--virtual-time-budget` 下渲染器**会停止派发 rAF 帧**。
# 实测(失败样本)打点计数冻结在 2,之后 40 次采样纹丝不动 —— 而
# markmap-view 的 `renderData` 里有 `await new Promise(requestAnimationFrame)`,
# 于是渲染永远等不到恢复,页面卡在 8 节点的半渲染态。同一份**正确**报告
# 连跑 3 次就会有 1 次报"末态节点 8 ≠ 点击前 13",那是**环境供帧问题**,
# 不是被测对象的缺陷。把帧调度换成语义等价的 `setTimeout(fn, 16)`
# (同样是"下一帧才跑"的异步),虚拟时间就会可靠推进。
#
# **会不会把真 bug 一起盖掉**:不会。变异体 mut-m1(queue 空串行化)装垫片后
# ⑦b 仍稳定报峰值 4,正确实现稳定报 1 —— 各 3/3 复现,判据一分不少。
#
# **必须早于 d3**:d3-timer 在**加载时**就把 `requestAnimationFrame` 抓进
# 变量(`setFrame = typeof requestAnimationFrame === "function" ? …`),
# 晚于 d3 再打补丁,d3 用的是原生的那个,垫片等于白装。
# 所以按"越靠前越好"选锚点,首选 </head> 之前。
_RAF_SHIM = """
(function(){
  if(!window.requestAnimationFrame)return;
  var n=0;
  window.__mmkRAF=function(){return n};
  window.requestAnimationFrame=function(cb){
    n++;
    return setTimeout(function(){
      try{cb(typeof performance!=='undefined'?performance.now():Date.now())}catch(e){}
    },16);
  };
  window.cancelAnimationFrame=function(id){clearTimeout(id)};
})();
"""
# 按优先级排列:插得越早越好(最早的那个在 </head> 前,早于三个 vendor 脚本)
_RAF_ANCHORS = [
    re.compile(r'</head\s*>', re.I),
    re.compile(r'<script\s+id\s*=\s*["\']mmk-(?:d3|lib|view)["\']', re.I),
    BOOT_ANCHOR_RE,
]


def install_raf_shim(html):
    """把 rAF 垫片插进自检副本。返回 (html, 是否装上)。

    装不上不算致命(老报告可能把三个 vendor 脚本放在 CDN 上),但要显式告诉
    调用方 —— 垫片缺席时 ⑦a/⑦b 会偶发假红,那种红不该算在被测对象头上。
    """
    tag = "<script>\n%s\n</script>\n" % _RAF_SHIM
    for r in _RAF_ANCHORS:
        m = r.search(html)
        if m:
            return html[:m.start()] + tag + html[m.start():], True
    return html, False


def unescape_attr(s):
    """把 DOM 序列化进属性的 JSON 解回来(手工替换,不引 html 模块以兼容老解释器)。"""
    for a, b in (("&quot;", '"'), ("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&")):
        s = s.replace(a, b)
    return s


def parse_probe(dom):
    """从 body 属性取回探针 JSON;没回填返回 None(超时/脚本挂了)。"""
    m = re.search(r'%s\s*=\s*"([^"]*)"' % PROBE_ATTR, dom, re.I)
    if not m:
        return None
    try:
        return json.loads(unescape_attr(m.group(1)))
    except ValueError:
        return None


def inject_before_body(html, js):
    """把探针脚本插到 </body> 前(必须晚于 mmk-boot,才能看到它的初渲染)。"""
    tag = "<script>\n%s\n</script>\n" % js
    i = html.lower().rfind("</body>")
    return (html[:i] + tag + html[i:]) if i >= 0 else (html + tag)


def inject_before(html, anchor_re, js):
    """把脚本插到锚点**之前**(用于要早于 boot 执行的计量器)。

    找不到锚点返回 None —— 让调用方显式处理"装不上",而不是静默把脚本
    插到文末(那样它比 boot 晚执行,计量器永远读到 0 次调用,反而给出
    "串行化没问题"的假绿)。
    """
    m = anchor_re.search(html)
    if not m:
        return None
    tag = "<script>\n%s\n</script>\n" % js
    return html[:m.start()] + tag + html[m.start():]


def run_probe(exe, work, fname, html, js, pre=""):
    """写副本 → 无头跑 → 取探针结果。返回 (结果 dict 或 None, 副本路径)。

    pre: 需要**早于 mmk-boot** 执行的脚本(如并发计量器);装不上返回 (None, None)。
    """
    src = html
    if pre:
        src = inject_before(src, BOOT_ANCHOR_RE, pre)
        if src is None:
            return None, None
    p = os.path.join(work, fname)
    save(p, inject_before_body(src, js))
    return parse_probe(dump_dom(exe, p)), p


def deep_checks(exe, work, light, good_nodes):
    """⑤⑥⑦a⑦b 四条深度断言。返回 [(状态, 消息), …];状态 ∈ ok/fail/warn。"""
    out = []

    # ---- ⑤ 降级兜底(抽空依赖,真阴性) ----
    blanked, nv = VENDOR_BODY_RE.subn(lambda m: m.group(1) + m.group(3), light)
    if nv < 3:
        out.append(("warn", "深度⑤跳过:只找到 %d 个 mmk-* 脚本体(应为 3)—— "
                            "依赖可能没内联,先跑 `python scripts/mindmap.py <报告.html>`" % nv))
    else:
        r, _ = run_probe(exe, work, "deep-fallback.html", blanked, PROBE_FALLBACK)
        if r is None:
            out.append(("fail", "深度⑤降级探针未回填(超时或 boot 抛异常)"))
        else:
            items = r.get("items") or 0
            note = (r.get("note") or "").strip()
            ok = (str(r.get("attr")) == "1" and items > 0
                  and not r.get("svg") and str(r.get("h") or "").startswith("auto"))
            tail = "降级列表 %s 条,height=%s" % (items, r.get("h"))
            if good_nodes and items != good_nodes:
                ok = False
                tail += " ≠ 正常渲染节点数 %d —— **内容有丢失**,不是完好的兜底" % good_nodes
            if not ok and str(r.get("attr")) != "1":
                tail += ";未见 data-mmk-fallback —— 依赖被抽空后**没有降级**,页面应是空白"
            out.append(("ok" if ok else "fail",
                        "降级兜底生效:抽空依赖后转为结构化列表,内容完整(%s)" % tail))
            if ok and note:
                out.append(("ok", "  降级提示语:%s" % note[:96]))

    # ---- ⑥ 语言切换 / ⑦ab 连点串行(需要 ≥2 份 md 源) ----
    r, _ = run_probe(exe, work, "deep-lang.html", light, PROBE_LANG)
    if r is None:
        out.append(("fail", "深度⑥语言切换探针未回填(超时或 boot 抛异常)"))
    elif (r.get("tabs") or 0) < 2:
        out.append(("warn", "深度⑥⑦a⑦b跳过:只有 %s 个语言标签页(报告是单语言)"
                            % r.get("tabs")))
    else:
        bad = []
        if r.get("h0") != 1 or r.get("s0") != 1:
            bad.append("初态容器/svg=%s/%s(应为 1/1)" % (r.get("h0"), r.get("s0")))
        if not (r.get("n0") or 0) > 0:
            bad.append("初态节点=0")
        for k, tag in (("1", "切 EN"), ("2", "切回")):
            if (r.get("n" + k) or 0) <= 0:
                bad.append("%s后节点=0" % tag)
            if r.get("h" + k) != 1:
                bad.append("%s后容器 %s 个(应为 1,叠加式实现会越切越多)"
                           % (tag, r.get("h" + k)))
            if r.get("s" + k) != 1:
                bad.append("%s后 svg %s 个(应为 1)" % (tag, r.get("s" + k)))
        if r.get("on") != r.get("want"):
            bad.append("切回后高亮 %r ≠ 期望 %r" % (r.get("on"), r.get("want")))
        if (r.get("srcs") or 0) < 2:
            bad.append("静态 md 源 %s 份(应 ≥2)" % r.get("srcs"))
        out.append(("fail" if bad else "ok",
                    "语言切换为重建而非叠加:%s" % (";".join(bad) if bad else
                    "节点 %s→%s→%s,容器/svg 恒 1/1,<html lang> 通路已连通,md 源 %s 份"
                    % (r.get("n0"), r.get("n1"), r.get("n2"), r.get("srcs")))))

        # ---- ⑦a 连点末态(不装计量器 —— 装了就看不清末态) ----
        r2, _ = run_probe(exe, work, "deep-race.html", light, PROBE_RACE)
        if r2 is None:
            out.append(("fail", "深度⑦a连点探针未回填(超时或 boot 抛异常)"))
        else:
            bad2 = []
            n0 = r2.get("n0") or 0
            if (r2.get("n") or 0) <= 0:
                bad2.append("末态节点=0")
            elif n0 and r2.get("n") != n0:
                bad2.append("末态节点 %s ≠ 点击前 %s(渲染丢了节点)"
                            % (r2.get("n"), n0))
            if r2.get("h") != 1:
                bad2.append("末态容器 %s 个(应为 1)" % r2.get("h"))
            if r2.get("s") != 1:
                bad2.append("末态 svg %s 个(应为 1)" % r2.get("s"))
            if r2.get("all") != 1:
                bad2.append("页内 svg.markmap 共 %s 个(应为 1,多余即游离 svg)"
                            % r2.get("all"))
            if r2.get("fb"):
                bad2.append("末态处于降级态")
            if r2.get("on") != r2.get("want"):
                bad2.append("末态高亮 %r ≠ 最后入队 %r" % (r2.get("on"), r2.get("want")))
            # "没收敛"这一条只有在**环境确认供过帧**时才算被测对象的错。
            # 供帧计数读不到(垫片没装上)时降级为 WARN —— 见文件头 rAF 垫片一节:
            # 无头环境不供帧会让正确报告也停在 8 节点,那不是报告的缺陷。
            raf2 = r2.get("raf")
            env_blind = (raf2 is None or (isinstance(raf2, int) and raf2 < 0))
            if not r2.get("converged"):
                if env_blind:
                    bad2 = None      # 单独处理:见下面的 warn 分支(不阻断 ⑦b)
                else:
                    bad2.append("末态在 5s 内没收敛到期望形态(采样轨迹 n/h/svgs/all: %s)"
                                % (" ".join(r2.get("seen") or [])[-160:]))
            if bad2 is None:
                out.append(("warn", "深度⑦a无法判定:末态采样 5s 内没收敛,且环境供帧"
                                    "计数读不到(rAF 垫片未装上)—— 分不清是「报告卡在"
                                    "半渲染」还是「无头环境不供帧」,故不据此判红。"
                                    "采样轨迹:%s"
                                    % (" ".join(r2.get("seen") or [])[-160:])))
            else:
                out.append(("fail" if bad2 else "ok",
                            "连点末态干净:同 tick 4 次点击后%s" %
                            (";".join(bad2) if bad2 else
                             "节点 %s 个(与点击前一致)、容器 1 个、svg 1 个、"
                             "无游离 svg、高亮与末次入队一致(环境供帧 %s 次)"
                             % (r2.get("n"), raf2))))

        # ---- ⑦b 并发峰值(装计量器,只读第一个宏任务边界) ----
        if not BOOT_ANCHOR_RE.search(light):
            out.append(("warn", "深度⑦b跳过:找不到 <script id=\"mmk-boot\"> 锚点,"
                                "并发计量器插不进去(引导脚本被改名或被删?)"))
        else:
            r3, _ = run_probe(exe, work, "deep-conc.html", light, PROBE_CONC, pre=METER_JS)
            if r3 is None:
                out.append(("fail", "深度⑦b并发探针未回填(超时或 boot 抛异常)"))
            else:
                mx = r3.get("mx")
                bad3 = []
                if not r3.get("seen") or mx is None or (isinstance(mx, int) and mx < 0):
                    out.append(("warn", "深度⑦b并发计量器未生效(峰值 %r)—— 本次只有 ⑦a "
                                        "的末态结论,**不足以**证明 queue 真在等渲染"
                                        % mx))
                elif mx == 0:
                    out.append(("warn", "深度⑦b计量器装上了但一次渲染都没数到(峰值 0)"
                                        "—— 探针读点或时序不对,结论不可信"))
                else:
                    if mx > 1:
                        bad3.append("并发渲染峰值 %d(应为 ≤1)—— queue 没等到渲染完成,"
                                    "是空串行化。典型写法:用静态工厂 Markmap.create,"
                                    "它把 setData 的 promise 丢掉了" % mx)
                    ok3 = not bad3
                    # 这一条**不依赖环境供帧**:峰值读的是"同时在跑的渲染数"。
                    # 好实现被 await 挡住、后续渲染排不进来(峰值恒 1);坏实现
                    # 的 then 拿到 undefined、4 个立刻起跑(峰值 4)—— 两种情况下
                    # 帧来不来都一样。所以这里只把供帧数印出来,不拿它改判。
                    out.append(("fail" if bad3 else "ok",
                                "连点已串行化:同 tick 4 次点击后并发渲染峰值 %d(≤1)"
                                "(环境供帧 %s 次)%s"
                                % (mx, r3.get("raf"),
                                   "" if ok3 else
                                   ";采样 %s" % (r3.get("samples") or []))))
                    if ok3:
                        out.append(("ok", "  (⑦b读点在第一个宏任务边界:末态 DOM 分辨不出"
                                          "并发,这里才是串行化的唯一证据)"))

    # 清理深度副本
    for f in ("deep-fallback.html", "deep-lang.html", "deep-race.html",
              "deep-conc.html"):
        try:
            os.remove(os.path.join(work, f))
        except OSError:
            pass
    return out


def load(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


def save(p, s):
    d = os.path.dirname(os.path.abspath(p))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def strip_assets(html):
    """剥掉内嵌资源的 base64 载荷,保留标签与结构。

    只换掉 `data:...;base64,...` 这段**内容**,不删标签 —— 删掉标签会让
    CSS 选择器(如 `.mcover img` / `#markmap` 的兄弟规则)的匹配面变化,
    那样测的就不是同一份布局了。
    """
    n = len(BASE64_RE.findall(html))
    return BASE64_RE.sub("", html), n


def dump_dom(browser_exe, path):
    """无头浏览器跑一遍,返回渲染后的 DOM 文本。"""
    cmd = [browser_exe, "--headless=new", "--no-sandbox",
           "--disable-setuid-sandbox", "--disable-gpu", "--hide-scrollbars",
           "--virtual-time-budget=15000", "--dump-dom", topdf.file_url(path)]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = p.stdout or b""
    return out.decode("utf-8", "replace")


def subtree(dom, tag_re):
    """取 tag_re 匹配到的元素及其子树(配平 <div> 扫描)。返回 (开标签, 子树)。

    **为什么不用正则整体剥 `<script>`**:`--dump-dom` 吐出的 DOM 里,
    脚本源码可能以文本形式**泄漏到元素之外**(实测:boot 里 `.replace(/</g,…)`
    这类含 `/</` 的片段被浏览器重新解析,序列化成 `replace(="" <="" g`,于是
    脚本边界错位、源码混进正文)。那种情况下「剥脚本再全文判定」既会
    把源码里的 `data-mmk-fallback` 当成真降级(假阳性),也会把判断依据搅乱。
    只取 `#markmap` 子树就没有这个问题 —— 判定面被限死在容器内部。
    """
    m = tag_re.search(dom)
    if not m:
        return None, None
    i, depth = m.end(), 1
    for t in re.finditer(r"<(/?)div\b[^>]*>", dom[i:], re.I):
        if t.group(0).endswith("/>"):
            continue
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return m, dom[m.start():i + t.end()]
    return m, dom[m.start():]          # 没配平到(截断)→ 给到文末


def evaluate(dom):
    """对渲染后的 DOM 做断言。返回 (状态, 消息列表);状态 ∈ ok/skip/fail。"""
    msgs = []
    host, sub = subtree(dom, HOST_RE)
    if not host:
        return "skip", ["报告里没有 #markmap 容器 —— 本次不含交互脑图,跳过"]

    sub = sub or ""

    # ② 降级:只在子树/开标签里判定(源码里的字面量已被排除在判定面之外)
    if FALLBACK_MARK in (host.group(0) or "") or "mmk-fb" in sub:
        why = ""
        m = re.search(r"交互脑图未渲染\(([^)]{0,120})\)", sub)
        if m:
            why = m.group(1).strip()
        msgs.append("脑图**渲染失败并已降级**%s" % (":" + why if why else ""))
        msgs.append("降级本身是设计好的兜底(内容没丢),但这说明依赖/解析出了问题,"
                    "交付前必须查清 —— 跑 `python scripts/mindmap.py <报告.html> --check`")
        return "fail", msgs

    # ③ 容器里有东西吗(空 #markmap = boot 压根没跑起来,最隐蔽的一种)
    if not sub[len(host.group(0)):].strip():
        msgs.append("#markmap 是**空容器** —— 渲染没发生,也没触发降级。"
                    "多半是 mmk-boot 没执行(脚本被提前闭合 / 被 CSP 拦),"
                    "或 markdown 源为空。这是静态校验完全看不到的一种失效")
        return "fail", msgs

    # ④ svg 必须是 #markmap 的直接子节点(markmap-view 就是这么挂的)
    tail = sub[len(host.group(0)):len(host.group(0)) + 600]
    if not SVG_RE.search(tail):
        msgs.append("#markmap 有内容但没有 <svg class=\"markmap\"> —— "
                    "boot 跑了却没产出图形(依赖缺失?Transformer 报错?)")
        return "fail", msgs

    # ⑤ 节点数
    n = len(NODE_RE.findall(sub))
    if n == 0:
        msgs.append("svg 在,但 .markmap-node = 0 —— 树是空的,markdown 源可能只有标题")
        return "fail", msgs

    msgs.append("脑图渲染成功:svg 已挂载,节点 %d 个" % n)
    return "ok", msgs


def main():
    ap = argparse.ArgumentParser(description="交互脑图运行时自检")
    ap.add_argument("html")
    ap.add_argument("--dir", default="", help="工作区(副本放 <dir>/build/)")
    ap.add_argument("--browser", default="auto", choices=["auto", "edge", "chrome"])
    ap.add_argument("--exe", default="", help="浏览器可执行文件路径(绿色版/非默认位置)")
    ap.add_argument("--keep", action="store_true", help="保留去资源副本供排查")
    ap.add_argument("--quick", action="store_true",
                    help="只做基础渲染断言,跳过 ⑤降级 / ⑥语言切换 / ⑦ab 连点串行 "
                         "这几条深度检查")
    a = ap.parse_args()

    if not os.path.isfile(a.html):
        sys.exit("[ERR] 找不到报告:%s" % a.html)
    html = load(a.html)

    if not HOST_RE.search(html):
        print("[SKIP] 报告里没有 #markmap 容器 —— 本次不含交互脑图")
        return

    name, exe = topdf.find_browser(a.browser, a.exe)
    if not exe:
        print("[WARN] 找不到 Edge / Chrome,跳过脑图运行时自检(不阻断交付)。")
        print("       静态项仍由 `python scripts/validate.py <报告.html> --dir <工作区>` 覆盖。")
        return

    # 去资源副本:排除 base64 解析与脑图抢主线程造成的假失败
    work = os.path.join(os.path.abspath(a.dir) if a.dir
                        else os.path.dirname(os.path.abspath(a.html)), "build", "mindcheck")
    light, n_assets = strip_assets(html)
    # 垫片装进**副本**,让后面所有探针(基础渲染 + ⑤⑥⑦ab)都跑在可靠供帧的环境里。
    # 装不上要显式说出来 —— 那会让 ⑦a 偶发假红,用户得知道红可能是环境造成的。
    light, shim_ok = install_raf_shim(light)
    lp = os.path.join(work, "light.html")
    save(lp, light)
    print("[1/3] 去资源副本:%s(剥掉 %d 处 base64 载荷,rAF 垫片%s)"
          % (lp, n_assets, "已装" if shim_ok else "**未装**(锚点缺失,⑦a 可能偶发假红)"))

    print("[2/3] %s 无头渲染中(--virtual-time-budget=15000)…" % name)
    dom = dump_dom(exe, lp)

    status, msgs = evaluate(dom)
    good_nodes = 0
    for m in msgs:
        print(("  [ OK ] " if status == "ok" else "  [FAIL] ") + m)
    if status == "ok":
        mm = re.search(r"节点\s+(\d+)\s*个", msgs[-1])
        good_nodes = int(mm.group(1)) if mm else 0
    else:
        # 基础渲染都没过,深度检查没有意义(而且会掩盖真正的首个错因)
        print("  [SKIP] 基础渲染未通过,跳过深度检查 —— 先修上面这条")
        a.quick = True

    deep_failed = False
    if not a.quick:
        print("  --- [3/3] 深度运行时检查"
              "(降级兜底 / 语言切换 / 连点末态 / 连点并发峰值) ---")
        for st, m in deep_checks(exe, work, light, good_nodes):
            tag = {"ok": "[ OK ] ", "warn": "[WARN] ", "fail": "[FAIL] "}[st]
            print("  " + tag + m)
            if st == "fail":
                deep_failed = True

    if a.keep:
        print("  (副本保留:%s)" % lp)
    else:
        try:
            os.remove(lp)
            os.rmdir(work)
        except OSError:
            pass

    if status == "fail" or deep_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
