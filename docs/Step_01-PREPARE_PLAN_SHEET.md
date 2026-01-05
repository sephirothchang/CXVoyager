# STEP 01 - PREPARE_PLAN_SHEET

目的
- 在部署流程开始前定位并解析客户提供的规划表（Excel），构建结构化的 PlanModel，并执行初步的校验与环境预检。

输入
- 项目根目录下的规划表（文件名包含 `SmartX超融合` / `规划设计表` / `ELF环境` 等关键词），或通过 CLI/上下文显式指定的路径。
- CLI 选项（`--strict-validation`、`--debug`、`--dry-run` 等）。
- 默认配置文件 `cxvoyager/common/config/default.yml`。

输出
- `ctx.plan`：已构建的 `PlanModel`（Pydantic）。
- `ctx.extra['parsed_plan']`：原始解析字典（用于后续阶段和日志）。
- `ctx.extra['precheck']`：依赖检测、网络/端口/占用预检结果与验证报告。

关键模块
- `cxvoyager.integrations.excel.planning_sheet_parser`：定位并解析 Excel，清洗单元格、抽取三大表（virtual_network / hosts / mgmt）。
- `cxvoyager.models.planning_sheet_models`：Pydantic 模型（PlanModel、MgmtInfo 等）用于数据校验与类型转换。
- `cxvoyager.core.validation.validator`：业务规则校验（必填项、IP 去重、网段冲突等）。
- `cxvoyager.core.deployment.prechecks`：执行 ping、TCP 端口探测、IP 占用检查等。
- `cxvoyager.common.dependency_checks`：检查运行时依赖包。

主要流程
1. 加载配置与 CLI 选项（决定 strict 模式等）。
2. 使用 `find_plan_file` 在项目根目录定位文件（或使用 `--plan` 指定）。
3. 调用 `parse_plan` 生成原始解析字典（保留 `_derived_network` 等派生结构）。
4. 通过 `to_model` 将解析字典转换为 `PlanModel`，并将原始解析缓存在 `ctx.extra['parsed_plan']`。
5. 运行规则验证，记录 errors/warnings；在 strict 模式将 warnings 提升为 errors。
6. 运行依赖检查；若缺少必要依赖则报错或警告（视配置）。
7. 运行 IP 占用与连通性预检（ping、端口探测、VIP/管理地址冲突检测）。
8. 汇总并写入上下文，供后续阶段复用，避免重复解析与探测。

容错与注意事项
- Mgmt（管理信息）解析对 NTP/DNS 支持 IP 或 FQDN；若解析失败会记录 warning 并将 mgmt 置为空，避免阻断后续阶段。
- 解析产生的 IP 地址对象在日志/JSON 序列化时需要转换为字符串。
- 网络探测默认不在 strict 模式下作为阻断性错误，除非配置要求。

日志与可观测
- 关键日志：`logs/stage_prepare.log`（阶段日志），全局日志 `logs/cxvoyager.log`。
- 将解析和预检摘要记录在阶段日志的 `progress_extra` 中，便于快速定位问题。

操作提示
- 若规划表文件名不匹配关键词，可通过 `--plan /path/to/file.xlsx` 显式指定。
- 在调试时启用 `--dry-run` 可跳过实际部署，仅验证解析与预检。
- 若预检失败，可检查网络连通性或调整配置中的超时设置。
