# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of CXVoyager.
#
# CXVoyager is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CXVoyager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CXVoyager.  If not, see <https://www.gnu.org/licenses/>.

"""交互式入口：允许用户在 CLI 与 Web UI 模式间切换。"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path


def _is_en() -> bool:
    lang = os.environ.get("CXVOYAGER_LANG", "").lower()
    return lang.startswith("en")


def _t(cn: str, en: str) -> str:
    return en if _is_en() else cn


def _print_menu() -> None:
    print("\n=== " + _t("CXVoyager 交互入口", "CXVoyager Entry") + " ===")
    print("1) " + _t("CLI 模式 (CXVoyager CLI)", "CLI Mode (CXVoyager CLI)"))
    print("2) " + _t("Web UI 模式 (CXVoyager Web Console)", "Web UI Mode (CXVoyager Web Console)"))
    print("3) " + _t("安装依赖（离线包）", "Install deps (offline)") )
    print("0) " + _t("退出", "Exit"))


def _prompt_choice(prompt: str | None = None) -> str:
    if prompt is None:
        prompt = _t("请选择模式: ", "Select mode: ")
    try:
        return input(prompt).strip().lower()
    except EOFError:  # Ctrl+D
        return "0"


def _run_cli_shell() -> None:
    from cxvoyager.resources.interfaces.cli.app import app as cli_app

    def invoke_cli(args: list[str]) -> None:
        try:
            cli_app(prog_name="cxvoyager", args=args)
        except SystemExit as exc:  # Typer/Click 会抛出 SystemExit
            if exc.code not in (0, None):
                print(_t(f"命令以退出码 {exc.code} 结束", f"Command exited with code {exc.code}"))
        except Exception as exc:  # noqa: BLE001
            print(_t(f"执行命令失败: {exc}", f"Command failed: {exc}"))

    print("\n" + _t("欢迎使用 CXVoyager CLI。请输入命令（例如: run --debug），输入 exit 返回主菜单。",
                      "Welcome to CXVoyager CLI. Type commands (e.g., run --debug); type exit to return."))
    print(_t("输入 help 查看指令列表。", "Type help to list commands."))
    while True:
        try:
            command = input("cli> ").strip()
        except EOFError:
            print(_t("\n检测到 EOF，返回主菜单。", "\nEOF detected, returning to menu."))
            break
        except KeyboardInterrupt:
            print(_t("\n已取消当前命令，继续停留在 CLI 模式。", "\nCommand canceled; staying in CLI."))
            continue

        if not command:
            continue
        normalized = command.lower()
        if normalized in {"exit", "quit", "q"}:
            break
        if normalized in {"help", "?"}:
            invoke_cli(["--help"])
            continue

        try:
            args = shlex.split(command)
        except ValueError as exc:
            print(_t(f"无法解析命令: {exc}", f"Cannot parse command: {exc}"))
            continue

        invoke_cli(args)

    print(_t("已退出 CLI 交互模式。", "Exited CLI shell."))


def _resolve_port(value: str | None, default: int) -> int:
    if not value:
        return default
    try:
        port = int(value)
    except ValueError:
        raise ValueError("端口必须是整数") from None
    if not (0 < port < 65536):
        raise ValueError("端口需处于 1-65535 之间")
    return port


def _run_web_ui() -> None:
    import uvicorn

    default_host = os.environ.get("CXVOYAGER_WEB_HOST", "0.0.0.0")
    default_port = os.environ.get("CXVOYAGER_WEB_PORT")

    try:
        port = _resolve_port(default_port, 8080)
    except ValueError as exc:
        print(f"环境变量 CXVOYAGER_WEB_PORT 无效: {exc}，已回退到 8080。")
        port = 8080

    host = default_host or "0.0.0.0"

    display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    print(_t(
        f"启动 CXVoyager Web 控制台，监听 {host}:{port}",
        f"Starting CXVoyager Web Console on {host}:{port}"
    ))
    print(_t(
        f"本机访问 http://{display_host}:{port} (可设置 CXVOYAGER_WEB_HOST/CXVOYAGER_WEB_PORT 覆盖)",
        f"Access locally: http://{display_host}:{port} (override via CXVOYAGER_WEB_HOST/CXVOYAGER_WEB_PORT)"
    ))
    print(_t(f"接口文档 http://{display_host}:{port}/docs", f"API docs: http://{display_host}:{port}/docs"))
    print(_t("按 Ctrl+C 停止服务。", "Press Ctrl+C to stop."))
    try:
        uvicorn.run(
            "cxvoyager.resources.interfaces.web.web_server:app",
            host=host,
            port=port,
            log_level="info",
            access_log=False,
        )
    except KeyboardInterrupt:
        print("\n已停止 Web UI 服务。")


def _install_offline_dependencies() -> None:
    project_root = Path(__file__).resolve().parent
    offline_dir = project_root / "cxvoyager" / "resources" / "offline_packages"
    requirements_file = project_root / "requirements.txt"

    if not offline_dir.exists():
        print(_t(
            f"离线目录 {offline_dir} 不存在，请先准备离线依赖包。",
            f"Offline dir {offline_dir} not found; prepare offline packages first."
        ))
        return

    if not any(offline_dir.iterdir()):
        print(_t(
            f"离线目录 {offline_dir} 为空，请先执行 scripts/prepare_offline_packages.py 下载依赖。",
            f"Offline dir {offline_dir} is empty; run scripts/prepare_offline_packages.py to download deps."
        ))
        return

    if not requirements_file.exists():
        print(_t(
            f"未找到 {requirements_file}，无法读取依赖列表。",
            f"requirements file {requirements_file} not found; cannot install deps."
        ))
        return

    print(_t("开始安装依赖（离线模式）...", "Installing dependencies (offline)..."))
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-index",
        "--find-links",
        str(offline_dir),
        "-r",
        str(requirements_file),
    ]
    try:
        subprocess.check_call(cmd)
        print(_t("依赖安装完成。", "Dependencies installed."))
    except subprocess.CalledProcessError as exc:
        print(_t(
            f"安装过程失败，退出码 {exc.returncode}。请检查离线包或手动执行上述命令。",
            f"Install failed with exit code {exc.returncode}. Check offline packages or rerun manually."
        ))


def main() -> None:
    shortcuts: dict[str, str] = {
        "1": "cli",
        "cli": "cli",
        "c": "cli",
        "2": "web",
        "web": "web",
        "w": "web",
        "3": "install",
        "install": "install",
        "deps": "install",
        "0": "exit",
        "exit": "exit",
        "quit": "exit",
        "q": "exit",
    }

    while True:
        _print_menu()
        choice = shortcuts.get(_prompt_choice(), "invalid")
        if choice == "cli":
            _run_cli_shell()
        elif choice == "web":
            _run_web_ui()
        elif choice == "install":
            _install_offline_dependencies()
        elif choice == "exit":
            print(_t("再见！", "Goodbye!"))
            break
        else:
            print(_t("无效的选择，请重新输入。", "Invalid choice, please retry."))


if __name__ == "__main__":  # pragma: no cover
    main()
