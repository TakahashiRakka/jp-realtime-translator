"""
系统音频抓取：用 soundcard 库直接做 WASAPI 回环（loopback），
捕获电脑正在播放的声音（浏览器/播放器里的日语视频），
重采样为 16kHz 单声道 PCM 放入队列，供 Whisper 识别。

不依赖 ffmpeg。soundcard 在 Windows 上原生支持“扬声器回环”捕获。
额外维护一个短时的“近期样本”环形缓冲，用于实时音量电平表。
"""
import collections
import queue
import threading

import numpy as np
from config import CONFIG

# numpy 2.x 移除了废弃的 fromstring，而部分 soundcard 版本仍在使用；
# 模块级垫片无害，先打上兜底（ndarray.tostring 无法垫片，由 patch_soundcard.py 处理）。
if not hasattr(np, "fromstring"):
    np.fromstring = lambda buf, dtype=float: np.frombuffer(buf, dtype=dtype)  # type: ignore[attr-defined]

try:
    import soundcard as sc
except ImportError:
    sc = None


def _ensure_sc():
    if sc is None:
        raise RuntimeError(
            "缺少依赖库 soundcard。\n"
            "请在虚拟环境中执行： pip install soundcard"
        )


def list_wasapi_devices():
    """
    列出可用音频设备名（含扬声器回环设备与麦克风）。
    回环设备（=扬声器/耳机，可捕获系统播放声）排在前面。
    """
    _ensure_sc()
    names = []
    try:
        mics = sc.all_microphones(include_loopback=True)
    except Exception as e:
        raise RuntimeError(f"枚举音频设备失败：{e}")
    for m in mics:
        name = m.name or "(未命名设备)"
        names.append((name, bool(getattr(m, "isloopback", False))))

    # 回环优先；同名去重
    seen = set()
    ordered = []
    for name, _lb in sorted(names, key=lambda t: 0 if t[1] else 1):
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _resolve_device(name: str | None):
    """按名称找到设备（优先回环变体）；name 为空则取默认扬声器的回环。"""
    _ensure_sc()
    mics = sc.all_microphones(include_loopback=True)

    if name:
        n = name.strip()
        low = n.lower()
        # 精确匹配（回环优先）→ 模糊匹配（回环优先）
        for m in mics:
            if m.isloopback and (m.name or "").strip() == n:
                return m
        for m in mics:
            if (m.name or "").strip() == n:
                return m
        for m in mics:
            if m.isloopback and low in (m.name or "").lower():
                return m
        for m in mics:
            if low in (m.name or "").lower():
                return m
        raise RuntimeError(
            f"找不到音频设备「{name}」。\n请点“刷新设备”查看/选择可用设备名。"
        )

    # 默认：默认扬声器的回环
    try:
        spk = sc.default_speaker()
        m = sc.get_microphone(spk.id, include_loopback=True)
        if m is not None and m.isloopback:
            return m
    except Exception:
        pass
    # 兜底：任意一个回环设备
    for m in mics:
        if m.isloopback:
            return m
    raise RuntimeError(
        "未找到可用的回环音频设备（扬声器）。\n"
        "请点“刷新设备”后手动选择你的扬声器设备名。"
    )


class AudioCapture:
    def __init__(self, device: str | None = None):
        self.device = device or CONFIG.WASAPI_DEVICE
        self.recorder = None   # soundcard recorder（进入 with 语义后长期持有）
        self.proc = None       # 保留字段：旧接口兼容，无实际用途
        self.queue: "queue.Queue[bytes]" = queue.Queue()
        # 最近 250ms 的样本，用于电平表（不直接消费队列数据）
        self.recent = collections.deque(maxlen=int(0.25 * CONFIG.SAMPLE_RATE))
        self._thread = None
        self._stop = False

    def start(self, loopback: bool | None = None):
        mic = _resolve_device(self.device or None)
        try:
            self.recorder = mic.recorder(
                samplerate=CONFIG.SAMPLE_RATE,
                channels=CONFIG.CHANNELS,
                blocksize=1024,
            )
            self.recorder.__enter__()
        except Exception as e:
            self.recorder = None
            raise RuntimeError(
                f"无法打开音频设备「{mic.name}」：{e}\n"
                "可尝试换一个设备（优先选扬声器/耳机类回环设备）。"
            )
        self._stop = False
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self):
        rec = self.recorder
        if rec is None:
            return
        while not self._stop:
            try:
                # record() 会阻塞直到凑够帧数，不会空转
                data = rec.record(numframes=1024)
            except Exception:
                break
            if data is None or len(data) == 0:
                continue
            arr = np.asarray(data, dtype=np.float32).reshape(-1)
            self.recent.extend(arr)
            pcm16 = (np.clip(arr, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
            self.queue.put(pcm16)

    def drain(self) -> np.ndarray:
        """非阻塞取走当前队列里所有 PCM，返回 float32 归一化音频。"""
        buf = b""
        while True:
            try:
                buf += self.queue.get_nowait()
            except queue.Empty:
                break
        if not buf:
            return np.array([], dtype=np.float32)
        return np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0

    def level(self) -> float:
        """当前音量 RMS（0~1 量级），用于电平表。"""
        if not self.recent:
            return 0.0
        a = np.array(self.recent, dtype=np.float32)
        return float(np.sqrt(np.mean(a * a)))

    def stop(self):
        self._stop = True
        rec = self.recorder
        self.recorder = None
        if rec is not None:
            try:
                rec.__exit__(None, None, None)
            except Exception:
                pass
