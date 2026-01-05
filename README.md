# CXVoyager

> **许可证**：本项目依据 [GNU GPLv3](LICENSE) 授权发布，使用或分发时请遵守许可条款。

CXVoyager 是一个端到端部署引擎，结合规划表、CloudTower API 与 SmartX 管理接口，自动完成规划解析、集群初始化、配置、服务部署与验证流程，目标是让运维团队以最少的人工干预交付 SmartX SMTX 集群。

## 快速开始

- **Windows**：PowerShell 运行 `start-windows.ps1`
- **macOS**：终端运行 `start-macos.command`
- **Linux**：`chmod +x start-linux.sh && ./start-linux.sh`
- **SMTXOS**：`chmod +x start-smtxos.sh && ./start-smtxos.sh`（详见 [docs/USAGE_SMTXOS.md](docs/USAGE_SMTXOS.md)）

### 运行要求

- Python 3.10+
- 规划表置于项目根目录，文件名需包含“SmartX超融合”“规划设计表”“ELF环境”等关键词
- 无外网环境可运行 `scripts/prepare_offline_installation_packages.py` 生成所需依赖包

## 架构概览

CXVoyager 采用领域划分的模块化架构：

- **core/**：部署阶段、运行上下文与进度管理
- **integrations/**：Excel、SmartX、CloudTower 等外部系统适配
- **common/**：配置、并行、日志、网络等基础设施
- **interfaces/**：CLI、Web 与 API 接口实现
- **models/**：共享类型与数据定义

详细架构请参考 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 部署阶段速览

执行引擎围绕 15 个阶段组织，不同阶段通过 `Stage` 枚举与能力映射文档 `core/deployment/stage_capabilities.yml` 协调：

- **STEP 01 PREPARE_PLAN_SHEET**：解析规划表并进行网络/IP 校验
- **STEP 02 INIT_CLUSTER**：触发 SmartX 集群部署并采集主机扫描
- **STEP 03 CONFIG_CLUSTER**：登录 Fisheye 配置 VIP、网络、密码与镜像
- **STEP 04 DEPLOY_CLOUDTOWER**：上传 CloudTower ISO、创建 VM 并启动安装
- **STEP 05 ATTACH_CLUSTER**：将部署的集群接入 CloudTower
- **STEP 06 CLOUDTOWER_CONFIG**：配置 NTP/DNS/策略/镜像等 CloudTower 高阶功能
- **STEP 07 CHECK_CLUSTER_HEALTHY**：生成健康报告与治理建议
- **STEP 08-12 DEPLOY_*（OBS/BACKUP/ER/SFS/SKS）**：依序上传 Observability、Backup、ER、SFS、SKS 镜像
- **STEP 13 CREATE_TEST_VMS**：创建测试虚机并验证网络、存储连通性
- **STEP 14 PERF_RELIABILITY**：性能测试与容灾验证
- **STEP 15 CLEANUP**：归档日志、清理缓存与收尾

更多阶段细节见 `docs/Step_XX-*.md`。

## CLI 使用指南

- 进入交互主菜单：`python -m cxvoyager` 或 `python main.py`
- 解析规划表：`python -m cxvoyager parse`
- 跳过扫描校验：`python -m cxvoyager check --no-scan`
- 按阶段执行：`python -m cxvoyager run --stages prepare,init_cluster --dry-run`
- 交互部署：`python -m cxvoyager deploy`
- 列出可选阶段：`python -m cxvoyager stages-list`
- 英文界面：`CXVOYAGER_LANG=en_US python -m cxvoyager`

### CLI 调试选项

- `--debug`：打开 DEBUG 级别日志
- `--strict-validation`：更严格的规划表/阶段校验
- `--dry-run`：模拟执行并输出参数与阶段决策，不触发 API

## Web 控制台

FastAPI + SPA 提供了可视化的部署控制台，相关设计与计划整理在 [docs/web_frontend_design.md](docs/web_frontend_design.md)。

### 快速启动

```bash
uvicorn cxvoyager.interfaces.web.web_server:app --reload --port 8000
```

- 默认访问 http://localhost:8000/；`/ui` 会自动重定向到主页面。
- `/docs` 暴露 OpenAPI 文档，主要接口包括 `POST /api/run`、`GET /api/tasks`、`POST /api/tasks/{id}/abort` 等。
- 前端会定期轮询 `/api/tasks` 以及 `/api/stages`，展示任务卡片、阶段计划与全局进度。
- 任务记录持久化在 `logs/web_tasks.json`，服务重启后可恢复历史任务。

### 关键组件

- `cxvoyager/interfaces/web/web_server.py`：FastAPI 工厂函数，挂载 API 路由与静态资源目录。
- `cxvoyager/interfaces/web/routers/deployment_routes.py`：处理任务提交、状态查询、终止与阶段能力元数据。
- `cxvoyager/interfaces/web/task_scheduler.py`：调度线程池、持久化 `TaskRecord` 与管理 `TaskManager`。
- `cxvoyager/interfaces/web/static/`：SPA 资源（`index.html`、`assets/app.js`、`styles.css`、`progress-feed.js`）。
- `cxvoyager/core/deployment/stage_capabilities.yml`：为 Web 前端 `GET /api/stages` 提供阶段依赖、产出与自动注入规则。

## 规划表说明

规划表是部署的唯一输入，文件名需包含“SmartX超融合”“规划设计表”“ELF环境”等关键词。重要 Sheet：

- **虚拟网络**：管理/存储/业务等网络划分
- **主机规划**：管理、生产、BMC、SSH 等地址与凭据
- **集群管理信息**：CloudTower API 地址与 Token 或用户名/密码

字段坐标与解析逻辑详见 [接口示例文件/规划表字段坐标.md](接口示例文件/规划表字段坐标.md)。

### 验证细节

- CIDR 合法性与重叠检测
- VIP 与管理 IP 冲突校验
- IPv6/IPv4 兼容性提示
- 绑定模式映射（`active-backup` → `ACTIVE_BACKUP`）

## 离线安装

无外网时：

1. 运行 `scripts/prepare_offline_installation_packages.py` 准备依赖包
2. 在交互菜单选择“安装依赖（离线包）”

## 更多文档

- [架构设计](docs/ARCHITECTURE.md)
- [CloudTower 部署设计](docs/CLOUDTOWER_DEPLOYMENT_DESIGN.md)
- [集群配置设计](docs/CONFIG_CLUSTER_DESIGN.md)
- [阶段详细文档](docs/INDEX.md)
- [使用指南（Windows）](USAGE_WINDOWS.md)、[Linux](USAGE_LINUX.md)、[macOS](USAGE_MACOS.md)

