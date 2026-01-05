$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$venvDir = Join-Path $scriptDir ".venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
$reqFile = Join-Path $scriptDir "requirements.txt"
$offlineDir = Join-Path $scriptDir "cxvoyager\common\resources\offline_packages"
$stampFile = Join-Path $venvDir ".requirements.sha256"

# Prepare offline packages if needed
if (-not (Test-Path $offlineDir) -or -not (Get-ChildItem -Path $offlineDir -File -ErrorAction SilentlyContinue | Select-Object -First 1)) {
	Write-Host "准备离线安装包..."
	python "$scriptDir\scripts\prepare_offline_installation_packages.py"
}

function Install-Requirements {
	if (-not (Test-Path $reqFile)) {
		return
	}

	$reqHash = (Get-FileHash $reqFile -Algorithm SHA256).Hash
	if (Test-Path $stampFile) {
		$saved = Get-Content $stampFile -ErrorAction SilentlyContinue | Select-Object -First 1
		if ($saved -eq $reqHash) {
			return
		}
	}

	$hasOffline = (Test-Path $offlineDir) -and (Get-ChildItem -Path $offlineDir -File -ErrorAction SilentlyContinue | Select-Object -First 1)
	if ($hasOffline) {
		try {
			& $pythonExe -m pip install --no-index --find-links $offlineDir -r $reqFile
			$reqHash | Set-Content $stampFile
			return
		} catch {
			Write-Warning "离线依赖安装失败，尝试联网安装..."
		}
	} else {
		Write-Host "未找到离线依赖，尝试联网安装..."
	}

	& $pythonExe -m pip install --no-cache-dir -r $reqFile
	$reqHash | Set-Content $stampFile
}

# Create venv if missing
if (-not (Test-Path $pythonExe)) {
	python -m venv $venvDir
}

if (Test-Path $pythonExe) {
	Install-Requirements
	& $pythonExe (Join-Path $scriptDir "main.py") @args
	exit $LASTEXITCODE
}

# Fallback to system python
python (Join-Path $scriptDir "main.py") @args