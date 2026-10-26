# Japanese Realtime Transcriber · Translator · Grammar Parser

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows)](https://www.microsoft.com/windows)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/TakahashiRakka/jp-realtime-translator/actions/workflows/ci.yml/badge.svg)](https://github.com/TakahashiRakka/jp-realtime-translator/actions/workflows/ci.yml)

> Japanese audio playing on your PC → live Chinese translation + per-word grammar breakdown.
> No virtual audio cable, no ffmpeg, and your audio never leaves your machine.

[中文文档](README.md) · [FAQ](README.md#常见问题-faq) · [Contributing](CONTRIBUTING.md)

---

## What it does

Watch a Japanese drama, a livestream, or play a game — and get subtitles in real time.

| Feature | Description |
| --- | --- |
| 🎧 System audio capture | WASAPI loopback captures whatever your speakers are playing. No virtual sound card, no ffmpeg. |
| 🗣️ Japanese ASR | Local Qwen3-ASR via Ollama (auto punctuation, auto segmentation); faster-whisper as an offline fallback |
| 🌏 Chinese translation | Local Qwen3 model, natural-sounding output |
| 📚 Per-word grammar parsing | Surface / reading / part of speech / meaning / grammar note for every token |
| 📊 Live input meter | Instantly see whether audio is actually being captured |
| 💾 Subtitle export | One-click Markdown / SRT / TXT; SRT drops straight into your video player |
| 🔒 Fully local | Audio and text never leave your computer |

---

## Quick start

### 0. Requirements

| Item | Requirement |
| --- | --- |
| OS | Windows 10 / 11 (WASAPI loopback; macOS and Linux are not supported yet) |
| Python | 3.10+, with **Add python.exe to PATH** checked at install time |
| Ollama | Install from [ollama.com](https://ollama.com) — runs the ASR and translation models |
| Hardware (recommended) | 16 GB RAM; an NVIDIA GPU helps a lot |

### 1. Pull the models

```bash
ollama pull frozenlab/qwen3-asr:1.7b   # speech recognition (default engine, required)
ollama pull qwen3:14b                  # translation + grammar parsing (required)
```

> Less than 16 GB RAM? Use a smaller translation model: `ollama pull qwen3:8b`,
> then set `Qwen 模型名` to `qwen3:8b` in the app's Settings dialog.

### 2. Run it

```bash
git clone https://github.com/TakahashiRakka/jp-realtime-translator.git
cd jp-realtime-translator
```

**Option A (recommended): double-click `run.bat`.**
It creates `.venv`, installs dependencies, applies the soundcard compatibility patch, and launches the GUI.
It also falls back to the Tsinghua PyPI mirror automatically if the official index fails.

**Option B: manual setup**

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python patch_soundcard.py      # fixes soundcard × numpy 2.x (idempotent)
python main.py
```

### 3. Use it

1. Pick your **speakers / headphones** in the device dropdown (loopback devices are listed first). Hit "刷新设备" if unsure.
2. Play some Japanese audio.
3. Click **▶ 开始** and watch the input meter — if it moves, audio is being captured.
4. Enable "自动语法解析" for a grammar table on every line, or leave it off and click "解析末句语法" on demand (much lighter on resources).

> Want to see the UI first? Tick **模拟模式** — no model is loaded at all.

---

## Configuration

A `config.json` is created next to `main.py` on first run (git-ignored). You can also edit it
from the in-app Settings dialog. Priority: **environment variable > config.json > default**.

| Key | Default | Description |
| --- | --- | --- |
| `ASR_ENGINE` | `qwen3-asr` | `qwen3-asr` (default) or `whisper` |
| `ASR_MODEL` | `frozenlab/qwen3-asr:1.7b` | Ollama model name for Qwen3-ASR |
| `WHISPER_MODEL` | `small` | tiny / base / small / medium / large-v3 |
| `WHISPER_DEVICE` | `cpu` | `cpu` or `cuda` |
| `WHISPER_COMPUTE_TYPE` | `int8` | int8 / int8_float16 / float16 |
| `CHUNK_SECONDS` | `4.0` | Seconds per recognition segment |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `QWEN_MODEL` | `qwen3:14b` | Translation + grammar model |
| `QWEN_TEMPERATURE` | `0.3` | Lower = more deterministic |
| `QWEN_DISABLE_THINKING` | `true` | Disable Qwen3's thinking trace (faster, cleaner) |
| `AUTO_GRAMMAR` | `false` | Parse grammar for every sentence automatically |
| `WASAPI_DEVICE` | `""` | Device name; empty = default speaker loopback |
| `MOCK` | `false` | Mock mode — no model calls at all |
| `EXPORT_DIR` | `""` | Default export directory |

Every key can be overridden by an environment variable of the same name:

```bash
set CHUNK_SECONDS=3
set QWEN_MODEL=qwen3:8b
python main.py
```

---

## Choosing an ASR engine

| | Qwen3-ASR (default) | faster-whisper |
| --- | --- | --- |
| Runs in | Local Ollama | Local Python process |
| Needs Ollama | ✅ Yes | ❌ No |
| Japanese accuracy | Higher, auto punctuation | Decent; long sentences may break |
| Language detection | 52 languages, automatic | Manual (`ja`) |
| Extra dependency | None beyond `soundcard` + `numpy` | `faster-whisper` (large) |

Switch by setting `ASR 引擎` to `whisper` in Settings, then install the optional dependency:

```bash
pip install -r requirements-whisper.txt
```

---

## How it works

```
System audio ──WASAPI loopback──▶ AudioCapture ──16 kHz mono──▶ (chunk every N seconds, non-overlapping)
                                                                        │
                                                                        ▼
                                                                       ASR ──▶ Japanese text
                                                                        │
                                                                        ▼
                                                                   Translator (local Qwen3)
                                                                        │
                                                    ┌───────────────────┴───────────────────┐
                                                    ▼                                       ▼
                                          Chinese translation                    Per-word grammar table
                                                    │
                                                    ▼
                                            Export md / srt / txt
```

Capture, recognition, and translation each run on their own thread, so the UI stays responsive.
Requests to Ollama explicitly **bypass the system proxy** so that `localhost:11434` isn't hijacked.

---

## Project layout

```
jp-realtime-translator/
├── main.py                   # tkinter UI, main loop, export
├── audio_capture.py          # WASAPI loopback capture, device enumeration, level meter
├── asr.py                    # Dual ASR engines (Qwen3-ASR / faster-whisper)
├── translator.py             # Qwen3 translation + structured grammar parsing
├── config.py                 # Config loading (env > config.json > defaults)
├── config.example.json       # Config template
├── patch_soundcard.py        # soundcard × numpy 2.x patch (idempotent)
├── run.bat                   # One-click launcher
├── requirements.txt          # Core dependencies
├── requirements-whisper.txt  # Optional dependency for the whisper engine
└── tests/smoke_test.py       # Smoke test (mock mode, no model or network needed)
```

---

## FAQ

**The input meter doesn't move / nothing is transcribed.**
Check the device — you need a **speaker/headphone loopback device** (listed first in the dropdown).
Also make sure audio is actually playing through that output. Try "刷新设备" to re-enumerate.

**"No available loopback audio device."**
Some Bluetooth headsets and HDMI outputs don't expose a loopback channel. Use wired speakers or the onboard audio output.

**"Qwen 未连接" even though Ollama is running.**
Usually a proxy hijacking local requests. The app already bypasses proxies, but also check that
<http://localhost:11434> opens in your browser, and add `localhost` to your proxy's bypass list.

**"ASR model not found in Ollama."**
Run `ollama pull frozenlab/qwen3-asr:1.7b` and restart the app.

**Too much latency?**
In order: ① lower `CHUNK_SECONDS` to 2–3; ② switch the translation model to `qwen3:8b`;
③ turn off "自动语法解析" (grammar parsing is far slower than plain translation); ④ set the whisper device to `cuda` if you have an NVIDIA GPU.

**Slow or failing model downloads.**
HuggingFace is redirected to the `hf-mirror.com` mirror and Xet storage is disabled by default.
If it still fails, set `HF_ENDPOINT=https://hf-mirror.com` manually and retry.

**Should I commit `models/`?**
No — it holds runtime-downloaded weights (~460 MB) and is git-ignored.

**Can I translate microphone input (games, meetings)?**
Yes. Just pick the corresponding **microphone** in the device dropdown.

---

## Roadmap

- [ ] Speaker diarization
- [ ] Pronunciation scoring / shadowing
- [ ] Vocabulary book with Anki card export
- [ ] Session history search and replay
- [ ] macOS / Linux support (PulseAudio / BlackHole)
- [ ] Dark mode

---

## Legal and privacy

- All processing happens **locally**. No audio or text is uploaded anywhere.
- Captured audio may be copyrighted. Use it only for **personal learning** within fair-use bounds,
  and comply with the laws in your jurisdiction and the terms of the content you're playing.
- Do not use this tool for covert recording or anything that violates others' privacy.

---

## License

[MIT License](LICENSE) © 2026 TakahashiRakka
