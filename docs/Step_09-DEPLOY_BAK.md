# STEP 09 - DEPLOY_BAK

目的
- 上传并登记 Backup（BAK）应用包到目标平台，流程与 OBS 上传类似但可以使用不同的 API 路径和包名模式。

输入
- 本地 BAK 包文件（pattern: `Backup-X86_64-*.tar.gz`）或配置的包路径
- `ctx.extra['parsed_plan']` 与 `ctx.plan`
- API 配置（`api.bak_base_url` / `api.base_url` / token）

输出
- `ctx.extra['deploy_results']['bak']`：上传与登记结果摘要

关键模块
- `cxvoyager.core.deployment.handlers.app_upload`：通用上传逻辑（包查找、base_url 决定、登录/上传）。
- `cxvoyager.integrations.smartx.api_client`：HTTP 客户端。

主要流程
1. 查找符合 `Backup-X86_64-*` 模式的最新包。
2. 确定上传基址（同 OBS 优先级）。
3. 获取 CloudTower token 并执行上传请求。
4. 记录上传摘要并写入阶段输出。

容错与注意事项
- 上传失败时应保留包名与路径、上传尝试日志与 HTTP 响应以便追溯。
- 在离线或受限网络场景下，建议预先将包放到可访问的 artifact 目录并使用 `--dry-run` 检查流程。