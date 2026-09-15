# -*- coding: utf-8 -*-
"""屏幕截图工具：按【空格】截图，按【Esc】退出。

用法：
    python screen_capture.py               # 截全屏（多显示器）
    python screen_capture.py --window      # 只截当前活动窗口
    python screen_capture.py --dir D:\\shots   # 自定义保存目录

截图自动保存到 屏幕截图/ 目录，文件名带时间戳。
"""

import argparse
import ctypes
import ctypes.wintypes
import datetime
import os
import threading
import time

from PIL import ImageGrab
from pynput import keyboard


def enable_dpi_awareness():
    """高 DPI 下让坐标/截图正确。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def snap(save_dir, window_only=False):
    os.makedirs(save_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    if window_only:
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            box = (rect.left, rect.top, rect.right, rect.bottom)
            img = ImageGrab.grab(bbox=box)
        except Exception as e:
            print(f"[提示] 窗口截图失败({e})，已回退全屏")
            img = ImageGrab.grab(all_screens=True)
    else:
        img = ImageGrab.grab(all_screens=True)
    path = os.path.join(save_dir, f"截图_{ts}.png")
    img.save(path)
    return path


class Capturer:
    def __init__(self, save_dir, window_only=False):
        self.save_dir = save_dir
        self.window_only = window_only
        self.last = 0.0
        self.stop_flag = False

    def on_press(self, key):
        if key == keyboard.Key.esc:
            print("\n[退出] 已停止监听")
            self.stop_flag = True
            return False
        if key == keyboard.Key.space:
            now = time.time()
            if now - self.last < 0.35:  # 防按住连拍
                return
            self.last = now
            try:
                path = snap(self.save_dir, self.window_only)
                size_kb = os.path.getsize(path) / 1024
                print(f"[截图] {os.path.basename(path)} ({size_kb:.0f} KB)")
                try:
                    import winsound
                    winsound.Beep(1200, 80)
                except Exception:
                    pass
            except Exception as e:
                print(f"[错误] 截图失败: {e}")


def main():
    ap = argparse.ArgumentParser(description="空格截图工具")
    ap.add_argument("--window", action="store_true", help="只截当前活动窗口")
    ap.add_argument("--dir", default=None, help="截图保存目录")
    args = ap.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    save_dir = args.dir or os.path.join(base, "屏幕截图")
    enable_dpi_awareness()

    c = Capturer(save_dir, args.window)
    print("=" * 46)
    print("  空格截图工具已启动")
    print(f"  保存目录: {save_dir}")
    print(f"  模式: {'活动窗口' if args.window else '全屏'}")
    print("  按【空格】截图 · 按【Esc】退出")
    print("=" * 46)

    with keyboard.Listener(on_press=c.on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()
