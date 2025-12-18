# STEP 07 - CHECK_CLUSTER_HEALTHY

目的
- 使用 CloudTower 或集群巡检接口对集群进行健康检查，收集接口与服务状态并生成巡检报告。

输入
- `ctx.extra['attach_cluster']`（包含 CloudTower 与集群标识）
- API 认证信息

输出
- `ctx.extra['check_cluster_healthy']`：巡检结果（健康/异常项、建议处理措施、原始接口返回）
- 导出的巡检报告文件（可选）

关键模块
- `cxvoyager.core.deployment.handlers.check_cluster_healthy`：巡检触发与结果解析逻辑
- CloudTower 巡检/监控 API 或自定义脚本

主要流程
1. 构建认证后的 API 客户端，调用巡检相关接口获取集群各子系统状态（compute、storage、network 等）。
2. 解析接口返回，转换为可读的健康项/异常项（error/warning），并提炼建议措施。
3. 将巡检结果写入 `ctx.extra` 并可导出为 JSON/ZIP 报表。

容错与注意事项
- 巡检可能涉及大量异步任务，需要合理的超时与轮询策略。
- 对于短暂的网络抖动，应保留多次采样以避免误报。

日志与可观测
- 将巡检过程的关键事件与时间戳记录到阶段日志，导出报告便于审计。