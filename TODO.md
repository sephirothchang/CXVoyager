# TODO


- [x] 规划表新增存储架构变量（O20），载荷生成根据混闪/全闪切分，并完善磁盘角色分配与标记（NVMe/SSD/HDD 场景全覆盖，含报错策略）。
- [x] 初始化前 API 统一使用预置 default-x-smartx-token；报错提示改为中英双语以便诊断。
- [x] SVT/VMTools 分片上传与重试逻辑完善，确保缺块重传与空结果非中断处理。
- [x] CPU 兼容性配置流程实现（获取推荐架构 → 设置 → 校验）。
- [x] 分层/不分层存储架构已接入规划表（混闪/全闪逻辑、生盘角色与校验）。


- [ ] [cxvoyager/core/deployment/handlers/config_cluster.py#L915-L980](cxvoyager/core/deployment/handlers/config_cluster.py#L915-L980) 批量更新主机 smartx/root 密码流程需修复（当前逻辑未正常生效，依赖 paramiko/SSH，需按设计完成批量修改与错误处理）。
- [ ] [cxvoyager/core/deployment/payload_builder.py#L390](cxvoyager/core/deployment/payload_builder.py#L390) 管理网络 VLAN ID 从规划表获取而非写死。
- [ ] [cxvoyager/core/deployment/payload_builder.py#L452](cxvoyager/core/deployment/payload_builder.py#L452) 存储网络 VLAN ID 从规划表获取而非写死。
- [ ] [接口示例文件/API接口及示例.md#L2206-L2207](接口示例文件/API接口及示例.md#L2206-L2207) CloudTower 机架拓扑配置尚未实现，需补齐“读取单独机架表 + 调用 CloudTower 接口”自动化。



- [ ] [docs/Step_08-DEPLOY_OBS.md](docs/Step_08-DEPLOY_OBS.md) | [cxvoyager/core/deployment/handlers/deploy_obs.py](cxvoyager/core/deployment/handlers/deploy_obs.py) Stage 08 OBS 部署未打通，需补齐自动化实现/接口调用/结果校验。
- [ ] [docs/Step_08-DEPLOY_OBS.md](docs/Step_08-DEPLOY_OBS.md) | [cxvoyager/core/deployment/handlers/deploy_obs.py](cxvoyager/core/deployment/handlers/deploy_obs.py) Stage 08 OBS 部署与配置需通过 SSH 登录 OBS 虚拟机完成 DNS 配置文件修改并校验。
- [ ] [docs/Step_09-DEPLOY_BAK.md](docs/Step_09-DEPLOY_BAK.md) | [cxvoyager/core/deployment/handlers/deploy_bak.py](cxvoyager/core/deployment/handlers/deploy_bak.py) Stage 09 备份服务部署未打通，需补齐实现与校验。
- [ ] [docs/Step_10-DEPLOY_ER.md](docs/Step_10-DEPLOY_ER.md) | [cxvoyager/core/deployment/handlers/deploy_er.py](cxvoyager/core/deployment/handlers/deploy_er.py) Stage 10 远程复制/ER 部署未打通，需补齐实现与校验。
- [ ] [docs/Step_11-DEPLOY_SFS.md](docs/Step_11-DEPLOY_SFS.md) | [cxvoyager/core/deployment/handlers/deploy_sfs.py](cxvoyager/core/deployment/handlers/deploy_sfs.py) Stage 11 SFS 部署未打通，需补齐实现与校验。
- [ ] [docs/Step_12-DEPLOY_SKS.md](docs/Step_12-DEPLOY_SKS.md) | [cxvoyager/core/deployment/handlers/deploy_sks.py](cxvoyager/core/deployment/handlers/deploy_sks.py) Stage 12 SKS 部署未打通，需补齐实现与校验。
- [ ] [docs/Step_13-CREATE_TEST_VMS.md](docs/Step_13-CREATE_TEST_VMS.md) | [cxvoyager/core/deployment/handlers/create_test_vms.py](cxvoyager/core/deployment/handlers/create_test_vms.py) Stage 13 测试 VM 创建未打通，需补齐实现与校验。
- [ ] [docs/Step_14-PERF_RELIABILITY.md](docs/Step_14-PERF_RELIABILITY.md) | [cxvoyager/core/deployment/handlers/perf_reliability.py](cxvoyager/core/deployment/handlers/perf_reliability.py) Stage 14 性能/可靠性验证未打通，需补齐实现与校验。
- [ ] [docs/Step_15-CLEANUP.md](docs/Step_15-CLEANUP.md) | [cxvoyager/core/deployment/handlers/cleanup.py](cxvoyager/core/deployment/handlers/cleanup.py) Stage 15 环境清理未打通，需补齐实现与校验。
- [ ] - [ ] [docs/Step_15-CLEANUP.md](docs/Step_15-CLEANUP.md) | [cxvoyager/core/deployment/handlers/cleanup.py](cxvoyager/core/deployment/handlers/cleanup.py) 将所有与密码修改相关的操作统一放到最终环境清理阶段，作为收尾工作执行。

- [ ] Stage 收尾：SSH 连接 OBS，修改 DNS 配置
	- 阶段：收尾（cleanup）或 OBS 部署后的收尾步骤。
	- 内容：使用 SSH 登录 OBS VM，修改 DNS（按规划表/配置），并校验生效；需要补充实现及文档说明。



