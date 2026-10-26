"""冒烟测试：在模拟模式（MOCK=1）下验证核心链路不报错。

特点：不需要 Ollama、不需要模型权重、不需要音频设备、不需要网络。
因此既能在 CI 上跑，也能在本地随时跑：

    python tests/smoke_test.py
"""
import os
import sys

# 允许直接以 `python tests/smoke_test.py` 运行：把项目根目录加入模块搜索路径
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# 必须在导入 config 之前设置 —— Config 在模块导入时就会读取环境变量
os.environ["MOCK"] = "1"

import base64  # noqa: E402
import numpy as np  # noqa: E402

from asr import ASR, float32_to_wav_b64  # noqa: E402
from config import CONFIG  # noqa: E402
from translator import Translator  # noqa: E402

_SENTENCE = "今日はとてもいい天気ですね。"
_TOKEN_FIELDS = ("surface", "reading", "pos", "meaning", "grammar")


def _check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_mock_enabled():
    _check(CONFIG.MOCK is True, "MOCK 未生效：config 没有正确读取环境变量")


def test_asr():
    engine = ASR()
    engine.load()
    _check(engine.ready, "模拟模式下 ASR 应处于就绪状态")
    audio = np.zeros(CONFIG.SAMPLE_RATE, dtype=np.float32)
    text = engine.transcribe(audio)
    _check(bool(text), "模拟模式下 ASR 应返回非空文本")
    _check(not text.startswith("[识别失败]"), f"ASR 返回了错误：{text}")


def test_translate():
    zh = Translator().translate(_SENTENCE)
    _check(bool(zh), "翻译结果不应为空")
    _check(not zh.startswith("[翻译失败]"), f"翻译返回了错误：{zh}")


def test_analyze():
    res = Translator().analyze(_SENTENCE)
    _check(isinstance(res, dict), "analyze 应返回 dict")
    _check(bool(res.get("translation")), "解析结果应包含 translation")
    _check(bool(res.get("tokens")), "解析结果应包含 tokens")
    for tok in res["tokens"]:
        for key in _TOKEN_FIELDS:
            _check(key in tok, f"词条缺少字段 {key}：{tok}")


def test_wav_encoding():
    raw = base64.b64decode(float32_to_wav_b64(np.zeros(1600, dtype=np.float32), 16000))
    _check(raw[:4] == b"RIFF", "WAV 头部应为 RIFF")
    _check(raw[8:12] == b"WAVE", "WAV 头部应为 WAVE")


def main():
    tests = [
        test_mock_enabled,
        test_asr,
        test_translate,
        test_analyze,
        test_wav_encoding,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as exc:                      # noqa: BLE001
            failed += 1
            print(f"  FAIL  {test.__name__}: {exc}")
        else:
            print(f"  PASS  {test.__name__}")

    print()
    if failed:
        print(f"{failed}/{len(tests)} 项失败")
        return 1
    print(f"全部 {len(tests)} 项冒烟测试通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
