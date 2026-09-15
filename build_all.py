# -*- coding: utf-8 -*-
"""一键重建全部报告：心率解析 → CPET 清洗/合并 → 分析 → 周报。

用法:
    python build_all.py            # 依依赖顺序重建，任一步失败即停
    python build_all.py --continue # 失败也继续后续步骤
    python build_all.py --list     # 仅列出步骤
"""
import os
import subprocess
import sys
import time

BLOOD = os.path.dirname(os.path.abspath(__file__))

# 步骤：(名称, 脚本相对路径, 是否必需)
STEPS = [
    ("心率场次清单", r"心率\inventory_hr.py", True),
    ("心率画像汇总", r"心率\hr_profile.py", True),
    ("新 CPET 清洗/去重/分级", r"最大摄氧量\clean_new_cpet.py", True),
    ("CPET 合并进主数据集", r"最大摄氧量\merge_new_cpet.py", True),
    ("深度分析 + Excel", r"最大摄氧量\analysis_core.py", True),
    ("交互仪表盘", r"最大摄氧量\interactive_report.py", True),
    ("图文结合周报(最大摄氧量)", r"build_cpet_report.py", True),
    ("综合周报统计", r"weekly_stats.py", True),
    ("综合周报(全数据域)", r"build_weekly_report.py", True),
    ("心率周对比", r"build_week_compare.py", False),
    ("教练简报表", r"build_coach_report_v4.py", False),
]


def py():
    """优先使用工作区捆绑 Python，其次当前解释器。"""
    bundled = (r"C:\Users\labops\.cache\codex-runtimes\codex-primary-runtime"
               r"\dependencies\python\python.exe")
    if os.path.exists(bundled):
        return bundled
    return sys.executable


def main():
    cont = "--continue" in sys.argv
    if "--list" in sys.argv:
        for i, (name, path, need) in enumerate(STEPS, 1):
            print(f"{i:2d}. [{'必需' if need else '可选'}] {name}  <-  {path}")
        return

    python = py()
    print(f"构建入口: {BLOOD}")
    print(f"Python  : {python}\n")
    ok, fail = 0, 0
    for i, (name, rel, need) in enumerate(STEPS, 1):
        script = os.path.join(BLOOD, rel)
        t0 = time.time()
        print(f"▶ [{i}/{len(STEPS)}] {name} ...", flush=True)
        try:
            r = subprocess.run([python, script], cwd=BLOOD)
            dt = time.time() - t0
            if r.returncode == 0:
                print(f"  ✔ 完成 ({dt:.1f}s)\n")
                ok += 1
            else:
                print(f"  ✘ 失败 (code={r.returncode}, {dt:.1f}s)\n")
                fail += 1
                if not cont:
                    print("中止：任一步骤失败。加 --continue 可跳过继续。")
                    sys.exit(1)
        except Exception as e:
            print(f"  ✘ 异常: {e}\n")
            fail += 1
            if not cont:
                sys.exit(1)
    print(f"构建完成：成功 {ok} 步，失败 {fail} 步。")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
