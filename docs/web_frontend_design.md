# Web 控制台前端设计与优化计划

## 1. 架构综述

### 1.1 关键目录与模块
- **静态入口**：`cxvoyager/interfaces/web/static/index.html` 组织首页、部署向导、任务列表三大视图，并挂载 `assets/app.js` 与 `assets/styles.css`。
- **核心脚本**：`cxvoyager/interfaces/web/static/assets/app.js` 负责阶段选取、任务轮询、任务卡片渲染及全局日志展示。
- **消息组件**：`cxvoyager/interfaces/web/static/assets/progress-feed.js` 提供 `ProgressFeed`，用于标准化日志格式与样式。
- **样式资源**：`cxvoyager/interfaces/web/static/assets/styles.css` 定义整体布局、控件、任务卡片、时间线等视觉风格。
- **后端接口层**：`cxvoyager/interfaces/web/routers/deployment_routes.py` 与 `task_scheduler.py` 暴露任务 API 和执行调度；`api_models.py` 负责前端消费的 Pydantic 模型。

### 1.2 状态与数据流
- `stageCatalog` 缓存阶段元信息；`taskStore` 保存轮询返回的任务快照。
- 阶段能力元数据由 `cxvoyager/core/deployment/stage_capabilities.yml` 提供，启动时加载至内存并附带版本号与上下文字段说明，前端 `GET /api/stages` 的返回即基于该配置实时渲染。
- `fetchTasks()` 每 2 秒请求 `/api/tasks`，归并任务状态、阶段历史与 `progress_messages`，并驱动 `renderTasks()` 与 `renderGlobalProgress()`。
- 每个任务卡片当前包含标题、状态徽章、进度块、阶段表格（`table.task-stage-table`，含顺序、阶段、状态、开始/结束时间）以及预检摘要。
- 全局进展面板 `#global-progress` 使用 `globalProgressFeed.renderInto()` 展示跨任务实时日志（默认截取最新 12 条）。

### 1.3 现有接口能力
- `GET /api/stages`：输出阶段顺序、分组、描述。
- `POST /api/run`：提交部署任务并返回即时快照。
- `GET /api/tasks` / `GET /api/tasks/{id}`：查询任务列表或详情。
- `POST /api/tasks/{id}/abort`：中止运行中的任务并记录原因。
- `DELETE /api/tasks/{id}`：删除任务记录（不影响后台执行结果）。

## 2. 现有 UI 模块简述

### 2.1 全阶段最新进展面板
- 依赖 `ProgressFeed` 组件展示 info/warning 级别日志，使用固定窗口（limit=12），暂未提供历史窗口交互。

### 2.2 任务卡片
- 顶部显示任务编号与状态徽章（`STATUS_TEXT` 映射）。
- 进度块包含完成百分比、当前阶段提示及失败时的错误文案。
- 阶段信息通过 `table.task-stage-table` 呈现，展示“顺序 / 阶段 / 状态 / 开始时间 / 结束时间 / 耗时”，当前阶段以徽章高亮。
- 预检摘要展示 warnings/errors 计数与网络异常列表。
- 操作区提供“中止任务”“删除记录”按钮，前者仅在执行中启用。

## 3. 改造需求与执行计划

### 3.1 全阶段最新进展支持拖动窗口
**目标**：允许用户通过滑块窗口回看更久远的日志，同时保留自动追踪最新日志的体验。

**交互设计**
- 滑块区间以“窗口开始序号 / 结束序号”形式展示，默认锁定最新窗口；当用户拖动时弹出“历史窗口模式”提示。
- 提供“回到最新”按钮，或当滑块拖至末端时自动恢复实时视图。

**数据结构调整**
- `globalProgressBuffer`：在 `app.js` 中缓存最近 300 条日志，使用 `${taskId}-${timestamp}` 作为去重键。
- `progressViewport`：结构 `{ size: number, offset: number, lockToLatest: boolean }`，存放在模块级状态并同步至 `sessionStorage`，刷新后可恢复用户偏好。

**前端改动**
- 在 `index.html` 的 `.progress-board` 内增加 `<div class="progress-board__controls">`（含 `<input type="range">`、窗口描述、回到最新按钮）。
- `app.js`：
  - 新建 `mergeProgressMessages(buffer, incoming)`，负责去重、截断、排序。
  - 调整 `renderGlobalProgress()`，根据 `progressViewport` 取切片后交由 `globalProgressFeed` 渲染，并在锁定模式下自动同步滑块。
  - 新增 `updateProgressViewport()` 响应滑块事件并刷新窗口说明文本。
- `progress-feed.js`：
  - 增加 `renderWindow(messages, { offset, size })`，对归一化结果进行切片并返回，兼容现有 `render`。
  - 保留“最多渲染 N 条”的约束，确保性能稳定。
- `styles.css`：新增 `.progress-board__controls` 与 `.progress-board__range` 样式，移动端下改为纵向排布。

**测试要点**
- 滑块移动不会触发额外的网络请求或重置任务筛选。
- 观察历史窗口时新日志到达不强制跳转；点击“回到最新”后恢复自动追踪。
- 移动端滑块可顺畅拖动，布局不溢出。
- 刷新页面后仍能保持用户上次选择的窗口大小。

### 3.2 合并阶段列表与时间线组件
> **最新进度**：基础版已合并上线，任务卡片统一以阶段表格展示顺序、状态与起止时间。

**现状回顾**
- `app.js` 中新增阶段表格渲染逻辑，复用 `stage_history` 计算开始/结束时间并依据阶段状态着色。
- 旧 `.stage-list` / `.task-timeline` DOM 与样式已移除，统一改用 `task-stage-table` 与 `stage-status` 系列样式。

**增量计划**
- 针对“耗时”列探索可视化方式（如进度条或性能阈值高亮）。
- 在移动端探索折叠式卡片布局或水平滚动，以提升可读性。
- 根据用户反馈调整状态文本或增加备注列（如阶段输出摘要）。

### 3.3 任务中止按钮与后端支持
**目标**：为运行中任务提供“中止任务”操作，可靠终止后续阶段并向前端展示结果。

**前端改动**
- 任务卡片按钮区新增 `button.task-abort-btn`（位于删除按钮左侧），仅在 `pending`/`running` 状态启用。
- `STATUS_TEXT` 增加 `aborted: '已终止'`，阶段表格添加终止样式，并在卡片顶部展示终止原因。
- `app.js` 更新事件委托：
  - `handleAbortClick(taskId)` 负责禁用按钮、调用 API、处理 200/404/409 响应并弹出提示。
  - 新增 `abortRequestCache`（Map）避免重复点击导致的并发请求。
- 阶段表格渲染时将终止阶段标记为“终止”，未执行的后续阶段结束时间显示 `—`。

**后端改动**
- `TaskStatus` 新增 `aborted`；`TaskRecord` 扩展 `abort_requested`、`abort_reason`、`aborted_at` 字段。
- `TaskManager`：
  - `_running_tasks` 存储 `{ future, cancel_flag: threading.Event }`；
  - 新增 `abort(task_id, reason=None)`：
    - 在 `pending/running` 状态下设置 `cancel_flag`，立刻持久化并返回最新快照；
    - 若 `Future.cancel()` 失败，则等待执行线程在阶段间检查 `cancel_flag` 后抛出 `TaskAbortedError`；
    - 已结束任务返回 409，保持幂等。
  - `_run_task` 在阶段循环中检查 `cancel_flag`，触发时写入 `abort_reason`、`aborted_at` 并追加 `event='aborted'`。
  - `serialize_task` / `_deserialize_task` 支持新字段，保障重启恢复。
- `deployment_routes.py` 增加 `POST /tasks/{task_id}/abort`，返回 `TaskSummaryModel`；
- `api_models.py` 更新 `TaskStatus` Enum、`TaskSummaryModel`，对外暴露终止信息。
- `deployment_executor.execute_run` / `stage_manager.run_stages` 支持 `abort_signal`：每个阶段开始前、阶段完成回调中检查 `abort_signal.is_set()`，并将信号注入 `RunContext.extra['abort_signal']`。

**API 契约**
- **请求**：`POST /api/tasks/{task_id}/abort`，Body `{ "reason": "人为终止" }`（可选）。
- **响应 200**：`{"task": TaskSummaryModel}`，其中 `status="aborted"`，`abort_reason`、`aborted_at` 字段非空。
- **响应 409**：`{"detail": "Task already finished"}`，前端需提示“任务已结束，无需重复终止”。
- **响应 404**：任务不存在，提示用户刷新列表。

**测试建议**
- `TaskManager.abort` 在 pending/running/done 状态下的行为与持久化结果。
- `_run_task` 接收到终止请求后是否停止后续阶段并追加阶段历史记录。
- `/tasks/{id}/abort` 接口的 200、404、409 分支响应。
- 前端端到端：运行中任务点击“中止”后状态立即变更为“已终止”，阶段表格和全局进展同步显示。
- 模拟阶段内部循环检测 `abort_signal`，确保长耗时阶段可被打断。

### 3.4 阶段解耦与 CloudTower 独立部署模式
**背景现状**
- 当前阶段顺序：01 `prepare` → 02 `init_cluster` → 03 `config_cluster` → 04 `deploy_cloudtower`。
- `deploy_cloudtower` 依赖 `init_cluster` 阶段提前写入的 `ctx.extra['host_scan']`、集群部署成功的令牌信息，以及配置阶段产出的网络/凭据。
- Web 前端在阶段选择时强制 04 依赖 02/03，无法覆盖“集群已部署，仅需重新上传 CloudTower ISO”的场景。

**目标**
- 允许用户在阶段选择中勾选 `01 + 04`（可选加 `03`），跳过重新部署集群。
- 在跳过 02 的前提下，通过新的判定逻辑确认集群已处于可用状态，并准备好 `deploy_cloudtower` 所需的上下文数据。

**阶段与判断方案**
1. **新增阶段 `cluster_state_probe`（编号 02.5）**
   - 在 `Stage` Enum 中增加 `cluster_state_probe`，元信息描述为“复用已部署集群并验证令牌”。
   - 运行职责：
     1. 读取 `RunContext.extra['selected_stages']` 判断是否处于“CloudTower-only”模式（定义：选择了 `deploy_cloudtower` 且未选择 `init_cluster`）。
     2. 尝试通过配置项 `api.base_url` / 规划表中的 CloudTower IP 请求 Token/健康探针接口（例如 `/api/v2/images` `HEAD` 请求或 `/api/v2/auth/token/validate`）。
     3. 若成功，写入 `ctx.extra['cluster_ready'] = True`、`ctx.extra['cloudtower_token']`（必要时），并构造最小化 `host_scan`（可从 `plan.mgmt.Cloudtower_IP` 构造虚拟节点，同步 `ctx.extra['host_scan']`）。
     4. 若失败（不可达、403、超时），返回引导信息，提示用户补充配置或重新执行 `init_cluster`。
   - 当 `init_cluster` 也在阶段列表中时，该阶段会短路退出，仅把 `ctx.extra['cluster_ready_mode'] = 'full-deploy'` 回写，供后续阶段参考。

2. **更新 `prepare` 阶段判定**
   - 在处理配置与预检后读取 `selected_stages`，计算运行模式：
     ```python
     ctx.extra['run_mode'] = 'cloudtower-only' if (
         'deploy_cloudtower' in selected and 'init_cluster' not in selected
     ) else 'full'
     ```
   - `run_mode == 'cloudtower-only'` 时：
     - 保留规划表解析、依赖检查、IP 预检；
     - 跳过对 `deploy_payload`、主机扫描等依赖 `init_cluster` 的临时缓存准备，将责任交给 `cluster_state_probe`。

3. **阶段编排与前端规则**
   - `run_stages()` 读取阶段选择后自动插入 `cluster_state_probe`：
     ```python
     if Stage.deploy_cloudtower in selected and Stage.init_cluster not in selected:
         inject_after(Stage.prepare, Stage.cluster_state_probe)
     ```
   - 前端阶段选择器：
     - 去掉“04 必须勾选 02”的硬性校验，改为提示“若跳过阶段 02，请确保集群已部署并配置 API base_url”。
     - 在任务提交 payload 中新增 `modeHint: 'cloudtower-only' | 'full'`，供后端在日志中回显。
     - 阶段列表 UI 新增 `02.5 复用已部署集群` 描述，并在 Hover 文案里说明适用条件。

4. **阶段执行后的上下文契约**
   - `cluster_state_probe` 需保证以下字段可供 `deploy_cloudtower` 使用：
     - `ctx.extra['host_scan']`：至少包含一个条目 `{ cloudtower_ip: { 'host_ip': cloudtower_ip } }`；
     - `ctx.extra['cloudtower_token']`（若通过接口拉取到新的临时 token）；
     - `ctx.extra['cluster_ready'] = True`。
   - `deploy_cloudtower` 在入口处新增守卫：若未找到 `cluster_ready` 且未跑过 `init_cluster`，主动输出可读错误。

**风险 & 兼容性提示**
- **Token 接口差异**：不同 CloudTower 版本可能存在 Token 获取 API 差异，需要在实现中提供策略或 fallback（如先尝试 `/api/v2/auth/token/refresh`，失败再尝试旧接口）。
- **最小化 `host_scan` 数据**：若后续阶段（如 `config_cluster`）依赖完整主机描述，应在 `cluster_state_probe` 中识别仅执行 04 的场景，并提示用户无法执行 03/其它阶段。
- **网络探测开销**：额外的健康检查会延长任务启动时间，建议设置 3 秒超时并支持用户配置。
- **日志/审计可读性**：需要在阶段日志中明确提示所处运行模式，避免误判“为何没跑 init_cluster”。

**优化机会**
- 将 `cluster_state_probe` 的探测结果缓存 5 分钟，重复执行 `01+04` 时可复用，减少频繁探测。
- 在前端阶段卡片上标记“复用模式”，并联动展示集群状态信息（版本号、最近检查时间）。
- 为 `run_mode` 新增 API 暴露（如 `/api/tasks/{id}` 返回 `execution_mode`），便于后续统计与审计。

### 3.5 任意阶段组合策略（已落地）
**现状速览**
- 后端已引入统一的阶段能力配置文件 `cxvoyager/core/deployment/stage_capabilities.yml`，`version=1`，并对上下文字段与阶段说明提供中文注释，便于研发/前端协作。
- `GET /api/stages` 直接读取该配置生成响应，包含阶段顺序、依赖、产出、探针自动插入关系等元数据。
- `deploy_cloudtower`、`config_cluster` 等阶段的上下文依赖与产出已在配置中声明，`cluster_state_probe` 通过 `auto_inject_for` 被自动插入到需要补足上下文的阶段前。

**配置结构概览**
- `version`: 配置结构版本号，执行器在任务提交时会记录所用版本，便于审计回溯。
- `context_keys`: 描述可被阶段读写的上下文字段，包含中文 `description` 与 `populated_by` 阶段列表。
- `stages`: 为每个阶段/探针提供 `order`、`requires`、`optional_requires`、`produces`、`notes`、`auto_inject_for` 等字段，帮助执行器推导依赖、补足缺失上下文。

```yaml
version: 1
context_keys:
  host_scan:
    description: 通过 SmartX API 或模拟数据获取的主机清单。
    populated_by: [init_cluster, cluster_state_probe]
stages:
  deploy_cloudtower:
    order: 4
    requires: [config, host_scan, cluster_ready]
    produces: [cloudtower_upload, cluster_ready]
    notes: >-
      解析 ISO 工件并分片上传，记录摘要供后续阶段复用。
  cluster_state_probe:
    type: probe
    auto_inject_for: [deploy_cloudtower, config_cluster]
```

**组合决策流程**
1. 前端仅提交用户勾选的阶段集合 `requested`，不再做硬性校验；接口可选携带 `modeHint`、`configOverrides` 等辅助信息。
2. 后端解析 `stage_capabilities.yml`：
   - 构建 `requires → produces` 图，并判断是否需要插入 `auto_inject_for` 声明的探针；
   - 若仍存在无法满足的上下文字段，直接返回 400，提示缺失项和建议阶段。
3. 解析结果生成 `resolved_plan`：
   - 以配置中的 `order` 字段为唯一排序基准；
   - 自动插入的探针会标记到 `injected_stages`，供任务记录回显。
4. 在阶段执行前，`stage_manager` 会根据 `requires` 做一次入口校验，并将 `resolved_plan` / `requested` / `injected` 一并写入 `RunContext.extra` 和任务持久化记录。

**前端交互与 API 约定**
- `GET /api/stages` 渲染阶段选择器时展示 `requires/produces`、`notes` 等信息，并在 hover/详情弹窗中显示中文说明和可选依赖。
- 提交任务前可调用 `POST /api/run/dry-check`（待补充）或直接提交 `POST /api/run`，后端返回的任务快照中包含：
  - `requested_stages`: 用户原始勾选；
  - `resolved_plan`: 实际执行顺序；
  - `injected_stages`: 自动补入的探针列表；
  - `capability_version`: 使用的元数据版本号。
- 任务详情页、阶段表格使用 `resolved_plan` 渲染真实执行路径，并可根据 `capability_version` 决定提示文案。

**典型场景回放**
- **CloudTower 专用流程（01+04）**：配置文件声明 `deploy_cloudtower.requires = {config, host_scan, cluster_ready}`，系统检测到 `init_cluster` 未被选择，自动插入 `cluster_state_probe` 来补足 `host_scan`、`cluster_ready`、`cloudtower_token`。
- **只运行配置阶段（03）**：若`host_scan` 缺失，则同样由 `cluster_state_probe` 提供最小化集群信息，否则返回“缺少主机映射”错误提示。
- **逆序执行 04→03**：解析顺序仍按 `order` 排列（03 在 04 之前执行），确保上下文前置；若用户强行仅选 04，再手动运行 03，会依据 `requires` 的缺失给出引导。

**数据持久化与审计**
- 任务记录新增字段：`requested_stages`、`resolved_plan`、`injected_stages`、`capability_version`。
- `stage_capabilities.yml` 每次更新需同步 bump `version`，并在发布说明中记录变更点；任务快照内包含版本号，有助于定位历史执行所用的能力模型。
- 长期计划：将 `capability_snapshot`（执行时的 `requires/produces` 映射）缓存至 `logs/`，用于调试元数据与实际阶段实现不一致的问题。

**风险 & 兼容性提示**
- **Token 接口差异**：不同 CloudTower 版本可能存在 Token 获取 API 差异，需要在实现中提供策略或 fallback（如先尝试 `/api/v2/auth/token/refresh`，失败再尝试旧接口）。
- **最小化 `host_scan` 数据**：若后续阶段（如 `config_cluster`）依赖完整主机描述，应在 `cluster_state_probe` 中识别仅执行 04 的场景，并提示用户无法执行 03/其它阶段。
- **网络探测开销**：额外的健康检查会延长任务启动时间，建议设置 3 秒超时并支持用户配置。
- **日志/审计可读性**：需要在阶段日志中明确提示所处运行模式，避免误判“为何没跑 init_cluster”。

**优化机会**
- 将 `cluster_state_probe` 的探测结果缓存 5 分钟，重复执行 `01+04` 时可复用，减少频繁探测。
- 在前端阶段卡片上标记“复用模式”，并联动展示集群状态信息（版本号、最近检查时间）。
- 为 `run_mode` 新增 API 暴露（如 `/api/tasks/{id}` 返回 `execution_mode`），便于后续统计与审计。


### 3.6 风险与缓解策略
- **能力元数据失真**：若阶段 `requires/produces` 描述与实际实现不一致，会导致组合校验误判。→ **应对**：配置文件或代码层统一定义能力元数据，纳入单测，比对阶段执行前后的上下文 diff。
- **探针阶段副作用**：自动插入的 `probe` 可能对生产集群造成额外负载。→ **应对**：对探针分类（只读/读写），并允许用户在 UI 上禁用高风险探针或调节并发/超时。
- **用户理解成本**：自由组合可能让新手难以判断所需上下文。→ **应对**：在 UI 中提供“推荐组合”快捷按钮和实时提示，文档附上常见场景指南。
- **配置热更新风险**：若阶段能力配置文件在任务执行中途变更，可能导致解析结果与执行逻辑不一致。→ **应对**：对配置文件加版本锁，任务提交时记录版本号，执行期间禁止热更新或采取读写锁并在日志中提示。
- **终止粒度不足**：若阶段内部缺少信号检查，中止请求可能延迟到阶段结束才生效。→ **应对**：在核心耗时流程（节点扫描、镜像导入等）中注入 `abort_signal.is_set()` 判断并抛出 `TaskAbortedError`，并通过集成测试验证终止耗时。
- **日志缓冲占用内存**：维护较大 buffer 容易导致浏览器内存上涨。→ **应对**：限制最大条数为 300，使用 `slice(-N)` 统一截断；触发阈值时记录 `performance.mark` 供调优。
- **滑块跨浏览器兼容**：`input[type=range]` 在 Safari/iOS 的样式自定义受限。→ **应对**：采用原生样式保底，同时提供按钮翻页退化体验。
- **状态一致性**：终止后需确保 CLI / Web 接口语义一致。→ **应对**：扩展 CLI 文案、API 模型与序列化逻辑，同时补充单测覆盖 `aborted` 状态。
- **并发状态竞争**：终止与删除操作可能并发触发竞态。→ **应对**：后端使用锁保护 `_running_tasks`，前端在按钮上增加节流，并通过 409 状态码提示重复操作。

## 4. 实施步骤建议
1. **后端扩展**：实现中止机制、更新模型与序列化，并补充单元测试。
2. **前端组件重构**：引入阶段表格组件，调整任务卡片布局与样式。
3. **全局日志窗口**：重构进展面板与 `ProgressFeed`，实现滑块窗口与“回到最新”交互。
4. **联调验证**：覆盖任务完成、失败、终止三类场景；校验阶段表格、日志窗口、状态文案。
5. **文档与交付**：更新用户说明，必要时提供历史任务迁移脚本，并在发布说明中标注新 API。

> **里程碑规划**：
> - **M1**：后端中止 API 与模型字段完成并通过单测、序列化回归。
> - **M2**：前端阶段视图与终止交互上线，完成设计走查与无障碍检查。
> - **M3**：全局日志滑块发布并通过性能基准测试（窗口切换 < 16ms）。
> - **M4**：完成端到端联调、发布说明更新，准备发版。

---
本文档梳理了现有 Web 控制台架构，并给出“进展滑块”“阶段视图合并”“任务中止”三项改造的计划，后续开发可据此逐步落地并补齐测试。