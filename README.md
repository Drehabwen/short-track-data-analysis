# SpeedTrack Pro｜短道速滑训练数据分析

面向短道速滑教练的本地训练复盘与科研分析工作台。前端运行在 `localhost:3000`，后端运行在 `localhost:8000`，业务数据由本地数据库保存。

> **隐私说明：** 本仓库只发布可审查源码，不含真实运动员姓名、血液/心率/体能/比赛数据、`blood.db`、Excel/CSV、医学报告、安装包或内部种子数据。请只导入已获授权并完成合规处理的数据。

> **v1.1（短道速滑定制版）**：新增登录与三角色权限（管理员/教练/运动员）、运动员管理、指标参考区间与超标统计、运动员个人数据页。

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Next.js 15 (React 19) + ECharts（本地打包） |
| 后端 | FastAPI + SQLAlchemy + JWT 认证 |
| 数据库 | PostgreSQL（开发）/ SQLite（桌面打包版） |
| 统计 | scipy（Friedman / Kruskal-Wallis / Wilcoxon + Holm / Spearman） |

## 源码启动

首次运行先准备环境：

```powershell
Copy-Item .env.example .env
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
cd ..\frontend
npm install
```

请编辑根目录 `.env`，设置数据库密码和随机 `JWT_SECRET`。随后从仓库根目录运行：

```
.\start.ps1      # 一键启动（PG + 后端 + 前端，自动打开浏览器）
.\stop.ps1       # 停止前后端（PG 保留）
```

- 前端界面：http://localhost:3000
- API 文档：http://localhost:8000/docs

## 本地演示账号

执行 `python -m scripts.init_db` 时会创建以下本地演示账号。它们仅用于开发验证，首次部署后必须修改密码。

| 角色 | 账号 | 密码 |
|------|------|------|
| 管理员（全部权限） | admin | admin123 |
| 教练（录入+查看+编辑） | coach | coach123 |
| 运动员（仅看自己的数据） | athlete | athlete123 |

登录页有快捷登录按钮。首次部署后请修改默认密码。

## 角色权限

| 功能 | 管理员 | 教练 | 运动员 |
|------|--------|------|--------|
| 总览仪表盘（团队） | ✅ | ✅ | 只显示个人 |
| 个体追踪（全部） | ✅ | ✅ | 仅自己 |
| 组别对比/科研统计 | ✅ | ✅ | — |
| 运动员管理（CRUD） | ✅ | ✅ | — |
| 血液数据（查看） | ✅ | ✅ | — |
| 血液数据（编辑/导入） | ✅ | ✅ | — |

## 目录结构

```
├── start.ps1 / stop.ps1       # 启动/停止脚本
├── backend/                   # FastAPI 后端
│   ├── app/
│   │   ├── main.py            # 应用入口
│   │   ├── config.py          # 配置（数据库连接等）
│   │   ├── models.py          # ORM 模型（participants/samples/research_projects/observations...）
│   │   ├── api/               # 路由（总览/追踪/统计/数据管理/导入）
│   │   └── services/          # 统计引擎 + CSV 导入
│   ├── alembic/               # 数据库迁移（0001 legacy 基线 / 0002 Phase1 模型）
│   ├── scripts/init_db.py     # 建表 + 导入种子数据
│   └── .venv/                 # Python 虚拟环境
├── frontend/                  # Next.js 前端
│   ├── app/                   # 四个页面
│   │   ├── page.jsx           # 总览仪表盘
│   │   ├── tracking/          # 个体追踪
│   │   ├── groups/            # 组别对比（科研）
│   │   └── data/              # 数据管理
│   ├── components/            # Sidebar / ECharts 封装
│   └── lib/api.js             # API 客户端
└── Academic/outputs/...       # 原始校准数据（导入源）
```

## 数据库

- 连接：`postgresql+psycopg://postgres:postgres123@localhost:5432/blood_analysis`
- 初始化：`cd backend && .\.venv\Scripts\python scripts\init_db.py`
- 私有种子数据不在本仓库中；初始化脚本在找不到种子文件时会安全跳过数据导入
- PostgreSQL 本体：`C:\pgsql18`（免安装 zip 版，initdb 初始化于 `C:\pgsql18\data`）
  - 启动：`C:\pgsql18\pgsql\bin\pg_ctl.exe -D C:\pgsql18\data -l C:\pgsql18\pg.log start`
  - 停止：`C:\pgsql18\pgsql\bin\pg_ctl.exe -D C:\pgsql18\data stop`

## 数据库迁移（Phase 1）

所有正式 schema 变更通过 Alembic 迁移完成（见 `docs/M1_ENGINEERING_FOUNDATION.md`）：

```powershell
cd backend
.\venv\Scripts\alembic.exe upgrade head        # 干净环境：建全库
.\venv\Scripts\alembic.exe stamp 0d3789d85228  # 存量库（已有旧表）首次接入时先 stamp 基线
.\venv\Scripts\alembic.exe upgrade head
```

## 数据字典（Phase 1）

数据字典（11 项指标，含来源/版本/LOD）种子脚本，幂等可重跑：

```powershell
cd backend
.\venv\Scripts\python -m scripts.seed_measures
```

Phase 1 关键文档：`docs/PRD_PHASE1_RESEARCH_DATA_FOUNDATION.md`（PRD）、`docs/PRD_CONFIRMED_DECISIONS.md`（开工前 10 项决策确认）、`docs/M1_ENGINEERING_FOUNDATION.md`（M1 里程碑记录）。

## 功能

**教练端**
- 总览仪表盘：全队状态、时间点/组别/性别分布、异常预警（CK 偏高 / T/C 比值偏低 / 待复核）
- 个体追踪：单运动员五指标三时间点趋势、T/C 比值、自动恢复评估

**科研端**
- 组别对比：三组（常规恢复/拔罐+推拿/艾灸+推拿）× 三时间点 Kruskal-Wallis
- 纵向检验：Friedman + Wilcoxon 配对（Holm 校正）
- 相关分析：指标间 Spearman ρ

**数据管理**
- 血样查询与筛选、人工修正数值与 QC 状态、内置校准数据导入（幂等）

## 新数据导入

1. 后端 API `POST /api/import/csv`：上传符合字段规范的 CSV
2. 内部分发版可通过数据管理页导入已授权的本地数据
3. 导入前请完成去标识化、访问授权和备份

## 注意

- `.env.example` 中的密码和密钥均为占位符，部署前必须替换
- 统计中睾酮低于检测限（`<0.0868`）的值按 censored 处理，不参与数值统计
