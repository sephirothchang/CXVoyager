# 存储介质与架构组合说明

下表列出主机磁盘介质组合与规划表存储架构（分层 / 全闪不分层）对应的处理逻辑、角色分配与标记。

- 分层 = 混闪分层（storage_architecture=mixed_tier 或含“分层/混闪/tier”字样）
- 不分层 = 全闪不分层（storage_architecture=all_flash_non_tier 或含“全闪/不分层/all flash”字样）
- NVMe 判定：`drive` 名称含 `nvme` 且 `type` 为 `SSD` 即视为 NVMe 盘

| 介质组合 | 规划表架构 | 角色分配 | `disk_data_with_cache` | `with_faster_ssd_as_cache` | 行为 |
| --- | --- | --- | --- | --- | --- |
| 全 SSD / 全 NVMe | 分层 | 全部 `data` | True | True | 允许 |
| 全 SSD / 全 NVMe | 不分层 | 全部 `data` | True | True | 允许 |
| SSD + HDD | 分层 | SSD→`cache`，HDD→`data` | False | True | 允许 |
| SSD + HDD | 不分层 | —— | —— | —— | 报错：不分层不可含 HDD |
| NVMe + SSD | 分层 | NVMe→`cache`，SSD→`data` | False | True | 允许 |
| NVMe + SSD | 不分层 | —— | —— | —— | 报错：不分层不可混 NVMe/SSD |
| NVMe + HDD | 分层 | NVMe→`cache`，其余→`data` | False | True | 允许 |
| NVMe + HDD | 不分层 | —— | —— | —— | 报错：不分层不可含 HDD |
| 全 HDD | 任意 | —— | —— | —— | 报错：需含 SSD/NVMe |
| 其它混合（未列出） | 分层 | 最快盘(NVMe/SSD)→`cache`，其余→`data` | False | True | 允许 |

备注：
- 系统盘（function=`boot`）保持原功能，不参与角色分配。
- 报错为部署时抛出异常，需调整规划表介质或存储架构后重试。
