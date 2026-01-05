$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "启动 CXVoyager 启动脚本 (Windows)..."

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$venvDir = Join-Path $scriptDir ".venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
$reqFile = Join-Path $scriptDir "requirements.txt"
$offlineDir = Join-Path $scriptDir "cxvoyager\common\resources\offline_packages"
$stampFile = Join-Path $venvDir ".requirements.sha256"
$requiredPythonVersion = "3.11.9"
$pythonInstaller = Join-Path $scriptDir "cxvoyager\common\resources\python-windows\python-3.11.9-amd64.exe"

function Get-PythonVersion([string]$pythonCmd) {
	try {
		return (& $pythonCmd --version) -replace "Python\s+", ""
	} catch {
		return $null
	}
}

function Ensure-Python {
	param([string]$preferred = "python")
	$cmd = $preferred
	$detected = Get-PythonVersion $cmd
	if (-not $detected -or $detected -ne $requiredPythonVersion) {
		$answer = Read-Host "检测到系统 Python ($detected) 不符合要求，是否安装内置 $requiredPythonVersion ? [Y/N]"
		if ($answer -match '^[Yy]$') {
			if (-not (Test-Path $pythonInstaller)) {
				Write-Error "找不到 Python 安装包: $pythonInstaller"
				exit 1
			}
			Write-Host "正在安装 $requiredPythonVersion ..."
			$targetDir = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311"
			$arguments = "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 TargetDir=`"$targetDir`""
			Start-Process -FilePath $pythonInstaller -ArgumentList $arguments -Wait
			$cmd = Join-Path $targetDir "python.exe"
		} else {
			Write-Host "使用系统 Python: $detected"
		}
	}
	return $cmd
}

$basePython = Ensure-Python
$basePythonVersion = Get-PythonVersion $basePython
Write-Host "使用 Python $basePythonVersion ($basePython)"

# Prepare offline packages if requirements changed
$offlineStampFile = Join-Path $scriptDir ".offline_packages.sha256"
$reqHash = (Get-FileHash $reqFile -Algorithm SHA256).Hash
if (-not (Test-Path $offlineStampFile) -or ((Get-Content $offlineStampFile -ErrorAction SilentlyContinue) -ne $reqHash)) {
	Write-Host "准备离线安装包..."
	& $basePython "$scriptDir\scripts\prepare_offline_installation_packages.py"
	$reqHash | Set-Content $offlineStampFile
}

function Install-Requirements {
	if (-not (Test-Path $reqFile)) {
		return
	}

	$reqHash = (Get-FileHash $reqFile -Algorithm SHA256).Hash
	if (Test-Path $stampFile) {
		$saved = Get-Content $stampFile -ErrorAction SilentlyContinue | Select-Object -First 1
		if ($saved -eq $reqHash) {
			Write-Host "依赖未变化，跳过安装"
			return
		}
	}

	$hasOffline = (Test-Path $offlineDir) -and (Get-ChildItem -Path $offlineDir -File -ErrorAction SilentlyContinue | Select-Object -First 1)
	if ($hasOffline) {
		try {
			Write-Host "使用离线包安装依赖..."
			& $pythonExe -m pip install --no-index --find-links $offlineDir -r $reqFile
			$reqHash | Set-Content $stampFile
			return
		} catch {
			Write-Warning "离线依赖安装失败，尝试联网安装..."
		}
	} else {
		Write-Host "未找到离线依赖，尝试联网安装..."
	}

	Write-Host "使用联网安装依赖..."
	& $pythonExe -m pip install --no-cache-dir -r $reqFile
	$reqHash | Set-Content $stampFile
}

# Create venv if missing
if (-not (Test-Path $pythonExe)) {
	Write-Host "创建虚拟环境..."
	& $basePython -m venv $venvDir
}

if (Test-Path $pythonExe) {
	Install-Requirements
	& $pythonExe (Join-Path $scriptDir "main.py") @args
	exit $LASTEXITCODE
}

# Fallback to ensured python
& $basePython (Join-Path $scriptDir "main.py") @args