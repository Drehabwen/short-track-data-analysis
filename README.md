# 短道速滑运动员血液数据分析平台

本地部署的运动员训练监控与科研分析工作台。**数据不出网**——所有数据存储在本机 PostgreSQL，前端图表库本地打包，无任何外部请求。

> **v1.1（短道速滑定制版）**：新增登录与三角色权限（管理员/教练/运动员）、运动员管理、指标参考区间与超标统计、运动员个人数据页。

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Next.js 15 (React 19) + ECharts（本地打包） |
| 后端 | FastAPI + SQLAlchemy + JWT 认证 |
| 数据库 | PostgreSQL 18（本地 zip 版，`C:\pgsql18`） |
| 统计 | scipy（Friedman / Kruskal-Wallis / Wilcoxon + Holm / Spearman） |

## 快速启动

```
.\start.ps1      # 一键启动（PG + 后端 + 前端，自动打开浏览器）
.\stop.ps1       # 停止前后端（PG 保留）
```

- 前端界面：http://localhost:3000
- API 文档：http://localhost:8000/docs

## 登录账号（演示）

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
- 数据源：`Academic/outputs/clean_analysis_2026-07-21/blood_visits_curated.csv`（162 条校准记录：69 名运动员）
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

1. 数据管理页 → "导入内置数据"：重新导入打包内的校准 CSV
2. 后端 API `POST /api/import/csv`：上传符合 curated 列结构的 CSV
3. 未来：图片 OCR 提取（二期）

## 注意

- PostgreSQL 密码 `postgres123` 仅用于本地开发，正式部署请修改
- 统计中睾酮低于检测限（`<0.0868`）的值按 censored 处理，不参与数值统计
