"""
日语语音识别：支持两种本地引擎，由 config 的 ASR_ENGINE 切换。

  - "qwen3-asr" : 走本地 Ollama 的 Qwen3-ASR 模型（frozenlab/qwen3-asr），
                 准确度高，支持 52 种语言自动检测、自动标点；
                 音频以 16kHz 单声道 WAV 的 base64 经 /api/chat 的 images 字段传入。
  - "whisper"   : 本地 faster-whisper（保留作为回退 / 无需 Ollama 时）。

双引擎对外的接口一致：ready / loading / error / load() / transcribe(audio)。
"""
import base64
import io
import json
import os
import random
import re
import urllib.error
import urllib.request
import wave

import numpy as np

from config import CONFIG

# 国内网络下 huggingface.co 基本不可直连；默认改用 hf-mirror.com 镜像，并禁用 Xet 存储。
# 若用户已显式设置这些环境变量，则尊重用户设置。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

_HERE = os.path.dirname(os.path.abspath(__file__))

# 绕过系统代理的 opener（Ollama 在本机，走代理反而连不上）
_OLLAMA_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _ollama_json(url: str, payload: dict | None = None, timeout: float = 60):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    resp = _OLLAMA_OPENER.open(req, timeout=timeout)
    try:
        return json.loads(resp.read().decode("utf-8", "ignore"))
    finally:
        resp.close()


def float32_to_wav_b64(audio: np.ndarray, sr: int = 16000) -> str:
    """把 float32 归一化音频（[-1,1]）编码为 16kHz 单声道 WAV 的 base64。"""
    a = np.asarray(audio, dtype=np.float32).reshape(-1)
    pcm = (np.clip(a, -1.0, 1.0) * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return base64.b64encode(buf.getvalue()).decode("ascii")


_MOCK_SENTENCES = [
    "今日はとてもいい天気ですね。",
    "これから一緒に映画を見に行きませんか。",
    "日本語の勉強は毎日続けることが大切です。",
    "この本はとても面白くて、一晩で読んでしまいました。",
    "昨日の試験は思ったより難しかったです。",
]


def _strip_lang_prefix(text: str) -> str:
    """Qwen3-ASR 返回会以 'language XXX' 开头（可能紧跟正文或换行），去掉该前缀；
    无语音时还会残留 '<asr_text>' 占位 token，一并清掉。"""
    t = re.sub(r"^language\s+[A-Za-z]+\s*", "", text or "", count=1, flags=re.IGNORECASE)
    t = t.replace("<asr_text>", "").replace("</asr_text>", "")
    return t.strip()


class WhisperASR:
    """本地 faster-whisper 引擎（回退用）。"""

    def __init__(self):
        self.model = None
        self.ready = CONFIG.MOCK
        self.loading = False
        self.error = None

    def _model_path(self) -> str:
        for name in (CONFIG.WHISPER_MODEL, f"faster-whisper-{CONFIG.WHISPER_MODEL}"):
            local = os.path.join(_HERE, "models", name)
            if os.path.isfile(os.path.join(local, "model.bin")):
                return local
        return CONFIG.WHISPER_MODEL

    def _load_model(self, device: str):
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError(
                "缺少可选依赖 faster-whisper（whisper 引擎才需要它）。请执行：\n"
                "    pip install -r requirements-whisper.txt\n"
                "若不想安装，可改用默认的 qwen3-asr 引擎（需要本地 Ollama）。\n"
                f"（原始错误：{e}）"
            ) from e
        return WhisperModel(
            self._model_path(),
            device=device,
            compute_type=CONFIG.WHISPER_COMPUTE_TYPE,
        )

    def load(self):
        if CONFIG.MOCK:
            self.ready = True
            return
        if self.model is not None or self.loading:
            return
        self.loading = True
        self.error = None
        try:
            try:
                self.model = self._load_model(CONFIG.WHISPER_DEVICE)
            except Exception as first_err:
                if CONFIG.WHISPER_DEVICE.lower() == "cpu":
                    raise
                try:
                    self.model = self._load_model("cpu")
                except Exception:
                    raise first_err
            self.ready = True
        except Exception as e:
            self.error = str(e)
        finally:
            self.loading = False

    def transcribe(self, audio: np.ndarray) -> str:
        if CONFIG.MOCK:
            return random.choice(_MOCK_SENTENCES)
        if self.model is None:
            self.load()
            if self.model is None:
                return ""
        if audio is None or len(audio) == 0:
            return ""
        segments, _ = self.model.transcribe(
            audio,
            language="ja",
            beam_size=1,
            condition_on_previous_text=False,
            vad_filter=True,
        )
        return "".join(seg.text for seg in segments).strip()


class Qwen3ASR:
    """本地 Ollama 上的 Qwen3-ASR 引擎（默认，准确度高）。"""

    def __init__(self):
        self.ready = CONFIG.MOCK
        self.loading = False
        self.error = None
        self._model_ok = False

    def _check_model(self) -> bool:
        try:
            data = _ollama_json(f"{CONFIG.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=5)
            models = [m.get("name", "") for m in data.get("models", [])]
            target = CONFIG.ASR_MODEL.split(":")[0]
            return any(m.split(":")[0] == target or m == CONFIG.ASR_MODEL for m in models)
        except Exception:
            return False

    def load(self):
        if CONFIG.MOCK:
            self.ready = True
            return
        self.loading = True
        self.error = None
        try:
            if not self._check_model():
                self.error = (
                    f"Ollama 中未找到 ASR 模型「{CONFIG.ASR_MODEL}」。\n"
                    f"请在终端执行： ollama pull {CONFIG.ASR_MODEL}\n"
                    f"（约 2.5GB，拉取完成后重开本程序即可。）"
                )
                self.ready = False
            else:
                self._model_ok = True
                self.ready = True
        finally:
            self.loading = False

    def transcribe(self, audio: np.ndarray) -> str:
        if CONFIG.MOCK:
            return random.choice(_MOCK_SENTENCES)
        if audio is None or len(audio) == 0:
            return ""
        wav_b64 = float32_to_wav_b64(audio, CONFIG.SAMPLE_RATE)
        payload = {
            "model": CONFIG.ASR_MODEL,
            "stream": False,
            "messages": [{"role": "user", "content": "", "images": [wav_b64]}],
        }
        try:
            data = _ollama_json(
                f"{CONFIG.OLLAMA_BASE_URL.rstrip('/')}/api/chat", payload, timeout=180
            )
            content = (data.get("message") or {}).get("content", "")
            return _strip_lang_prefix(content)
        except Exception as e:
            return f"[识别失败] {e}"


class ASR:
    """按配置选择引擎的工厂。对外接口与单引擎一致。"""

    def __new__(cls):
        if CONFIG.ASR_ENGINE.lower() == "qwen3-asr":
            return Qwen3ASR()
        return WhisperASR()


# 兼容直接 import：暴露默认引擎实例的常用属性名
ASRInstance = ASR
