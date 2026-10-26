"""
SoundCard 0.4.x 与 numpy>=2 的兼容补丁。

SoundCard 的 Windows 后端 (mediafoundation.py) 使用了 numpy 2.x 已移除的
`numpy.fromstring` 与 `ndarray.tostring`，导致录音/播放直接报错。
本脚本把这两处替换为等价的 `numpy.frombuffer` / `ndarray.tobytes`。

用法：安装依赖后运行一次（run.bat 已自动调用）：
    python patch_soundcard.py
幂等：已是新写法时不会有任何改动。
"""
import os
import re
import sys


def patch() -> int:
    try:
        import soundcard  # noqa: F401
    except ImportError:
        print("[patch_soundcard] 未安装 soundcard，跳过补丁。")
        return 0

    path = os.path.join(os.path.dirname(soundcard.__file__), "mediafoundation.py")
    if not os.path.exists(path):
        print(f"[patch_soundcard] 找不到 {path}，跳过。")
        return 0

    with open(path, encoding="utf-8") as f:
        src = f.read()

    new = src
    new = new.replace(
        "numpy.fromstring(_ffi.buffer(data_ptr, nframes*4*len(set(self.channelmap))), dtype='float32')",
        "numpy.frombuffer(_ffi.buffer(data_ptr, nframes*4*len(set(self.channelmap))), dtype='float32')",
    )
    new = re.sub(r"\.tostring\(\)", ".tobytes()", new)

    if new == src:
        print("[patch_soundcard] 无需修补（已是兼容写法）。")
        return 0

    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"[patch_soundcard] 已修补 numpy 2.x 兼容问题: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(patch())
