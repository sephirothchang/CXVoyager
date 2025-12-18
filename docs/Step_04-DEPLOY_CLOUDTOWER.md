# STEP 04 - DEPLOY_CLOUDTOWER

目的
- 在目标虚拟化平台上部署 CloudTower 管理组件：上传 ISO、创建 CloudTower 虚拟机、引导并验证 CloudTower 服务就绪。该阶段可选地在已有 CloudTower 服务存在时跳过或执行探测。 

输入
- `ctx.plan`（PlanModel）与 `ctx.extra['parsed_plan']`
- `ctx.extra['host_scan']`（用于推断 API 访问点 / host header）
- 配置项：`cloudtower`、`api` 段（超时、mock、base_url 等）
- 本地 CloudTower ISO（配置或项目资源路径）

输出
- `ctx.extra['deploy_cloudtower']`：CloudTower 部署元数据（状态、IP、上传摘要、组织/数据中心信息、session token 等）
- 可能会产出上传摘要（ISO 上传卷/镜像信息）、虚机 UUID 等 artifact

关键模块
- `cxvoyager.core.deployment.handlers.deploy_cloudtower`：该文件包含主流程与多个 helper（上传、虚机创建、监控安装日志、后置配置等）。
- `cxvoyager.integrations.smartx.api_client`：HTTP 客户端用于与已有平台或 Fisheye 交互（会话 token、查询/上传等）。
- CloudTower-specific helpers：ISO 上传切片、创建上传卷、组装虚机配置、轮询 installer 日志与 HTTPS 443 检查。

主要流程
1. 确保 ctx（plan/parsed_plan/host_scan）可用；必要时自动加载或解析规划表。
2. 初始化 API 客户端（Fisheye / SmartX）并基于 token/session 做鉴权（mock 模式会跳过实际登录）。
3. 检测现有 CloudTower ISO 列表，若已有相同 ISO 则可复用，否则创建上传卷并分片上传 ISO。
4. 组装 CloudTower 部署计划（网络、VM 配置、存储策略、SSH 凭证等），并创建 CloudTower VM。
5. 轮询 VM 启动与安装日志（`installer.out`），检查安装成功标志或超时处理。
6. 完成后执行后置配置：创建组织、数据中心、更新 NTP/DNS、修改 root 密码或创建管理用户等。
7. 将部署信息（IP、组织、session token 等）写入 `ctx.extra['deploy_cloudtower']`，供 `attach_cluster` 和 `cloudtower_config` 使用。

容错与注意事项
- 上传过程中网络中断、超时需支持分片重试；上传失败应清理未完成的上传卷或记录可恢复信息。
- CloudTower 安装日志可能延迟生成，初期需要允许一定的 grace period（当前实现允许 3 分钟内 installer 日志缺失）。
- CloudTower 使用自签 TLS 时，API 客户端通常需要 `verify=False` 或接入证书管理。
- 避免在日志中泄露敏感密码；仅记录最小必要信息并对 token 脱敏。

日志与可观测
- 阶段日志：`logs/stage_deploy_cloudtower.log`（上传进度、虚机创建、安装日志摘要）。
- 轮询与重试事件应记录每次尝试的时间戳与 outcome，便于定位失败原因。

操作提示
- 若已有 CloudTower 部署并希望跳过上传步骤，可在 `ctx.extra['deploy_cloudtower']` 中预置 `status: SERVICE_READY` 与 `ip` 字段。
- 在调试时可启用 mock 模式跳过真实上传/虚机创建，便于在离线环境中验证上游流程。