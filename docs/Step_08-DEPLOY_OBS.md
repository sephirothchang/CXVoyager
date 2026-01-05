# STEP 08 - DEPLOY_OBS

目的
- 上传并校验 Observability（OBS）应用包，必要时创建 OBS 实例、关联集群，并关联系统服务（CloudTower）。

输入
- `ctx.extra['parsed_plan']` 与 `ctx.plan`（用于确定 base_url 或主机列表）
- 本地包文件（pattern: `Observability-*-v*.tar.gz`，支持 X86_64/AARCH64）或配置的包路径
- API 配置（`api.obs_base_url` / `api.base_url` / token）

输出
- `ctx.extra['deploy_results']['OBS']`：上传 / 校验 / 实例 / 关联的完整结果（upload_id、tasks、verify、install_create/install_wait、associate、associate_system_service 等）

关键模块
- `cxvoyager.core.deployment.handlers.deploy_obs`：本阶段实现（上传、校验、实例创建、关联）。
- `cxvoyager.core.deployment.query_vnet`：按名称查询虚拟网络，回填 `vlan_id`。
- `cxvoyager.core.deployment.query_cluster`：按规划表集群名查 CloudTower 集群 ID。
- `cxvoyager.integrations.smartx.api_client`：HTTP/GraphQL 客户端。

主要流程
1. 查找包文件（`Observability-*-v*.tar.gz`）于 work_dir / 项目根 / release / resources / artifacts。
2. 解析 base_url（`api.obs_base_url` > `api.cloudtower_base_url`/`api.base_url` > deploy_cloudtower 输出 > 规划表 mgmt）。登录 CloudTower 获取 token + cookie。
3. GraphQL 校验 `observabilityInstanceAndApps`：确认包列表/实例；决定是否跳过上传；提取现有实例 ID。
4. 如未存在包则分片上传：`POST /api/ovm-operator/api/v3/chunkedUploads` → `.../v1/chunkedUploads` 分片 → `.../{upload_id}:commit` → 轮询 `POST /v2/api/get-tasks`。
5. 再次校验获取最新包/实例信息。
6. 若无实例且已定位集群：
	- 从规划表 `virtual_network` 找 `default` 取 ip/subnet/gateway，构造 vm_spec；通过 `query_vnet_by_name(name="default")` 获取 vlan_id。
	- 选择匹配的 Observability 包记录，调用 `createBundleApplicationInstance` 创建实例，`_wait_obs_instance` 轮询状态。
7. 将实例关联到集群 `updateBundleApplicationInstanceConnectClusters`。
8. 关联系统服务 `updateObservabilityConnectedSystemServices`（CloudTower），构造 `http://<cloudtower_host>/admin/observability/agent` 作为 agent URL；失败不阻断主流程。
9. 结果写入 `ctx.extra['deploy_results']['OBS']`，并镜像到 `deploy_obs_result`。

容错与注意事项
- 发现包已存在则跳过上传；缺少 vm_spec 关键字段或 vnet 未取到时跳过实例创建并记录 warning。
- 系统服务关联失败仅告警不中断；如需使用 https Agent URL 可修改逻辑/配置。
- 上传体积可能较大，确保网络稳定；token 每次实时获取避免过期。

日志与可观测
- 分片上传会记录进度/重试；校验与轮询日志包含版本、实例状态、关联结果；不记录敏感凭据或包二进制。

操作提示
- 若 OBS 包不存在，可预先下载并放置在根目录。
- 在调试时可启用 mock 模式跳过真实上传/实例创建。
- 若 DNS 更新失败，仅记录警告，不影响主流程。