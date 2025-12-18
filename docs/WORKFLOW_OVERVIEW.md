# WORKFLOW OVERVIEW

此文档概述 CXVoyager 的阶段式部署工作流，说明各阶段的顺序、依赖、输入/输出与执行要点，便于快速理解整体流程与各阶段之间的接口。

阶段序列（顺序执行）

1. STEP 01 - PREPARE_PLAN_SHEET
2. STEP 02 - INIT_CLUSTER
3. STEP 03 - CONFIG_CLUSTER
4. STEP 04 - DEPLOY_CLOUDTOWER
5. STEP 05 - ATTACH_CLUSTER
6. STEP 06 - CLOUDTOWER_CONFIG
7. STEP 07 - CHECK_CLUSTER_HEALTHY
8. STEP 08 - DEPLOY_OBS
9. STEP 09 - DEPLOY_BAK
10. STEP 10 - DEPLOY_ER
11. STEP 11 - DEPLOY_SFS
12. STEP 12 - DEPLOY_SKS
13. STEP 13 - CREATE_TEST_VMS
14. STEP 14 - PERF_RELIABILITY
15. STEP 15 - CLEANUP

每阶段简要说明（输入 / 输出 / 依赖）

- STEP 01 - PREPARE_PLAN_SHEET
  - 输入：项目根规划表或显式指定路径、CLI 选项、默认配置
  - 输出：`ctx.plan` (PlanModel), `ctx.extra['parsed_plan']`, `ctx.extra['precheck']`
  - 依赖：Excel 解析模块、验证规则、网络预检
  - 要点：解析结果缓存，mgmt 容错（NTP/DNS 可为 FQDN）

- STEP 02 - INIT_CLUSTER
  - 输入：`ctx.plan`、host scan 配置
  - 输出：`ctx.extra['deploy_payload']`, `ctx.extra['deploy_response']`, `ctx.extra['deploy_verify']`
  - 依赖：host_discovery_scanner、payload_builder
  - 要点：支持 mock 模式用于本地测试；轮询部署状态直到成功或超时

- STEP 03 - CONFIG_CLUSTER
  - 输入：部署验证结果、host_scan、parsed_plan
  - 输出：阶段配置结果（VIP/DNS/NTP 等）
  - 依赖：SmartX API 客户端、Fisheye 登录
  - 要点：脱敏日志、必要时重试或人工介入

- STEP 04..15
  - 详见各自 `Step_XX-*.md` 文档（`docs/Step_*.md`）。每个文档包含目的、输入/输出、关键模块、主要流程与容错建议。

并行性与控制

- 阶段由 `cxvoyager.core.deployment.stage_manager.run_stages` 顺序调度。
- 阶段内部可并行（例如主机扫描、payload 构建、部分上传任务），具体由各 handler 实现（通常通过 ThreadPoolExecutor 或自定义并行工具）。
- 支持外部中止：每个阶段在长耗时循环或等待点应调用 `raise_if_aborted` 检查 `abort_signal`。

上下文与数据契约

- 关键上下文变量：
  - `ctx.plan`：PlanModel（Pydantic），是阶段间共享的结构化规划数据。
  - `ctx.extra['parsed_plan']`：原始解析字典。
  - `ctx.extra['host_scan']`：主机扫描结果（供 init_cluster 与后续阶段使用）。
  - `ctx.extra['deploy_cloudtower']` / `ctx.extra['attach_cluster']`：CloudTower 阶段输出，供上传/配置/关联使用。
  - `ctx.extra['deploy_results']`：各类应用上传摘要集合。

失败与重试策略建议

- 将网络调用与上传操作按幂等性及错误代码分类：
  - 4xx：通常为请求/认证问题，需人工介入或重发正确参数。
  - 5xx / 网络错误：可配置重试（指数退避 + 抖动），记录每次尝试。
- 对长耗时或可中断子任务（分片上传、轮询安装、VM 创建），应保存操作中间状态到 `ctx.extra` 以支持断点恢复。

可观测性建议

- 每阶段输出结构化 `progress_extra` 日志，包含关键字段（stage, action, duration_ms, result）。
- 上传/分片、轮询与并行任务应导出简要统计（失败次数、平均耗时、吞吐）。

文档与代码对应

- 每个阶段的详细设计位于 `docs/Step_01-...` 至 `docs/Step_15-...`。
- 代码实现主要分布在 `cxvoyager/core/deployment/handlers/`，相关公共工具在 `cxvoyager/core/deployment/` 与 `cxvoyager/integrations/`。

下一步

- 我可以将 `WORKFLOW_OVERVIEW.md` 的关键信息自动加入 `docs/README.md` 或 `USAGE.md` 的快速索引位置，或将其生成一个简易流程图（ASCII 或 mermaid）。要我做哪一项？
