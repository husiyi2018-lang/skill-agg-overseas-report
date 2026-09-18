# 环境准备(换机器 / 第一次用,先看这页)

> 目标:**不需要你懂命令行**。缺什么,把下面那段提示词整段发给 Claude,它会替你装好。

---

## 一、先跑一次自检

```bash
python scripts/setup_check.py
```

它会逐项告诉你 OK / 缺失,并在结尾打印一段**兜底提示词**(已经把缺的东西填好了)。
如果连 `python` 都没有,先装 Python:https://www.python.org/downloads/

---

## 二、七项依赖:哪些是必需的

前五项是**机器上的技术依赖**,后两项是**你自己的两样东西** —— 人和人不一样,
所以技能里不预置,必须你自己填一次。

| 依赖 | 少了会怎样 | 必需? |
|---|---|---|
| **Python ≥3.8** | 所有脚本跑不起来 | ✅ 必需 |
| **`YOUCLOUD_API_KEY` 环境变量** | 取数直接失败,报告做不出来 | ✅ 必需 |
| **ffmpeg** | 封面(视频抽帧)和关键帧做不出来 | ✅ 必需 |
| **Pillow** | 封面不压缩 → 单文件可能胀到 20MB+ | ⭕ 强烈建议 |
| **Edge / Chrome** | 只影响**导 PDF**;HTML 报告照出 | ⚪ 可选 |
| **邀请注册链接** | 报告右上角按钮与 PDF 页眉空白,客户点不回来 | ✅ 必需(每人不同) |
| **pagepub CLI + API 密钥** | 报告发不出去公开链接,只能传大附件 | ✅ 必需 |

关于 `YOUCLOUD_API_KEY`:它是**你自己的账号凭据**,别人给不了 ——
登录 AppGrowing Global → 个人中心 / 企业信息 里复制 API Key。

---

## 三、只填一次的两样东西(每人不同)

### 3.1 邀请注册链接

报告是**你分享给客户**的,右上角那个渐变按钮和 PDF 页眉上的地址,挂的都是
**你自己的邀请注册链接** —— 客户点了注册,业绩才算你的。所以这条链接一人一条,
技能里不能预置任何固定值。

拿法:登录 AppGrowing Global → **邀请 / 推广** 页面 → 复制属于你的邀请注册链接。

存法(一条命令,存一次以后所有报告自动用,不用再填):

```bash
python scripts/set_profile.py --invite-url "https://你的邀请链接"
```

它会写进技能根目录的 `profile.json`。**这个文件在 `.gitignore` 里,不会进仓库** ——
换人用时 `python scripts/set_profile.py --clear` 清掉即可。
也可以用环境变量 `AGG_INVITE_URL` 临时顶掉文件里的值(优先级更高)。

### 3.2 pagepub(发布成公开链接)

报告做完最后一步是发布出去,客户点开一个网址就能看,不用下载几十 MB 的附件。

1. **装 CLI**:`curl -fsSL https://pagepub.net/cli/install.sh | sh`
   (Windows 若脚本不支持,就去 https://pagepub.net 下载压缩包,把 `pagepub.exe`
   放到 `C:\Users\<你>\.local\bin\` 下 —— 自检脚本会自己去那儿找,不要求你配 PATH)
2. **拿密钥**:登录 https://pagepub.net → 控制台「API 密钥」→ 新建密钥(`pp_` 开头)
3. **存密钥**(只需一次,凭据落在你本机 `~/.pagepub/config.json`):
   `pagepub login --api-key <你的密钥>`

> ⚠️ 密钥是**私密凭据**:只存本机,不要写进技能目录、不要提交到 git、
> 不要在报告里出现。

---

## 四、兜底提示词(直接复制给 Claude)

**不需要先跑自检** —— 下面这段自带"让它自己去看缺什么"的指令。
第一次用就把整段复制给 Claude(如果技能不在默认位置,把第 1 条里的路径改成实际路径):

```
请帮我把 agg-creative-report 这个报告技能跑起来(我第一次用):

1. 先读这个技能,搞清楚它需要什么环境:
   ~/.claude/skills/agg-creative-report/SKILL.md
   ~/.claude/skills/agg-creative-report/references/setup.md

2. 跑一次环境自检,看缺什么:
   python ~/.claude/skills/agg-creative-report/scripts/setup_check.py

3. 缺什么你**直接帮我装好、配好**,不要让我自己动手:
   - ffmpeg / Pillow 这类直接装(Windows 用 winget,Mac 用 brew,Linux 用 apt)
   - Edge 或 Chrome 没有就装一个
   - 需要我本人提供的凭据,请**一次性问全**:
       a) YOUCLOUD_API_KEY(AppGrowing 取数用)
       b) 我的邀请注册链接(要挂在每份分享出去的报告上,每人不同)
       c) pagepub API 密钥(把报告发布成公开链接用)
     每样都告诉我从哪个页面复制;能代我设就代我设
     (Windows 环境变量可用 setx,设完提醒我重开终端)
   - b 用 scripts/set_profile.py 存进本机档案;c 用 pagepub login 存好
   - 装 ffmpeg 后记得**重开终端**再验证

4. 装完重新跑一次 setup_check.py,确认必需项全部变成 [OK]

5. 全部就绪后,再问我:要分析哪个产品、哪个时间段;按 SKILL.md 的流程做完报告,
   最后用 pagepub 发布成公开链接发给我

遇到的任何选择你替我决定,不要反问我技术细节。
```

> Windows 注意:装完 ffmpeg 必须**重开终端**才认得到(环境变量刷新)。
> 如果自检说"找不到 ffmpeg"但你确定装了,先重开终端再跑一次。

---

## 五、手工装(如果不想用提示词)

| 依赖 | Windows | macOS | Linux |
|---|---|---|---|
| ffmpeg | `winget install --id Gyan.FFmpeg -e` | `brew install ffmpeg` | `sudo apt install ffmpeg` |
| Pillow | `python -m pip install Pillow` | 同左 | 同左 |
| 浏览器 | Edge 系统自带;`winget install Microsoft.Edge` | `brew install --cask google-chrome` | `sudo apt install chromium` |
| pagepub | 从 https://pagepub.net 下载 `pagepub.exe` → 放 `~/.local/bin/` | `curl -fsSL https://pagepub.net/cli/install.sh \| sh` | 同左 |

设 `YOUCLOUD_API_KEY`:

- **Windows**:开始菜单搜「环境变量」→ 用户变量 → 新建 `YOUCLOUD_API_KEY` → 值填你的 Key → 确定后**重开终端**
  (或 `setx YOUCLOUD_API_KEY "<你的key>"`)
- **macOS / Linux**:在 `~/.zshrc` 或 `~/.bashrc` 加 `export YOUCLOUD_API_KEY="<你的key>"`,然后 `source` 一下

---

## 六、常见问题

**Q:自检说找不到 ffmpeg / 浏览器,但我明明装了?**
两种可能:①装完没重开终端(Windows 最常见);②装在绿色版/非默认目录。
浏览器这种可以绕开设置直接指定:

```bash
python scripts/topdf.py <报告.html> --browser-exe "D:\绿色版\chrome.exe"
```

**Q:没有浏览器,是不是就交不了报告?**
不是。**HTML 报告本身就是自包含单文件**(图片视频全部内嵌 base64),双击就能看、能直接发人。
浏览器只影响最后一步"额外导出一份 PDF"。

**Q:没有 ffmpeg 能不能凑合?**
不行。这个技能的素材封面是**从视频首帧抽的**(数据源不提供封面图字段),关键帧也要 ffmpeg。
缺了这两步,报告里所有素材卡片都会是空的。

**Q:跑起来报 "未设置 YOUCLOUD_API_KEY"?**
回到第二节去拿 Key 并设成环境变量,设完重开终端。

**Q:自检说找不到 pagepub,但我确定装了?**
先看是不是装在非默认位置。自检会查 PATH 和 `~/.local/bin/`、
`%LOCALAPPDATA%\pagepub\` 这几个常见位置;装在别处就直接用绝对路径调用:
`"D:\tools\pagepub.exe" publish <报告目录> --name "报告名"`

**Q:邀请链接填错了 / 换了账号怎么办?**
重跑一次覆盖即可,不需要动技能里的任何文件:
`python scripts/set_profile.py --invite-url "新的链接"`
(想看看当前存的是什么:`python scripts/set_profile.py --show`)

**Q:我能不能把邀请链接直接写死在报告里,不用 profile.json?**
可以但要小心:报告不只你自己做,别人克隆这个技能后如果不填,
按钮就是空的。`validate.py` 会强制检查这条链接**必须已填且两处一致**,
所以填进 profile.json 是最省事、最不容易漏的做法。

**Q:profile.json 和 pagepub 密钥会被提交到仓库吗?**
不会。`profile.json` 已写进 `.gitignore`;pagepub 密钥只存在
`~/.pagepub/config.json`(技能目录之外)。自己提交前仍建议
`git status` 确认一眼。
