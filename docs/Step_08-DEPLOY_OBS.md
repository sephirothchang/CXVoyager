# STEP 08 - DEPLOY_OBS

目的
- 上传并登记 Observability（OBS）应用包到目标平台（CloudTower / Fisheye 后端），以供后续安装或分发。

输入
- `ctx.extra['parsed_plan']` 与 `ctx.plan`（用于确定 base_url 或主机列表）
- 本地包文件（pattern: `Observability-X86_64-*.tar.gz`）或配置的包路径
- API 配置（`api.obs_base_url` / `api.base_url` / token）

输出
- `ctx.extra['deploy_results']['obs']`：上传与登记结果概要（状态、上传 ID、错误信息）

关键模块
- `cxvoyager.core.deployment.handlers.app_upload`：通用的上传 helper，负责选择包、解析 base_url、调用 CloudTower 登录并进行分片上传。
- `cxvoyager.integrations.smartx.api_client`：发起上传请求（chunkedUploads 等）。

主要流程
1. 通过 `AppSpec` 定义的 package_pattern 在若干搜索目录（项目根、release/、artifacts/ 等）查找最新包。
2. 解析并决定上传基址（优先 `api.obs_base_url` -> `api.base_url` -> deploy_cloudtower 输出 -> PlanModel mgmt -> parsed_plan mgmt）。
3. 使用 `_resolve_cloudtower_token`（内部会调用 `cloudtower_login`）获取实时的 Authorization token。
4. 调用 OBS 上传接口（分块上传或一次性上传），并记录返回的 upload summary。
5. 将结果写入 `ctx.extra['deploy_results']`，并在阶段日志中记录上传进度与最终结果。

容错与注意事项
- 上传可能很大（GB/ISO 尺寸），请确保网络可靠，并支持续传/断点恢复机制。
- token 在上传前实时获取，避免使用过期 token 导致上传失败。

日志与可观测
- 记录每次分片上传的进度、重试次数与最终摘要；不要在日志中保留完整的包二进制内容或敏感凭据。