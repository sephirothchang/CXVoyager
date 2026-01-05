# STEP 06 - CLOUDTOWER_CONFIG

目的
- 在 CloudTower 服务就绪后，执行平台级别的高阶配置：组织/数据中心调整、NTP/DNS 更新、许可与策略应用、镜像/存储策略同步等。

输入
- `ctx.extra['attach_cluster']` 或 `ctx.extra['deploy_cloudtower']`（包含组织/数据中心信息与 session token）
- `ctx.plan` 与 `parsed_plan`（用于提取 NTP/DNS/cluster_vip 等）
- API 客户端与认证头

输出
- `ctx.extra['cloudtower_config']`：配置执行结果摘要（成功/失败项、变更列表等）

关键模块
- `cxvoyager.core.deployment.handlers.cloudtower_config`：阶段逻辑实现（请参照模块内 helper）。
- CloudTower GraphQL / REST 接口调用（更新 NTP、导入许可、配置镜像注册等）。

主要流程
1. 从上下文加载 CloudTower session 与组织信息，构建请求 headers（脱敏 token）。
2. 根据规划表提取 NTP/DNS 列表并调用 GraphQL/REST 接口进行更新。
3. 查询并同步存储策略、VDS、镜像库等元数据以保证后续自动化流程可用。
4. 可选择导入 license 或执行其他平台策略（基于 cfg 配置）。
5. 将所有变更与失败项记录到阶段输出供审计。

容错与注意事项
- 对于可能影响全局的配置（如 NTP/DNS），建议在变更前做一次 dry-run 或人工确认。
- 在 CloudTower API 调用失败时，区分可重试和不可重试错误并采取指数退避策略。

日志与可观测
- 记录配置前后差异摘要；对每项变更记录请求/响应的时间戳与 outcome。

操作提示
- 使用 --dry-run 预览配置；检查 CloudTower 管理界面验证设置。