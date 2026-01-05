# STEP 03 - CONFIG_CLUSTER

目的
- 在平台部署完成后，执行集群的网络、DNS、NTP、Fisheye（管理平台）等后置配置，确保集群服务就绪并符合组织策略。

输入
- `ctx.extra['deploy_verify']`（部署结果与状态）
- `ctx.extra['host_scan']`（主机扫描信息）
- `ctx.plan` 与 `ctx.extra['parsed_plan']`
- API 凭证与 base_url

输出
- 若成功，`ctx.extra` 中会写入阶段结果（如配置成功/失败条目）。

关键模块
- `cxvoyager.integrations.smartx.api_client`：SmartX HTTP 客户端。
- `cxvoyager.core.deployment.handlers.init_cluster._resolve_deployment_base`：解析部署 base URL 与 host header。
- 解析工具：从 parsed_plan 中提取 `DNS 服务器`、`NTP 服务器`、`cluster_vip`、Fisheye 管理员帐号等。

主要流程
1. 验证 `deploy_verify` 表明集群已经部署成功；否则中止阶段。
2. 初始化 API 客户端（基于 host_info 或配置的 base_url）。
3. 若需要，重新解析规划表以获取最新解析数据。
4. 使用 Fisheye 管理账号初始化/换密并登录以获取 session token。
5. 配置管理 VIP、DNS、NTP、以及其它集群级别设置（通过 PUT/POST 请求）。
6. 对关键配置执行结果检查并记录 warnings/errors。

容错与注意事项
- Fisheye 登录/初始化若失败，应记录为警告并提示人工干预。
- 对外部服务（DNS/NTP）配置后，应有验证步骤确保下游服务可达并生效。
- 避免在日志中直接输出明文密码或 token，相关日志应脱敏。

日志与可观测
- 详细记录每次配置 API 请求与返回的状态（脱敏后）。
- 将阶段动作与结果写入阶段日志 `logs/stage_config_cluster.log`。

操作提示
- 使用 --dry-run 预览配置变更；检查 NTP/DNS 设置的有效性。
