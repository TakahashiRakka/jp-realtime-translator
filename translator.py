"""
翻译 + 语法解析：调用本地 Ollama 上运行的 Qwen3（默认 qwen3:14b）。

提供两条路径：
  - translate() : 只做中文翻译，输出纯文本，最快（自动语法关闭时使用）
  - analyze()   : 输出结构化 JSON（翻译 + 逐词语法拆解），用于语法面板

使用标准库 urllib 调用（不依赖 requests），并显式绕过系统代理，
避免本机代理软件把 localhost:11434 的请求劫持导致连不上 Ollama。
内置重试、连通性自检与容错解析。
"""
import json
import re
import urllib.error
import urllib.request

from config import CONFIG

_TRANSLATE_PROMPT = (
    "你是一位日语翻译。请将下面的日语句子翻译成中文，只输出中文译文，"
    "不要任何解释、序号或多余文字：\n{sentence}"
)

_GRAMMAR_PROMPT = """你是一位精通日语的语言学家与翻译专家。请将下面的日语句子翻译成中文，并对每个词条做语法解析。

要求：
1. 给出整句自然、通顺的中文翻译。
2. 将句子按“词义 + 语法功能”拆解为词条（助词尽量与其依附的词合并，除非孤立更有教学意义），对每个词条给出：
   - surface : 原词（汉字/假名）
   - reading : 读音（平假名）
   - pos     : 词性（名词/动词/形容词/助动词/助词/副词/接续词/感叹词/前缀/后缀等）
   - meaning : 中文意思
   - grammar : 语法点说明（如：～ている 表进行中；は 提示主题；て形 连接；过去式 た 等），没有则填空字符串 ""
3. 严格只输出如下 JSON，不要包含 ``` 标记，不要任何解释或多余文字：
{{
  "translation": "整句中文翻译",
  "tokens": [
    {{"surface":"","reading":"","pos":"","meaning":"","grammar":""}}
  ]
}}

日语句子：
{sentence}
"""

# 绕过系统代理的 opener（Ollama 在本机，走代理反而连不上）
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _http_json(url: str, payload: dict | None = None, timeout: float = 180):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"})
    resp = _OPENER.open(req, timeout=timeout)
    try:
        return json.loads(resp.read().decode("utf-8", "ignore"))
    finally:
        resp.close()


class Translator:
    def __init__(self):
        self.base = CONFIG.OLLAMA_BASE_URL.rstrip("/")
        self.model = CONFIG.QWEN_MODEL

    def is_healthy(self) -> bool:
        """检查 Ollama 是否在线且目标模型已拉取。"""
        if CONFIG.MOCK:
            return True
        try:
            data = _http_json(f"{self.base}/api/tags", timeout=5)
            models = [m.get("name", "") for m in data.get("models", [])]
            target = self.model.split(":")[0]
            return any(m.split(":")[0] == target or m == self.model for m in models)
        except Exception:
            return False

    def _generate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": CONFIG.QWEN_TEMPERATURE},
        }
        if CONFIG.QWEN_DISABLE_THINKING:
            payload["think"] = False

        last_err = None
        for _ in range(2):  # 失败重试一次
            try:
                data = _http_json(f"{self.base}/api/generate", payload, timeout=180)
                return data.get("response", "")
            except (urllib.error.URLError, OSError, ValueError) as e:
                last_err = e
        raise last_err

    def translate(self, sentence: str) -> str:
        if CONFIG.MOCK:
            return "（模拟翻译）" + sentence
        try:
            return self._generate(_TRANSLATE_PROMPT.format(sentence=sentence)).strip()
        except Exception as e:
            return f"[翻译失败] {e}"

    def analyze(self, sentence: str) -> dict:
        if CONFIG.MOCK:
            return {
                "translation": "（模拟翻译）" + sentence,
                "tokens": [{"surface": sentence, "reading": "れい", "pos": "示例",
                            "meaning": "（模拟词条，用于测试 UI）", "grammar": ""}],
            }
        try:
            raw = self._generate(_GRAMMAR_PROMPT.format(sentence=sentence))
        except Exception as e:
            return {"translation": f"[解析失败] {e}", "tokens": []}
        return self._parse(raw)

    @staticmethod
    def _parse(text: str) -> dict:
        try:
            # 容忍模型在 JSON 前后夹带少量文字，抓取第一个 {...}
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                if isinstance(data, dict) and "translation" in data:
                    data.setdefault("tokens", [])
                    return data
        except Exception:
            pass
        return {"translation": text.strip(), "tokens": []}
