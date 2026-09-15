# -*- coding: utf-8 -*-
"""一键更新：心率数据 → CPET 结果报告。

流程：
  1. 清理 Excel 临时锁文件（~$*.xlsx）
  2. 心率场次清单（inventory_hr.py → 心率场次清单_全量.csv）
  3. 心率画像（hr_profile.py → hr_sessions.csv + hr_profile.csv）
  4. 两周心率统计（hr_2wk_stats.py → hr_2wk.json）
  5. 重新生成 CPET 结果报告（build_cpet_report.py → 最大摄氧量_结果报告.html）

用法：
  python update_hr_report.py            # 完整更新
  python update_hr_report.py --skip-2wk # 跳过第 4 步（日期范围未变时）

数据入口：把新心率场次 xlsx 放入 D:\\DEV\\blood\\心率\\ 后运行本脚本。
"""
import glob
import os
import subprocess
import sys

# 控制台编码兜底（Windows GBK 终端下避免 emoji 报错）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = r"D:\DEV\blood"
HR_DIR = os.path.join(BASE, "心率")
VO2_DIR = os.path.join(BASE, "最大摄氧量")

STEPS = [
    ("心率场次清单", os.path.join(HR_DIR, "inventory_hr.py")),
    ("心率画像", os.path.join(HR_DIR, "hr_profile.py")),
    ("两周心率统计", os.path.join(VO2_DIR, "hr_2wk_stats.py")),
    ("CPET 结果报告", os.path.join(BASE, "build_cpet_report.py")),
]

# 第 5 步：同步平台数据库（backend venv python + sync_hr.py）
BACKEND_PY = os.path.join(
    BASE, "blood_reports_package_20260726-141357", "backend", ".venv", "Scripts", "python.exe")
SYNC_HR = os.path.join(
    BASE, "blood_reports_package_20260726-141357", "backend", "scripts", "sync_hr.py")
SYNC_CPET = os.path.join(
    BASE, "blood_reports_package_20260726-141357", "backend", "scripts", "sync_cpet.py")


def clean_temp():
    removed = 0
    for f in glob.glob(os.path.join(HR_DIR, "~$*.xlsx")):
        try:
            os.remove(f)
            removed += 1
        except OSError:
            pass
    if removed:
        print(f"[0/4] 已清理 {removed} 个 Excel 临时锁文件")
    else:
        print("[0/4] 无 Excel 临时锁文件")


def run():
    clean_temp()
    for i, (name, script) in enumerate(STEPS, 1):
        print(f"[{i}/{len(STEPS)}] 运行 {name}: {os.path.basename(script)}")
        r = subprocess.run([sys.executable, script], cwd=BASE, capture_output=True, text=True)
        # 打印最后几行输出（含关键统计）
        tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-6:]
        for ln in tail:
            print("   ", ln[:110])
        if r.returncode != 0:
            err = (r.stderr or "").strip().splitlines()[-3:]
            print(f"   [失败] {name}（退出码 {r.returncode}）")
            for ln in err:
                print("   ", ln[:150])
            sys.exit(1)
        print(f"   [完成] {name}")

    out = os.path.join(VO2_DIR, "最大摄氧量_结果报告.html")
    if os.path.exists(out):
        import datetime
        mt = datetime.datetime.fromtimestamp(os.path.getmtime(out))
        print(f"\n报告已更新: {out}")
        print(f"   生成时间: {mt}")

    # 5. 同步平台数据库（若 backend 环境存在）
    if os.path.exists(BACKEND_PY) and os.path.exists(SYNC_HR):
        print(f"\n[5/6] 同步平台心率数据...")
        r = subprocess.run([BACKEND_PY, SYNC_HR], capture_output=True, text=True)
        for ln in (r.stdout or "").splitlines():
            print("   ", ln[:100])
        if r.returncode != 0:
            print("   [失败] 平台心率同步")
            sys.exit(1)
        print("   [完成] 平台心率已同步")

    # 6. 同步 CPET 测试到平台（新 .msstest / XML 自动纳入）
    if os.path.exists(BACKEND_PY) and os.path.exists(SYNC_CPET):
        print(f"\n[6/6] 同步平台 CPET 数据...")
        r = subprocess.run([BACKEND_PY, SYNC_CPET], capture_output=True, text=True)
        for ln in (r.stdout or "").splitlines():
            print("   ", ln[:100])
        if r.returncode != 0:
            print("   [失败] 平台 CPET 同步")
            sys.exit(1)
        print("   [完成] 平台 CPET 已同步")

    print("\n全部完成！")
    try:
        os.startfile(out)
    except OSError:
        pass


if __name__ == "__main__":
    run()
