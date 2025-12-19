# 使用说明（macOS）

本说明用于在 macOS 平台运行本程序。主入口脚本：`start-macos.command` 位于仓库根目录，可双击或在终端执行。

## 前提要求
- 操作系统：macOS 12+。
- Shell：终端 bash/zsh 可用。
- Python：推荐 Python 3.10+ （系统自带 Python 版本可能较低 ≤3.9.4，建议 homebrew 安装新版并使用虚拟环境）。

## 快速开始
1. 进入项目根目录。
2. 首次赋予脚本执行权限：
   ```bash
   chmod +x start-macos.command
   ```
3. 运行：
   - 在终端运行：
     ```bash
     ./start-macos.command
     ```
4. 按照交互式菜单选择操作（CLI/Web/离线安装等）
注：建议在联网环境下首次运行，以便下载缺失依赖。

## 日志与输出
- 日志位于 `logs/`（如 `cxvoyager.log.*`）。
- 构建后的部署载荷位于 `artifacts/`。
- 巡检报告（含 clusters_server_data.json）位于仓库根目录。

## 故障排查
- 无执行权限：确认已执行 `chmod +x start-macos.command`。
- 缺少依赖：确认已在虚拟环境中 `pip install -r requirements.txt`。
- Python 版本低：请升级或改用 3.10+。

## 其他
- Windows 用户参阅 `USAGE_WINDOWS.md`。
- Linux 用户参阅 `USAGE_LINUX.md`。