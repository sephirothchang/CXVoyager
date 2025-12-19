# 使用说明（Linux）

本说明用于在 Linux 平台运行本程序。主入口脚本：`start-linux.sh` 位于仓库根目录。

## 前提要求
- 操作系统：主流 Linux 发行版（如 Ubuntu/CentOS 等）。
- Shell：bash 可用。
- Python：推荐 Python 3.10+ 已安装并在 PATH 中（可用系统自带或虚拟环境）。

## 快速开始
1. 进入项目根目录。
2. 首次赋予脚本执行权限：
   ```bash
   chmod +x start-linux.sh
   ```
3. 运行：
   ```bash
   ./start-linux.sh
   ```
4. 按照交互式菜单选择操作（CLI/Web/离线安装等）
注：建议在联网环境下首次运行，以便下载缺失依赖。

## 日志与输出
- 日志位于 `logs/`（如 `cxvoyager.log.*`）。
- 构建后的部署载荷位于 `artifacts/`。
- 巡检报告（含 clusters_server_data.json）位于仓库根目录。

## 故障排查
- 无执行权限：确认已执行 `chmod +x start-linux.sh`。
- 缺少依赖：确认已在虚拟环境中 `pip install -r requirements.txt`。
- Python 版本低：请升级或改用 3.10+。
- 跨平台行尾问题：如有需要，可运行 `dos2unix start-linux.sh` 修正为 LF。

## 其他
- Windows 用户参阅 `USAGE_WINDOWS.md`。
- macOS 用户参阅 `USAGE_MACOS.md`。