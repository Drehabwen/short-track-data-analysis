# -*- coding: utf-8 -*-
"""HRV 分析服务：封装 hrvanalysis 库（RR 间期 → 全套指标）。"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

try:
    from hrvanalysis import get_frequency_domain_features, get_time_domain_features
    HRV_ENGINE = "hrvanalysis"
except Exception:  # 降级：numpy/scipy 自算
    HRV_ENGINE = "builtin"


def compute_hrv(rr_intervals: list[float]) -> dict:
    """RR 间期序列（毫秒）→ HRV 全套指标。

    返回时域（SDNN/RMSSD/pNN50/meanNN）+ 频域（LF/HF/LF-HF/总功率）。
    """
    rri = [float(x) for x in rr_intervals if x and x > 200 and x < 2500]
    if len(rri) < 30:
        return {"error": "RR 间期不足（至少 30 个有效值）", "n_rri": len(rri)}
    out: dict = {"n_rri": len(rri), "engine": HRV_ENGINE}
    try:
        td = get_time_domain_features(rri)
        out.update({
            "mean_nni": _f(td.get("mean_nni")),
            "sdnn": _f(td.get("sdnn")),
            "rmssd": _f(td.get("rmssd")),
            "sdsd": _f(td.get("sdsd")),
            "nni_50": int(td.get("nni_50") or 0),
            "pnni_50": _f(td.get("pnni_50")),
        })
    except Exception:
        _td_fallback(rri, out)
    try:
        fd = get_frequency_domain_features(rri, sampling_frequency=4.0)
        out.update({
            "lf": _f(fd.get("lf")),
            "hf": _f(fd.get("hf")),
            "lf_hf_ratio": _f(fd.get("lf_hf_ratio")),
            "lfnu": _f(fd.get("lfnu")),
            "hfnu": _f(fd.get("hfnu")),
            "total_power": _f(fd.get("total_power")),
        })
    except Exception:
        _fd_fallback(rri, out)
    return out


def _f(v) -> Optional[float]:
    try:
        f = float(v)
        return round(f, 2) if math.isfinite(f) else None
    except Exception:
        return None


def _td_fallback(rri, out):
    """纯 numpy 时域指标（标准公式）。"""
    arr = np.asarray(rri, dtype=float)
    diffs = np.diff(arr)
    out.update({
        "mean_nni": round(float(arr.mean()), 2),
        "sdnn": round(float(arr.std()), 2),
        "rmssd": round(float(np.sqrt(np.mean(diffs ** 2))), 2),
        "sdsd": round(float(diffs.std()), 2),
        "nni_50": int(np.sum(np.abs(diffs) > 50)),
        "pnni_50": round(float(np.mean(np.abs(diffs) > 50) * 100), 2),
        "engine": "builtin_time",
    })


def _fd_fallback(rri, out):
    """纯 scipy 频域指标（Welch PSD + 频带积分，标准定义）。"""
    try:
        from scipy.signal import welch
        arr = np.asarray(rri, dtype=float) / 1000.0  # ms → s
        t = np.cumsum(arr)
        # 等间隔重采样（4 Hz）
        fs = 4.0
        n = int(t[-1] * fs)
        if n < 8:
            return
        t_uniform = np.linspace(t[0], t[-1], n)
        rri_uniform = np.interp(t_uniform, t, arr)
        f, psd = welch(rri_uniform, fs=fs, nperseg=min(256, len(rri_uniform)))
        df = f[1] - f[0]
        def band(a, b):
            m = (f >= a) & (f <= b)
            return float(np.trapz(psd[m], f[m])) if m.any() else 0.0
        lf, hf = band(0.04, 0.15), band(0.15, 0.4)
        tp = band(0.003, 0.4)
        out.update({
            "lf": round(lf, 2), "hf": round(hf, 2),
            "lf_hf_ratio": round(lf / hf, 2) if hf > 0 else None,
            "lfnu": round(lf / (lf + hf) * 100, 2) if (lf + hf) > 0 else None,
            "hfnu": round(hf / (lf + hf) * 100, 2) if (lf + hf) > 0 else None,
            "total_power": round(tp, 2),
            "engine": "builtin_freq",
        })
    except Exception:
        pass


def recovery_level(sdnn: Optional[float], rmssd: Optional[float]) -> str:
    """恢复状态分级（基于参考：RMSSD 高 = 副交感主导 = 恢复好）。"""
    if rmssd is None:
        return "数据不足"
    if rmssd >= 60:
        return "恢复良好"
    if rmssd >= 40:
        return "恢复正常"
    if rmssd >= 25:
        return "恢复偏低"
    return "疲劳风险"
