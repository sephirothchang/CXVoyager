# STEP 12 - DEPLOY_SKS

目的
- 上传并登记 SKS（Key/Secret 服务或其他服务）应用包，与其它应用上传阶段流程一致。

输入
- 本地 SKS 包文件
- `ctx.plan` 与 `parsed_plan`
- API 配置 (sks_base_url 或通用 base_url)

输出
- `ctx.extra['deploy_results']['sks']` 上传摘要

关键模块
- `cxvoyager.core.deployment.handlers.app_upload`
- SmartX API 客户端

主要流程
1. 包查找 -> base_url 决定 -> 实时 token 获取 -> 上传 -> 记录输出

容错与注意事项
- 如需立即触发安装或注册，请在后续阶段指定对应动作和 API 调用。