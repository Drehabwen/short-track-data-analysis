# -*- coding: utf-8 -*-
"""应用配置：数据库连接、常量。本地部署，数据不出网。"""
import os
import sys
from pathlib import Path

# 轻量 .env 加载（优先环境变量；无 python-dotenv 依赖）
def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        # 已存在的环境变量优先，.env 不覆盖
        if key and key not in os.environ:
            os.environ[key] = val

# PyInstaller 打包（onefile）下：可写数据放 exe 同目录，只读资源在解包目录
FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(sys._MEIPASS)
else:
    APP_DIR = Path(__file__).resolve().parent.parent.parent
    RESOURCE_DIR = APP_DIR

_load_dotenv(APP_DIR / ".env")

# 数据库连接：默认本地 PostgreSQL，支持环境变量 / .env 覆盖
# 打包版默认使用 exe 同目录的 SQLite（零依赖）
if FROZEN:
    _default_db_url = f"sqlite:///{(APP_DIR / 'blood.db').as_posix()}"
else:
    _default_db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres123@localhost:5432/blood_analysis",
    )

DATABASE_URL = os.getenv("DATABASE_URL", _default_db_url)

# JWT 认证配置：密钥优先从环境变量 / .env 读取，开发默认值仅作兜底
JWT_SECRET = os.getenv("JWT_SECRET", "local-dev-secret-blood-analysis-2026")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "720"))  # 12 小时

# 项目根目录：打包版为 exe 同目录（持久化数据），开发版为 backend 的上一级
ROOT_DIR = APP_DIR

# 数据导入源目录（打包版从内置资源读取校准数据）
if FROZEN:
    SEED_DIR = RESOURCE_DIR / "seed"
else:
    SEED_DIR = ROOT_DIR / "Academic" / "outputs" / "clean_analysis_2026-07-21"

# 上传文件保存目录
UPLOAD_DIR = ROOT_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 检出限常量（用于 < 值）
TESTOSTERONE_LOD = 0.0868  # nmol/L

# 时间点定义
TIMEPOINTS = ["BL", "24H", "72H"]
TIMEPOINT_LABELS = {"BL": "训练前", "24H": "24小时后", "72H": "72小时后"}

# 指标定义：列名 -> (中文名, 单位)
ANALYTES = {
    "testosterone_value": ("睾酮", "nmol/L"),
    "cortisol_ug_dL": ("皮质醇", "μg/dL"),
    "urea_mmol_L": ("尿素", "mmol/L"),
    "creatine_kinase_U_L": ("肌酸激酶 CK", "U/L"),
    "ldh_U_L": ("乳酸脱氢酶 LDH", "U/L"),
}

# 组别定义
GROUPS = ["常规恢复", "拔罐+推拿", "艾灸+推拿"]
