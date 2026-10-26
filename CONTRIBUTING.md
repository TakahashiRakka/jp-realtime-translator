# 贡献指南

感谢你愿意为这个项目花时间。任何形式的贡献都受欢迎 —— 报 bug、提需求、改文档、写代码，都算。

> 本项目面向中文用户，issue 和 PR 用中文或英文都可以，能说清楚就行。

---

## 提 issue 之前

请先做这几件事，能省下大家不少时间：

1. **搜一遍已有 issue**（包括已关闭的），避免重复。
2. **更新到最新代码**，确认问题仍然存在。
3. 如果是运行报错，先看一遍 [README 的常见问题](README.md#常见问题-faq)，
   大部分「连不上 / 抓不到声音」的问题都能在那里解决。

提 bug 时，请务必带上：

| 信息 | 说明 |
| --- | --- |
| 系统版本 | 例如 Windows 11 23H2 |
| Python 版本 | `python --version` |
| Ollama 版本 | `ollama --version` |
| 使用的模型 | ASR 模型名 + Qwen 模型名 |
| 配置项 | `config.json` 里改过的项（**记得删掉设备名等隐私信息**） |
| 复现步骤 | 一步一步写清楚 |
| 完整报错 | 终端里的完整堆栈，不要只截一行 |

---

## 开发流程

### 1. Fork 并克隆

```bash
git clone https://github.com/<你的用户名>/jp-realtime-translator.git
cd jp-realtime-translator
```

### 2. 准备环境

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python patch_soundcard.py
```

不需要真实模型也能开发界面逻辑 —— 用**模拟模式**启动：

```bash
set MOCK=1
python main.py
```

模拟模式下不会调用任何模型，返回的是假数据，界面功能都能跑通。

### 3. 建分支

```bash
git checkout -b feat/你的功能名
```

分支命名建议：`feat/xxx`（新功能）、`fix/xxx`（修 bug）、`docs/xxx`（文档）、`refactor/xxx`（重构）。

### 4. 写代码

请遵守下面几条约定：

- **Python 版本**：兼容 3.10 及以上，不要只用 3.12+ 的语法。
- **依赖**：能不加就不加。新依赖必须是纯 Python 或有 Windows wheel 的，
  并且在 PR 里说明为什么要加。
- **只用标准库做 HTTP**：`translator.py` 和 `asr.py` 用 `urllib` 而非 `requests`，
  并且**显式绕过系统代理**（`ProxyHandler({})`）—— 这是为了让本机 Ollama 不被代理软件劫持，请不要改掉。
- **不阻塞 UI 线程**：耗时的模型调用必须放到后台线程，界面更新统一用 `root.after(0, ...)`。
- **注释与文档字符串**：中文即可，讲清「为什么」而不是「做了什么」。
- **不要提交** `config.json`、`models/`、`.venv/` —— 已在 `.gitignore` 中。
- **不要提交任何密钥、设备序列号、个人目录路径**。

### 5. 自测

```bash
python -m compileall -q main.py asr.py audio_capture.py config.py translator.py patch_soundcard.py tests
python tests/smoke_test.py        # 模拟模式冒烟测试，无需模型和网络
```

CI 会在 Windows 上跑 Python 3.10 ~ 3.13 的同样检查。
改了核心链路（采集 / 识别 / 翻译）的话，请再手动跑一遍真实流程确认能用。

### 6. 提交

提交信息建议用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/v1.0.0/) 风格：

```
feat: 支持导出 Anki 卡片
fix: 修复切换设备后电平表不重置
docs: 补充 CUDA 配置说明
refactor: 抽出 ASR 引擎公共基类
```

### 7. 发 PR

- 标题写清楚改了什么，正文说明**动机**和**验证方式**。
- 有界面改动的话，贴一张前后对比截图。
- 如果涉及行为变更，同步更新 `README.md` / `README_EN.md`。
- PR 会自动触发 CI，全绿后才会被 review。

---

## 我想帮忙，但不知道做什么

看 [README 的路线图](README.md#路线图)，或者直接搜带 `good first issue` 标签的 issue。
不确定某个想法合不合适？先开个 issue 讨论，比闷头写完再被否要好。

---

## 行为准则

参与本项目即表示你同意遵守 [行为准则](CODE_OF_CONDUCT.md)。
