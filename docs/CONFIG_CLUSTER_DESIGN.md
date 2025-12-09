# config_cluster 阶段设计

> **许可证**：本文档依据 [GNU GPLv3](../LICENSE) 授权发布。

## 背景与目标

`config_cluster` 阶段用于在集群完成基础部署后，依据规划表自动完成集群级配置，包括管理平台初始化、网络与服务参数设置、业务虚拟交换机/网络创建、主机账号维护、序列号回填等。本设计同步纳入 VMTools（SVT）上传能力，让该组件在云管及其他后续阶段可复用，但 **不** 被视为 CloudTower 部署的硬性前置条件。

## 范围

- Typer CLI / Web 调度均复用同一阶段实现。
- 覆盖 Fisheye 管理员初始化与 token 获取、VIP/DNS/NTP 配置、IPMI 批量账号管理、业务 VDS + VLAN 创建、主机账号轮换、序列号采集与规划表写回。
- 新增 VMTools（SVT）离线镜像上传设计，提供接口流转、重试与回滚策略。
- 不涉及 CloudTower 虚拟机的上传/安装/配置（见《CloudTower 部署设计》）。

## 输入与前置条件

### 规划表字段

| Sheet | 字段 | 用途 |
|-------|------|------|
| 集群管理信息 | Fisheye 管理员用户名/密码 | 初始化 Fisheye 并获取 API token |
| 集群管理信息 | 管理 VIP | 配置 `/api/v2/settings/vip` |
| 集群管理信息 | DNS / NTP 服务器 | 配置 `/api/v2/settings/dns` 与 `/api/v2/settings/ntp` |
| 主机规划 | 带外地址、用户名、密码 | 组装 IPMI 批量配置载荷 |
| 虚拟网络 | 业务 VDS 名称、绑定网卡、VLAN/VIP | 构建 VDS 与业务网络创建载荷 |
| 云管理网络 | VMTools 上传所需宿主机、网络信息（如需在后续阶段下发） |
| 附件/文档描述 | 集群序列号写回位置（默认 `文档描述!C18`，可在 `field_variables.py` 中调整） |

> **假设**：若部分字段缺失，阶段会记录 warning 并跳过相应步骤；关键字段（如 Fisheye 密码）缺失时将直接失败。

### 运行环境

- SmartX API 基础地址、认证 token：
  - 优先读取 `ctx.config['api']`（可由 CLI 参数覆盖）。
  - 若 `deploy_verify` 输出中未包含真实 Base URL，则 `_resolve_deployment_base` 会回退到首个主机扫描结果。
- 规划表解析结果应在 `prepare` 阶段产出，`config_cluster` 可从 `ctx.extra['parsed_plan']` 直接复用；若缺失会按需重新解析。
- 若需上传 VMTools（SVT）镜像，ISO 文件应预置在项目根目录（默认 `SMTX_VMTOOLS-*.iso`），或在配置中指明路径；未提供时仅跳过上传步骤。

## 流程拆解

```
verify deploy -> init API client -> 解析规划表 ->
 1. 初始化 Fisheye 管理员
 2. 登录获取 token      \
 3. 配置 VIP/DNS/NTP     |=> 使用会话 token
 4. 批量配置 IPMI        /
 5. 创建业务 VDS          -> 若返回 job_id 则轮询获取 uuid
 6. 创建业务 VLAN        -> 校验 vlans_count
 7. 批量更新主机登录密码
 8. （可选）上传 VMTools (SVT)
 9. 获取集群序列号并回填规划表
```

下文对关键步骤作扩展设计说明。

### 1. Fisheye 管理员初始化与登录

| 接口 | 方法 | 用途 |
|------|------|------|
| `/api/v3/users:setupRoot` | POST | 初始化 root / smartx 管理员账号，若已初始化可返回错误，需记录 warning |
| `/api/v3/sessions` | POST | 使用上一接口设定的凭据登录，获取会话 token |

- 请求体：`{"username": "root", "password": "***", "encrypted": false}`。
- 日志中仅输出用户名与密码长度，避免泄露明文。
- 登录失败时，记录 warning 并提示人工处理；后续步骤若无 token，仍可使用配置中的 token（若存在）。

### 2. 管理 VIP / DNS / NTP 配置

| 接口 | 方法 | 载荷要点 |
|------|------|----------|
| `/api/v2/settings/vip` | PUT | `{"management_vip": "<vip>", "iscsi_vip": null}` |
| `/api/v2/settings/dns` | PUT | `{"dns_servers": ["1.1.1.1"]}` |
| `/api/v2/settings/ntp` | PUT | `{"ntp_mode": "external", "ntp_servers": ["ntp1"]}` |

- 若任一列表为空，阶段仅记录 warning 并继续。
- 配置失败不会立即终止，但会在结果集中标记 `warning`。

### 3. IPMI 批量账号配置

- 依据 Host 扫描（`ctx.extra['host_scan']`）提供的 UUID / Hostname 与规划表中的带外参数，构建 `accounts` 列表。
- 接口：`POST /api/v2/ipmi/upsert_accounts`。
- 响应中若部分失败，需在日志中标记告警并继续执行。

### 4. 业务 VDS 与网络创建

1. 调用 `POST /api/v2/network/vds` 创建业务虚拟交换机。
   - 载荷包含 `name`, `bond_mode`, `hosts_associated[{host_uuid, nics_associated[]}]`。
2. 若响应直接返回 `uuid`，保存并继续；如返回 `job_id`，调用 `GET /api/v2/jobs/{job_id}` 直至成功，解析 `result.vds.uuid`。
3. 基于规划表逐条调用 `POST /api/v2/network/vds/{vds_uuid}/vlans`，创建业务虚拟网络。
4. 结束后调用 `GET /api/v2/network/vds/{vds_uuid}` 校验 `vlans_count` 是否匹配预期。

### 5. 主机账号密码更新

- 匿名化处理每台主机的 root/smartx 密码。
- 实现建议：对每台主机并行执行 SSH、调用内部接口或复用 API（视实际流程而定）。当前代码逻辑由 `_update_host_login_passwords` 占位。

### 6. VMTools（SVT）上传设计

为确保后续需要 SVT 工具的场景（例如 CloudTower 配置驱动、管理虚拟机优化等）能够直接复用资源，本阶段提供可选的离线上传能力；若实际场景不需要，可跳过此步骤。

#### 6.1 创建上传卷

```
POST /api/v2/svt_image/create_volume
Query: name=<文件名>, size=<字节数>
Headers: x-smartx-token
Response: {
  "chunk_size": <int>,
  "zbs_volume_id": "...",
  "image_uuid": "..."
}
```

- 文件名可从本地 ISO 实际名称（如 `SMTX_VMTOOLS-4.0.0-2506271023.iso`）。
- `size` 以字节为单位，可通过 `Path(file).stat().st_size` 获取。
- 将返回值保存至 `ctx.extra['config_cluster']['svt_upload']`，以供后续分片上传和 CloudTower 阶段使用。

#### 6.2 分片上传

```
POST /api/v2/svt_image/upload_template
Query: zbs_volume_id=<id>&chunk_num=<int>&image_uuid=<uuid>
Body: multipart/form-data (file=<二进制数据>)
```

- 按 `chunk_size` 切分文件，`chunk_num` 从 0 递增。
- 每片上传失败时重试两次；若仍失败，调用 `DELETE /api/v2/images/{image_uuid}` 清理上传卷，并重新执行「创建上传卷 + 上传」一次。
- 上传完成的判定：服务器返回 `to_upload` 为空或显式返回 `next_chunk` 超出范围。

#### 6.3 上传结果

- 上传成功后，将 `image_uuid`、`zbs_volume_id`、`file_name`、`chunk_size`、`sha256` 写入 `ctx.extra['config_cluster']['svt_image']`。
- 如需在后续阶段挂载该镜像，可将信息同步到 `ctx.extra['deploy_cloudtower']['vmtools']`。

### 7. 集群序列号获取与规划表写回

- 接口：`GET /api/v2/tools/license`。
- 解析 `data.license_info.serial_number`（待根据实际响应确定字段）。
- 若解析成功且规划表路径存在，通过 `openpyxl` 写入指定单元格。
- 写入失败不应终止阶段，但需记录 warning。

## 错误处理与回滚策略

| 场景 | 行动 |
|------|------|
| Fisheye 初始化失败 | 记录 warning，允许人工处理后重跑阶段 |
| 会话 token 获取失败 | 若配置中存在 token，则继续；否则阶段失败 |
| VDS 创建返回 job 失败 | 标记 warning 并跳过业务网络创建 |
| VMTools 上传失败 | 删除上传卷并重试一次；仍失败则阶段失败 |
| 规划表写回失败 | 记录 warning，但保留序列号于 `ctx.extra` |

所有 API 调用均应通过 `stage_logger` 写出结构化日志（包含 `action`, `status`, `error`）。

## 数据输出

`ctx.extra.setdefault('config_cluster', {})` 内推荐结构：

```python
{
  "results": [
    {"action": "配置 DNS 服务器", "status": "ok"},
    ...
  ],
  "svt_image": {
    "image_uuid": "...",
    "zbs_volume_id": "...",
    "file_name": "SMTX_VMTOOLS-4.0.0-2506271023.iso",
    "chunk_size": 134217728,
    "sha256": "..."
  }
}
```

## 安全与日志

- 对密码、token 等敏感字段在日志中统一脱敏（替换为 `***` 或 `机密凭据`）。
- 上传文件应执行 SHA256 校验，结果写入日志供审计。
- 建议将 VMTools 上传过程的详细进度写入 `logs/stage_config_cluster.log`。

## 测试建议

1. **单元测试**：
   - 构造虚拟规划表输入，验证 VDS/VLAN 载荷构造逻辑。
   - Mock API 客户端，测试上传重试与回滚流程。
2. **集成测试（mock）**：
   - 扩展 mock API，模拟 SVT 上传、VDS 创建的 job 状态机。
   - 在 `tests/test_config_cluster.py` 中新增覆盖 VMTools 上传的测试用例。
3. **端到端演练**：
   - 使用真实环境或沙箱 API，验证阶段执行顺序、日志与 `ctx.extra` 输出。

## 后续工作

- 根据官方接口文档补全返回结构与字段映射，更新 Pydantic 模型。
- 支持配置化的 VMTools 路径、chunk 大小阈值等。
- 与 CloudTower 阶段协商共享结构，确保其可以直接引用 `ctx.extra['config_cluster']['svt_image']`。
- 考虑在 Web UI/CLI 提示上传进度百分比与剩余时间估算。
