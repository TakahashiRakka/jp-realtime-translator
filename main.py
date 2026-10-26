"""
主程序：tkinter 三栏界面
  - 左：日语原文（上） / 中文翻译（下），实时追加字幕
  - 右：语法解析（当前句的逐词拆解树）

流程（多线程，准实时按句分段，不重叠以避免重复字幕）：
  音频回环抓取 -> 累积到固定长度 -> Whisper 识别日语
  -> Qwen3 翻译（+ 可选语法解析）-> 更新界面

改进点：配置持久化(settings)、实时音量电平表、语法自动/按需、字幕导出、
Ollama 连通性自检、设备可手填/刷新、模型后台加载状态。
"""
import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import numpy as np

from audio_capture import AudioCapture, list_wasapi_devices
from asr import ASR
from config import CONFIG
from translator import Translator

# 语法解析表格的列定义
COLUMNS = [
    ("surface", "原词", 120),
    ("reading", "读音", 100),
    ("pos", "词性", 80),
    ("meaning", "意思", 160),
    ("grammar", "语法说明", 280),
]

# 设置面板字段 (key, 标签, 占位)
SETTINGS_FIELDS = [
    ("ASR_ENGINE", "ASR 引擎 (qwen3-asr/whisper)", "qwen3-asr"),
    ("ASR_MODEL", "Qwen3-ASR 模型名", "frozenlab/qwen3-asr:1.7b"),
    ("WHISPER_MODEL", "Whisper 模型", "small"),
    ("WHISPER_DEVICE", "Whisper 设备 (cpu/cuda)", "cpu"),
    ("CHUNK_SECONDS", "分段秒数", "4"),
    ("OLLAMA_BASE_URL", "Ollama 地址", "http://localhost:11434"),
    ("QWEN_MODEL", "Qwen 模型名", "qwen3:14b"),
    ("EXPORT_DIR", "导出目录(可选)", ""),
]


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.running = False
        self.thread: threading.Thread | None = None
        self.capture: AudioCapture | None = None
        self.asr = ASR()
        self.translator = Translator()
        self.entries = []            # 字幕历史: {ts, ja, zh, tokens}
        self.last_ja = ""
        self.ollama_ok: bool | None = None

        self._build_ui()
        self.update_status()
        self.root.after(100, self._tick)   # 启动电平表轮询

    # ---------------- UI 构建 ----------------
    def _build_ui(self):
        self.root.title("日语实时转写 · 翻译 · 语法解析  (本地 Qwen3 + Whisper)")
        self.root.geometry("1200x760")

        # 工具栏（第一行：控制）
        bar = ttk.Frame(self.root)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=6)
        self.start_btn = ttk.Button(bar, text="▶ 开始", command=self.start)
        self.start_btn.pack(side="left", padx=(0, 4))
        self.stop_btn = ttk.Button(bar, text="■ 停止", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="解析末句语法", command=self.parse_last).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="导出", command=self.export).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="清除", command=self.clear).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="设置", command=self.open_settings).pack(side="left", padx=(0, 4))

        # 设备选择
        ttk.Label(bar, text="音频设备:").pack(side="left", padx=(8, 2))
        self.device_var = tk.StringVar(value=CONFIG.WASAPI_DEVICE)
        self.device_combo = ttk.Combobox(bar, textvariable=self.device_var, width=34, state="normal")
        self._refresh_devices()
        self.device_combo.pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="刷新设备", command=self._refresh_devices).pack(side="left", padx=(0, 4))

        # 模式开关
        self.mock_var = tk.BooleanVar(value=CONFIG.MOCK)
        ttk.Checkbutton(bar, text="模拟模式(不调用模型)", variable=self.mock_var,
                        command=lambda: self._set_config(MOCK=self.mock_var.get())).pack(side="left", padx=6)
        self.auto_var = tk.BooleanVar(value=CONFIG.AUTO_GRAMMAR)
        ttk.Checkbutton(bar, text="自动语法解析", variable=self.auto_var,
                        command=lambda: self._set_config(AUTO_GRAMMAR=self.auto_var.get())).pack(side="left", padx=6)

        # 第二行：电平表 + 状态
        status_bar = ttk.Frame(self.root)
        status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 4))
        ttk.Label(status_bar, text="输入电平:").pack(side="left")
        self.meter = ttk.Progressbar(status_bar, orient="horizontal", length=200, maximum=100, mode="determinate")
        self.meter.pack(side="left", padx=(4, 10))
        self.status_var = tk.StringVar(value="待机")
        self.status_label = ttk.Label(status_bar, textvariable=self.status_var, foreground="#1f8a4c")
        self.status_label.pack(side="left")

        # 左栏：日语原文 + 中文翻译
        left = ttk.Frame(self.root)
        left.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        left.rowconfigure(1, weight=1)
        left.rowconfigure(3, weight=1)
        left.columnconfigure(0, weight=1)

        ttk.Label(left, text="日语原文（识别结果）", font=("", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.ja_box = scrolledtext.ScrolledText(left, wrap=tk.WORD, font=("", 11))
        self.ja_box.grid(row=1, column=0, sticky="nsew")

        ttk.Label(left, text="中文翻译", font=("", 11, "bold")).grid(row=2, column=0, sticky="w", pady=(6, 2))
        self.zh_box = scrolledtext.ScrolledText(left, wrap=tk.WORD, font=("", 11))
        self.zh_box.grid(row=3, column=0, sticky="nsew")

        # 右栏：语法解析
        right = ttk.Frame(self.root)
        right.grid(row=2, column=1, sticky="nsew", padx=8, pady=4)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="语法解析（当前句逐词拆解）", font=("", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.tree = ttk.Treeview(right, columns=[c[0] for c in COLUMNS], show="headings")
        for key, label, width in COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        vsb = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")

        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=1)

    def _refresh_devices(self):
        try:
            devs = list_wasapi_devices()
        except Exception as e:
            messagebox.showwarning("枚举设备失败", str(e))
            return
        self.device_combo["values"] = devs
        if not self.device_var.get() and devs:
            self.device_var.set(devs[0])

    def _set_config(self, **kwargs):
        CONFIG.update(**kwargs)
        self.update_status()

    # ---------------- 状态 ----------------
    def update_status(self):
        parts = ["● 录音中" if self.running else "待机"]
        if self.asr.loading:
            parts.append("语音模型加载中…")
        elif self.asr.ready:
            parts.append("ASR就绪")
        elif self.asr.error:
            parts.append("ASR加载失败!")
        if self.ollama_ok is True:
            parts.append("Qwen已连接")
        elif self.ollama_ok is False:
            parts.append("Qwen未连接!")
        self.status_var.set("   |   ".join(parts))
        # 错误用红色提示
        if self.asr.error:
            self.status_label.configure(foreground="#d33")
        else:
            self.status_label.configure(foreground="#3a8")

    def _tick(self):
        """电平表轮询 + 状态刷新（主线程定时器）。"""
        if self.running and self.capture is not None and self.capture.recorder is not None:
            lvl = self.capture.level()
            self.meter["value"] = min(100, int(lvl * 800))
        else:
            self.meter["value"] = 0
        self.root.after(100, self._tick)

    # ---------------- 控制 ----------------
    def start(self):
        if self.running:
            return
        device = self.device_var.get().strip()
        self.capture = AudioCapture(device=device)
        try:
            self.capture.start()
        except Exception as e:
            messagebox.showerror("启动失败", str(e))
            return

        # 运行时参数即时生效；Whisper 模型变更会在下面重新实例化时生效
        CONFIG.update(AUTO_GRAMMAR=self.auto_var.get(), MOCK=self.mock_var.get())
        self.asr = ASR()
        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.device_combo.configure(state="disabled")
        self.update_status()

        # 后台：加载语音模型 + 检查 Ollama
        threading.Thread(target=self._load_asr, daemon=True).start()
        threading.Thread(target=self._check_ollama, daemon=True).start()

        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.capture:
            self.capture.stop()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.device_combo.configure(state="normal")
        self.update_status()

    def clear(self):
        self.entries = []
        self.last_ja = ""
        self.ja_box.delete("1.0", tk.END)
        self.zh_box.delete("1.0", tk.END)
        self._fill_tree([])

    def _load_asr(self):
        self.asr.load()
        if self.asr.error:
            err = self.asr.error
            def show_err():
                self.ja_box.insert(tk.END, f"[语音模型加载失败] {err}\n"
                                           "已自动回退 cpu 仍失败。请检查网络（模型下载走 hf-mirror.com）"
                                           "或在设置里把 Whisper 模型改小（如 tiny/base）。\n\n")
            self.root.after(0, show_err)
        self.root.after(0, self.update_status)

    def _check_ollama(self):
        self.ollama_ok = self.translator.is_healthy()
        self.root.after(0, self.update_status)

    # ---------------- 主循环 ----------------
    def _loop(self):
        acc = np.array([], dtype=np.float32)
        chunk_samples = int(CONFIG.CHUNK_SECONDS * CONFIG.SAMPLE_RATE)
        while self.running:
            time.sleep(0.05)
            if not self.asr.ready:
                continue
            new = self.capture.drain()
            if new is not None and len(new):
                acc = np.concatenate([acc, new]) if len(acc) else new
            if len(acc) >= chunk_samples:
                segment = acc[:chunk_samples]
                acc = acc[chunk_samples:]   # 余下部分留到下次，避免重叠重复
                self._process(segment)

    def _process(self, segment):
        ja = self.asr.transcribe(segment)
        if not ja:
            return

        if CONFIG.AUTO_GRAMMAR:
            res = self.translator.analyze(ja)
            zh = res.get("translation", "")
            tokens = res.get("tokens", [])
        else:
            zh = self.translator.translate(ja)
            tokens = []

        entry = {"ts": time.strftime("%H:%M:%S"), "ja": ja, "zh": zh, "tokens": tokens}
        self.entries.append(entry)
        self.last_ja = ja
        self.root.after(0, self._update_ui, entry)

    def parse_last(self):
        if not self.last_ja:
            messagebox.showinfo("提示", "还没有可解析的句子，请先开始并播放音频。")
            return

        def work():
            res = self.translator.analyze(self.last_ja)
            if self.entries:
                self.entries[-1]["tokens"] = res.get("tokens", [])
            self.root.after(0, self._fill_tree, res.get("tokens", []))
            self.root.after(0, lambda: self.update_status())

        self.update_status()
        threading.Thread(target=work, daemon=True).start()

    # ---------------- UI 更新 ----------------
    def _update_ui(self, entry):
        self.ja_box.insert(tk.END, f"[{entry['ts']}] {entry['ja']}\n")
        self.ja_box.see(tk.END)
        self.zh_box.insert(tk.END, f"[{entry['ts']}] {entry['zh']}\n")
        self.zh_box.see(tk.END)
        self._fill_tree(entry["tokens"])

    def _fill_tree(self, tokens):
        for child in self.tree.get_children():
            self.tree.delete(child)
        if not tokens:
            self.tree.insert("", tk.END, values=("（未解析语法：关闭了自动解析，或点“解析末句语法”）", "", "", "", ""))
            return
        for t in tokens:
            self.tree.insert("", tk.END, values=(
                t.get("surface", ""), t.get("reading", ""), t.get("pos", ""),
                t.get("meaning", ""), t.get("grammar", ""),
            ))

    # ---------------- 设置面板 ----------------
    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.geometry("420x320")
        win.transient(self.root)
        win.grab_set()

        vars_ = {}
        for i, (key, label, placeholder) in enumerate(SETTINGS_FIELDS):
            ttk.Label(win, text=label).grid(row=i, column=0, sticky="w", padx=10, pady=6)
            v = tk.StringVar(value=str(getattr(CONFIG, key)))
            e = ttk.Entry(win, textvariable=v, width=34)
            e.grid(row=i, column=1, padx=10, pady=6)
            vars_[key] = (v, placeholder)

        def save():
            updates = {}
            for key, (v, _) in vars_.items():
                val = v.get().strip()
                if key == "CHUNK_SECONDS":
                    try:
                        updates[key] = max(1.0, float(val))
                    except ValueError:
                        messagebox.showerror("错误", "分段秒数必须是数字")
                        return
                else:
                    updates[key] = val
            CONFIG.update(**updates)
            self._refresh_devices()
            self.update_status()
            win.destroy()
            messagebox.showinfo("已保存", "设置已写入 config.json，部分项将在下次“开始”时生效。")

        ttk.Button(win, text="保存", command=save).grid(row=len(SETTINGS_FIELDS), column=0, pady=12, padx=10)
        ttk.Button(win, text="取消", command=win.destroy).grid(row=len(SETTINGS_FIELDS), column=1, pady=12)

    # ---------------- 导出 ----------------
    def export(self):
        if not self.entries:
            messagebox.showinfo("提示", "暂无可导出的内容。")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            initialdir=CONFIG.EXPORT_DIR or None,
            filetypes=[("Markdown", "*.md"), ("SRT 字幕", "*.srt"), ("纯文本", "*.txt")],
        )
        if not path:
            return
        try:
            ext = path.rsplit(".", 1)[-1].lower()
            if ext == "srt":
                content = self._to_srt()
            elif ext == "txt":
                content = self._to_txt()
            else:
                content = self._to_md()
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            CONFIG.update(EXPORT_DIR=os.path.dirname(path))
            messagebox.showinfo("已导出", f"已保存到：\n{path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _to_txt(self):
        lines = []
        for e in self.entries:
            lines.append(f"[{e['ts']}] {e['ja']}")
            lines.append(f"[{e['ts']}] {e['zh']}")
            lines.append("")
        return "\n".join(lines)

    def _to_srt(self):
        lines = []
        for i, e in enumerate(self.entries, 1):
            start = e["ts"]
            # 结束时间用下一条的时间，最后一条加 4 秒
            if i < len(self.entries):
                end = self.entries[i]["ts"]
            else:
                end = self._add_sec(start, int(CONFIG.CHUNK_SECONDS))
            lines.append(str(i))
            lines.append(f"{self._srt_time(start)} --> {self._srt_time(end)}")
            lines.append(e["ja"])
            lines.append(e["zh"])
            lines.append("")
        return "\n".join(lines)

    def _to_md(self):
        lines = ["# 日语实时转写 · 翻译 · 语法解析", ""]
        for e in self.entries:
            lines.append(f"## [{e['ts']}] {e['ja']}")
            lines.append(f"**翻译**：{e['zh']}")
            if e["tokens"]:
                lines.append("")
                lines.append("| 原词 | 读音 | 词性 | 意思 | 语法说明 |")
                lines.append("| --- | --- | --- | --- | --- |")
                for t in e["tokens"]:
                    cells = [str(t.get(k, "")) for k in ("surface", "reading", "pos", "meaning", "grammar")]
                    cells = [c.replace("|", "\\|") for c in cells]
                    lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _srt_time(hms: str) -> str:
        try:
            h, m, s = (int(x) for x in hms.split(":"))
        except Exception:
            return "00:00:00,000"
        return f"{h:02d}:{m:02d}:{s:02d},000"

    @staticmethod
    def _add_sec(hms: str, sec: int) -> str:
        try:
            h, m, s = (int(x) for x in hms.split(":"))
        except Exception:
            return hms
        tot = h * 3600 + m * 60 + s + sec
        return f"{tot // 3600:02d}:{(tot % 3600) // 60:02d}:{tot % 60:02d}"


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
