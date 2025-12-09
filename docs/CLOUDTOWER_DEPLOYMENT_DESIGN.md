# CloudTower 部署设计

> **许可证**：本文档依据 [GNU GPLv3](../LICENSE) 授权发布。

## 背景与目标

CloudTower 是 SmartX 集群的集中管理与运维控制面。`deploy_cloudtower`、`attach_cluster`、`cloudtower_config` 等阶段负责从规划表抽取信息，自动化完成 CloudTower 的部署、初始化配置与与集群的互联。本设计文档用于指导后续实现真实 API 调用逻辑，并对接现有的阶段调度框架。

## 范围

- 覆盖 CLI & Web 触发的自动化流程。
- 详细描述 ISO 上传、虚拟机创建、安装、网络配置、脚本执行、后置验证与配置步骤。
- 明确失败重试、日志记录、上下文共享（`ctx.extra`）的策略。
- 不直接包含 UI 流程，但需输出足够的接口以供前端显示进度。

## 输入与前置条件

### 规划表字段

| Sheet | 字段 | 说明 |
|-------|------|------|
| 集群管理信息 | Cloudtower IP | 部署完成后 CloudTower 的管理地址 |
| 集群管理信息 | Cloudtower 虚拟机名称 | 用于平台上的虚拟机命名，全小写，不修改guest os 内部hostname|
| 集群管理信息 | Cloudtower 管理员密码 | 安装完成后初始管理员密码，必须与安全策略匹配 |
| 文档描述 | Cloudtower 组织名称 | 后续配置阶段使用 |（位于规划表“文档描述”Sheet，C15单元格，默认值 SMTX-HCI）

### 运行环境

- SmartX API 访问凭证：`x-smartx-token` 通过api示例中的## 登录fisheye获取token方法获取。
- ISO 介质：可通过根目录已存在的 `cloudtower-<version>.<os>.<arch>.iso`，若不存在则提示不存在，中止部署流程。
- Python 依赖按 `requirements.txt` 安装（需包含 `requests`, `tenacity`, `pydantic` 等模块）。

## 总体流程概览
```
    开始
        │
        ▼
    验证规划表字段
        │
        ▼
    前置校验（ISO、资源、网络）
        │
        ▼
    ISO 上传 ──► chunk分片上传失败重试三次，如果仍然失败，删除该上传卷，重新创建上传卷并上传（重试一次）
        │
        ▼
    虚拟机创建与资源分配 ──► 失败重试三次，如果仍然失败，中止部署
        │
        ▼
    启动安装与自动化交互
        │
        ▼
    配置网络与执行安装脚本 ──► 失败回滚
        │
        ▼
    安装完成验证与基础配置 ──► 失败回滚
        │
        ▼
      输出结果
```

CloudTower 部署阶段内部细分：

1. 前置校验与上下文准备。
2. cloudtower ISO 上传（创建上传卷、分片上传、失败回滚）。
3. 虚拟机创建与资源分配（包含等待 Guest OS 与 VMTools 可用）。
4. 启动安装、监控进度与自动化交互（SSH读取屏幕打印或后台日志）。
5. 安装完成验证与基础配置（管理员密码、网络、服务状态）。
6. 输出结果供后续阶段使用（IP、序列号、任务日志路径）。

> **说明**：若场景需要 VMTools（SVT）镜像，可在 `config_cluster` 阶段按《[config_cluster 阶段设计](CONFIG_CLUSTER_DESIGN.md)》执行上传；CloudTower 部署流程本身不依赖该步骤，缺省情况下可直接跳过。

## 详细设计

### 1. 前置校验

- 确认 `ctx.plan` 中 CloudTower 相关字段可用，缺失时记录 warning 并进入失败分支。
- 校验 ISO 是否存在；若需在线下载，先调用离线包准备脚本或预留下载逻辑。
- 读取部署配置（CPU/内存/磁盘大小、目标主机），可允许在 `default.yml` 中提供默认值。
- 预先拉取宿主机资源信息（cpu/mem 使用率）以判断可部署性。
- 当以“仅部署 CloudTower”模式运行时（仅选择 `prepare`+`deploy_cloudtower`），会通过 `_verify_existing_cluster_services` 触发 Fisheye 登录测试；若 401，则 `_refresh_fisheye_token` 会尝试使用规划表凭证刷新 token。

### 2. ISO 上传流水线

| 步骤 | 接口 | 关键参数 | 说明 |
|------|------|----------|------|
| 2.0 查询已存在 ISO | `GET /api/v2/images` | `name`（可选自定义查询参数） | 若存在同名同大小且包含 `path` 的镜像，则复用并跳过上传 |
| 2.1 创建上传卷 | `POST /api/v2/images/upload/volume` | `size`, `device`, `name`, `task_id` | 返回 `image_uuid`, `zbs_volume_id`, `chunk_size`, 初始 `to_upload` |
| 2.2 分片上传 | `POST /api/v2/images/upload` | `image_uuid`, `zbs_volume_id`, `chunk_num` | 使用 `multipart/form-data` 上传二进制块；根据 `chunk_size` 切片 |
| 2.3 失败回滚 | `DELETE /api/v2/images/{image_uuid}` | `image_uuid` | 上传失败时删除上传卷，支持一次重试 |

实现细节：

- `_find_existing_cloudtower_iso` 会在上传前调用 `GET /api/v2/images`，并依据名称与文件大小比对；若响应中包含有效的 `uuid` 与 `path`，则复用已有镜像并写入 `ctx.extra['deploy_cloudtower']['iso']`，后续挂载逻辑无需重新上传。必要时可通过 `cloudtower.extra_image_query_params` 传入服务端特定的过滤参数（例如自定义状态或分页设置）。
- `_create_cloudtower_upload_volume` 会根据 `cloudtower.extra_volume_params` 补充查询参数，日志记录可发现 `device`、`chunk_size`、`to_upload` 等关键信息。
- `_upload_cloudtower_iso_chunks` 使用流式读文件并维护 SHA256 校验、上传速率、剩余时间估算；`progress_extra` 中会输出 `progress_percent` 与 `speed_bps`，便于前端展示实时进度。
- 若任意分片上传失败，会抛出异常并由调用方触发 `_cleanup_upload_volume` 删除上传卷，避免遗留脏数据。
- `_build_base_headers` 始终为 Fisheye API 请求附加 `x-smartx-token` 与 `host` 头部；`APIClient` 在底层也会根据 `base_url` 自动补齐 `host`，确保即便个别调用未显式传入，也不会因缺少 Host 头导致接口报错。

实现要点：

- 采用 `tenacity` 提供的退避重试策略（每个分片最多 3 次）。
- 记录每个分片的 `chunk_num` 与 SHA256 校验码，便于断点续传。
- `to_upload` 字段用于驱动下一轮上传；当服务端返回空数组时表示上传完成。
- 上传完成后将 `image_uuid`、`zbs_volume_id` 持久化到 `ctx.extra['deploy_cloudtower']['iso_upload']`，供后续挂载。必要时将进度写入 `logs/stage_deploy_cloudtower.log`。

### 3. CloudTower 虚拟机创建

1. `_query_storage_policy_uuid`：调用 `/api/v2/storage_policies` 获取策略列表；若返回 401，会尝试使用规划表中 Fisheye 凭据刷新 token 后重试一次。
2. `_resolve_vds_details`：调用 `/api/v2/network/vds` 根据名称匹配 VDS，提取 `uuid` 与 `ovsbr_name`。
3. `_resolve_vlan_uuid`：调用 `/api/v2/network/vds/{vds_uuid}/vlans`，优先按 VLAN 名称匹配，其次按 ID 匹配。
4. `_create_cloudtower_vm`：向 `/api/v2/vms` 提交创建请求，负载包含 vCPU、内存、磁盘、NIC、CD-ROM 等完整配置；接口返回 `job_id` 与可选的 `vm_uuid`。
5. `_poll_cloudtower_job`：轮询 `/api/v2/jobs/{job_id}` 直至状态进入 `done`/`success`，并记录状态流转。
6. `_wait_for_vm_guest_agent_ready`：轮询 `/api/v2/vms/{vm_uuid}`，仅依据 `guest_info.ga_state`（要求 `ga_state == Running`，保留 `ga_version` 仅用于记录）判断 Guest Agent 是否就绪，随后才能下发网络配置。
7. `_fetch_vm_primary_mac`：查询 `/api/v2/vms/{vm_uuid}` 获取首个 NIC 的 MAC 地址。
8. `_configure_vm_network_configuration`：调用 `PUT /api/v2/vms/{vm_uuid}` 更新 `nics` 配置，触发后台任务后再轮询直至完成。

所有步骤的进度均通过 `create_stage_progress_logger` 输出，确保 CLI 与 Web UI 能收到结构化日志。

### 4. 安装与自动化交互

- `_install_and_verify_cloudtower_services` 负责通过 SSH 执行部署脚本：
    - `_create_ssh_client_and_connect` 载入 `paramiko` 创建连接，支持自定义端口、超时与凭据。
    - `_run_sudo_command` 依次执行 `/usr/share/smartx/tower/preinstall.sh` 与安装器启动命令，后台命令也会记录日志。
    - `_wait_for_installation_success` 定期读取 `nohup.out`（首次读取允许 3 分钟缓冲期），抓取成功关键字 `Install Operation Center Successfully`。
- SSH 会话结束后调用 `_verify_cloudtower_https_port` 轮询 443 端口可达性（3 次重试，间隔 10 秒），确认服务启动。

### 5. 安装完成验证

安装完成后执行 `_configure_cloudtower_post_install`：

1. `_resolve_cloudtower_setup_inputs` 整理组织、数据中心、NTP、DNS、集群凭据等参数，来源依次为规划表、解析结果、`default.yml`。
2. `_cloudtower_create_root_user`、`_cloudtower_create_organization`、`_cloudtower_check_setup`：通过 GraphQL 接口初始化 root 用户与组织。
3. `_cloudtower_login`：调用 `/v2/api/login` 获取后续 REST 调用所需的 token。
4. `_cloudtower_update_ntp`：根据需要更新 NTP 服务；DNS 会通过 `_update_cloudtower_dns_via_ssh` 写入 `/etc/resolv.conf`。
5. `_cloudtower_query_license`：查询部署许可证信息，便于后续阶段判断功能可用性。

所有结果与输入会存入上下文，以 JSON 结构输出给后续阶段。

### 6. 后续阶段接口

`ctx.extra['deploy_cloudtower']` 会写入如下结构，`attach_cluster` 与 `cloudtower_config` 阶段可直接复用：

- `status`: CloudTower 服务状态标识（当前为 `SERVICE_READY`）。
- `ip` / `base_url`: Web 控制台访问地址。
- `iso`: 上传卷摘要（`image_uuid`, `sha256`, `uploaded_chunks`）。
- `vm`: 虚拟机摘要（`name`, `uuid`, `storage_policy_uuid`, `os_version`, `guest_agent_state`）。
- `network`: 管理网络信息（`ip`, `gateway`, `subnet_mask`, `vds_uuid`, `vlan_uuid`）。
- `cloudtower`: 初始化后的组织、会话 token、NTP/DNS/License 结果等。

若阶段挂载失败或发生异常，日志会包含 `error` 字段，并且不会写入 `status`，以便上游感知失败并中止流程。

## 错误处理与回滚

| 场景 | 处理措施 |
|------|----------|
| 创建上传卷失败 | 直接失败，提示检查磁盘资源 |
| 分片上传失败超过重试次数 | 删除上传卷，重新创建并重传一次；若仍失败，阶段失败 |


所有失败路径需调用 `stage_logger.error` 输出详细上下文，并保证返回的异常被 stage manager 捕获。

## 日志与可观测性

- 使用 `create_stage_progress_logger` 输出结构化日志，字段包含 `step`, `chunk_num`, `vm_uuid`, `elapsed` 等。
- 上传阶段可额外将进度写入 `logs/upload_cloudtower.json`，便于 Web 前端实时展示百分比。
- SSH 命令输出保存至 `logs/cloudtower_install_<timestamp>.log`。
- 若启用 debug 模式，将每个 API 请求与响应摘要写入调试日志（注意脱敏 token）。

## 安全性考虑

- 管理员密码与 token 只存放于内存，日志中以 `机密凭据` 替换。
- 上传 ISO 时校验文件 SHA256，以防止损坏或被篡改。
- SSH 会话完成后立即销毁密钥材料。
- 若用户要求，可在部署完成后删除 ISO 上传卷与中间镜像文件。

## 测试策略

1. **单元测试**：
   - 为 ISO 上传逻辑编写 mock 测试，验证分片重试、回滚路径。
   - 为 Job 轮询实现编写超时、失败、成功三种分支的测试。
2. **集成测试（mock 模式）**：
   - 扩展现有 mock API，模拟 CloudTower 安装的 job/state 机。
   - 在 `tests/test_workflow_stages.py` 中新增 `deploy_cloudtower` 场景。
3. **离线模式验证**：
   - 借助 `scripts/test_build_payload.py` 构造最小上下文，验证 iso 文件路径、上下文输出结构。
4. **验收测试**：
   - 在实验环境运行真实 API，验证全流程耗时 < 45 min，日志可追踪。

## 待定与后续工作

- 确认 SmartX API 中 CloudTower VM 创建与安装的具体端点及字段命名。
- 设计 Web UI 进度条映射（例如上传百分比、安装阶段）。
- 明确序列号写回 Excel 的具体格式与位置。
- 补充 CloudTower 巡检接口集成文档。

