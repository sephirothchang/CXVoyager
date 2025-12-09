# CXVoyager 架构与目录规范

> 本文档描述新的模块化目录结构、命名约定以及主要组件之间的依赖关系，作为团队协作与后续扩展的统一参考。

## 顶层概览

```
CXVoyager/
├── cxvoyager/                # 应用核心包
│   ├── command_line_interface.py
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
│           ├── command_definitions.py
│           ├── command_handlers.py
│           └── interactive_prompts.py
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
