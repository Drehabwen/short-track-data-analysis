# -*- coding: utf-8 -*-
"""幂等导入统一数据集中的 500m 运动成绩排行。"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import CompetitionResult, Participant  # noqa: E402


SOURCE = Path(r"D:\DEV\blood\统一数据集\运动成绩_500m排行.csv")
COMPETITION_NAME = "统一数据集500m排行"
SOURCE_NOTE = "来源：统一数据集/运动成绩_500m排行.csv"

# 原表中少数行没有编号，按姓名补齐。王慧霖是主表中的姓名变体“王慧琳”。
NAME_ALIASES = {"王慧霖": "C13"}


def resolve_participant(row, by_id, by_name):
    participant_id = (row.get("编号") or "").strip()
    if participant_id and participant_id in by_id:
        return participant_id
    name = (row.get("姓名") or "").strip()
    participant_id = NAME_ALIASES.get(name) or by_name.get(name)
    if participant_id:
        return participant_id
    raise ValueError(f"无法关联运动员：编号={row.get('编号')!r}，姓名={name!r}")


def import_rows():
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)

    with SOURCE.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    db = SessionLocal()
    try:
        participants = db.query(Participant).all()
        by_id = {p.participant_id: p.participant_id for p in participants}
        by_name = {p.name: p.participant_id for p in participants if p.name}
        created = 0
        skipped = 0
        conflicts = []

        for row in rows:
            participant_id = resolve_participant(row, by_id, by_name)
            rank = int(row["排名"])
            seconds = round(float(row["500m(s)"]), 2)
            time_result = f"{seconds:.2f}"
            lap7 = (row.get("7圈(s)") or "").strip()
            note = f"{SOURCE_NOTE}；原表排名：{rank}"
            if lap7:
                note += f"；7圈成绩：{lap7}s"

            duplicate = (
                db.query(CompetitionResult)
                .filter(
                    CompetitionResult.participant_id == participant_id,
                    CompetitionResult.competition_name == COMPETITION_NAME,
                    CompetitionResult.event == "500m",
                    CompetitionResult.time_seconds == seconds,
                    CompetitionResult.rank == rank,
                )
                .first()
            )
            if duplicate:
                skipped += 1
                continue

            existing = (
                db.query(CompetitionResult)
                .filter(
                    CompetitionResult.participant_id == participant_id,
                    CompetitionResult.event == "500m",
                    CompetitionResult.time_seconds == seconds,
                )
                .all()
            )
            if existing:
                conflicts.append(
                    f"{participant_id}: {seconds:.2f}s 已有 {len(existing)} 条历史记录，保留并新增统一数据集记录"
                )

            db.add(
                CompetitionResult(
                    participant_id=participant_id,
                    competition_name=COMPETITION_NAME,
                    event="500m",
                    time_result=time_result,
                    time_seconds=seconds,
                    rank=rank,
                    note=note,
                )
            )
            created += 1

        db.commit()
        print(f"源文件行数：{len(rows)}")
        print(f"新增：{created} 条，跳过重复：{skipped} 条")
        print(f"成绩记录总数：{db.query(CompetitionResult).count()} 条")
        if conflicts:
            print("保留历史记录的冲突：")
            for conflict in conflicts:
                print(f"- {conflict}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import_rows()
