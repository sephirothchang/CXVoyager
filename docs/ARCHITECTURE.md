# CXVoyager 架构与目录规范

> 本文档描述新的模块化目录结构、命名约定以及主要组件之间的依赖关系，作为团队协作与后续扩展的统一参考。

## 顶层概览

```
CXVoyager/
├── cxvoyager/                # 应用核心包
│   ├── application_version.py
│   ├── core/
│   │   ├── deployment/
│   │   │   ├── planning_sheet_processor.py
│   │   │   ├── host_discovery_scanner.py
│   │   │   ├── payload_builder.py
│   │   │   ├── deployment_executor.py
│   │   │   ├── stage_manager.py
│   │   │   └── workflow_engine.py
│   │   ├── cluster/
│   │   │   ├── lifecycle_manager.py
│   │   │   ├── configuration_handler.py
│   │   │   ├── health_monitor.py
│   │   │   └── network_configurator.py
│   │   └── validation/
│   │       ├── business_rules_validator.py
│   │       ├── data_integrity_checker.py
│   │       ├── network_validator.py
│   │       └── resource_validator.py
│   ├── integrations/
│   │   ├── smartx/
│   │   │   ├── api_client.py
│   │   │   ├── data_models.py
│   │   │   ├── endpoint_definitions.py
│   │   │   └── auth_handler.py
│   │   ├── excel/
│   │   │   ├── planning_sheet_parser.py
│   │   │   ├── field_variables.py
│   │   │   ├── template_processor.py
│   │   │   └── data_extractor.py
│   │   └── cloudtower/
│   │       ├── api_client.py
│   │       ├── config_manager.py
│   │       └── deployment_handler.py
│   ├── models/
│   │   ├── planning_sheet_models.py
│   │   ├── deployment_payload_models.py
│   │   ├── cluster_configuration_models.py
│   │   ├── host_information_models.py
│   │   └── network_configuration_models.py
│   ├── common/
│   │   ├── application_config.py
│   │   ├── system_constants.py
│   │   ├── custom_exceptions.py
│   │   ├── logging_config.py
│   │   ├── utility_functions.py
│   │   ├── network_utils.py
│   │   └── filesystem_utils.py
│   └── interfaces/
│       ├── web/
│       │   ├── web_server.py
│       │   ├── api_models.py
│       │   ├── task_scheduler.py
│       │   ├── routers/
│       │   │   ├── deployment_routes.py
│       │   │   ├── cluster_routes.py
│       │   │   └── system_routes.py
│       │   └── static/
│       └── cli/
│           ├── app.py
│           ├── __init__.py
│           └── __main__.py
├── scripts/
├── tests/
├── docs/
└── examples/
```

### 分层说明

- **core/**：存放业务核心逻辑，按领域拆分为 `deployment/`、`cluster/` 与 `validation/`。
- **integrations/**：与外部系统或数据源交互的适配器层，保持与核心逻辑的单向依赖。
- **models/**：集中定义数据模型（Pydantic/数据结构），减少循环依赖。
- **common/**：通用基础设施（配置、常量、日志、工具函数等）。
- **interfaces/**：向外暴露的接口层，包括 Web API、CLI 等。

## 命名约定

| 类型 | 约定 | 示例 |
| ---- | ---- | ---- |
| 包/目录 | 小写单词，按域分组 | `core/deployment/`、`integrations/smartx/` |
| 模块文件 | “业务语义 + 功能后缀”，3~4 个单词内 | `payload_builder.py`、`host_discovery_scanner.py` |
| 类 | PascalCase，与模块语义呼应 | `DeploymentPayloadBuilder`、`HostDiscoveryScanner` |
| 函数 | snake_case，动词开头 | `build_payload()`、`scan_hosts()` |
| 常量 | 大写蛇形 | `DEFAULT_TIMEOUT` |
| 测试 | `tests/<层级>/test_<模块>.py` | `tests/unit/test_payload_builder.py` |
| 脚本 | 动词开头描述用途 | `verify_payload_generator.py` |

## 依赖关系

- **core** 依赖 **models**、**common**；不得反向依赖。
- **integrations** 可依赖 **models**、**common**，但不应依赖 **interfaces**。
- **interfaces** 只调用 **core** 暴露的服务或 **integrations** 提供的适配器。
- **scripts/tests** 通过公共 API 与核心逻辑交互，避免直接访问内部实现细节。

依赖方向示意：

```
common  ————─┐
models  —————├─▶ core ─▶ interfaces
integrations ┘              ▲
                            │
                     scripts/tests
```

## 迁移注意事项

1. 逐步迁移模块到新目录，保持 `__init__.py` 中的导出接口稳定。
2. 每次移动/重命名前，更新引用并运行测试，避免大量堆积后难以排查。
3. 保留向后兼容入口（如旧的 `main.py`/`__main__.py`），在内部重定向到新模块。
4. 长期维护者请在 `docs/developer/architecture_overview.md` 中同步变更历史。

## 后续维护建议

- 使用 `import-linter` 或自定义检查脚本持续监控依赖方向。
- 新增模块时先更新本文件的目录树，确保结构与命名一致。
- 定期审查 `scripts/`，将成熟脚本视情况纳入核心模块或 CLI。

## 前端设计（Web UI）

- 目标：提供任务提交、阶段进度可视化、实时日志流和工件下载入口，便于运维与交付人员操作和查看任务状态。
- 技术栈（当前仓库）：基于 FastAPI/Uvicorn 的后端 REST 接口 + 静态前端文件（`cxvoyager/interfaces/web/static/`）或轻量模板渲染；后续可替换为单页应用（React/Vue）。
- 关键组件：
       - `web_server.py`：启动 FastAPI 服务并挂载路由与中间件。
       - `routers/`：按功能拆分路由，例如 `deployment_routes.py`（任务提交/查询）、`cluster_routes.py`（集群操作）、`system_routes.py`（健康/版本）。
       - `task_scheduler.py`：接收任务请求并与 `core` 层的 `stage_manager.run_stages` 交互，负责将 RunContext 注入并持久化任务记录到 `logs/web_tasks.json`。
       - 静态与前端资源：`interfaces/web/static/` 存放前端 JS/CSS/图标；`templates/`（若存在）用于服务器端渲染页面。
- 实时更新策略：
       - Web 前端轮询或 WebSocket/SSE：后端应提供 WebSocket 或 Server-Sent Events 接口以推送阶段进度与日志；若未实现，可使用短轮询。
       - 日志流：阶段内部应把关键 progress 事件写入阶段日志并通过消息广播器（或直接从文件 tail）流给前端。
- 权限与 UI 控制：任务提交/中止需要鉴权；前端应根据用户角色隐藏敏感操作（例如 clean/delete）。

## 后端设计（服务与模块交互）

- 目标：把部署流程组织为可组合、可测试、可监控的阶段（stage）处理函数，保证上下文 `RunContext` 在阶段间传递状态与产物。
- 核心组件：
       - `stage_manager.py`：定义 `Stage` 枚举、阶段元数据、`run_stages` 调度逻辑、`raise_if_aborted` 中断机制与阶段 handler 注册装饰器。
       - 阶段 handlers：位于 `core/deployment/handlers/` 下，每个阶段为独立模块（如 `prepare.py`、`init_cluster.py`、`deploy_cloudtower.py`、`deploy_obs.py` 等），通过 `@stage_handler` 注册。
       - `runtime_context.RunContext`：携带 `plan`、`config`、`extra`（共享产物）、`work_dir` 与 `completed_stages` 等运行时元数据。
       - 解析与验证：`integrations/excel/planning_sheet_parser.py`（解析 Excel），`core/validation/validator.py`（规则校验）。
       - 外部系统适配（integrations）：SmartX/CloudTower API 客户端、Excel 解析适配器、其他第三方接口封装。
       - 通用工具：`app_upload.py`（应用上传助手）、`host_discovery_scanner`（并发主机扫描）、`payload_builder`（构建部署载荷）、`prechecks`（网络与端口预检）。

## 交互与数据流

1. 用户通过 CLI 或 Web 提交任务，请求被封装为初始 `RunContext` 放入任务队列（`task_scheduler`）。
2. `stage_manager.run_stages` 按所选阶段顺序调用已注册的 handler，每个 handler 接受一个字典上下文（包含 `ctx` RunContext、`abort_signal` 等）。
3. 阶段内部读取/写入 `ctx.plan`、`ctx.extra` 中的键值用于传递产物：如 `parsed_plan`、`host_scan`、`deploy_payload`、`deploy_cloudtower`、`deploy_results`。
4. 关键外部调用（API 交互、上传、主机扫描）通过 `integrations` 层封装，保证单元测试时可以使用 mock（`APIClient.mock`）。
5. 异常与重试策略应在调用方按需实现（短期网络错误重试、幂等性判断与指数退避），并把最终结果写入阶段日志与 `ctx.extra`。

## API 与扩展点

- 公开 API：`/api/tasks`（创建/查询/中止任务）、`/api/plans/preview`（上传/预览规划表解析结果）、`/api/deployments/*`（触发/查看部署）。
- Handler 注册：新阶段通过 `@stage_handler(Stage.<name>)` 装饰器注册到调度器。
- 插件化建议：可将阶段处理函数以 entry_points 或插件目录方式动态加载，支持第三方扩展阶段。

## 安全、认证与运维

- 认证：支持基于 token 的 API 认证（`api.x-smartx-token`），Web 接口建议使用 JWT 或会话管理，并在日志中脱敏敏感字段。
- 凭据管理：不要在配置文件中硬编码 secrets，建议使用环境变量或外部 Secret 管理（Vault/KMS）。
- 日志与审计：阶段日志应包含足够的 context（task_id、stage、timestamp、action、result），并导出结构化 JSON 以便后续聚合。
- 备份与恢复：任务关键中间状态（如上传卷 id、分片 offset、部署任务 id）应保存在可恢复的存储中，支持断点续跑。

---

已将前/后端设计与数据流补充到本文件，若需要我可以：
- 生成简图（PNG/SVG）来展示模块交互（需 mermaid-cli 或外部工具）。
- 将 API 路由与示例请求/响应模版列为附录。

