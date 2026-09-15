# -*- coding: utf-8 -*-
"""轻量提示气泡：右上角弹出，自动消失（由 ipad_capture_ocr.py 调用）。
用法: python toast_win.py "消息文本" [成功|失败]
"""

import sys
import tkinter as tk


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else "完成"
    kind = sys.argv[2] if len(sys.argv) > 2 else "成功"
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    # 右下角弹出
    w, h = 420, 76
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{sw - w - 24}+{sh - h - 90}")
    bg = "#122b3d" if kind == "成功" else "#3d1613"
    fg = "#38c3e0" if kind == "成功" else "#ff8b7f"
    frame = tk.Frame(root, bg=bg, highlightbackground="#1e3b4f", highlightthickness=1)
    frame.pack(fill="both", expand=True)
    icon = "✓" if kind == "成功" else "✗"
    tk.Label(frame, text=icon, font=("Microsoft YaHei", 22, "bold"),
             bg=bg, fg=fg).pack(side="left", padx=(16, 8), pady=14)
    tk.Label(frame, text=msg, font=("Microsoft YaHei", 12, "bold"),
             bg=bg, fg="#eaf4fa", anchor="w", justify="left").pack(
        side="left", fill="both", expand=True, pady=14)
    # 2.2 秒后自动关闭
    root.after(2200, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
