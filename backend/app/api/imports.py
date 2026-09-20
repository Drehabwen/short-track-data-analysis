# -*- coding: utf-8 -*-
"""数据导入 API：种子数据 + 上传 CSV。"""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.importer import import_visits_csv

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/seed")
def import_seed(
    db: Session = Depends(get_db)
):
    """导入打包内的校准数据（blood_visits_curated.csv），幂等。"""
    result = import_visits_csv()
    return result


@router.post("/csv")
async def import_csv(
    file: UploadFile = File(...)
):
    """上传自定义 CSV（需与 curated 列结构一致）。"""
    import tempfile
    from pathlib import Path

    suffix = Path(file.filename or "upload.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = import_visits_csv(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return result

