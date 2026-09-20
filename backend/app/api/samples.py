# -*- coding: utf-8 -*-
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..models import Participant, Sample

router = APIRouter(prefix="/api", tags=["samples"])

TP_LABELS = {"BL": "训练前", "24H": "24小时后", "72H": "72小时后"}


@router.get("/participants/{participant_id}/samples", response_model=list[schemas.SampleOut])
def participant_samples(participant_id: str, db: Session = Depends(get_db)):
    samples = (
        db.query(Sample)
        .filter(Sample.participant_id == participant_id)
        .order_by(Sample.time_order)
        .all()
    )
    if not samples:
        raise HTTPException(status_code=404, detail="未找到该运动员的血样记录")
    return samples


@router.get("/samples", response_model=list[schemas.SampleOut])
def list_samples(
    timepoint: str | None = Query(None),
    group: str | None = Query(None),
    participant: str | None = Query(None),
    review_status: str | None = Query(None),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Sample)
    if timepoint:
        query = query.filter(Sample.timepoint == timepoint)
    if group:
        query = query.join(Participant).filter(Participant.group_name == group)
    if participant:
        query = query.filter(Sample.participant_id == participant)
    if review_status:
        query = query.filter(Sample.review_status == review_status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Sample.visit_id.ilike(like)) | (Sample.participant_id.ilike(like))
        )
    return query.order_by(Sample.participant_id, Sample.time_order).all()


@router.patch("/samples/{sample_id}", response_model=schemas.SampleOut)
def update_sample(
    sample_id: int,
    payload: schemas.SampleUpdate,
    db: Session = Depends(get_db),
):
    sample = db.get(Sample, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="样本不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(sample, field, value)
    # 睾酮 raw/value 联动
    if payload.testosterone_raw is not None:
        raw = payload.testosterone_raw.strip()
        sample.testosterone_raw = raw
        sample.testosterone_qualifier = "<" if raw.startswith("<") else None
        sample.testosterone_below_lod = raw.startswith("<")
        try:
            sample.testosterone_value = None if raw.startswith("<") else float(raw.lstrip("<>"))
        except ValueError:
            sample.testosterone_value = None
    db.commit()
    db.refresh(sample)
    return sample


@router.get("/export/samples.xlsx")
def export_samples_xlsx(
    timepoint: str | None = Query(None),
    group: str | None = Query(None),
    participant: str | None = Query(None),
    review_status: str | None = Query(None),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """把当前筛选下的血样记录导出为 Excel（openpyxl 生成）。"""
    query = db.query(Sample, Participant).join(
        Participant, Sample.participant_id == Participant.participant_id
    )
    if timepoint:
        query = query.filter(Sample.timepoint == timepoint)
    if group:
        query = query.filter(Participant.group_name == group)
    if participant:
        query = query.filter(Sample.participant_id == participant)
    if review_status:
        query = query.filter(Sample.review_status == review_status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Sample.visit_id.ilike(like)) | (Sample.participant_id.ilike(like))
        )
    rows = query.order_by(Sample.participant_id, Sample.time_order).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "血样数据"
    headers = [
        "样本编号",
        "运动员编号",
        "组别",
        "时间点",
        "采集时间",
        "睾酮(raw)",
        "睾酮(nmol/L)",
        "皮质醇(μg/dL)",
        "尿素(mmol/L)",
        "肌酸激酶(U/L)",
        "LDH(U/L)",
        "QC状态",
        "备注",
    ]
    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="13443E")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill

    for sample, part in rows:
        ws.append(
            [
                sample.visit_id,
                sample.participant_id,
                part.group_name or "",
                TP_LABELS.get(sample.timepoint, sample.timepoint),
                sample.collection_time.strftime("%Y-%m-%d %H:%M")
                if sample.collection_time
                else "",
                sample.testosterone_raw or "",
                sample.testosterone_value,
                sample.cortisol_ug_dL,
                sample.urea_mmol_L,
                sample.creatine_kinase_U_L,
                sample.ldh_U_L,
                sample.review_status or "",
                sample.review_note or "",
            ]
        )

    widths = [16, 14, 12, 12, 18, 12, 14, 14, 14, 16, 12, 14, 28]
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + idx)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=blood_samples.xlsx"},
    )

