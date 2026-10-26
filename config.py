"""
全局配置。
优先级：环境变量 > config.json > 默认值。
修改设置后会写入 config.json，下次启动自动生效；部分项（Ollama 地址/模型、自动语法）可运行时即时生效。
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_HERE, "config.json")

_DEFAULTS = {
    "WHISPER_MODEL": "small",          # tiny/base/small/medium/large-v3
    "WHISPER_DEVICE": "cpu",           # cpu 或 cuda
    "WHISPER_COMPUTE_TYPE": "int8",    # int8 / int8_float16 / float16
    "ASR_ENGINE": "qwen3-asr",         # qwen3-asr（Ollama 本地模型，准度高）| whisper（faster-whisper 本地）
    "ASR_MODEL": "frozenlab/qwen3-asr:1.7b",  # qwen3-asr 的 Ollama 模型名（需先 ollama pull）
    "SAMPLE_RATE": 16000,
    "CHANNELS": 1,
    "CHUNK_SECONDS": 4.0,              # 每段识别的音频长度（秒）
    "OVERLAP_SECONDS": 0.0,            # 预留：段间重叠（当前采用不重叠，避免重复字幕）
    "WASAPI_DEVICE": "",               # 留空=自动挑选扬声器
    "LOOPBACK": True,                  # True=以 WASAPI 回环方式捕获“系统正在播放”的声音（扬声器）
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "QWEN_MODEL": "qwen3:14b",         # 本地 ollama pull 的模型名
    "QWEN_TEMPERATURE": 0.3,
    "QWEN_DISABLE_THINKING": True,     # 关闭 Qwen3 思考链，更快更干净
    "AUTO_GRAMMAR": True,              # True=每句自动解析语法；False=仅翻译，按需手动解析
    "MOCK": False,                     # True=不调用任何模型，返回假数据（测试 UI）
    "EXPORT_DIR": "",                  # 导出默认目录（留空=上次位置/文档）
}

_ENV_MAP = {
    "WHISPER_MODEL": "WHISPER_MODEL",
    "WHISPER_DEVICE": "WHISPER_DEVICE",
    "WHISPER_COMPUTE_TYPE": "WHISPER_COMPUTE_TYPE",
    "ASR_ENGINE": "ASR_ENGINE",
    "ASR_MODEL": "ASR_MODEL",
    "CHUNK_SECONDS": "CHUNK_SECONDS",
    "OVERLAP_SECONDS": "OVERLAP_SECONDS",
    "WASAPI_DEVICE": "WASAPI_DEVICE",
    "LOOPBACK": "LOOPBACK",
    "OLLAMA_BASE_URL": "OLLAMA_BASE_URL",
    "QWEN_MODEL": "QWEN_MODEL",
    "QWEN_TEMPERATURE": "QWEN_TEMPERATURE",
    "QWEN_DISABLE_THINKING": "QWEN_DISABLE_THINKING",
    "AUTO_GRAMMAR": "AUTO_GRAMMAR",
    "MOCK": "MOCK",
    "EXPORT_DIR": "EXPORT_DIR",
}


class Config:
    def __init__(self):
        self._data = dict(_DEFAULTS)
        self._load_file()
        self._apply_env()
        for k, v in self._data.items():
            setattr(self, k, v)

    def _load_file(self):
        if os.path.exists(_CONFIG_PATH):
            try:
                with open(_CONFIG_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                self._data.update({k: v for k, v in data.items() if k in _DEFAULTS})
            except Exception:
                pass

    def _apply_env(self):
        for key, env in _ENV_MAP.items():
            val = os.getenv(env)
            if val is None:
                continue
            cur = _DEFAULTS[key]
            if isinstance(cur, bool):
                self._data[key] = val.strip().lower() in ("1", "true", "yes", "on")
            elif isinstance(cur, float):
                try:
                    self._data[key] = float(val)
                except ValueError:
                    pass
            else:
                self._data[key] = val

    def save(self):
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def update(self, **kwargs):
        changed = False
        for k, v in kwargs.items():
            if k in _DEFAULTS and self._data.get(k) != v:
                self._data[k] = v
                setattr(self, k, v)
                changed = True
        if changed:
            self.save()
        return changed


CONFIG = Config()
