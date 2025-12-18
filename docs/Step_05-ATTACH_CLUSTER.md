# STEP 05 - ATTACH_CLUSTER

目的
- 将已部署或已存在的物理/虚拟集群挂载到 CloudTower：创建数据中心、关联集群并确保集群状态为 CONNECTED。

输入
- `ctx.plan` 与 `ctx.extra['parsed_plan']`
- `ctx.extra['deploy_cloudtower']`（若阶段 04 已执行，包含 CloudTower IP、组织与 session）
- API 访问信息（若未在 ctx 中提供，则自动探测 CloudTower IP 并登录）

输出
- `ctx.extra['attach_cluster']`：关联结果（datacenter id、cluster info、状态等）

关键模块
- `cxvoyager.core.deployment.handlers.attach_cluster`：主流程包含自动探测、登录、组织获取、数据中心创建与集群关联。
- CloudTower 专用 API 的调用封装（在 deploy_cloudtower 模块中存在用于登录和请求的 helper）。

主要流程
1. 尝试从上下文获取阶段 04 的输出（`deploy_cloudtower`）；若存在且状态为 `SERVICE_READY` 则沿用其 session/token。
2. 若缺失，则尝试基于规划表/配置探测 CloudTower IP 并检测 443 端口连通性。
3. 使用 `APIClient` 与 `_cloudtower_login` 登录获取 Authorization token。
4. 查询已有组织（复用）或调用创建数据中心 API；获取 `organization_id`。
5. 调用 CloudTower 集群关联 API，提交 cluster VIP、用户名与密码，轮询 `get-clusters` 接口，直至 `CONNECTED` 或超时。
6. 将关联成功的结果写入 `ctx.extra['attach_cluster']`。

容错与注意事项
- 如果无法探测到 CloudTower 或 443 端口不可达，应中止并提示人工处理。
- 关联过程中若返回 `FAILED/ERROR` 状态，应记录原因并提示回滚或人工重试。
- session token 可能失效，若未找到 token 将尝试重新登录。

日志与可观测
- 记录每次 API 请求与轮询状态（脱敏 token），并在失败时保留接口返回的原始信息用于排查。