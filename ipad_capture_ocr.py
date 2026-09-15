# -*- coding: utf-8 -*-
"""
iPad 投屏自动截图 + OCR 智能识别重命名工具
==========================================
场景：iPad 通过 LonelyScreen 投屏到 Windows，本程序只监控该投屏窗口，
按【F8】截图（可在配置改为 space）→ 自动裁剪黑边 → OCR 识别顶部区域（姓名/日期/时间）→
智能重命名为「姓名_日期_时间.png」，识别失败则用「未知选手_时间戳.png」。

依赖安装（任选其一，建议用国内镜像加速）：
    pip install pyautogui pygetwindow keyboard opencv-python-headless easyocr pandas
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

使用步骤：
    1. 打开 LonelyScreen，iPad 投屏成功；
    2. 运行：python ipad_capture_ocr.py
    3. 按【空格】保存当前投屏画面；按【Esc】退出；
    4. 截图与日志保存在配置的 SAVE_DIR（默认 ./投屏截图）。
"""

import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime

import cv2
import ctypes
from ctypes import wintypes
import numpy as np
import pandas as pd
from PIL import Image
import pyautogui
import pygetwindow as gw
import keyboard

try:
    import easyocr
except ImportError:
    easyocr = None


# ==================== 配置区（按需修改） ====================
CONFIG = {
    # LonelyScreen 窗口标题关键字（匹配包含该文字的窗口）
    "WINDOW_KEYWORD": "LonelyScreen",
    # 截图保存目录（自动创建）
    "SAVE_DIR": os.path.join(os.path.dirname(os.path.abspath(__file__)), "投屏截图"),
    # 截图后裁剪黑边，保留有效画面
    "CROP_BLACK_BARS": True,
    # 裁剪时四周多保留的像素，避免裁掉有效内容
    "CROP_MARGIN": 6,
    # OCR 识别顶部区域比例（窗口高度的前 25%）
    "OCR_TOP_RATIO": 0.25,
    # OCR 识别置信度阈值，低于此值的文本丢弃
    "OCR_CONF": 0.35,
    # easyocr 语言（ch_sim=简体中文, en=英文/数字）
    "OCR_LANG": ["ch_sim", "en"],
    # 是否用 GPU（一般机器填 False 用 CPU）
    "OCR_GPU": False,
    # OCR 前放大倍数，提升小字识别率
    "OCR_UPSCALE": 2,
    # 空格防抖时间（秒），按住空格不会连拍
    "DEBOUNCE_SEC": 0.5,
    # 截图热键：默认 f8（与打字无冲突）；如仍想用空格改 "space"
    # 注意：用 space 时程序会自动检测输入框，焦点在文本框/聊天框时不触发截图
    "HOTKEY": "f8",
    # 识别日志 CSV（pandas 写入，方便日后统计）
    "LOG_CSV": "识别日志.csv",
    # 运动员名单来源（blood.db），用于 OCR 姓名模糊匹配
    "ROSTER_DB": os.path.join(os.path.dirname(os.path.abspath(__file__)), "blood.db"),
    # 当前运动员归属规则：识别不到姓名时，照片归到最近一位已识别运动员
    # （新运动员姓名出现后自动切换归属）
    "KEEP_LAST_ATHLETE": True,
    # 当前运动员记录文件（保存在截图目录，重启后仍记住归属）
    "CURRENT_ATH_FILE": "_当前运动员.txt",
}
# ============================================================

# 提示气泡脚本路径（相对本文件所在目录）
_TOAST_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "toast_win.py")


def _enable_dpi_awareness():
    """高 DPI 缩放下保证窗口坐标与截图一致。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


_enable_dpi_awareness()


# -------------------- 全局状态 --------------------
_exit_event = threading.Event()
_last_shot = 0.0
_reader = None           # easyocr Reader 惰性初始化
_reader_lock = threading.Lock()
_ROSTER = None           # 运动员名单缓存
_current_athlete = None  # 当前归属运动员（识别不到姓名时沿用）

# 常见文本输入控件类名（space 热键时用于避免与打字冲突）
_TEXT_INPUT_CLASSES = {
    "Edit", "RichEdit20W", "RichEdit20A", "RichEditD2DPT", "RICHEDIT",
    "Scintilla", "ConsoleWindowClass", "IME",
}


def _focused_is_text_input():
    """检测当前焦点是否在文本输入控件上（仅 space 热键时使用）。"""
    try:
        hwnd = _user32.GetForegroundWindow()
        tid = _user32.GetWindowThreadProcessId(hwnd, None)
        gui = wintypes.GUITHREADINFO()
        gui.cbSize = ctypes.sizeof(wintypes.GUITHREADINFO)
        if not _user32.GetGUIThreadInfo(tid, ctypes.byref(gui)):
            return False
        if not gui.hwndFocus:
            return False
        buf = ctypes.create_unicode_buffer(128)
        _user32.GetClassNameW(gui.hwndFocus, buf, 128)
        return buf.value in _TEXT_INPUT_CLASSES
    except Exception:
        return False


def notify(msg, kind="成功"):
    """右下角弹提示 + 提示音，不阻塞主流程。"""
    try:
        subprocess.Popen(
            [sys.executable, _TOAST_SCRIPT, msg, kind],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        import winsound
        winsound.Beep(1500 if kind == "成功" else 400, 120)
    except Exception:
        pass


# -------------------- 窗口工具 --------------------
def find_mirror_window():
    """查找 LonelyScreen 投屏窗口（选面积最大的可见窗口），返回窗口对象或 None。"""
    kw = CONFIG["WINDOW_KEYWORD"].lower()
    try:
        wins = gw.getAllWindows()
    except Exception as e:
        print(f"[错误] 枚举窗口失败: {e}")
        return None
    best = None
    for w in wins:
        title = (w.title or "")
        if kw in title.lower():
            if w.isMinimized:
                continue
            if w.width <= 0 or w.height <= 0:
                continue
            if best is None or w.width * w.height > best.width * best.height:
                best = w
    if best is None:
        return None
    return best


# -------------------- 截图 --------------------
_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def capture_window(win):
    """抓取指定窗口的自身内容（PrintWindow），不被其他窗口遮挡影响。
    返回 BGR 图像。若 PrintWindow 输出空白，回退为置顶+区域截图。
    """
    hwnd = int(win._hWnd)
    rect = wintypes.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        raise RuntimeError("窗口尺寸无效")

    hwnd_dc = _user32.GetWindowDC(hwnd)
    mem_dc = _gdi32.CreateCompatibleDC(hwnd_dc)
    bmp = _gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    old = _gdi32.SelectObject(mem_dc, bmp)
    try:
        # PW_RENDERFULLCONTENT=2：抓取窗口完整内容（含被遮挡部分）
        ok = _user32.PrintWindow(hwnd, mem_dc, 2)
        # 读取像素
        bmi = _BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h  # 负值表示自顶向下
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0
        buf = ctypes.create_string_buffer(w * h * 4)
        got = _gdi32.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
        if got != h or not ok:
            raise RuntimeError("PrintWindow 无内容")
    finally:
        _gdi32.SelectObject(mem_dc, old)
        _gdi32.DeleteObject(bmp)
        _gdi32.DeleteDC(mem_dc)
        _user32.ReleaseDC(hwnd, hwnd_dc)

    # BGRA -> BGR
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)[:, :, :3].copy()
    # 若全黑说明 PrintWindow 拿不到硬件内容，回退置顶+区域截图
    if arr.mean() < 3:
        return _capture_fallback(win, rect)
    return arr


def _capture_fallback(win, rect):
    """回退方案：把窗口置顶后按区域截图，截完恢复。"""
    hwnd = int(win._hWnd)
    _user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
    time.sleep(0.15)
    try:
        x, y = max(0, rect.left), max(0, rect.top)
        sw = _user32.GetSystemMetrics(0)   # SM_CXSCREEN
        sh = _user32.GetSystemMetrics(1)   # SM_CYSCREEN
        w = min(rect.right - rect.left, sw - x)
        h = min(rect.bottom - rect.top, sh - y)
        shot = pyautogui.screenshot(region=(x, y, w, h))
        return cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
    finally:
        _user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002)


# -------------------- 黑边裁剪 --------------------
def crop_black_bars(img):
    """裁剪四周纯黑边，只保留有效画面。"""
    if img is None or img.size == 0:
        return img
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 亮度 > 10 视为有效内容（黑边亮度接近 0）
    _, th = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
    ys, xs = np.where(th > 0)
    if len(xs) == 0:
        print("[提示] 画面全黑，跳过裁剪")
        return img
    m = CONFIG["CROP_MARGIN"]
    h, w = img.shape[:2]
    x0, x1 = max(0, int(xs.min()) - m), min(w - 1, int(xs.max()) + m)
    y0, y1 = max(0, int(ys.min()) - m), min(h - 1, int(ys.max()) + m)
    return img[y0:y1 + 1, x0:x1 + 1]


# -------------------- OCR --------------------
def get_reader():
    """惰性初始化 easyocr Reader（首次会下载模型，耗时较长）。"""
    global _reader
    if easyocr is None:
        raise RuntimeError("未安装 easyocr，请先运行: pip install easyocr")
    with _reader_lock:
        if _reader is None:
            print("[OCR] 首次运行正在加载识别模型（自动下载，约 1-3 分钟）...")
            _reader = easyocr.Reader(
                CONFIG["OCR_LANG"], gpu=CONFIG["OCR_GPU"], verbose=False)
            print("[OCR] 模型就绪")
    return _reader


def ocr_top_region(img):
    """OCR 识别顶部区域，返回文本列表（按置信度过滤）。"""
    h, w = img.shape[:2]
    top = img[: max(1, int(h * CONFIG["OCR_TOP_RATIO"])), :]
    # 放大提升小字识别率
    up = CONFIG["OCR_UPSCALE"]
    top = cv2.resize(top, (top.shape[1] * up, top.shape[0] * up),
                     interpolation=cv2.INTER_CUBIC)
    reader = get_reader()
    results = reader.readtext(top, detail=1, paragraph=False)
    lines = []
    for bbox, text, conf in results:
        if conf >= CONFIG["OCR_CONF"]:
            lines.append(str(text).strip())
    return lines


def clean_name(text):
    """清洗姓名文本：去掉常见标签与标点。"""
    if not text:
        return None
    text = re.sub(r"姓名|运动员|选手|测试|时间|日期|[:：、，,|/\\·\s]+", "", text)
    text = text.strip(" -—")
    return text or None


def load_roster():
    """从 blood.db 读取运动员名单（找不到则返回空表）。"""
    global _ROSTER
    if _ROSTER is not None:
        return _ROSTER
    _ROSTER = []
    try:
        import sqlite3
        con = sqlite3.connect(CONFIG["ROSTER_DB"])
        _ROSTER = [r[0] for r in con.execute("SELECT name FROM athletes") if r[0]]
        con.close()
    except Exception as e:
        print(f"[警告] 名单加载失败，姓名匹配不可用: {e}")
    return _ROSTER


def load_current_athlete():
    """启动时读取上次的当前归属运动员。"""
    global _current_athlete
    try:
        p = os.path.join(CONFIG["SAVE_DIR"], CONFIG["CURRENT_ATH_FILE"])
        if os.path.exists(p):
            _current_athlete = open(p, encoding="utf-8").read().strip() or None
    except Exception:
        _current_athlete = None
    return _current_athlete


def save_current_athlete(name):
    """持久化当前归属运动员（重启后仍生效）。"""
    try:
        os.makedirs(CONFIG["SAVE_DIR"], exist_ok=True)
        p = os.path.join(CONFIG["SAVE_DIR"], CONFIG["CURRENT_ATH_FILE"])
        with open(p, "w", encoding="utf-8") as f:
            f.write(name)
    except Exception as e:
        print(f"[警告] 当前运动员记录失败: {e}")


def _seq_score(name, text):
    """按字符顺序匹配：name 中的字符在 text 中依次出现多少个。"""
    i = matched = 0
    for ch in name:
        j = text.find(ch, i)
        if j >= 0:
            matched += 1
            i = j + 1
    return matched / len(name) if name else 0


def match_name(lines):
    """把 OCR 文本与运动员名单做模糊匹配（容忍 OCR 错字/顺序颠倒）。"""
    roster = load_roster()
    if not roster or not lines:
        return None
    clean = "".join(re.sub(r"[\W_]+", "", t) for t in lines)
    best, best_score = None, 0.0
    for n in roster:
        if len(n) < 2:
            continue
        sc = max(_seq_score(n, clean), _seq_score(n, clean[::-1]))
        if sc > best_score:
            best, best_score = n, sc
    return best if best_score >= 0.6 else None


def parse_ocr_lines(lines):
    """从 OCR 文本中提取 姓名 / 日期(YYYYMMDD) / 时间(HHMMSS)。"""
    name = date = time_str = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 日期：2026-08-09 / 2026/8/9 / 2026.08.09
        m_date = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", line)
        if m_date:
            date = (f"{m_date.group(1)}{int(m_date.group(2)):02d}"
                    f"{int(m_date.group(3)):02d}")
            name = clean_name(line[:m_date.start()]) or name
        # 时间：10:22:35 / 10.22.35 / 10：22（OCR 常把冒号识别成点或全角）
        m_time = re.search(r"(?<!\d)(\d{1,2})[:.．：](\d{2})(?:[:.．：](\d{2}))?(?!\d)", line)
        if m_time:
            hh, mm = int(m_time.group(1)), int(m_time.group(2))
            ss = int(m_time.group(3) or 0)
            if 0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59:
                time_str = f"{hh:02d}{mm:02d}{ss:02d}"
    # 未在同行取到姓名时，取第一行像人名的文本
    if name is None:
        for line in lines:
            line = line.strip()
            if 2 <= len(line) <= 12 and not re.fullmatch(r"[\d\s:.\-/]+", line):
                name = clean_name(line)
                if name:
                    break
    return name, date, time_str


# -------------------- 命名与保存 --------------------
def unique_path(path):
    """已存在则追加 _1/_2，避免覆盖。"""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{stem}_{i}{ext}"):
        i += 1
    return f"{stem}_{i}{ext}"


def build_filename(name, date, time_str):
    """按规则生成文件名；姓名缺失用未知选手，日期/时间缺失用拍摄时间兜底。"""
    now = datetime.now()
    date = date or now.strftime("%Y%m%d")
    time_str = time_str or now.strftime("%H%M%S")
    if name:
        base = f"{name}_{date}_{time_str}"
    else:
        base = f"未知选手_{date}_{time_str}"
    return unique_path(os.path.join(CONFIG["SAVE_DIR"], f"{base}.png"))


def append_log(row):
    """用 pandas 追加一条识别日志。"""
    try:
        log_path = os.path.join(CONFIG["SAVE_DIR"], CONFIG["LOG_CSV"])
        df = pd.DataFrame([row])
        if os.path.exists(log_path):
            old = pd.read_csv(log_path, encoding="utf-8-sig")
            df = pd.concat([old, df], ignore_index=True)
        df.to_csv(log_path, index=False, encoding="utf-8-sig")
    except Exception as e:
        print(f"[警告] 日志写入失败: {e}")


# -------------------- 主流程 --------------------
def on_capture():
    """热键回调：截图 → 裁剪 → OCR → 重命名保存。"""
    global _last_shot, _current_athlete
    if CONFIG["HOTKEY"] == "space" and _focused_is_text_input():
        print("[提示] 焦点在输入框，已跳过截图（避免与打字冲突）")
        return
    now = time.time()
    if now - _last_shot < CONFIG["DEBOUNCE_SEC"]:
        return  # 防抖
    _last_shot = now

    print("-" * 50)
    win = find_mirror_window()
    if win is None:
        print(f"[提示] 未找到标题含「{CONFIG['WINDOW_KEYWORD']}」的窗口，"
              f"请确认 LonelyScreen 已打开并投屏")
        notify("未找到投屏窗口，请检查 LonelyScreen", "失败")
        return
    print(f"[窗口] 已捕获: {win.title}  ({win.width}x{win.height})")

    try:
        img = capture_window(win)
    except Exception as e:
        print(f"[错误] 截图失败: {e}")
        return

    if CONFIG["CROP_BLACK_BARS"]:
        img = crop_black_bars(img)
    print(f"[裁剪] 黑边去除完成: {img.shape[1]}x{img.shape[0]}")

    try:
        lines = ocr_top_region(img)
        name, date, time_str = parse_ocr_lines(lines)
        # 名单模糊匹配优先：纠正 OCR 错字或姓名顺序
        roster_name = match_name(lines)
        if roster_name:
            name = roster_name
            _current_athlete = roster_name
            save_current_athlete(roster_name)
        elif CONFIG["KEEP_LAST_ATHLETE"] and _current_athlete:
            # 识别不到姓名时，照片归到最近一位已识别运动员
            name = _current_athlete
        else:
            # 忽略页面标题等非名单文本，避免错误命名
            name = None
        print(f"[OCR] 识别文本: {' | '.join(lines) if lines else '（无）'}")
        if roster_name:
            print(f"[OCR] 识别到新运动员: {roster_name}（已切换归属）")
        elif name:
            print(f"[OCR] 沿用当前运动员: {name}")
        print(f"[OCR] 日期={date or '？'} 时间={time_str or '？'}")
    except Exception as e:
        print(f"[错误] OCR 失败，将按时间戳命名: {e}")
        name = date = time_str = None

    path = build_filename(name, date, time_str)
    os.makedirs(CONFIG["SAVE_DIR"], exist_ok=True)
    try:
        # cv2.imwrite 不支持中文路径，用 PIL 保存
        Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).save(path)
        ok = True
    except Exception as e:
        print(f"[错误] 图片写入失败: {e}")
        ok = False
    if ok:
        size_kb = os.path.getsize(path) / 1024
        print(f"[保存] {os.path.basename(path)} ({size_kb:.0f} KB)")
        notify(f"已保存 {os.path.basename(path)}")
        append_log({
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "文件": os.path.basename(path),
            "OCR姓名": name or "",
            "OCR日期": date or "",
            "OCR时间": time_str or "",
        })
    else:
        print("[错误] 图片写入失败，请检查保存目录权限")
        notify("图片保存失败，请检查目录权限", "失败")
    print("-" * 50)


def on_exit():
    """Esc 回调：退出。"""
    print("\n[退出] 正在结束...")
    _exit_event.set()


def warmup():
    """启动时预热 OCR 模型，避免第一次按空格卡顿。"""
    print("[预热] 正在加载 OCR 模型...")
    try:
        get_reader()
    except Exception as e:
        print(f"[警告] OCR 模型加载失败（首次联网下载或缺少模型）: {e}")


def main():
    print("=" * 50)
    print("  iPad 投屏截图 + OCR 智能命名")
    print(f"  监控窗口: {CONFIG['WINDOW_KEYWORD']}")
    print(f"  保存目录: {CONFIG['SAVE_DIR']}")
    print(f"  按【{CONFIG['HOTKEY']}】截图 · 按【Esc】退出")
    print("=" * 50)
    os.makedirs(CONFIG["SAVE_DIR"], exist_ok=True)
    cur = load_current_athlete()
    if cur:
        print(f"  当前归属运动员: {cur}（识别不到姓名时沿用）")
    notify(f"截图工具已启动，按 {CONFIG['HOTKEY']} 截图")

    # 后台线程预热模型，不阻塞主流程
    threading.Thread(target=warmup, daemon=True).start()

    keyboard.add_hotkey(CONFIG["HOTKEY"], on_capture)
    keyboard.add_hotkey("esc", on_exit)
    try:
        while not _exit_event.is_set():
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        print("[退出] 程序已结束，截图保存在:", CONFIG["SAVE_DIR"])


if __name__ == "__main__":
    sys.exit(main())
