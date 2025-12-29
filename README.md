# CXVoyager

> **许可证**：本项目依据 [GNU GPLv3](LICENSE) 授权发布，使用或分发时请遵守许可条款。

CXVoyager 是一个自动化工具，用于基于集群规划表完成 SmartX SMTX 集群的端到端部署和配置。它涵盖从规划表解析、集群初始化、CloudTower 部署与关联、业务应用部署到测试与清理的完整流程，旨在简化部署、减少错误并提高效率。

## 快速开始

- **Windows**：PowerShell 运行 `start-windows.ps1`
- **macOS**：终端运行 `start-macos.command`
- **Linux**：`chmod +x start-linux.sh && ./start-linux.sh`
- **SMTXOS** `chmod +x start-smtxos.sh && ./start-smtxos.sh`（详见 [USAGE_SMTXOS.md](USAGE_SMTXOS.md)）

### 运行要求

- Python 3.10+
- 规划表置于项目根目录，文件名包含“SmartX超融合”“规划设计表”“ELF环境”
- 无外网场景可提前准备离线包，或运行 `scripts/prepare_offline_packages.py` 下载

## 架构概述

CXVoyager 采用模块化架构，按领域分层组织代码：

- **core/**：业务核心逻辑，包括部署、集群管理和验证
- **integrations/**：外部系统适配器（SmartX API、Excel 解析、CloudTower）
- **models/**：数据模型定义
- **common/**：通用基础设施（配置、日志、工具函数）
- **interfaces/**：接口层（CLI、Web API）

详细架构请参考 [ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 部署阶段

CXVoyager 将部署流程分为 15 个阶段，每个阶段有明确的输入输出和目的。以下是阶段索引（详细文档见 `docs/Step_XX-*.md`）：

- **STEP 01 - PREPARE_PLAN_SHEET**：解析规划表并做验证与网络预检
- **STEP 02 - INIT_CLUSTER**：主机扫描、构建部署载荷并触发集群部署
- **STEP 03 - CONFIG_CLUSTER**：Fisheye 登录并配置集群 VIP/DNS/NTP 等
- **STEP 04 - DEPLOY_CLOUDTOWER**：上传 ISO、创建 CloudTower VM 并安装
- **STEP 05 - ATTACH_CLUSTER**：将集群接入 CloudTower
- **STEP 06 - CLOUDTOWER_CONFIG**：CloudTower 高阶配置（NTP/DNS/策略/镜像）
- **STEP 07 - CHECK_CLUSTER_HEALTHY**：调用巡检接口生成健康报告
- **STEP 08 - DEPLOY_OBS**：上传 Observability 包
- **STEP 09 - DEPLOY_BAK**：上传 Backup 包
- **STEP 10 - DEPLOY_ER**：上传 ER 包
- **STEP 11 - DEPLOY_SFS**：上传 SFS 包（需同步存储策略）
- **STEP 12 - DEPLOY_SKS**：上传 SKS 包
- **STEP 13 - CREATE_TEST_VMS**：创建测试虚机并验证连通性
- **STEP 14 - PERF_RELIABILITY**：执行性能基准与故障注入测试
- **STEP 15 - CLEANUP**：清理临时资源、归档日志

## CLI 使用

- 进入交互主菜单：`python -m cxvoyager` 或 `python main.py`
- 解析规划表：`python -m cxvoyager parse`
- 校验（跳过扫描）：`python -m cxvoyager check --no-scan`
- 按阶段执行：`python -m cxvoyager run --stages prepare,init_cluster --dry-run`
- 交互部署：`python -m cxvoyager deploy`
- 列出阶段：`python -m cxvoyager stages-list`
- 英文界面：设置 `CXVOYAGER_LANG=en_US`

### 调试选项

- `--debug`：启用 DEBUG 日志
- `--strict-validation`：严格校验模式
- `--dry-run`：预览模式，不实际执行

## 规划表说明

规划表是部署信息来源，需包含“SmartX超融合”“规划设计表”“ELF环境”关键词。关键 Sheet：

- **虚拟网络**：管理/存储/业务网络配置
- **主机规划**：集群主机信息
- **集群管理信息**：CloudTower 等管理平台信息

字段坐标和解析逻辑见 [规划表字段坐标.md](接口示例文件/规划表字段坐标.md)。

### 验证细节

- CIDR 合法性检查与重叠检测
- VIP 与管理地址冲突检查
- IPv6/IPv4 兼容性警告
- 绑定模式映射（active-backup -> ACTIVE_BACKUP 等）

## 离线安装

在无外网环境：

1. 联网准备：运行 `scripts/prepare_offline_packages.py`
2. 离线安装：交互菜单选择“安装依赖（离线包）”

## 更多文档

- [架构设计](docs/ARCHITECTURE.md)
- [CloudTower 部署设计](docs/CLOUDTOWER_DEPLOYMENT_DESIGN.md)
- [集群配置设计](docs/CONFIG_CLUSTER_DESIGN.md)
- [阶段详细文档](docs/INDEX.md)
- [使用指南](USAGE_WINDOWS.md) / [Linux](USAGE_LINUX.md) / [macOS](USAGE_MACOS.md)

