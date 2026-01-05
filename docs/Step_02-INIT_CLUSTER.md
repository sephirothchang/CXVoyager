# STEP 02 - INIT_CLUSTER

目的
- 基于解析后的 `PlanModel` 和主机扫描结果，构建部署载荷并触发平台（SmartX）接口开始集群初始化部署。

输入
- `ctx.plan`（PlanModel）
- `ctx.extra['parsed_plan']`（可选，若 ctx.plan.source_file 可用则重新解析）
- `ctx.extra['host_scan']`（主机扫描结果，若不存在则调用扫描模块）
- API 配置（`api.base_url`、`api.x-smartx-token` 等）

输出
- `ctx.extra['deploy_payload']`：构建好的部署载荷（JSON-serializable dict）。
- `ctx.extra['artifacts']['deploy_payload']`：载荷文件路径（artifact）。
- `ctx.extra['deploy_response']`：API 调用的返回值。
- `ctx.extra['deploy_verify']`：部署验证/轮询结果。

关键模块
- `cxvoyager.core.deployment.host_discovery_scanner`：并发扫描主机，收集网卡、IP、磁盘等信息（支持 mock）。
- `cxvoyager.core.deployment.payload_builder`：把 `PlanModel` 与主机扫描数据转换为目标平台需要的部署载荷结构。
- `cxvoyager.integrations.smartx.api_client`：用于调用 SmartX API（支持 mock 模式）。
- `cxvoyager.common.mock_scan_host`：用于 mock 主机数据的生成（测试或离线使用）。

主要流程
1. 从上下文或配置读取 SmartX API 凭证、base_url 与超时设置。
2. 如果开启 mock 模式，使用内置示例数据替代真实扫描；否则调用 `scan_hosts` 执行并发扫描并收集 host_info。
3. 使用 `generate_deployment_payload` 把 PlanModel、host_info 与解析字典（可选）合成为部署载荷。
4. 将载荷写出为 artifact，并通过 APIClient 调用 `/api/v2/deployment/cluster` 触发集群部署。
5. 轮询部署状态（`/api/v2/deployment/host/deploy_status`）直到完成或超时，写入 `ctx.extra['deploy_verify']`。

容错与注意事项
- 扫描阶段可能返回警告或空结果；若扫描结果为空且未启用 mock，会抛出错误终止。
- 载荷生成失败应记录详细异常并中止部署。
- API 调用对网络错误、HTTP 错误要区分处理（可考虑重试策略与指数退避）。

日志与可观测
- 记录主机扫描警告与扫描结果摘要（host IP 列表）到阶段日志。
- 在调用部署接口和轮询时，截断或脱敏长返回以避免日志噪声或泄漏敏感信息。

操作提示
- 使用 --mock 跳过真实扫描；检查 artifacts/ 中的载荷文件。
