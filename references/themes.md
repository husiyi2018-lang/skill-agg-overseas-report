# 主题与 favicon

`shell.html` 里有一个主题槽：

```html
<style>
/* {{THEME_CSS}} */     ← 从下面复制一整套贴进来
</style>
```

**换主题只需贴一段 CSS，不用改任何 class 名**。图表颜色会跟着自动变（调色板是运行时从 CSS 变量读的）。

## 四套预设

| 主题 | 气质 | 适合 |
|---|---|---|
| `base` | 粉紫（默认） | 出海短剧 App / 内容型产品 |
| `gold` | 部落金 | 策略 / 中重度游戏，或需要「厚重、史诗感」的产品 |
| `teal` | 青金 | 工具 / 金融 / 生活服务类 App |
| `indigo` | 深蓝 | 品牌向产品，或客户演示稿 |

---

## `base` —— 粉紫（默认）

适合：出海短剧 App / 内容型产品

**不贴任何主题块就是它** —— `shell.html` 基础 CSS 的 `:root` 默认值就是这套。

**不需要贴任何东西。** 如果要显式写出来（比如给别的主题做基准对照），贴这段：

```css
:root{
  --bg:#0f0b14; --bg2:#17111f; --card:#1b1424; --card2:#221a2d;
  --ink:#ece6f2; --ink2:#a99cb8; --line:#332741;
  --brand:#c2185b; --brand-d:#8e0f42; --brand-l:#f0568e;
  --ember:#ff8a3d; --ember-d:#e06a1c;
  --gold:#ffd166; --teal:#2ec4b6; --violet:#7b5cff; --danger:#ff4d6d;
  --grad-brand:linear-gradient(120deg,#c2185b,#7b5cff 55%,#ff8a3d);
}
```

**favicon**：**已固定**为 AppGrowing 品牌图标（深色版，base64 内嵌），报告无需替换。

---

## `gold` —— 部落金

适合：策略 / 中重度游戏，或需要「厚重、史诗感」的产品

COC 报告原样（已清理原报告里 `--brand-l:#f0b martial;` 这行脏值）。

**主题块**（整段复制进主题槽）：

```css
:root{
  --bg:#0d1114; --bg2:#141a1e; --card:#182025; --card2:#1e282e;
  --ink:#e8eef1; --ink2:#96a8b2; --line:#2a3840;
  --brand:#c8892a; --brand-d:#8f5f14; --brand-l:#f0b451;
  --ember:#e0703a; --ember-d:#b8562a;
  --gold:#ffd166; --teal:#3fbf9f; --violet:#5b8fd6; --danger:#e05252;
  --grad-brand:linear-gradient(120deg,#c8892a,#e0703a 55%,#8f5f14);
  --shadow:0 8px 24px rgba(0,0,0,.5);
  --shadow-lg:0 16px 44px rgba(0,0,0,.62);
  --r:18px;
}
body{background-image:
    radial-gradient(circle at 6% 3%, rgba(200,137,42,.16), transparent 30%),
    radial-gradient(circle at 94% 8%, rgba(91,143,214,.10), transparent 32%),
    radial-gradient(circle at 72% 95%, rgba(224,112,58,.10), transparent 32%);}
#progress{background:linear-gradient(90deg,var(--gold),var(--teal),var(--ember))}
nav.side{background:linear-gradient(180deg,#111719,#0d1114)}
.brand .logo{background:linear-gradient(145deg,var(--brand-l),var(--brand) 60%,var(--brand-d));box-shadow:0 6px 18px rgba(200,137,42,.50)}
#menuBtn{box-shadow:0 8px 22px rgba(200,137,42,.50)}
h2{background:linear-gradient(90deg,rgba(200,137,42,.28),transparent 72%);border-left-color:var(--brand-l)}
h3{color:var(--brand-l);border-left-color:var(--brand)}
.s-arrow{color:var(--brand-l)}
.kpi::before{background:linear-gradient(180deg,var(--brand-l),var(--brand-d))}
.kpi.good::before{background:linear-gradient(180deg,var(--teal),#146355)}
.kpi.danger::before{background:linear-gradient(180deg,var(--danger),#8a1f1f)}
.step em{color:var(--brand-l)}
blockquote.lead{background:linear-gradient(90deg,rgba(200,137,42,.18),var(--card) 62%)}
thead th{background:linear-gradient(180deg,#33301f,#26251a)}
tbody tr:hover{background:rgba(200,137,42,.13)}
.gal-no{background:var(--grad-brand)}
.gal-tag{background:var(--brand)}
.gal-tag.t2{background:var(--violet)}
.gal-verdict{border-left-color:var(--brand-l)}
.b-lang{background:rgba(200,137,42,.94)}
.badge.b-type{background:rgba(91,143,214,.92)}
.mchip{color:#e2c9a0;background:rgba(200,137,42,.16);border-color:rgba(200,137,42,.30)}
.chip2{color:#e2c9a0;background:rgba(200,137,42,.15);border-color:rgba(200,137,42,.30)}
.newsbtn{background:rgba(200,137,42,.15);border-color:rgba(200,137,42,.45)!important;color:var(--brand-l)!important}
.newsbtn:hover{background:var(--brand);color:#111!important;border-color:var(--brand)!important}
.lv-h{background:rgba(224,82,82,.18);color:#ff9a9a;border-color:rgba(224,82,82,.40)}
.lv-m{background:rgba(255,209,102,.16);color:var(--gold);border-color:rgba(255,209,102,.35)}
.lv-l{background:rgba(150,168,178,.14);color:var(--ink2);border-color:var(--line)}
.g-row dt{color:var(--brand-l)}
.g-row.why dt{color:var(--teal)}
.g-row.kf dt{color:var(--gold)}
.kf-label{color:var(--gold)}
.fbtn.on{background:var(--brand);border-color:var(--brand);color:#111}
.fcell .fl{color:var(--brand-l)}
.tl-item::before{background:var(--brand);box-shadow:0 0 0 2px var(--brand-l)}
.tl::before{background:linear-gradient(180deg,var(--brand-l),var(--teal),var(--ember))}
.tl-ts{background:var(--brand);color:#111}
.aud-c{border-top-color:var(--brand)}
.aud-c:nth-child(2){border-top-color:var(--violet)}
.aud-c:nth-child(3){border-top-color:var(--teal)}
.pcard::before{background:var(--grad-brand)}
.pcard.hl{border-color:rgba(200,137,42,.45)}
.mm-root{background:var(--grad-brand);color:#111}
.mm-l1{background:rgba(200,137,42,.20);border-color:rgba(200,137,42,.42)}
blockquote{border-left-color:var(--brand)}
blockquote strong{color:var(--gold)}
blockquote.warn{border-left-color:var(--danger);background:linear-gradient(90deg,rgba(224,82,82,.09),var(--card) 60%)}
blockquote.warn strong{color:#ff9a9a}
blockquote.fix{border-left-color:var(--teal);background:linear-gradient(90deg,rgba(63,191,159,.09),var(--card) 60%)}
blockquote.fix strong{color:var(--teal)}
.keep{color:var(--teal)}
.borrow{color:var(--brand-l)}
.num{color:var(--gold)}
details.rev summary{background:rgba(200,137,42,.13);border-color:rgba(200,137,42,.30)}
```

**favicon**：**已固定**为 AppGrowing 品牌图标（深色版，base64 内嵌），报告无需替换。

---

## `teal` —— 青金

适合：工具 / 金融 / 生活服务类 App

新增。整体偏「清爽、工具感」。

**主题块**（整段复制进主题槽）：

```css
:root{
  --bg:#0b1414; --bg2:#12201f; --card:#162726; --card2:#1d3130;
  --ink:#e6f0ef; --ink2:#93a9a6; --line:#26403e;
  --brand:#0f9b8e; --brand-d:#0a6b62; --brand-l:#3fd6c4;
  --ember:#e8973a; --ember-d:#b8701f;
  --gold:#ffd166; --teal:#2ec4b6; --violet:#5b8fd6; --danger:#e05252;
  --grad-brand:linear-gradient(120deg,#0f9b8e,#e8973a 55%,#0a6b62);
  --shadow:0 8px 24px rgba(0,0,0,.5);
  --shadow-lg:0 16px 44px rgba(0,0,0,.62);
  --r:18px;
}
body{background-image:
    radial-gradient(circle at 6% 3%, rgba(15,155,142,.16), transparent 30%),
    radial-gradient(circle at 94% 8%, rgba(91,143,214,.10), transparent 32%),
    radial-gradient(circle at 72% 95%, rgba(232,151,58,.10), transparent 32%);}
#progress{background:linear-gradient(90deg,var(--gold),var(--teal),var(--ember))}
nav.side{background:linear-gradient(180deg,#0f1a19,#0b1414)}
.brand .logo{background:linear-gradient(145deg,var(--brand-l),var(--brand) 60%,var(--brand-d));box-shadow:0 6px 18px rgba(15,155,142,.50)}
#menuBtn{box-shadow:0 8px 22px rgba(15,155,142,.50)}
h2{background:linear-gradient(90deg,rgba(15,155,142,.28),transparent 72%);border-left-color:var(--brand-l)}
h3{color:var(--brand-l);border-left-color:var(--brand)}
.s-arrow{color:var(--brand-l)}
.kpi::before{background:linear-gradient(180deg,var(--brand-l),var(--brand-d))}
.kpi.good::before{background:linear-gradient(180deg,var(--teal),#0d5c53)}
.kpi.danger::before{background:linear-gradient(180deg,var(--danger),#8a1f1f)}
.step em{color:var(--brand-l)}
blockquote.lead{background:linear-gradient(90deg,rgba(15,155,142,.18),var(--card) 62%)}
thead th{background:linear-gradient(180deg,#1b3331,#152826)}
tbody tr:hover{background:rgba(15,155,142,.13)}
.gal-no{background:var(--grad-brand)}
.gal-tag{background:var(--brand)}
.gal-tag.t2{background:var(--violet)}
.gal-verdict{border-left-color:var(--brand-l)}
.b-lang{background:rgba(15,155,142,.94)}
.badge.b-type{background:rgba(91,143,214,.92)}
.mchip{color:#a8ded8;background:rgba(15,155,142,.16);border-color:rgba(15,155,142,.30)}
.chip2{color:#a8ded8;background:rgba(15,155,142,.15);border-color:rgba(15,155,142,.30)}
.newsbtn{background:rgba(15,155,142,.15);border-color:rgba(15,155,142,.45)!important;color:var(--brand-l)!important}
.newsbtn:hover{background:var(--brand);color:#06201d!important;border-color:var(--brand)!important}
.lv-h{background:rgba(224,82,82,.18);color:#ff9a9a;border-color:rgba(224,82,82,.40)}
.lv-m{background:rgba(255,209,102,.16);color:var(--gold);border-color:rgba(255,209,102,.35)}
.lv-l{background:rgba(147,169,166,.14);color:var(--ink2);border-color:var(--line)}
.g-row dt{color:var(--brand-l)}
.g-row.why dt{color:var(--teal)}
.g-row.kf dt{color:var(--gold)}
.kf-label{color:var(--gold)}
.fbtn.on{background:var(--brand);border-color:var(--brand);color:#06201d}
.fcell .fl{color:var(--brand-l)}
.tl-item::before{background:var(--brand);box-shadow:0 0 0 2px var(--brand-l)}
.tl::before{background:linear-gradient(180deg,var(--brand-l),var(--teal),var(--ember))}
.tl-ts{background:var(--brand);color:#06201d}
.aud-c{border-top-color:var(--brand)}
.aud-c:nth-child(2){border-top-color:var(--violet)}
.aud-c:nth-child(3){border-top-color:var(--teal)}
.pcard::before{background:var(--grad-brand)}
.pcard.hl{border-color:rgba(15,155,142,.45)}
.mm-root{background:var(--grad-brand);color:#06201d}
.mm-l1{background:rgba(15,155,142,.20);border-color:rgba(15,155,142,.42)}
blockquote{border-left-color:var(--brand)}
blockquote strong{color:var(--gold)}
blockquote.warn{border-left-color:var(--danger);background:linear-gradient(90deg,rgba(224,82,82,.09),var(--card) 60%)}
blockquote.warn strong{color:#ff9a9a}
blockquote.fix{border-left-color:var(--teal);background:linear-gradient(90deg,rgba(46,196,182,.09),var(--card) 60%)}
blockquote.fix strong{color:var(--teal)}
.keep{color:var(--teal)}
.borrow{color:var(--brand-l)}
.num{color:var(--gold)}
details.rev summary{background:rgba(15,155,142,.13);border-color:rgba(15,155,142,.30)}
```

**favicon**：**已固定**为 AppGrowing 品牌图标（深色版，base64 内嵌），报告无需替换。

---

## `indigo` —— 深蓝

适合：品牌向产品，或客户演示稿

新增。整体偏「商务、理性」。

**主题块**（整段复制进主题槽）：

```css
:root{
  --bg:#0b0f1a; --bg2:#111726; --card:#151c2e; --card2:#1c2438;
  --ink:#e8ecf7; --ink2:#96a1bb; --line:#26314a;
  --brand:#3b5bdb; --brand-d:#28409e; --brand-l:#7c93f5;
  --ember:#e0703a; --ember-d:#b8562a;
  --gold:#ffd166; --teal:#2ec4b6; --violet:#7b5cff; --danger:#e05252;
  --grad-brand:linear-gradient(120deg,#3b5bdb,#e0703a 55%,#28409e);
  --shadow:0 8px 24px rgba(0,0,0,.5);
  --shadow-lg:0 16px 44px rgba(0,0,0,.62);
  --r:18px;
}
body{background-image:
    radial-gradient(circle at 6% 3%, rgba(59,91,219,.16), transparent 30%),
    radial-gradient(circle at 94% 8%, rgba(123,92,255,.10), transparent 32%),
    radial-gradient(circle at 72% 95%, rgba(224,112,58,.10), transparent 32%);}
#progress{background:linear-gradient(90deg,var(--gold),var(--teal),var(--ember))}
nav.side{background:linear-gradient(180deg,#0d1220,#0b0f1a)}
.brand .logo{background:linear-gradient(145deg,var(--brand-l),var(--brand) 60%,var(--brand-d));box-shadow:0 6px 18px rgba(59,91,219,.50)}
#menuBtn{box-shadow:0 8px 22px rgba(59,91,219,.50)}
h2{background:linear-gradient(90deg,rgba(59,91,219,.28),transparent 72%);border-left-color:var(--brand-l)}
h3{color:var(--brand-l);border-left-color:var(--brand)}
.s-arrow{color:var(--brand-l)}
.kpi::before{background:linear-gradient(180deg,var(--brand-l),var(--brand-d))}
.kpi.good::before{background:linear-gradient(180deg,var(--teal),#146355)}
.kpi.danger::before{background:linear-gradient(180deg,var(--danger),#8a1f1f)}
.step em{color:var(--brand-l)}
blockquote.lead{background:linear-gradient(90deg,rgba(59,91,219,.18),var(--card) 62%)}
thead th{background:linear-gradient(180deg,#26304d,#1b2338)}
tbody tr:hover{background:rgba(59,91,219,.13)}
.gal-no{background:var(--grad-brand)}
.gal-tag{background:var(--brand)}
.gal-tag.t2{background:var(--violet)}
.gal-verdict{border-left-color:var(--brand-l)}
.b-lang{background:rgba(59,91,219,.94)}
.badge.b-type{background:rgba(123,92,255,.92)}
.mchip{color:#b9c4f0;background:rgba(59,91,219,.16);border-color:rgba(59,91,219,.30)}
.chip2{color:#b9c4f0;background:rgba(59,91,219,.15);border-color:rgba(59,91,219,.30)}
.newsbtn{background:rgba(59,91,219,.15);border-color:rgba(59,91,219,.45)!important;color:var(--brand-l)!important}
.newsbtn:hover{background:var(--brand);color:#fff!important;border-color:var(--brand)!important}
.lv-h{background:rgba(224,82,82,.18);color:#ff9a9a;border-color:rgba(224,82,82,.40)}
.lv-m{background:rgba(255,209,102,.16);color:var(--gold);border-color:rgba(255,209,102,.35)}
.lv-l{background:rgba(150,161,187,.14);color:var(--ink2);border-color:var(--line)}
.g-row dt{color:var(--brand-l)}
.g-row.why dt{color:var(--teal)}
.g-row.kf dt{color:var(--gold)}
.kf-label{color:var(--gold)}
.fbtn.on{background:var(--brand);border-color:var(--brand);color:#fff}
.fcell .fl{color:var(--brand-l)}
.tl-item::before{background:var(--brand);box-shadow:0 0 0 2px var(--brand-l)}
.tl::before{background:linear-gradient(180deg,var(--brand-l),var(--teal),var(--ember))}
.tl-ts{background:var(--brand);color:#fff}
.aud-c{border-top-color:var(--brand)}
.aud-c:nth-child(2){border-top-color:var(--violet)}
.aud-c:nth-child(3){border-top-color:var(--teal)}
.pcard::before{background:var(--grad-brand)}
.pcard.hl{border-color:rgba(59,91,219,.45)}
.mm-root{background:var(--grad-brand);color:#fff}
.mm-l1{background:rgba(59,91,219,.20);border-color:rgba(59,91,219,.42)}
blockquote{border-left-color:var(--brand)}
blockquote strong{color:var(--gold)}
blockquote.warn{border-left-color:var(--danger);background:linear-gradient(90deg,rgba(224,82,82,.09),var(--card) 60%)}
blockquote.warn strong{color:#ff9a9a}
blockquote.fix{border-left-color:var(--teal);background:linear-gradient(90deg,rgba(46,196,182,.09),var(--card) 60%)}
blockquote.fix strong{color:var(--teal)}
.keep{color:var(--teal)}
.borrow{color:var(--brand-l)}
.num{color:var(--gold)}
details.rev summary{background:rgba(59,91,219,.13);border-color:rgba(59,91,219,.30)}
```

**favicon**：**已固定**为 AppGrowing 品牌图标（深色版，base64 内嵌），报告无需替换。

---

## 换主题时还要顺手改的 3 处

主题块管不到的地方，需要手动同步，否则会**主题不统一**：

1. **`.brand .logo` 里的 emoji** —— hero 左上角图标，跟主题语义配（金主题用 🛡、短剧用 ▶、工具用 ◆）
2. **图表里的 `C.violet` / `C.ember`** —— 这两个是「对比色」，不是主题色。如果主题本身已经很接近 violet，把竞品色改成 `C.gold`
3. **表内联涨跌色** —— `<td style="color:#3fbf9f">` 这类硬编码。金/青主题下 `#3fbf9f` 没问题；换 indigo 建议统一改成 `var(--teal)`

## 自检

换完主题跑一遍：

```bash
python scripts/validate.py <报告.html>
```

它会检查 CSS 是否全部落在 `<style>` 块内 —— **这是换主题最容易踩的坑**（见 `pitfalls.md` §1）。
