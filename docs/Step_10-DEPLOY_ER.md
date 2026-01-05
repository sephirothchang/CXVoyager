# STEP 10 - DEPLOY_ER

目的
- 上传并登记 ER（Replica / Recovery）应用包并在平台上注册/分发。

输入
- 本地 ER 包文件（pattern 约定）
- `ctx.plan` 与 `ctx.extra['parsed_plan']`
- API 配置（`api.er_base_url` / token）

输出
- `ctx.extra['deploy_results']['er']`：上传与登记结果摘要

关键模块
- `cxvoyager.core.deployment.handlers.app_upload`：用于查找包和上传的通用工具
- API 客户端

主要流程
1. 搜索符合 ER 包名模式的文件并选择最新版本。
2. 决定基址并获取实时 token。
3. 执行上传并登记，记录返回信息。

容错与注意事项
- 与 OBS/BAK 相同的上传注意事项：续传、重试、脱敏日志等。
- 若部署后需要立即执行安装，后续阶段应根据返回的上传摘要发起安装调度。

日志与可观测
- 上传进度与重试记录在阶段日志中；登记结果摘要便于跟踪。

操作提示
- ER 包需预先放置在指定目录；文件名需匹配模式以便自动识别。
- 当前为占位实现，失败时记录警告不中断流程。