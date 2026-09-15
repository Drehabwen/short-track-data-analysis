# -*- coding: utf-8 -*-
"""Build the analysis-ready RehabID-Fatigue v0.1 data package.

The script keeps source observations intact and adds provenance, linkage and
quality flags. It intentionally does not impute or silently repair values.
"""
from __future__ import annotations

import csv
import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(r"D:\DEV\blood")
UNIFIED = ROOT / "统一数据集"
OUT_LONG = UNIFIED / "RehabID-Fatigue_v0.1_long.csv"
OUT_DICT = UNIFIED / "RehabID-Fatigue_v0.1_data_dictionary.csv"
OUT_QC = UNIFIED / "RehabID-Fatigue_v0.1_qc.json"
OUT_SPLITS = UNIFIED / "RehabID-Fatigue_v0.1_splits.json"
OUT_README = UNIFIED / "RehabID-Fatigue_v0.1_README.md"

MAIN_FILE = UNIFIED / "统一数据集_受试者主表.csv"
HR_FILE = UNIFIED / "心率明细表.csv"
BLOOD_FILE = UNIFIED / "血液明细表_链接后.csv"
MATRIX_FILE = UNIFIED / "数据完整性矩阵.csv"
CPET_FILE = ROOT / "最大摄氧量" / "最大摄氧量数据" / "cpet_enriched.csv"

LONG_FIELDS = [
    "subject_id", "name", "source_table", "source_file", "modality",
    "feature", "timepoint", "record_date", "unit", "value",
    "numeric_value", "qualifier", "link_status", "quality_flag",
    "original_field",
]


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def number(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def clean(value):
    return "" if value is None else str(value).strip()


def quality(value, qualifier=""):
    value = clean(value)
    qualifier = clean(qualifier)
    if qualifier:
        return "censored"
    if not value:
        return "missing"
    return "observed"


def record(subject_id, name, source_table, source_file, modality, feature,
           timepoint, record_date, unit, value, qualifier="", link_status="linked",
           original_field=""):
    value = clean(value)
    n = number(value)
    return {
        "subject_id": clean(subject_id),
        "name": clean(name),
        "source_table": source_table,
        "source_file": source_file,
        "modality": modality,
        "feature": feature,
        "timepoint": timepoint,
        "record_date": clean(record_date),
        "unit": unit,
        "value": value,
        "numeric_value": "" if n is None else n,
        "qualifier": clean(qualifier),
        "link_status": link_status,
        "quality_flag": quality(value, qualifier),
        "original_field": original_field,
    }


def infer_main_field(field, value):
    """Return modality, feature, timepoint, unit for a wide-table field."""
    if field == "intervention":
        return "study_design", "intervention", "study", "category"
    if field == "load_pct":
        return "exercise_load", "load_pct", "exercise", "%"

    m = re.fullmatch(r"(avg_power|peak_power)_p([1-5])", field)
    if m:
        return "exercise_load", m.group(1), f"p{m.group(2)}", "W"

    aggregate_units = {
        "hr_sessions": "sessions", "hr_minutes": "min", "hr_avg": "bpm",
        "hr_max": "bpm", "hr_trimp_sum": "AU", "hr_rel_mean": "%",
        "hr_zero_rate_mean": "%", "hr_ice_sessions": "sessions",
        "hr_land_sessions": "sessions",
    }
    if field in aggregate_units:
        return "training_load", field[3:], "aggregate", aggregate_units[field]

    m = re.fullmatch(r"hr_(rest|post|24h|72h)_(avg|max)", field)
    if m:
        tp = {"rest": "baseline", "post": "post_exercise"}.get(m.group(1), m.group(1))
        return "physiology", f"heart_rate_{m.group(2)}", tp, "bpm"

    for prefix, modality, feature, unit in [
        ("cmj_", "performance", "cmj_height", "cm"),
        ("vas_", "subjective", "vas", "points"),
        ("rpe_", "subjective", "rpe", "points"),
        ("lactate_", "physiology", "lactate", "mmol/L"),
        ("hr_", "physiology", "heart_rate", "bpm"),
    ]:
        if field.startswith(prefix):
            tp = field[len(prefix):]
            tp = {"rest": "baseline", "post": "post_exercise", "interv": "intervention"}.get(tp, tp)
            return modality, feature, tp, unit

    if field.startswith("hrv_"):
        return "physiology", field[4:], "baseline", "native"

    if field.startswith("pt_"):
        return "baseline_function", field[3:], "baseline", "native"

    # Blood columns are emitted from the linked long table below to preserve
    # the laboratory unit and qualifier. Avoid duplicating them here.
    if field.startswith("blood_"):
        return None

    return "metadata", field, "study", "native"


def date_from_filename(text):
    m = re.search(r"(20\d{2})[._-](\d{2})[._-](\d{2})", clean(text))
    return "-".join(m.groups()) if m else ""


def main():
    main_rows = read_csv(MAIN_FILE)
    hr_rows = read_csv(HR_FILE)
    blood_rows = read_csv(BLOOD_FILE)
    matrix_rows = read_csv(MATRIX_FILE)
    cpet_rows = read_csv(CPET_FILE) if CPET_FILE.exists() else []

    alias_to_id = {}
    id_to_name = {}
    for row in main_rows:
        sid, name = clean(row.get("subject_id")), clean(row.get("name"))
        if sid:
            id_to_name[sid] = name
            alias_to_id[name] = sid
            for alias in clean(row.get("name_aliases")).split(";"):
                if alias:
                    alias_to_id[alias] = sid

    long_rows = []
    dictionary = {}

    def add(row):
        long_rows.append(row)
        key = (row["modality"], row["feature"], row["timepoint"], row["unit"])
        dictionary.setdefault(key, {
            "field": row["feature"],
            "modality": row["modality"],
            "feature": row["feature"],
            "timepoint": row["timepoint"],
            "unit": row["unit"],
            "description": describe(row["modality"], row["feature"]),
            "source_table": row["source_table"],
            "source_file": row["source_file"],
            "notes": "原始值保留；缺失、删失和未匹配通过质量字段标记",
        })

    # 1) Main wide table -> long observations.
    identity = {"subject_id", "name", "name_aliases", "class", "coach", "gender",
                "age", "height_cm", "weight_kg"}
    for row in main_rows:
        for field, value in row.items():
            if field in identity or field.startswith("blood_"):
                continue
            inferred = infer_main_field(field, value)
            if inferred is None:
                continue
            modality, feature, tp, unit = inferred
            add(record(row.get("subject_id"), row.get("name"), "统一受试者主表",
                       MAIN_FILE.name, modality, feature, tp, "", unit, value,
                       original_field=field))

    # 2) HR session detail -> one row per metric per session.
    hr_map = {
        "平均心率": ("heart_rate_session", "mean_hr", "bpm"),
        "最大心率": ("heart_rate_session", "max_hr", "bpm"),
        "TRIMP": ("heart_rate_session", "trimp", "AU"),
        "时长min": ("heart_rate_session", "duration", "min"),
        "高强度min": ("heart_rate_session", "high_intensity_duration", "min"),
        "0值率%": ("heart_rate_session", "zero_rate", "%"),
    }
    for row in hr_rows:
        name = clean(row.get("姓名"))
        sid = alias_to_id.get(name, "")
        link = "linked" if sid else "unmatched_name"
        for source_field, (modality, feature, unit) in hr_map.items():
            add(record(sid, name, "心率明细表", HR_FILE.name, modality, feature,
                       clean(row.get("类型")) or "session", clean(row.get("日期")),
                       unit, row.get(source_field), link_status=link,
                       original_field=source_field))

    # 3) Blood laboratory detail. Keep qualifiers and native units.
    for row in blood_rows:
        sid = clean(row.get("participant_id"))
        link = "linked" if sid in id_to_name else "unmatched_id"
        add(record(sid, row.get("实验表姓名"), "血液明细表", BLOOD_FILE.name,
                   "blood_lab", clean(row.get("analyte")), clean(row.get("timepoint")),
                   "", clean(row.get("unit")), row.get("result_value"),
                   qualifier=row.get("qualifier"), link_status=link,
                   original_field="result_value"))

    # 4) CPET enriched summaries. Keep this as an event/source table, not a
    # forced one-row-per-subject merge, because some athletes have repeated tests.
    cpet_fields = [
        ("meas_max_vo2", "vo2_max", "L/min"),
        ("meas_max_vo2kg", "vo2_max_per_kg", "mL/kg/min"),
        ("peak_wr", "peak_work_rate", "W"),
        ("exercise_dur_s", "exercise_duration", "s"),
        ("meas_max_rer", "rer_max", "ratio"),
        ("valid_class", "validity_class", "category"),
    ]
    for row in cpet_rows:
        name = clean(row.get("name"))
        sid = alias_to_id.get(name, "")
        link = "linked" if sid else "unmatched_name"
        date = date_from_filename(row.get("file"))
        for source_field, feature, unit in cpet_fields:
            if source_field in row:
                add(record(sid, name, "CPET enriched", CPET_FILE.name, "cpet",
                           feature, "test", date, unit, row.get(source_field),
                           link_status=link, original_field=source_field))

    # Append dictionary records as stable rows.
    dict_rows = sorted(dictionary.values(), key=lambda x: (x["modality"], x["feature"], x["timepoint"]))
    write_csv(OUT_LONG, long_rows, LONG_FIELDS)
    write_csv(OUT_DICT, dict_rows, ["field", "modality", "feature", "timepoint", "unit",
                                    "description", "source_table", "source_file", "notes"])

    # QC summary. No imputation, outlier deletion or silent alias correction is performed.
    source_counts = Counter(r["source_table"] for r in long_rows)
    link_counts = defaultdict(Counter)
    for r in long_rows:
        link_counts[r["source_table"]][r["link_status"]] += 1
    matrix_values = [number(r.get("完整度%")) for r in matrix_rows]
    matrix_values = [x for x in matrix_values if x is not None]
    flags = []
    for row in main_rows:
        cmj = number(row.get("cmj_pre"))
        hr_max = number(row.get("hr_max"))
        if cmj is not None and cmj > 100:
            flags.append({"subject_id": row.get("subject_id"), "field": "cmj_pre",
                          "value": cmj, "reason": "check_cmj_value_gt_100_cm"})
        if hr_max is not None and hr_max > 210:
            flags.append({"subject_id": row.get("subject_id"), "field": "hr_max",
                          "value": hr_max, "reason": "check_hr_max_gt_210_bpm"})
        if not clean(row.get("intervention")):
            flags.append({"subject_id": row.get("subject_id"), "field": "intervention",
                          "value": "", "reason": "missing_intervention"})
    for row in blood_rows:
        if clean(row.get("qualifier")) not in ("", "<"):
            flags.append({"subject_id": row.get("participant_id"), "field": "qualifier",
                          "value": row.get("qualifier"), "reason": "unreviewed_lab_qualifier"})

    qc = {
        "dataset_version": "RehabID-Fatigue v0.1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "main_subjects": len(main_rows),
            "hr_detail_rows": len(hr_rows),
            "blood_detail_rows": len(blood_rows),
            "cpet_enriched_rows": len(cpet_rows),
        },
        "outputs": {
            "long_rows": len(long_rows),
            "dictionary_rows": len(dict_rows),
        },
        "source_row_counts": dict(source_counts),
        "link_status_counts": {k: dict(v) for k, v in link_counts.items()},
        "completeness_percent": {
            "n": len(matrix_values),
            "min": min(matrix_values) if matrix_values else None,
            "median": sorted(matrix_values)[len(matrix_values) // 2] if matrix_values else None,
            "mean": round(sum(matrix_values) / len(matrix_values), 2) if matrix_values else None,
            "max": max(matrix_values) if matrix_values else None,
        },
        "flags": flags,
        "processing_rules": [
            "所有源值按原样保留，不做插补、不删除异常值。",
            "主表宽表字段转换成长表记录，并保留 original_field。",
            "血液结果保留 qualifier 和 unit；< 型结果标记为 censored。",
            "姓名只使用已有别名映射进行链接，未匹配记录保留并标记。",
            "CPET 保持事件级记录，避免重复测试被强行压成单一受试者行。",
        ],
    }
    OUT_QC.write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
    splits = build_splits(main_rows)
    OUT_SPLITS.write_text(json.dumps(splits, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_README.write_text(build_readme(qc), encoding="utf-8")
    print(json.dumps({"long": str(OUT_LONG), "dictionary": str(OUT_DICT),
                      "qc": str(OUT_QC), "splits": str(OUT_SPLITS),
                      "readme": str(OUT_README),
                      "long_rows": len(long_rows), "dictionary_rows": len(dict_rows)},
                     ensure_ascii=False, indent=2))


def describe(modality, feature):
    descriptions = {
        "cmj_height": "反向纵跳高度",
        "vas": "疼痛视觉模拟评分",
        "rpe": "主观用力程度评分",
        "lactate": "血乳酸",
        "heart_rate": "时间点心率",
        "mean_hr": "训练场次平均心率",
        "max_hr": "训练场次最大心率",
        "trimp": "训练冲量",
        "vo2_max": "最大摄氧量",
        "vo2_max_per_kg": "相对最大摄氧量",
        "peak_work_rate": "峰值功率",
        "exercise_duration": "运动持续时间",
        "blood_lab": "血液实验室指标",
    }
    return descriptions.get(feature, feature)


def build_readme(qc):
    return f"""# RehabID-Fatigue v0.1

## 用途

面向运动疲劳—恢复研究的分析数据包。它把受试者主表、心率明细、血液化验和 CPET 摘要放进同一个带来源标记的长表，服务于后续的通用模型、个体化模型和层级模型比较。

## 数据范围

- 主表：{qc['inputs']['main_subjects']} 名受试者，保留原始宽表字段对应的长表记录。
- 心率明细：{qc['inputs']['hr_detail_rows']} 行训练场次数据。
- 血液明细：{qc['inputs']['blood_detail_rows']} 行，保留单位和检验限定符。
- CPET enriched：{qc['inputs']['cpet_enriched_rows']} 行；重复测试保持为独立事件。

## 文件

- `RehabID-Fatigue_v0.1_long.csv`：一行一个观测，包含 `subject_id`、时间点、模态、特征、单位、来源文件和质量标记。
- `RehabID-Fatigue_v0.1_data_dictionary.csv`：字段、单位、时间点和来源说明。
- `RehabID-Fatigue_v0.1_qc.json`：规模、链接状态、完整率和需人工复核的记录。
- `RehabID-Fatigue_v0.1_splits.json`：固定随机种子的受试者留出和时间留出规则。

## 处理规则

1. 不做插补，不删除异常值，不把缺失值当作零。
2. 血液结果中的 `<` 保留在 `qualifier`，并将 `quality_flag` 标记为 `censored`。
3. 已知姓名别名只用于链接；无法链接的记录保留，`link_status` 标记为 `unmatched_name` 或 `unmatched_id`。
4. CPET 不强行并入单行受试者宽表，以免重复测试丢失时间信息。

## 建议的首轮分析

以 CMJ 24/72 h 恢复为主要功能结局，分别比较通用、个体化和层级模型；用 RPE、VAS、心率、乳酸、CK 和 CPET 指标做辅助结局或敏感性分析。数据切分至少包括受试者留出、时间留出和缺失模态场景，具体规则见 `RehabID-Fatigue_v0.1_splits.json`。

## 复核重点

请先查看 `RehabID-Fatigue_v0.1_qc.json` 中的 flags，再锁定分析版数据。任何异常值、别名和干预缺失都应在分析记录中说明。
"""


def build_splits(main_rows):
    """Create deterministic subject-level and temporal evaluation recipes."""
    rng = random.Random(20260906)
    strata = defaultdict(list)
    for row in main_rows:
        sid = clean(row.get("subject_id"))
        if sid:
            strata[clean(row.get("intervention")) or "missing_intervention"].append(sid)
    train, validation, test = [], [], []
    for key in sorted(strata):
        ids = sorted(strata[key])
        rng.shuffle(ids)
        n = len(ids)
        n_test = max(1, round(n * 0.2))
        n_val = max(1, round(n * 0.2))
        test.extend(ids[:n_test])
        validation.extend(ids[n_test:n_test + n_val])
        train.extend(ids[n_test + n_val:])
    return {
        "dataset_version": "RehabID-Fatigue v0.1",
        "random_seed": 20260906,
        "subject_split": {
            "train": sorted(train),
            "validation": sorted(validation),
            "test": sorted(test),
            "stratification": "intervention; missing intervention kept as its own stratum",
            "leakage_guard": "all records belonging to a test subject stay out of train and validation",
        },
        "temporal_holdout": {
            "train_timepoints": ["baseline", "pre", "post_exercise", "intervention"],
            "test_timepoints": ["24h", "72h"],
            "note": "Use only when the outcome is defined at 24h/72h; do not use future timepoints as features.",
        },
        "missing_modality_stress_tests": [
            {"name": "no_hrv", "drop_features": ["sdnn", "rmssd", "lf_hf", "total_power"]},
            {"name": "no_force_or_jump", "drop_features": ["cmj_height", "force_plate", "jump"]},
            {"name": "no_blood", "drop_modalities": ["blood_lab"]},
            {"name": "sparse_72h", "drop_timepoints": ["72h"]},
        ],
        "not_yet_available": [
            "cross-device holdout requires device/protocol labels to be normalized in the raw sources",
            "intervention effect analysis requires a pre-specified causal design and handling of non-random assignment",
        ],
    }


if __name__ == "__main__":
    main()
