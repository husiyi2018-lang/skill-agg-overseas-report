# agg-overseas-report

海外产品「素材投放与创意策略综合报告」生成器（Agent Skill）。

基于 [AppGrowing Global](https://appgrowing.ai)（aggclaw 分析引擎），产出自包含单文件 HTML 报告：零外部依赖、可离线、素材可在线播放、内置数字保真校验。适用于出海游戏 / 短剧 App / 工具金融 App 的单产品深拆、竞品对标与选品。

## 安装

### 方式一：给 Agent 一句话（推荐）

把下面这句发给任何能执行命令的 Agent（Claude Code / WorkBuddy / Codex / n8n 等）：

```
把 https://github.com/husiyi2018-lang/skill-agg-overseas-report 克隆到你的 skills 目录（如 ~/.workbuddy/skills/agg-overseas-report 或 ~/.claude/skills/agg-overseas-report），然后阅读其中的 SKILL.md 并按其执行。
```

### 方式二：手动安装（WorkBuddy / Claude Code）

```bash
# WorkBuddy 用户
git clone https://github.com/husiyi2018-lang/skill-agg-overseas-report.git ~/.workbuddy/skills/agg-overseas-report

# Claude Code 用户（项目级）
git clone https://github.com/husiyi2018-lang/skill-agg-overseas-report.git .claude/skills/agg-overseas-report
```

### 方式三：下载 zip

```bash
curl -L https://github.com/husiyi2018-lang/skill-agg-overseas-report/archive/refs/heads/main.zip -o skill.zip
unzip skill.zip -d ~/.workbuddy/skills/
mv ~/.workbuddy/skills/skill-agg-overseas-report-main ~/.workbuddy/skills/agg-overseas-report
```

## 环境要求

安装后先跑自检，它会告诉你缺什么，并生成一段可整段交给 Agent 的兜底提示词：

```bash
python scripts/setup_check.py
```

| 依赖 | 必需性 | 说明 |
|---|---|---|
| Python ≥ 3.8 | ✅ | |
| `YOUCLOUD_API_KEY` 环境变量 | ✅ | 自己的 AppGrowing 账号凭据：登录 AppGrowing Global → 个人中心 / 企业信息 → 复制 API Key |
| ffmpeg | ✅ | 视频抽帧 / 关键帧；装完需重开终端 |
| Pillow | ⭕ 建议 | 封面压缩，否则报告胀到 20MB+ |
| Edge / Chrome | ⚪ 可选 | 仅影响导出 PDF，HTML 报告不受影响 |

## 使用

对 Agent 说触发词即可，例如：

- 「分析 Pokemon Go 的素材策略」
- 「本周有哪些值得分析的游戏」「什么游戏在火」
- 「拆解这条素材」「和 XX 对比」

报告流程：setup → fetch → materialize → HTML → derived → validate → PDF。

## 目录结构

```
SKILL.md              # Agent 阅读的主指令
USAGE-客户版.md        # 面向使用者的说明
scripts/              # 取数 / 图表 / 校验 / 导出脚本
references/           # 分场景深度参考文档
assets/               # 报告 HTML 模板与前端依赖（离线可用）
```

## 许可

供内部与合作伙伴使用，基于 AppGrowing Global 数据生成报告时需遵守平台数据使用条款。
