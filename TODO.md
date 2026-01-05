# TODO

## 已完成
- [x] 规划表新增存储架构变量（O20），载荷生成根据混闪/全闪切分，并完善磁盘角色分配与标记（NVMe/SSD/HDD 场景全覆盖，含报错策略）。
- [x] 初始化前 API 统一使用预置 default-x-smartx-token；报错提示改为中英双语以便诊断。
- [x] SVT/VMTools 分片上传与重试逻辑完善，确保缺块重传与空结果非中断处理。
- [x] CPU 兼容性配置流程实现（获取推荐架构 → 设置 → 校验）。
- [x] 分层/不分层存储架构已接入规划表（混闪/全闪逻辑、生盘角色与校验）。
- [x] 当前不支持网络融合场景，需补齐规划表设计与载荷生成逻辑（已支持三网独立和存储网络独立两种场景）。
  - [x] 网络融合场景规划表设计与优化，需要在规划表中新增相关字段以支持网络融合配置，增加一个网络融合的选项，用来明确融合结构。
  - [x] [cxvoyager/core/deployment/payload_builder.py#L390](cxvoyager/core/deployment/payload_builder.py#L390) 管理网络当前仅支持access，需支持 VLAN ID 从规划表获取而非写死 0。
  - [x] [cxvoyager/core/deployment/payload_builder.py#L452](cxvoyager/core/deployment/payload_builder.py#L452) 存储网络 VLAN ID 从规划表获取而非写死 0。
- [x] [cxvoyager/core/deployment/handlers/config_cluster.py#L915-L980](cxvoyager/core/deployment/handlers/config_cluster.py#L915-L980) 批量更新主机 smartx/root 密码流程需修复（当前逻辑未正常生效，依赖 paramiko/SSH，需按设计完成批量修改与错误处理）。
- [x] OBS 部署已经完成

## 待支持功能

- [ ] cloudtower 的 DNS 配置功能支持
- [ ] [接口示例文件/API接口及示例.md#L2206-L2207](接口示例文件/API接口及示例.md#L2206-L2207) | [cxvoyager/core/deployment/handlers/deploy_cloudtower.py](cxvoyager/core/deployment/handlers/deploy_cloudtower.py) CloudTower 机架拓扑配置：读取机架表并调用 CloudTower 接口自动化配置。
- [ ] [cxvoyager/core/deployment/handlers/deploy_obs.py](cxvoyager/core/deployment/handlers/deploy_obs.py) OBS 开启网络流量可视化功能；执行后将序列号回写规划表。
- [ ] [cxvoyager/core/deployment/handlers/deploy_bak.py](cxvoyager/core/deployment/handlers/deploy_bak.py) 备份阶段：序列号写回到规划表。
- [ ] [cxvoyager/core/deployment/handlers/deploy_obs.py](cxvoyager/core/deployment/handlers/deploy_obs.py) SSH 连接 OBS 修改 DNS（按规划表/配置），并校验生效；补充实现与文档说明。
- [ ] [cxvoyager/core/deployment/payload_builder.py](cxvoyager/core/deployment/payload_builder.py) 备份存储网络 VLAN ID 当前固定为 0，需支持从规划表读取并生成。
- [ ] [cxvoyager/core/deployment/payload_builder.py](cxvoyager/core/deployment/payload_builder.py) 三网融合场景支持：规划表字段映射、载荷生成与校验。


## 模块优化
- [ ] 优化模块目录结构
	- 评估并优化 `cxvoyager` 目录下各模块的职责划分，考虑将部分通用功能抽象为独立工具模块，提升代码复用性和可维护性；更新相关导入路径及文档说明。
- [ ] 抽象包查找模块
	- 将 `find_latest_package` 从 `cxvoyager/core/deployment/handlers/app_upload.py` 抽象为公共工具模块（建议路径：`cxvoyager/core/utils/package_finder.py`），负责在指定目录集合中匹配包名模式并返回最新版本包；附带单元测试并在原调用处更新引用。
- [ ] 收敛规划表解析
	- 优化并收敛 `integrations.excel.planning_sheet_parser` 的功能，确保所有模块通过该模块获取解析后的规划表（`ctx.plan` / `ctx.extra['parsed_plan']`），避免解析逻辑在多处散落；补充回归测试。
- [ ] 优化 SSH 命令执行模块
	- 评估并优化 `cxvoyager/core/deployment/login_cloudtower.py` 中的 SSH 命令执行逻辑，确保命令执行的健壮性和错误处理；考虑将重复代码抽象为公共函数或类，提升代码复用性和可维护性。

## 占位实现
- [ ] [docs/Step_10-DEPLOY_ER.md](docs/Step_10-DEPLOY_ER.md) | [cxvoyager/core/deployment/handlers/deploy_er.py](cxvoyager/core/deployment/handlers/deploy_er.py) Stage 10 远程复制/ER 部署未打通，需补齐实现与校验。
- [ ] [docs/Step_11-DEPLOY_SFS.md](docs/Step_11-DEPLOY_SFS.md) | [cxvoyager/core/deployment/handlers/deploy_sfs.py](cxvoyager/core/deployment/handlers/deploy_sfs.py) Stage 11 SFS 部署未打通，需补齐实现与校验。
- [ ] [docs/Step_12-DEPLOY_SKS.md](docs/Step_12-DEPLOY_SKS.md) | [cxvoyager/core/deployment/handlers/deploy_sks.py](cxvoyager/core/deployment/handlers/deploy_sks.py) Stage 12 SKS 部署未打通，需补齐实现与校验。
- [ ] [docs/Step_13-CREATE_TEST_VMS.md](docs/Step_13-CREATE_TEST_VMS.md) | [cxvoyager/core/deployment/handlers/create_test_vms.py](cxvoyager/core/deployment/handlers/create_test_vms.py) Stage 13 测试 VM 创建未打通，需补齐实现与校验。
- [ ] [docs/Step_14-PERF_RELIABILITY.md](docs/Step_14-PERF_RELIABILITY.md) | [cxvoyager/core/deployment/handlers/perf_reliability.py](cxvoyager/core/deployment/handlers/perf_reliability.py) Stage 14 性能/可靠性验证未打通，需补齐实现与校验。
- [ ] [docs/Step_15-CLEANUP.md](docs/Step_15-CLEANUP.md) | [cxvoyager/core/deployment/handlers/cleanup.py](cxvoyager/core/deployment/handlers/cleanup.py) Stage 15 环境清理未打通，需补齐实现与校验。
- [ ] [docs/Step_15-CLEANUP.md](docs/Step_15-CLEANUP.md) | [cxvoyager/core/deployment/handlers/cleanup.py](cxvoyager/core/deployment/handlers/cleanup.py) 将所有与密码修改相关的操作统一放到最终环境清理阶段，作为收尾工作执行。




