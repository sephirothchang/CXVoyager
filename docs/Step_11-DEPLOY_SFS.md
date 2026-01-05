# STEP 11 - DEPLOY_SFS

目的
- 上传并登记 SFS（分布式文件系统）应用包，流程与其他应用上传类似，但可能需要额外的存储策略或 VDS 配置。

输入
- 本地 SFS 包文件
- `ctx.plan` 与 `parsed_plan`
- API 配置 (sfs_base_url 或通用 base_url)

输出
- `ctx.extra['deploy_results']['sfs']` 上传摘要

关键模块
- `cxvoyager.core.deployment.handlers.app_upload`
- SmartX API 客户端

主要流程
1. 查找包并选择最新版本
2. 决定上传基址并获取 token
3. 上传并登记，记录结果

容错与注意事项
- SFS 相关配置（存储策略）需与 CloudTower 中的存储策略一致或提前同步。

日志与可观测
- 上传与登记日志记录进度和结果。

操作提示
- 确保 SFS 包文件名匹配模式；当前为占位实现。