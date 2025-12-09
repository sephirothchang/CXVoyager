# 部署前 IP 检测逻辑规划

## 目标概述
- 在 `prepare` 阶段完成所有关键 IP 的连通性与占用检查，确保后续阶段（集群初始化、配置、CloudTower 部署等）不会因为前置网络问题而失败。
- 将检测结果分类为 **阻断性错误 (error)**、**非阻断警告 (warning)**、**信息提示 (info)**，所有探测完成后一次性汇总并根据严重级别抛出异常或提示用户。
- 将检测报告写入 `RunContext.extra['precheck']['ip_checks']`，方便 CLI / Web 前端展示细节。
- 通过线程池实现批量并发探测，并在 DEBUG 日志级别下输出逐 IP 的 JSON 详情，方便故障定位。

## 严重性分级与处理策略
| 级别 | 示例 | 处理方式 |
| ---- | ---- | -------- |
| error | 主机管理 IP 80 端口不可达、集群 VIP 被占用、存储 IP 被占用、CloudTower IP 冲突 | 全部探测结束后汇总抛出 `RuntimeError`，阻断运行 |
| warning | 主机管理 IP SSH(22) 不通、带外 IP ping/623 不通 | 记录在结果中并打印警告，不中断 |
| warning★ | 未部署 CloudTower 时目标 IP 被非 CloudTower 服务占用 | 同时记录 warning 与阻断性 error（详见下文特殊处理） |
| info | 主机管理 IP HTTPS(443) 不通（服务未起）、未部署 CloudTower 且探测到 CloudTower 服务 | 仅输出日志和报告，不中断 |

## 检测项明细

### 1. 主机管理 IP（集群扫描所需）
- **输入来源**：`ctx.plan.hosts` 中的 `管理地址`。
- **探测步骤**：
  1. ICMP ping（失败记为 error）。
  2. TCP 80 端口握手（失败记为 error，理由：后续 API 调用依赖）。
  3. TCP 443 端口握手（失败仅 info，当前阶段 CloudInit 可能未启用 HTTPS）。
  4. TCP 22 端口握手（失败记为 warning，提示 SSH 通道未开）。
- **处理**：每台主机输出一份检测结果，记录四项探测布尔值和消息；`80` 或 ping 失败写入 error 列表。

### 2. 集群 VIP（冲突检测）
- **输入来源**：`ctx.plan.hosts` 中 `集群VIP` 字段去重后得到一个目标集合。
- **探测步骤**：
  - 对每个 VIP 尝试 ICMP；若 ping 响应即视为被占用。
  - 可选：尝试常见端口（80/443/902）以增加可靠性，第一次上线可先基于 ICMP。
- **处理**：任意 VIP 被占用加入 error 列表，消息需指明具体 IP。

### 3. 存储 IP（冲突检测）
- **输入来源**：`ctx.plan.hosts` 中 `存储地址`。
- **探测步骤**：与集群 VIP 相同：至少做 ICMP，必要时补充端口检测。
- **处理**：被占用（ping 成功）即视为 error。

### 4. CloudTower IP 占用识别
- **输入来源**：
  - `ctx.plan.mgmt` 的 `Cloudtower_IP`（来自 Excel）。
  - 选定阶段列表：当用户勾选阶段 04（`Stage.deploy_cloudtower`）。
- **探测步骤**：
  1. 尝试 `https://<ip>/v2/api/login`（使用 `httpx`，timeout 3-5s，`verify=False` 以兼容自签证书）。
  2. 
     - 若响应 200 且包含可识别的 CloudTower login JSON，判定目标为 CloudTower。
     - cloudtower返回特征可能是如下示例结构
     - 返回值200
{
        "task_id": "string",
        "data": {
            "token": "string"
        }
        }
        或返回400、404、500等
        {
        "code": "ResourceLocked",
        "props": null,
        "stack": "string",
        "message": "string",
        "status": 0,
        "operationName": "string",
        "path": "string"
        }
     - 若请求成功但响应非 CloudTower 特征，记为“被其他服务使用”。
     - 若网络不通（连接失败 / 超时），视为“未占用”。
- **处理分支**：
  - 若阶段 04 部署cloudtower 被选中：探测为 CloudTower 或其他服务占用 -> error（提示 IP 已被占用）。
  - 若阶段 04 未选：
    - 探测为 CloudTower -> info（说明存在现有 CloudTower，符合预期）。
  - 探测为其他服务 -> 先记录 warning，再将该记录提升为 error（执行阶段必须终止）。

### 5. 带外 IP（BMC）
- **输入来源**：`ctx.plan.hosts` 中的 `带外地址`。
- **探测步骤**：
  1. ICMP ping。
  2. TCP 623 端口握手（RMCP/RMCP+）。
- **处理**：若任一检查失败 -> warning；继续运行但在报告中突出显示。

### 6. 汇总与抛错策略
- 统一使用一个 `PrecheckReport`（可用 dataclass 或 Pydantic）收集所有检测结果。
- 每个检测子任务返回结构 `{"category": str, "target": str, "probes": {...}, "level": "info|warning|error", "message": str}`。
- `prepare.handle_prepare` 在所有子任务结束后：
  - 将结果写入 `ctx.extra['precheck']['ip_checks']`。
  - 若存在 `error` 级别记录，合并消息（或列出 JSON）并抛出 `RuntimeError`。
  - 否则分别对 warning/info 调用 `stage_logger.warning/info` 输出。

## 模块与改造建议

### `cxvoyager/common/network_utils.py`
- 新增 `ProbeTask`/`ProbeResult` 数据结构与 `run_probe_tasks` 带线程池的探测执行器。
- 封装 `probe_icmp`、`probe_tcp`，支持重试与耗时统计，并在 DEBUG 模式输出原始探测 JSON。
- 保留 `batch_connectivity` 兼容旧逻辑，但 `prepare` 阶段改用新接口。

### `cxvoyager/core/deployment/prechecks/`
- `mgmt_hosts.py`：管理 IP 的 ICMP+TCP 综合检查。
- `cluster_vip.py`：判定 VIP 是否空闲。
- `storage_ip.py`：判定存储 IP 是否空闲。
- `cloudtower_ip.py`：识别 CloudTower 与其他服务占用情形。
- `bmc_ip.py`：带外链路健康检查。
- `runner.py`：汇总所有检查并输出 `PrecheckReport`。

### `cxvoyager/core/deployment/handlers/prepare.py`
- 调用 `run_ip_prechecks` 完成全部检测，将结果写入 `ctx.extra['precheck']['ip_checks']`。
- 遇到 `error` 级别记录时统一抛出异常；对 `warning`/`info` 记录写入日志但不中断。

### `cxvoyager/core/deployment/deployment_executor.py`
- 将用户选择的阶段列表写入 `ctx.extra['selected_stages']`，供 CloudTower 检测分支使用。

### `cxvoyager/common/config/default.yml`
- `precheck` 节点拆分为并发/各类探测的超时与端口配置：
  ```yaml
  precheck:
    concurrency: 8
    mgmt:
      timeout: 2
      retries: 0
      ports: [80, 443, 22]
    vip_probe:
      timeout: 1
      retries: 0
      ports: []
    storage_probe:
      timeout: 1
      retries: 0
      ports: []
    cloudtower_probe:
      timeout: 3
      retries: 0
      verify_ssl: false
    bmc_probe:
      timeout: 2
      retries: 0
      port: 623
  ```

### 测试用例
- 在 `utils/tests` 或新增 `tests/test_precheck_ip.py`：
  - 使用 monkeypatch 模拟 `network_utils`/`httpx` 返回值，覆盖各分支（80 失败抛错、CloudTower 被占、warning 场景等）。
  - 验证 `PrecheckReport` 汇总逻辑与 `prepare` 阶段抛异常/告警行为。

## 其它优化建议
- **并发探测**：现已通过线程池默认并发执行，可按需调整配置。
- **缓存结果**：对于相同 IP 重复探测（如 VIP 与主机管理 IP 重合），可以缓存第一次的探测结果避免重复操作。
- **用户反馈**：CLI/日志在 DEBUG 等级下输出 JSON 报告，可继续优化为 Rich 表格。
- **可扩展性**：`PrecheckReport` 应预留字段（如 `suggestion`、`evidence`）以便后续增加更多网络项或集成 UI。

---
以上为当前实现的检测逻辑概览，可在后续迭代中继续扩展更多网络项或可视化呈现方式。