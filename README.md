# 日语实时转写 · 翻译 · 语法解析

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python\&logoColor=white)

![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows)

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

![Local-first](https://img.shields.io/badge/Privacy-100%25%20本地运行-brightgreen)

![CI](https://github.com/<your-github-username>/jp-realtime-translator/actions/workflows/ci.yml/badge.svg)

> 电脑里正在播放日语 —— 屏幕上同步出现**中文翻译**和**逐词语法拆解**。  
> 不装虚拟声卡、不依赖 ffmpeg、音频不出本机，全部在你自己的电脑上跑完。

[English README](README_EN.md) · [常见问题](#常见问题-faq) · [参与贡献](CONTRIBUTING.md)

---

## 目录

- [它能做什么](#它能做什么)
- [效果预览](#效果预览)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [两种 ASR 引擎怎么选](#两种-asr-引擎怎么选)
- [工作原理](#工作原理)
- [项目结构](#项目结构)
- [常见问题 FAQ](#常见问题-faq)
- [路线图](#路线图)
- [使用与合规提示](#使用与合规提示)
- [许可证](#许可证)

---

## 它能做什么

看日剧、看生放送、打游戏、听日语播客时，把电脑正在播放的声音实时变成字幕：

| 能力         | 说明                                                          |
| ---------- | ----------------------------------------------------------- |
| 🎧 系统声音直采  | 用 WASAPI 回环抓取「扬声器正在播放的声音」，无需虚拟声卡、无需 ffmpeg                  |
| 🗣️ 日语语音识别 | 默认走本地 Ollama 的 Qwen3-ASR（自动断句、自动加标点）；可切 faster-whisper 离线回退 |
| 🌏 中文翻译    | 本地 Qwen3 模型翻译，输出自然通顺的中文                                     |
| 📚 逐词语法解析  | 拆成「原词 / 读音 / 词性 / 意思 / 语法点」，助词、て形、た形、敬语都能讲清楚                |
| 📊 实时电平表   | 一眼看出有没有抓到声音，不用盲猜                                            |
| 💾 字幕导出    | 一键导出 Markdown / SRT / TXT，SRT 可直接挂到播放器                      |
| 🔒 全本地运行   | 音频和文本只在你的机器上流转，不上传任何服务器                                     |

---

## 效果预览

> 📷 **TODO**：把你的界面截图放到 `docs/screenshot.png`，然后取消下面这行的注释。

界面分三栏：左上日语原文、左下中文翻译、右侧当前句的语法拆解表（原词 / 读音 / 词性 / 意思 / 语法说明）。

---

## 快速开始

### 0. 前置条件

| 项目     | 要求                                                  |
| ------ | --------------------------------------------------- |
| 操作系统   | Windows 10 / 11（依赖 WASAPI 回环，macOS / Linux 暂不支持）    |
| Python | 3.10 及以上，安装时勾选 **Add python.exe to PATH**           |
| Ollama | [ollama.com](https://ollama.com) 下载安装，用于跑 ASR 和翻译模型 |
| 硬件（建议） | 16GB 内存；有 NVIDIA 显卡体验会好很多                           |

### 1. 拉取模型

安装完 Ollama 后，在**终端**里执行（约需下载 2.5GB + 9GB，视模型而定）：

```bash
ollama pull frozenlab/qwen3-asr:1.7b   # 语音识别（默认引擎，必需）
ollama pull qwen3:14b                  # 翻译 + 语法解析（必需）
```

> 内存小于 16GB？把翻译模型换成小一点的：`ollama pull qwen3:8b`，  
> 然后在程序「设置」里把 `Qwen 模型名` 改成 `qwen3:8b`。

### 2. 运行

```bash
git clone https://github.com/<your-github-username>/jp-realtime-translator.git
cd jp-realtime-translator
```

**方式 A（推荐）：双击 `run.bat`**  
它会自动完成：创建 `.venv` → 安装依赖 → 修补 soundcard 兼容问题 → 启动界面。  
全过程无需手动敲命令，断网重试也已内置（官方源失败会自动切清华镜像）。

**方式 B：手动启动**

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python patch_soundcard.py      # 修补 soundcard 与 numpy 2.x 的兼容问题（幂等，可重复执行）
python main.py
```

### 3. 开始使用

1. 界面顶部「音频设备」选择你的**扬声器 / 耳机**（回环设备已排在下拉框最前面）；不确定就点「刷新设备」。
2. 播放一段日语音频。
3. 点 **▶ 开始**，观察「输入电平」条是否在跳动 —— 有跳动说明抓到声音了。
4. 勾选「自动语法解析」可以每句都出语法表；不勾则只翻译，需要时再点「解析末句语法」（更省资源）。

> 想先看看界面长什么样？勾选工具栏的 **模拟模式**，不加载任何模型就能体验完整 UI。

---

## 配置说明

首次运行会在程序目录生成 `config.json`（已在 `.gitignore` 中，不会提交）。  
也可以在界面的「设置」面板里改，改完自动写回。优先级：**环境变量 > config.json > 默认值**。

| 键                       | 默认值                        | 说明                                                    |
| ----------------------- | -------------------------- | ----------------------------------------------------- |
| `ASR_ENGINE`            | `qwen3-asr`                | 识别引擎：`qwen3-asr`（准）或 `whisper`（离线）                    |
| `ASR_MODEL`             | `frozenlab/qwen3-asr:1.7b` | Qwen3-ASR 的 Ollama 模型名                                |
| `WHISPER_MODEL`         | `small`                    | whisper 引擎的模型：tiny / base / small / medium / large-v3 |
| `WHISPER_DEVICE`        | `cpu`                      | `cpu` 或 `cuda`                                        |
| `WHISPER_COMPUTE_TYPE`  | `int8`                     | int8 / int8_float16 / float16                         |
| `CHUNK_SECONDS`         | `4.0`                      | 每多少秒切一段送去识别。调小更实时、调大更准                                |
| `OLLAMA_BASE_URL`       | `http://localhost:11434`   | Ollama 服务地址                                           |
| `QWEN_MODEL`            | `qwen3:14b`                | 翻译与语法解析模型                                             |
| `QWEN_TEMPERATURE`      | `0.3`                      | 越低越稳定，越高越自由                                           |
| `QWEN_DISABLE_THINKING` | `true`                     | 关闭 Qwen3 思考链，更快更干净                                    |
| `AUTO_GRAMMAR`          | `false`                    | 是否每句自动做语法解析                                           |
| `WASAPI_DEVICE`         | `""`                       | 音频设备名，留空自动选默认扬声器回环                                    |
| `MOCK`                  | `false`                    | 模拟模式，不调用任何模型（调试 UI 用）                                 |
| `EXPORT_DIR`            | `""`                       | 导出默认目录                                                |

所有键都可以用同名环境变量覆盖，例如：

```bash
set CHUNK_SECONDS=3
set QWEN_MODEL=qwen3:8b
python main.py
```

---

## 两种 ASR 引擎怎么选

|             | Qwen3-ASR（默认）               | faster-whisper           |
| ----------- | --------------------------- | ------------------------ |
| 运行方式        | 本地 Ollama                   | 本地 Python 进程             |
| 是否需要 Ollama | ✅ 是                         | ❌ 否                      |
| 日语准确度       | 更高，自动加标点                    | 一般，长句易断错                 |
| 语言检测        | 52 种自动检测                    | 需手动指定 `ja`               |
| 离线可用性       | 模型拉到本地后离线                   | 模型下载后离线                  |
| 额外依赖        | 无（`soundcard` + `numpy` 就够） | 需 `faster-whisper`（体积较大） |

切换：设置面板里把 `ASR 引擎` 改为 `whisper`，并安装可选依赖：

```bash
pip install -r requirements-whisper.txt
```

---

## 工作原理

```
┌──────────────┐   WASAPI 回环   ┌──────────────┐
│ 系统播放的声音 │ ──────────────▶ │ AudioCapture │  16kHz 单声道
└──────────────┘                 └──────┬───────┘
                                        │ 每 CHUNK_SECONDS 秒切一段（不重叠）
                                        ▼
                                 ┌──────────────┐
                                 │     ASR      │  Qwen3-ASR / faster-whisper
                                 └──────┬───────┘
                                        │ 日语原文
                                        ▼
                                 ┌──────────────┐
                                 │  Translator  │  本地 Ollama Qwen3
                                 └──────┬───────┘
                                        │
                        ┌───────────────┴───────────────┐
                        ▼                               ▼
                  中文翻译（左下栏）              逐词语法拆解（右栏）
                        │
                        ▼
                  导出 md / srt / txt
```

- 音频采集、识别、翻译分别在独立线程，界面不会卡死。
- 分段采用**不重叠**策略，避免相邻两段出现重复字幕。
- 与 Ollama 通信时**显式绕过系统代理**，避免代理软件劫持 `localhost:11434` 导致连不上。

---

## 项目结构

```
jp-realtime-translator/
├── main.py              # tkinter 三栏界面、主循环、导出
├── audio_capture.py     # WASAPI 回环采集、设备枚举、电平表
├── asr.py               # 双引擎语音识别（Qwen3-ASR / faster-whisper）
├── translator.py        # Qwen3 翻译 + 结构化语法解析
├── config.py            # 配置加载（环境变量 > config.json > 默认值）
├── config.example.json  # 配置模板
├── patch_soundcard.py   # soundcard × numpy 2.x 兼容补丁（幂等）
├── run.bat              # 一键启动：建 venv → 装依赖 → 打补丁 → 运行
├── requirements.txt     # 核心依赖
├── requirements-whisper.txt  # whisper 引擎的可选依赖
└── tests/smoke_test.py  # 冒烟测试（模拟模式，无需模型/网络）
```

---

## 常见问题 FAQ

**Q：电平表不动 / 识别不出字？**  
先确认设备选对了 —— 要选**扬声器/耳机类的回环设备**（下拉框里排在最前面）。  
再确认播放的是扬声器外放，而不是耳机插在别的设备上。点「刷新设备」重新枚举试试。

**Q：提示「未找到可用的回环音频设备」？**  
部分蓝牙耳机、HDMI 输出不暴露回环通道。改用有线扬声器或主板集成声卡输出即可。

**Q：状态栏显示「Qwen未连接」，但我明明开着 Ollama？**  
多半是代理软件劫持了本机请求。程序已内置绕过逻辑，但仍请检查：  
浏览器访问 <http://localhost:11434> 是否能打开；若开着 Clash 等工具，把 `localhost` 加入直连/绕过列表。

**Q：提示「Ollama 中未找到 ASR 模型」？**  
按[快速开始](#1-拉取模型)执行 `ollama pull frozenlab/qwen3-asr:1.7b`，拉完重开程序。

**Q：延迟太高？**  
按顺序优化：① 设置里把 `CHUNK_SECONDS` 调到 2~3；② 翻译模型换成 `qwen3:8b`；  
③ 关掉「自动语法解析」（语法解析比纯翻译慢得多）；④ 有 N 卡就把 whisper 设备设为 `cuda`。

**Q：模型下载很慢或失败？**  
程序已默认把 HuggingFace 指向 `hf-mirror.com` 镜像并禁用 Xet 存储。  
若仍失败，可手动设置环境变量 `HF_ENDPOINT=https://hf-mirror.com` 后重试。

**Q：models/ 目录里的文件要不要提交？**  
不要。它是运行时自动下载的权重（约 460MB），已在 `.gitignore` 中忽略。

**Q：能不能实时翻译游戏语音/会议麦克风？**  
可以。把「音频设备」选成对应的**麦克风**即可（下拉框里也列出了麦克风）。

---

## 路线图

欢迎认领，见 [CONTRIBUTING.md](CONTRIBUTING.md)。

- [ ] 说话人分离（区分不同角色）
- [ ] 发音评分 / 跟读对比
- [ ] 生词本：自动收集生词并导出 Anki 卡片
- [ ] 历史会话检索与回放
- [ ] macOS / Linux 支持（需替换音频回环方案，如 PulseAudio / BlackHole）
- [ ] 界面主题切换（深色模式）

---

## 使用与合规提示

- 本工具仅在**本机**处理音频，不会向任何外部服务上传你的音频或文本。
- 抓取的音频内容可能受版权保护。请仅用于**个人学习**等合理使用范畴，  
  并遵守你所在地区的法律法规与相关内容的服务条款。
- 请勿用于任何形式的录音窃听或侵犯他人隐私的场景。

---

## 许可证

[MIT License](LICENSE) © 2026 <your-github-username>

> 打包发布前，记得把 `<your-github-username>` 全局替换为你的 GitHub 用户名  
> （涉及 `README.md`、`README_EN.md`、`LICENSE`、`.github/ISSUE_TEMPLATE/`）。
