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

## 二、五项依赖:哪些是必需的

| 依赖 | 少了会怎样 | 必需? |
|---|---|---|
| **Python ≥3.8** | 所有脚本跑不起来 | ✅ 必需 |
| **`YOUCLOUD_API_KEY` 环境变量** | 取数直接失败,报告做不出来 | ✅ 必需 |
| **ffmpeg** | 封面(视频抽帧)和关键帧做不出来 | ✅ 必需 |
| **Pillow** | 封面不压缩 → 单文件可能胀到 20MB+ | ⭕ 强烈建议 |
| **Edge / Chrome** | 只影响**导 PDF**;HTML 报告照出 | ⚪ 可选 |

关于 `YOUCLOUD_API_KEY`:它是**你自己的账号凭据**,别人给不了 ——
登录 AppGrowing Global → 个人中心 / 企业信息 里复制 API Key。

---

## 三、兜底提示词(直接复制给 Claude)

**不需要先跑自检** —— 下面这段自带"让它自己去看缺什么"的指令。
第一次用就把整段复制给 Claude(如果技能不在默认位置,把第 1 条里的路径改成实际路径):

```
请帮我把 agg-overseas-report 这个报告技能跑起来(我第一次用):

1. 先读这个技能,搞清楚它需要什么环境:
   ~/.claude/skills/agg-overseas-report/SKILL.md
   ~/.claude/skills/agg-overseas-report/references/setup.md

2. 跑一次环境自检,看缺什么:
   python ~/.claude/skills/agg-overseas-report/scripts/setup_check.py

3. 缺什么你**直接帮我装好、配好**,不要让我自己动手:
   - ffmpeg / Pillow 这类直接装(Windows 用 winget,Mac 用 brew,Linux 用 apt)
   - Edge 或 Chrome 没有就装一个
   - YOUCLOUD_API_KEY 如果我没配:告诉我从哪个页面拿,能代我设就代我设
     (Windows 可以用 setx,设完提醒我重开终端)
   - 装 ffmpeg 后记得**重开终端**再验证

4. 装完重新跑一次 setup_check.py,确认必需项全部变成 [OK]

5. 全部就绪后,再问我:要分析哪个产品、哪个时间段,然后按 SKILL.md 的流程开工

遇到的任何选择你替我决定,不要反问我技术细节。
```

> Windows 注意:装完 ffmpeg 必须**重开终端**才认得到(环境变量刷新)。
> 如果自检说"找不到 ffmpeg"但你确定装了,先重开终端再跑一次。

---

## 四、手工装(如果不想用提示词)

| 依赖 | Windows | macOS | Linux |
|---|---|---|---|
| ffmpeg | `winget install --id Gyan.FFmpeg -e` | `brew install ffmpeg` | `sudo apt install ffmpeg` |
| Pillow | `python -m pip install Pillow` | 同左 | 同左 |
| 浏览器 | Edge 系统自带;`winget install Microsoft.Edge` | `brew install --cask google-chrome` | `sudo apt install chromium` |

设 `YOUCLOUD_API_KEY`:

- **Windows**:开始菜单搜「环境变量」→ 用户变量 → 新建 `YOUCLOUD_API_KEY` → 值填你的 Key → 确定后**重开终端**
  (或 `setx YOUCLOUD_API_KEY "<你的key>"`)
- **macOS / Linux**:在 `~/.zshrc` 或 `~/.bashrc` 加 `export YOUCLOUD_API_KEY="<你的key>"`,然后 `source` 一下

---

## 五、常见问题

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
