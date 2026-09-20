# M1 里程碑：工程与数据地基

> 对应 PRD 第 15 节 M1；验收标准：干净环境可按文档完成安装、迁移和启动。
> 前置确认见 `docs/PRD_CONFIRMED_DECISIONS.md`（10 项决策已定稿）。

## 1. 本里程碑交付

| # | 交付项 | 说明 |
|---|--------|------|
| 1 | 目录整理 | 源码/数据/生成物分离；新增 `data/archive/`（原始文件只读归档，决策 4）、`data/backups/`（备份保留近 10 份，决策 8） |
| 2 | .gitignore | 补全测试产物（`.pytest_cache`/`coverage`）与备份归档目录 |
| 3 | 正式数据库 | **PostgreSQL 18.4**（`C:\pgsql18`，库 `blood_analysis`）确认为正式库；SQLite 仅打包版兜底（config.py FROZEN 分支不变） |
| 4 | 数据库迁移 | 引入 Alembic；两个迁移：`0001` legacy 基线、`0002` Phase 1 新模型 |
| 5 | 项目与数据字典模型 | `ResearchProject` / `MeasureDefinition` / `Observation`（长表）；`Participant` 增加 `project_id` |
| 6 | 数据字典种子 | 11 项指标（血液 5 + 体成分 6 占位），带来源/适用人群/版本日期/LOD/单位换算 |
| 7 | 配置外置 | 沿用已有 .env 机制（JWT_SECRET / DATABASE_URL 均可外置，上一版本已完成） |

## 2. 数据库变更（迁移）

| 迁移 | 版本 | 内容 |
|------|------|------|
| `0001` | `0d3789d85228` | legacy 全量表基线（18 张，与旧 `create_all` schema 一致，含 surveys 系列） |
| `0002` | `1c463cb96558` | 新增 `research_projects` / `measure_definitions` / `observations`；`participants` 增加 `project_id` 列（nullable，FK 显式命名 `fk_participants_project_id`） |

### 迁移命令

```powershell
cd backend
# 干净环境：一键建全库
.\venv\Scripts\alembic.exe upgrade head
# 存量库（已有 create_all 旧表）首次接入：
.\venv\Scripts\alembic.exe stamp 0d3789d85228
.\venv\Scripts\alembic.exe upgrade head
# 生成新迁移（模型变更后）
.\venv\Scripts\alembic.exe revision --autogenerate -m "描述"
# 回滚到上一版本
.\venv\Scripts\alembic.exe downgrade -1
```

> 注意：`main.py` 启动时的 `create_all` 保留（幂等，仅补缺失表），但**所有正式 schema 变更一律走 Alembic 迁移**（PRD 执行规则 4）。

## 3. 新增模型（`backend/app/models.py`）

- **ResearchProject**：`slug`（唯一，用于数据版本号 `project-slug/YYYYMMDD.major.minor`）、`name`、`study_design`、`is_archived`（归档后只读，FR-01）。
- **MeasureDefinition**：数据字典；参考区间带 `reference_source` / `reference_population` / `reference_version` 元数据（决策 6）；`lod_value` + `lod_rule`（决策 7：`censored_is_normal` = 低于 LOD 视为正常低值、不参与数值统计）；`unit_conversions` JSON（允许单位→标准单位换算系数，PRD 第 8 节）。
- **Observation**：正式分析长表（每行 = 项目 + 参与者编码 + 指标 + 时间点）；`qualifier`/`value_text` 保留 `<` 值原文；`source_batch_id`/`source_row` 可追溯来源（M2 接入 ImportBatch）；`qc_status`/`is_excluded` 支撑数据质量（FR-04/05）。
- **Participant**：新增 `project_id`（nullable，legacy 数据为 NULL）；同一编码可在不同项目分别存在（FR-01 验收，M2 起按项目隔离；项目内唯一约束在 M2 处理）。

## 4. 数据字典种子（`backend/scripts/seed_measures.py`）

幂等 upsert，用法：`cd backend && .\venv\Scripts\python -m scripts.seed_measures`

- 血液 5 项：睾酮（LOD 0.0868 nmol/L，`censored_is_normal`）、皮质醇、尿素、CK、LDH——参考区间沿用现有校准数据。
- 体成分 6 项：身高、体重、BMI、体脂率、骨骼肌量、去脂体重——**仅字典占位**，数值待设备样例灌入（决策 2）。
- 全部指标：`reference_source="现有校准数据/教练组"`、`reference_version="2026-08-17"`（决策 6 占位，后续可替换为文献出处并走审计）。

## 5. 验收结果（2026-08-25 实测）

- [x] 干净空库 `alembic upgrade head`：21 张表全建成功；
- [x] `0002` upgrade / downgrade / 再 upgrade 往返通过（FK 显式命名后 downgrade 不再报错）；
- [x] 存量正式库 `stamp 0001 → upgrade head`：3 新表 + `participants.project_id` 建出，命名 FK 就位，**数据完好（93 participants / 162 samples）**；
- [x] 后端 `from app.main import app` 导入成功，`create_all` 幂等不冲突；
- [x] 数据字典种子首跑新增 11 条、重跑 0 新增（幂等）。

## 6. 已知限制 / 后续

- `Participant.participant_id` 目前仍全局唯一；项目内唯一约束（FR-01）待 M2 项目管理时以迁移实现。
- `Observation.project_id` 为 nullable：M2 导入链路强制绑定项目后收紧。
- 体成分参考区间与合理范围待设备样例确认后补齐。
- `samples` 宽表保留给 legacy 功能（仪表盘/追踪），新数据走 `observations` 长表；数据转写迁移在 M2/M3 排期。
