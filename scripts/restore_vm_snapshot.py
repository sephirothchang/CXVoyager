"""restore_vm_snapshot.py
快速批量将指定 vSphere 虚拟机还原到某个快照并开机。

特点与实现要点:
1. 使用 pyVmomi (vSphere SOAP API) 连接 vCenter
2. 支持通过参数/环境变量配置 vCenter 地址、账号与密码
3. 支持一次性处理多个虚拟机，逐台执行：查找 -> 还原 -> (可选) 开机 -> (可选) 等待开机完成
4. 快照查找递归遍历（支持多层快照树）
5. 对每个 Task 进行状态轮询，输出进度
6. 失败后继续处理其它虚拟机，并最终给出汇总结果
7. 开机后等待 VMware Tools 并可选通过 guest 命令配置网络参数
8. 支持线程池并发处理多台虚拟机，加速整体操作
9. 可选集成 rich 显示每台虚拟机的动态进度条

安全提示:
  不建议把真实密码硬编码在脚本里。推荐通过 --password 参数临时输入，或者使用环境变量 VCENTER_PASSWORD。

使用示例:
  python restore_vm_snapshot.py \
	  --server vcsa.c89.fun \
	  --user administrator@vsphere.local \
	  --password "P@ssw0rd!123" \
	  --vm SMTX-AUTO-DEPLOY-HOST-0001 SMTX-AUTO-DEPLOY-HOST-0002 SMTX-AUTO-DEPLOY-HOST-0003 \
	  --snapshot-name OS-Installed \
	  --power-on --wait-poweron

  (生产环境建议改为: 省略 --password 并在执行前:  set VCENTER_PASSWORD=xxxxx)

依赖:
  pip install pyvmomi

"""

from __future__ import annotations

import argparse
import atexit
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
import os
import shlex
import ssl
import sys
import time
from dataclasses import dataclass
from getpass import getpass
from typing import Any, Generator, Iterable, List, Optional, Tuple

try:
	from rich.console import Console
	from rich.live import Live
	from rich.progress import BarColumn, Progress, TaskID, TextColumn, TimeElapsedColumn
except ImportError:  # pragma: no cover
	Console = None  # type: ignore[assignment]
	Live = None  # type: ignore[assignment]
	Progress = None  # type: ignore[assignment]
	TaskID = int  # type: ignore[assignment]

try:
	from pyVim import connect
	from pyVmomi import vim, vmodl  # type: ignore
except ImportError as e:  # pragma: no cover - 仅在未安装依赖时触发
	print("[ERROR] 未找到 pyVmomi，请先安装: pip install pyvmomi", file=sys.stderr)
	raise


# ==========================
# 可集中修改的默认参数 (可被 CLI 覆盖)
# ==========================
DEFAULT_VCENTER_SERVER = "vcsa.c89.fun"
DEFAULT_VCENTER_USER = "administrator@vsphere.local"
DEFAULT_VCENTER_PASSWORD = "P@ssw0rd!123"
# 不在代码中硬编码密码，尝试取环境变量；若为空则后续交互式输入或通过 --password 传入
# DEFAULT_VCENTER_PASSWORD = os.getenv("VCENTER_PASSWORD", "")

# 默认要处理的虚拟机名称列表 (可被 --vm 覆盖)。
DEFAULT_VM_NAMES: List[str] = [
	"SMTX-AUTO-DEPLOY-HOST-0001",
	"SMTX-AUTO-DEPLOY-HOST-0002",
	"SMTX-AUTO-DEPLOY-HOST-0003",
	"SMTX-AUTO-DEPLOY-HOST-0004",
]

# 目标快照名 (可被 --snapshot-name 覆盖)
DEFAULT_SNAPSHOT_NAME = "SSD+HDD"

# 任务轮询间隔（秒）
TASK_POLL_INTERVAL = 1.0
POWERON_POLL_INTERVAL = 1.0
VMTOOLS_POLL_INTERVAL = 2.0
GUEST_PROCESS_POLL_INTERVAL = 2.0

DEFAULT_GUEST_COMMAND_TIMEOUT = 180

# 默认通过 VMware Tools 配置的网络参数
DEFAULT_CONFIGURE_IP = True
DEFAULT_GUEST_USER = os.getenv("GUEST_OS_USER", "root")
DEFAULT_GUEST_PASSWORD = os.getenv("GUEST_OS_PASSWORD", "HC!r0cks")
DEFAULT_VM_INTERFACE = "ens224"
DEFAULT_IP_PREFIX = 24
DEFAULT_GATEWAY = "10.0.20.1"
DEFAULT_DNS_SERVERS: List[str] = ["10.0.0.114"]
DEFAULT_IP_ASSIGNMENTS: List[str] = [
	"10.0.20.11",
	"10.0.20.12",
	"10.0.20.13",
	"10.0.20.14",
]


# ==========================
# 数据结构
# ==========================
@dataclass
class VMProcessResult:
	name: str
	success: bool
	message: str


@dataclass
class VMNetworkConfig:
	interface: str
	ip_address: str
	prefix: int
	gateway: str
	dns_servers: List[str]


class VMLogger:
	def __init__(
		self,
		vm_name: str,
		*,
		progress: Optional[Any] = None,
		task_id: Optional[Any] = None,
		console: Optional[Any] = None,
		quiet: bool = False,
		total_steps: int = 0,
	):
		self.vm_name = vm_name
		self.progress = progress
		self.task_id = task_id
		self.console = console
		self.quiet = quiet
		self.total_steps = total_steps
		self.completed = 0

	def start(self) -> None:
		if self.progress and self.task_id is not None:
			self.progress.update(self.task_id, total=self.total_steps, completed=0, description="准备中")
		elif not self.quiet:
			print(f"[VM] {self.vm_name}")

	def set_status(self, message: str) -> None:
		if self.progress and self.task_id is not None:
			self.progress.update(self.task_id, description=message)

	def advance(self, message: str) -> None:
		if self.progress and self.task_id is not None:
			self.completed = min(self.completed + 1, self.total_steps)
			self.progress.update(self.task_id, completed=self.completed, description=message)
		elif not self.quiet:
			print(f"  - {message}")

	def result(self, success: bool, message: str) -> None:
		if self.progress and self.task_id is not None:
			final_desc = f"{'成功' if success else '失败'} | {message}"
			self.progress.update(self.task_id, completed=self.total_steps, description=final_desc)
		elif not self.quiet:
			print(f"  -> 结果: {'成功' if success else '失败'} | {message}\n")


def calculate_total_steps(do_power_on: bool, configure_ip: bool) -> int:
	steps = 3  # 找 VM、找快照、还原
	if do_power_on or configure_ip:
		steps += 1  # 开机
	if configure_ip:
		steps += 2  # 等待 VMware Tools、配置网络
	return steps


# ==========================
# 辅助函数
# ==========================
def build_ssl_context(insecure: bool) -> Optional[ssl.SSLContext]:
	"""根据是否忽略证书构造 SSL Context."""
	if insecure:
		ctx = ssl._create_unverified_context()  # type: ignore[attr-defined]
		return ctx
	return None


def find_obj_by_name(content, vimtype, name: str):
	"""在 vCenter 内容中查找指定名称对象 (精确匹配)。"""
	container = content.viewManager.CreateContainerView(content.rootFolder, [vimtype], True)
	try:
		for obj in container.view:
			if obj.name == name:
				return obj
	finally:
		container.Destroy()
	return None


def iter_snapshots_recursively(snap_tree: Iterable[vim.vm.SnapshotTree]) -> Generator[vim.vm.SnapshotTree, None, None]:
	for node in snap_tree:
		yield node
		if node.childSnapshotList:
			yield from iter_snapshots_recursively(node.childSnapshotList)


def find_snapshot(vm: vim.VirtualMachine, snapshot_name: str) -> Optional[vim.vm.SnapshotTree]:
	"""递归查找虚拟机的指定快照节点。"""
	if not vm.snapshot or not vm.snapshot.rootSnapshotList:
		return None
	for snap in iter_snapshots_recursively(vm.snapshot.rootSnapshotList):
		if snap.name == snapshot_name:
			return snap
	return None


def wait_for_task(task: vim.Task, label: str, poll: float = TASK_POLL_INTERVAL):
	"""轮询等待 vSphere Task 结束。成功返回，失败抛出异常。"""
	while True:
		state = task.info.state
		if state == vim.TaskInfo.State.success:
			return task.info.result
		if state == vim.TaskInfo.State.error:
			fault = task.info.error
			raise RuntimeError(f"{label} 失败: {fault.msg if fault else 'Unknown error'}")
		time.sleep(poll)


def power_on_and_wait(vm: vim.VirtualMachine, wait: bool, timeout: int, suppress_output: bool = False):
	"""为 VM 开机，可选择等待其进入 poweredOn 状态。"""
	if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
		if not suppress_output:
			print("  - VM 已经是开机状态 (poweredOn)")
		return
	if not suppress_output:
		print("  - 正在开机 ...")
	task = vm.PowerOn()
	wait_for_task(task, f"开机任务({vm.name})")
	if wait:
		if not suppress_output:
			print("  - 等待 poweredOn 状态 ...")
		start = time.time()
		while vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
			if time.time() - start > timeout:
				raise TimeoutError(f"等待 VM {vm.name} 开机超时 ({timeout}s)")
			time.sleep(POWERON_POLL_INTERVAL)
		if not suppress_output:
			print("  - 已开机")


def wait_for_vmtools(content, vm: vim.VirtualMachine, timeout: int, suppress_output: bool = False) -> vim.VirtualMachine:
	"""等待 VMware Tools 进入运行状态，并返回最新的 VM 对象。"""
	if not suppress_output:
		print("  - 等待 VMware Tools 运行 ...")
	target_uuid = None
	try:
		target_uuid = vm.config.uuid  # type: ignore[attr-defined]
	except Exception:  # noqa: BLE001
		target_uuid = None
	current_vm = vm
	start = time.time()
	while True:
		tools_status = None
		if current_vm.guest:
			try:
				tools_status = current_vm.guest.toolsRunningStatus
			except Exception:  # noqa: BLE001
				tools_status = None
		if not tools_status and current_vm.summary and current_vm.summary.guest:
			tools_status = current_vm.summary.guest.toolsRunningStatus
		if tools_status == "guestToolsRunning":
			if not suppress_output:
				print("  - VMware Tools 已运行")
			return current_vm
		if time.time() - start > timeout:
			raise TimeoutError(f"等待 VMware Tools 运行超时 ({timeout}s)")
		time.sleep(VMTOOLS_POLL_INTERVAL)
		if target_uuid:
			refreshed = content.searchIndex.FindByUuid(None, target_uuid, True, False)
			if refreshed:
				current_vm = refreshed
		else:
			refreshed = find_obj_by_name(content, vim.VirtualMachine, current_vm.name)
			if refreshed:
				current_vm = refreshed


def build_guest_auth(username: str, password: str) -> vim.vm.guest.NamePasswordAuthentication:
	return vim.vm.guest.NamePasswordAuthentication(username=username, password=password, interactiveSession=False)


def wait_guest_process(pm: vim.vm.guest.ProcessManager, vm: vim.VirtualMachine, auth: vim.vm.guest.NamePasswordAuthentication, pid: int, timeout: int) -> Optional[int]:
	start = time.time()
	while True:
		try:
			proc_info = pm.ListProcessesInGuest(vm=vm, auth=auth, pids=[pid])
		except vim.fault.GuestOperationsFault as exc:
			raise RuntimeError(f"获取 Guest 进程状态失败: {exc.msg}") from exc
		except vmodl.MethodFault as exc:
			raise RuntimeError(f"获取 Guest 进程状态出错: {exc.msg}") from exc
		if proc_info:
			proc = proc_info[0]
			if proc.endTime is not None:
				return proc.exitCode
		if time.time() - start > timeout:
			raise TimeoutError(f"等待 Guest 进程 {pid} 完成超时 ({timeout}s)")
		time.sleep(GUEST_PROCESS_POLL_INTERVAL)


def configure_guest_network(
	content,
	vm: vim.VirtualMachine,
	auth: vim.vm.guest.NamePasswordAuthentication,
	interface: str,
	ip_address: str,
	prefix: int,
	gateway: str,
	dns_servers: Iterable[str],
	command_timeout: int,
):
	iface_q = shlex.quote(interface)
	ip_with_prefix_q = shlex.quote(f"{ip_address}/{prefix}")
	gateway_q = shlex.quote(gateway)
	commands = [
		"PATH=$PATH:/sbin:/usr/sbin",
		f"ip link set {iface_q} down || true",
		f"ip addr flush dev {iface_q}",
		f"ip addr add {ip_with_prefix_q} dev {iface_q}",
		f"ip link set {iface_q} up",
		f"ip route replace default via {gateway_q} dev {iface_q}",
	]
	dns_entries = [entry for entry in dns_servers if entry]
	if dns_entries:
		dns_args = " ".join(shlex.quote(f"nameserver {addr}") for addr in dns_entries)
		commands.append(f'printf "%s\\n" {dns_args} > /etc/resolv.conf')
	shell_cmd = "set -e; " + "; ".join(commands)
	pm = content.guestOperationsManager.processManager
	spec = vim.vm.guest.ProcessManager.ProgramSpec(programPath="/bin/sh", arguments=f"-c {shlex.quote(shell_cmd)}")
	try:
		pid = pm.StartProgramInGuest(vm=vm, auth=auth, spec=spec)
	except vim.fault.GuestOperationsFault as exc:
		raise RuntimeError(f"启动 Guest 命令失败: {exc.msg}") from exc
	except vmodl.MethodFault as exc:
		raise RuntimeError(f"启动 Guest 命令出错: {exc.msg}") from exc
	exit_code = wait_guest_process(pm, vm, auth, pid, command_timeout)
	if exit_code not in (0, None):
		raise RuntimeError(f"Guest 命令退出码 {exit_code}")



def process_vm(
	content,
	vm_name: str,
	snapshot_name: str,
	do_power_on: bool,
	wait_power_on: bool,
	power_on_timeout: int,
	configure_ip: bool,
	vmtools_timeout: int,
	network_config: Optional[VMNetworkConfig],
	guest_credentials: Optional[Tuple[str, str]],
	guest_command_timeout: int,
	logger: Optional[VMLogger] = None,
) -> VMProcessResult:
	"""对单台虚拟机执行：查找 -> 还原 -> (开机) -> (通过 VMware Tools 配置网络)。"""
	if logger:
		logger.start()
	else:
		print(f"[VM] {vm_name}")

	if logger:
		logger.set_status("查找虚拟机 ...")
	vm = find_obj_by_name(content, vim.VirtualMachine, vm_name)
	if vm is None:
		result = VMProcessResult(vm_name, False, "未找到虚拟机")
		if logger:
			logger.result(result.success, result.message)
		else:
			print(f"  -> 结果: 失败 | {result.message}\n")
		return result
	if logger:
		logger.advance("已找到虚拟机")

	if logger:
		logger.set_status("查找快照 ...")
	snap_node = find_snapshot(vm, snapshot_name)
	if not snap_node:
		result = VMProcessResult(vm_name, False, f"未找到快照: {snapshot_name}")
		if logger:
			logger.result(result.success, result.message)
		else:
			print(f"  -> 结果: 失败 | {result.message}\n")
		return result
	if logger:
		logger.advance("已定位快照")

	if logger:
		logger.set_status(f"还原快照 '{snapshot_name}' ...")
	task = snap_node.snapshot.RevertToSnapshot_Task()
	try:
		wait_for_task(task, f"还原快照({vm_name})")
	except Exception as e:  # noqa: BLE001
		result = VMProcessResult(vm_name, False, f"还原失败: {e}")
		if logger:
			logger.result(result.success, result.message)
		else:
			print(f"  -> 结果: 失败 | {result.message}\n")
		return result
	if logger:
		logger.advance("快照还原完成")
	else:
		print("  - 还原完成")

	result_vm = vm
	if do_power_on or configure_ip:
		if logger:
			logger.set_status("开机并等待 poweredOn ...")
		try:
			power_on_and_wait(
				vm,
				wait_power_on or configure_ip,
				power_on_timeout,
				suppress_output=logger is not None,
			)
		except Exception as e:  # noqa: BLE001
			result = VMProcessResult(vm_name, False, f"开机失败: {e}")
			if logger:
				logger.result(result.success, result.message)
			else:
				print(f"  -> 结果: 失败 | {result.message}\n")
			return result
		if logger:
			logger.advance("已开机")
		else:
			print("  - 已开机")
		result_vm = vm

	if configure_ip and network_config:
		if not guest_credentials:
			result = VMProcessResult(vm_name, False, "未提供 Guest OS 凭据，无法配置 IP")
			if logger:
				logger.result(result.success, result.message)
			else:
				print(f"  -> 结果: 失败 | {result.message}\n")
			return result
		if logger:
			logger.set_status("等待 VMware Tools 运行 ...")
		try:
			result_vm = wait_for_vmtools(
				content,
				result_vm,
				vmtools_timeout,
				suppress_output=logger is not None,
			)
		except Exception as e:  # noqa: BLE001
			result = VMProcessResult(vm_name, False, f"等待 VMware Tools 失败: {e}")
			if logger:
				logger.result(result.success, result.message)
			else:
				print(f"  -> 结果: 失败 | {result.message}\n")
			return result
		if logger:
			logger.advance("VMware Tools 已运行")
		else:
			print("  - VMware Tools 已运行")
		guest_user, guest_pwd = guest_credentials
		if logger:
			logger.set_status("配置网络 ...")
		try:
			auth = build_guest_auth(guest_user, guest_pwd)
			dns_list = network_config.dns_servers
			configure_guest_network(
				content,
				result_vm,
				auth,
				network_config.interface,
				network_config.ip_address,
				network_config.prefix,
				network_config.gateway,
				dns_list,
				guest_command_timeout,
			)
		except Exception as e:  # noqa: BLE001
			result = VMProcessResult(vm_name, False, f"配置网络失败: {e}")
			if logger:
				logger.result(result.success, result.message)
			else:
				print(f"  -> 结果: 失败 | {result.message}\n")
			return result
		if logger:
			logger.advance(f"网络配置完成 ({network_config.ip_address})")
		else:
			print(f"  - 网络配置完成 ({network_config.ip_address})")
		result = VMProcessResult(vm_name, True, f"成功 (IP={network_config.ip_address})")
		if logger:
			logger.result(result.success, result.message)
		else:
			print(f"  -> 结果: 成功 | {result.message}\n")
		return result

	result = VMProcessResult(vm_name, True, "成功")
	if logger:
		logger.result(result.success, result.message)
	else:
		print(f"  -> 结果: 成功 | {result.message}\n")
	return result


# ==========================
# 主逻辑
# ==========================
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="批量还原 vSphere 虚拟机至指定快照并可选开机")
	parser.add_argument("--server", default=DEFAULT_VCENTER_SERVER, help="vCenter Server 地址 / FQDN")
	parser.add_argument("--user", default=DEFAULT_VCENTER_USER, help="vCenter 登录用户名")
	parser.add_argument("--password", default=DEFAULT_VCENTER_PASSWORD, help="vCenter 登录密码 (留空则交互式输入或取环境变量)")
	parser.add_argument("--vm", nargs="+", default=DEFAULT_VM_NAMES, help="要处理的虚拟机名称列表")
	parser.add_argument("--snapshot-name", default=DEFAULT_SNAPSHOT_NAME, help="目标快照名称")
	parser.add_argument("--insecure", action="store_true", help="忽略 TLS 证书验证")
	parser.add_argument("--power-on", action="store_true", help="还原后开机")
	parser.add_argument("--wait-poweron", action="store_true", help="开机后等待直到 poweredOn")
	parser.add_argument("--poweron-timeout", type=int, default=300, help="等待开机超时时间(秒)")
	parser.add_argument("--vmtools-timeout", type=int, default=180, help="等待 VMware Tools 运行超时时间(秒)")
	parser.add_argument("--guest-user", default=DEFAULT_GUEST_USER, help="Guest OS 登录用户名 (用于 VMware Tools 命令执行)")
	parser.add_argument("--guest-password", default=DEFAULT_GUEST_PASSWORD, help="Guest OS 登录密码 (留空则交互式输入或取环境变量 GUEST_OS_PASSWORD)")
	parser.add_argument("--interface", default=DEFAULT_VM_INTERFACE, help="需配置的 Guest 网络接口名称")
	parser.add_argument("--ip", nargs="+", default=DEFAULT_IP_ASSIGNMENTS, help="IPv4 地址列表，与 --vm 顺序对应")
	parser.add_argument("--ip-prefix", type=int, default=DEFAULT_IP_PREFIX, help="IPv4 前缀长度 (CIDR)")
	parser.add_argument("--gateway", default=DEFAULT_GATEWAY, help="默认网关地址")
	parser.add_argument("--dns", nargs="+", default=DEFAULT_DNS_SERVERS, help="DNS 服务器地址列表")
	parser.add_argument("--guest-command-timeout", type=int, default=DEFAULT_GUEST_COMMAND_TIMEOUT, help="等待 Guest 命令完成超时时间(秒)")
	parser.add_argument("--max-workers", type=int, default=0, help="并发处理的线程数 (0 表示自动)" )
	parser.add_argument("--configure-ip", dest="configure_ip", action="store_true", help="通过 VMware Tools 配置 Guest 网络")
	parser.add_argument("--skip-config-ip", dest="configure_ip", action="store_false", help="跳过 Guest 网络配置")
	parser.set_defaults(configure_ip=DEFAULT_CONFIGURE_IP)
	parser.add_argument("--quiet", action="store_true", help="仅输出结果摘要")
	return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
	args = parse_args(argv)

	password = args.password
	if not password:
		# 优先从环境变量再交互
		env_pwd = os.getenv("VCENTER_PASSWORD")
		if env_pwd:
			password = env_pwd
		else:
			password = getpass("vCenter 密码: ")

	guest_password = args.guest_password
	if args.configure_ip:
		if not args.guest_user:
			print("[FATAL] 需要提供 --guest-user 以通过 VMware Tools 执行命令", file=sys.stderr)
			return 2
		if not guest_password:
			env_guest_pwd = os.getenv("GUEST_OS_PASSWORD")
			if env_guest_pwd:
				guest_password = env_guest_pwd
			else:
				guest_password = getpass("Guest OS 密码: ")

	dns_list = [dns for dns in args.dns if dns]
	network_plans: List[Optional[VMNetworkConfig]] = []
	guest_credentials: Optional[Tuple[str, str]] = None
	if args.configure_ip:
		if len(args.ip) != len(args.vm):
			print("[FATAL] --ip 数量必须与 --vm 数量一致", file=sys.stderr)
			return 2
		guest_credentials = (args.guest_user, guest_password)
		network_plans = [
			VMNetworkConfig(
				interface=args.interface,
				ip_address=ip_addr,
				prefix=args.ip_prefix,
				gateway=args.gateway,
				dns_servers=list(dns_list),
			)
			for ip_addr in args.ip
		]
	else:
		network_plans = [None for _ in args.vm]

	ssl_ctx = build_ssl_context(args.insecure)

	effective_power_on = args.power_on or args.configure_ip
	effective_wait_poweron = args.wait_poweron or args.configure_ip
	effective_insecure = args.insecure or ssl_ctx is None or getattr(ssl_ctx, "check_hostname", False) is False

	default_workers = min(len(args.vm), os.cpu_count() or 4)
	if default_workers < 1:
		default_workers = 1
	worker_count = args.max_workers if args.max_workers and args.max_workers > 0 else default_workers
	power_required = effective_power_on
	total_steps = calculate_total_steps(power_required, args.configure_ip)
	rich_available = Console is not None and Progress is not None and Live is not None
	if rich_available and not args.quiet:
		console = Console()  # type: ignore[operator]
		progress = Progress(  # type: ignore[operator]
			TextColumn("[bold cyan]{task.fields[vm_name]}[/]", justify="left"),
			BarColumn(bar_width=None),
			TextColumn("{task.description}", justify="left"),
			TimeElapsedColumn(),
		)
		use_rich = True
	else:
		console = None
		progress = None
		use_rich = False

	if not args.quiet:
		if use_rich and console:
			from rich.table import Table  # 局部导入避免非 rich 场景额外依赖
			from rich.panel import Panel
			from rich import box

			left_table = Table.grid(padding=(0, 1))
			left_table.add_column(justify="right", style="bold cyan")
			left_table.add_column(style="bold white")
			left_table.add_row("Server", args.server)
			left_table.add_row("User", args.user)
			left_table.add_row("Snapshot", args.snapshot_name)
			left_table.add_row("忽略证书", str(effective_insecure))
			left_table.add_row("开启虚拟机电源", str(effective_power_on))
			left_table.add_row("等待 Power On", str(effective_wait_poweron))
			left_table.add_row("并发线程", str(worker_count))
			left_table.add_row("VM 数量", str(len(args.vm)))

			right_column = Table.grid(padding=(1, 0))
			if args.configure_ip:
				network_table = Table(title="网络参数", box=box.SIMPLE, show_header=False, highlight=True)
				network_table.add_column("键", style="bold cyan")
				network_table.add_column("值", style="white")
				network_table.add_row("Guest 用户", args.guest_user)
				network_table.add_row("接口", args.interface)
				network_table.add_row("前缀", f"/{args.ip_prefix}")
				network_table.add_row("网关", args.gateway)
				dns_preview = ", ".join(dns_list) if dns_list else "<无>"
				network_table.add_row("DNS", dns_preview)
				right_column.add_row(network_table)

			vm_table = Table(title="虚拟机", box=box.SIMPLE, highlight=True, show_lines=False)
			vm_table.add_column("VM 名称", style="bold cyan")
			if args.configure_ip:
				vm_table.add_column("目标 IP", style="bold green")
			else:
				vm_table.add_column("备注", style="white")
			for idx, vm_name in enumerate(args.vm):
				ip_text = args.ip[idx] if args.configure_ip and idx < len(args.ip) else ("-" if args.configure_ip else "未配置 IP")
				vm_table.add_row(vm_name, ip_text)
			right_column.add_row(vm_table)

			layout_table = Table.grid(padding=(0, 3))
			layout_table.add_column(ratio=1)
			layout_table.add_column(ratio=1)
			layout_table.add_row(left_table, right_column)

			console.print(Panel.fit(layout_table, title="[bold magenta]vSphere VM Snapshot Restore[/]", border_style="magenta"))
		else:
			print("=== vSphere VM Snapshot Restore ===")
			print(f"Server: {args.server}")
			print(f"User  : {args.user}")
			print(f"VM 数量: {len(args.vm)} | Snapshot: {args.snapshot_name}")
			print(f"忽略证书(实际): {effective_insecure} | 开机(实际): {effective_power_on} (等待: {effective_wait_poweron})")
			print(f"并发线程: {worker_count}")
			if args.configure_ip:
				ips_preview = ", ".join(args.ip)
				dns_preview = ", ".join(dns_list) if dns_list else "<无>"
				print(f"Guest 用户: {args.guest_user} | 接口: {args.interface} | 前缀: /{args.ip_prefix}")
				print(f"网关: {args.gateway} | DNS: {dns_preview}")
				print(f"目标 IP: {ips_preview}\n")
			else:
				print()
			if not rich_available:
				print("[提示] 可安装 rich 以获得动态进度条: pip install rich\n")

	try:
		si = connect.SmartConnect(host=args.server, user=args.user, pwd=password, sslContext=ssl_ctx)
	except Exception as e:  # noqa: BLE001
		print(f"[FATAL] 无法连接 vCenter: {e}", file=sys.stderr)
		return 2
	atexit.register(connect.Disconnect, si)

	content = si.RetrieveContent()
	results_by_idx: dict[int, VMProcessResult] = {}
	logger_map: dict[int, VMLogger] = {}

	if use_rich and progress:
		context_manager = Live(progress, console=console, refresh_per_second=8)  # type: ignore[operator]
	else:
		context_manager = nullcontext()
	with context_manager:
		if use_rich and progress:
			for idx, vm_name in enumerate(args.vm):
				task_id = progress.add_task("等待开始", total=total_steps, vm_name=vm_name)
				logger_map[idx] = VMLogger(
					vm_name,
					progress=progress,
					task_id=task_id,
					console=console,
					quiet=args.quiet,
					total_steps=total_steps,
				)
		else:
			for idx, vm_name in enumerate(args.vm):
				logger_map[idx] = VMLogger(vm_name, quiet=args.quiet, total_steps=total_steps)

		with ThreadPoolExecutor(max_workers=worker_count) as executor:
			future_map = {
				executor.submit(
					process_vm,
					content,
					vm_name=vm_name,
					snapshot_name=args.snapshot_name,
					do_power_on=args.power_on,
					wait_power_on=args.wait_poweron,
					power_on_timeout=args.poweron_timeout,
					configure_ip=args.configure_ip,
					vmtools_timeout=args.vmtools_timeout,
					network_config=network_plans[idx] if idx < len(network_plans) else None,
					guest_credentials=guest_credentials,
					guest_command_timeout=args.guest_command_timeout,
					logger=logger_map.get(idx),
				): idx
				for idx, vm_name in enumerate(args.vm)
			}
			for future in as_completed(future_map):
				idx = future_map[future]
				vm_name = args.vm[idx]
				logger = logger_map.get(idx)
				try:
					res = future.result()
				except Exception as e:  # noqa: BLE001
					res = VMProcessResult(vm_name, False, f"异常: {e}")
					if logger:
						logger.result(res.success, res.message)
				results_by_idx[idx] = res

	results = [results_by_idx.get(i, VMProcessResult(args.vm[i], False, "未知结果")) for i in range(len(args.vm))]

	# 汇总
	success_cnt = sum(r.success for r in results)
	failure_cnt = len(results) - success_cnt
	if not use_rich:
		print("=== 汇总结果 ===")
		for r in results:
			print(f"{r.name}: {'成功' if r.success else '失败'} - {r.message}")
		print(f"总计: 成功 {success_cnt} | 失败 {failure_cnt}")

	return 0 if failure_cnt == 0 else 1


if __name__ == "__main__":  # pragma: no cover
	sys.exit(main())


