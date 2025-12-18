# 使用说明

> **许可证**：本文档依据 [GNU GPLv3](../LICENSE) 授权发布。

## 安装依赖
```bash
pip install -r requirements.txt
```

## CLI 示例
```bash
# 解析规划表
python -m cxvoyager.interfaces.cli parse

# 验证规划表
python -m cxvoyager.interfaces.cli check

# 执行阶段（自动加载 handlers, 含部署提交dry-run）
python -m cxvoyager.interfaces.cli run --stages prepare,init_cluster,deploy_obs --dry-run

# 调试与严格校验示例
python -m cxvoyager.interfaces.cli run --debug --strict-validation

# 并发扫描主机
python -m cxvoyager.interfaces.cli scan

# 交互选择阶段并执行部署
python -m cxvoyager.interfaces.cli deploy
```

## 工作流概览
本项目的阶段式工作流概览与各阶段详细设计请参阅：

- `docs/WORKFLOW_OVERVIEW.md`：整体阶段顺序、依赖与执行要点。
- `docs/Step_01-PREPARE_PLAN_SHEET.md` … `docs/Step_15-CLEANUP.md`：每个阶段的详细设计文档。

快速打开（项目根）：
```powershell
notepad docs\WORKFLOW_OVERVIEW.md
```

其他参考：

- `docs/WORKFLOW_FLOW.md`：Mermaid 流程图（可视化阶段顺序）。
- `docs/INDEX.md`：阶段索引（每阶段一行摘要，便于快速定位）。

### 规划表快速预览
```bash
# 优先读取项目根目录规划表，支持指定路径
python scripts/plan_preview.py                 # 自动在项目根目录查找
python scripts/plan_preview.py ./my_plan.xlsx  # 指定规划表路径
```
输出包含规划表路径、虚拟网络/主机/管理信息条目数，以及 mgmt 示例与 PlanModel.mgmt 展开，方便快速核对解析结果。

### 准备阶段 (prepare) 详细说明
执行 `prepare` 阶段时当前实现会完成以下动作（只读取规划表与进行环境/网络探测，不会对集群或主机做变更）：

1. 规划表定位：在项目根目录模糊匹配 `SmartX超融合`、`规划设计表`、`ELF环境` 关键词找到 xlsx。
2. Excel 解析：清洗空格/换行/合并单元格残留文本，抽取三个关键 Sheet（虚拟网络 / 主机规划 / 集群管理信息）。
3. 数据建模：将解析结果转换为 Pydantic 模型（PlanModel）以进行结构化校验。
4. 规则验证：
	- 必须存在至少 1 条主机记录；
	- 同一 IP 不允许在管理/存储地址表中重复；
	- 绑定模式非空时需在允许集合：active-backup / balance-tcp / balance-slb；
	- 管理平台核心字段缺失会记录为警告（当前策略：不立即失败，后续阶段可再强化）；NTP/DNS 支持 IP 或 FQDN。
	- 若 mgmt 解析异常会降级为空 mgmt 并记录 warning，避免阻断其他阶段。
5. 可选依赖检查：检测如 openpyxl / requests / tenacity / fastapi 等模块是否已安装；缺失项在报告中列出，默认仅警告（后续可切换为强制失败）。
6. 网络连通性：
	- ICMP：对每台主机管理地址执行 ping；
	- 端口：读取配置 `precheck.ports`（见 `cxvoyager/common/config/default.yml`）对每台主机进行 TCP 连接探测；
	- 汇总成功/失败列表，用于提前暴露网络或防火墙问题。
7. 汇总结果写入运行上下文 (`ctx.extra['precheck']`) 并输出到阶段日志；后续阶段可直接复用，不再重复解析/探测。

运行示例：
```bash
python -m cxvoyager.interfaces.cli run --stages prepare
```

查看结果：
```bash
# 阶段日志（概览、错误与警告）
type .\logs\stage_prepare.log | more

# 主日志（全局上下文与内部调试）
type .\logs\cxvoyager.log | more
```

退出语义（当前实现）：
* 解析/模型构建失败：阶段抛出异常，退出码非 0。
* 网络/端口存在失败：阶段日志记录 failed 列表，但默认不抛出（可根据需要后续升级为硬失败）。
* 依赖缺失：记录 warning，不抛出（计划支持参数切换为硬失败）。

后续计划（NEXT_STEPS 中跟踪）：
* 增加 CIDR / IPv6 / VIP 冲突校验。
* 增加可配置的校验严格度（warn / error 模式）。
* 生成结构化 JSON 报告文件供外部系统消费。

> 提示：若只想单独做验证而不做网络探测，可使用 `python -m cxvoyager.interfaces.cli check`，该命令仅解析 + 模型 + 业务规则，不执行依赖与网络检查。

### 集群初始化阶段 (init_cluster)
1. 并发请求每台主机的硬件/网卡/磁盘信息（mock 模式下自动填充示例）。
2. 选择每台主机首个可用 IPv6 地址作为部署 host_ip（若无则回退 IPv4 管理地址）。
3. 对磁盘进行系统盘剔除、SSD 判断（≥400GB 且非系统盘标记可用于缓存 with_faster_ssd_as_cache）。
4. 构建主机级载荷（ifaces/disks/uuid/passwords）。
5. （当前占位）VDS/Networks 暂提供默认结构，后续将直接使用解析的 `_derived_network`。
6. 主机扫描的 HTTP 超时与重试次数统一由 `cxvoyager/common/config/default.yml` 的 `host_scan` 段落维护，`init_cluster` 与 `host_discovery_scanner` 会直接读取该配置。

### 应用上传阶段 (deploy_obs / deploy_bak / deploy_er / deploy_sfs / deploy_sks)
1. 按阶段名称自动搜索对应包（如 deploy_obs 查找 `Observability-X86_64-*.tar.gz`，deploy_bak 查找 `Backup-X86_64-*.tar.gz`）。
2. --dry-run 下仅记录即将调用的 base_url、endpoint 与包名，不实际发起请求（无 mock）。
3. 非 dry-run 时向 `POST /api/ovm-operator/api/v3/chunkedUploads` 提交 `{origin_file_name: <包名>}`，需要 Bearer 令牌。
4. CloudTower 上传基址分辨顺序：`api.cloudtower_base_url` > `api.base_url` > deploy_cloudtower 阶段输出 > PlanModel.mgmt 中的 CloudTower IP > parsed_plan mgmt，默认 https。
5. 每次上传前都会调用 `cloudtower_login` 获取全新 token，不复用旧会话，减少冲突。
5. 结果写入 `ctx.extra['deploy_results'][<abbr>]`，并镜像到 `deploy_<abbr>_result`。 

### 新增 CLI 选项
* `--dry-run / --no-dry-run`：控制部署载荷是否只预览；若不指定则读取 `cxvoyager/common/config/default.yml` 的 `deploy.dry_run`。
* `--strict-validation / --no-strict-validation`：切换规划表校验严格度。开启后，只要存在 warnings（如 CIDR 重叠、IPv6 提示），`prepare` 阶段会直接抛错；默认值取自 `validation.strict`。
* `--debug / --no-debug`：临时提升日志级别到 DEBUG，便于调试；默认值取自配置中的 `logging.debug` 或 `logging.level`（若为 DEBUG）。

### 可用阶段枚举
```
prepare, init_cluster, config_cluster, deploy_cloudtower, attach_cluster,
cloudtower_config, check_cluster_healthy, deploy_obs, deploy_bak, deploy_er,
deploy_sfs, deploy_sks, create_test_vms, perf_reliability, cleanup
```

## 启动 Web
```bash
uvicorn cxvoyager.interfaces.web.web_server:app --reload --port 8000
```

> **提示：配置 SmartX API Token**
>
> 默认配置文件 `cxvoyager/common/config/default.yml` 中的 `api.x-smartx-token` 已提供默认令牌，如需替换为真实的 SmartX API Token，可改写该字段，或在启动前设置环境变量 `CXVOYAGER_API_TOKEN`（或 `SMARTX_TOKEN`）。
> `CXVOYAGER_API_BASE_URL`、`CXVOYAGER_API_TIMEOUT`、`CXVOYAGER_API_MOCK` 同样支持环境变量覆盖。

### Web UI 任务记录持久化
Web UI 在后台提交的部署任务会自动写入 `logs/web_tasks.json`，即使进程重启也会在启动时恢复：

- 任务状态、阶段进度与执行摘要都会从该文件中加载。
- 如果服务在任务执行过程中被重启，处于 `pending` / `running` 状态的记录会标记为 `failed`，并在任务历史中追加一条错误事件提示中断原因。
- 可以通过设置环境变量 `CXVOYAGER_TASK_STORAGE=/自定义/路径.json` 将存档文件重定向到其他位置，便于外部备份或共享。
- 任务仍可在 Web 界面删除；删除后会同步更新存档文件。
- 阶段进度表在“结束时间”后新增“耗时”列，会自动显示每个阶段的执行时长，便于快速识别耗时节点。

### 中止任务与优雅退出
- Web 前端的“中止任务”按钮会调用 `POST /api/tasks/{task_id}/abort`，后端立刻记录终止原因并触发内部取消信号。
- 阶段处理函数可以通过 `cxvoyager.core.deployment.stage_manager.raise_if_aborted()` 在长轮询或 `time.sleep()` 前后检测该信号，及时抛出 `AbortRequestedError` 结束阶段。
- 示例：`raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="等待部署进度")`。当检测到取消时会写入阶段日志“检测到终止请求”，并让任务状态稳定落入 `aborted`。
- 若新增阶段包含长耗时循环或外部等待，请在循环入口及休眠后调用该辅助函数，确保用户的终止请求可以在几秒内生效。

## 规划表
将规划表 xlsx 文件放在项目根目录，名称包含 `SmartX超融合`、`规划设计表`、`ELF环境` 关键词。

## 日志
主日志: logs/cxvoyager.log ；阶段日志: logs/stage_<stage>.log

## 测试
```bash
pytest -q
```

> ⚠️ **PytestReturnNotNoneWarning 说明**
>
> 运行测试时如果看到 `PytestReturnNotNoneWarning: Expected None, but test_payload_generator.py::test_payload_generation returned False`，这是因为 `test_payload_generation()` 仍采用脚本式返回布尔值的写法：当校验失败时显式返回 `False`。Pytest 会将测试函数视为断言集合，期望它们只抛出异常或使用 `assert`，而不是返回值。因此该布尔返回会触发警告，但不影响用例执行。
> 
> 若要消除警告，可将末尾的 `return len(differences) == 0` 替换为 `assert not differences` 等断言式写法，并在失败时抛出异常或断言错误。

## 打包
```bash
python scripts/package.py
```
