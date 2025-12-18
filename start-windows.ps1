$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$venvDir = Join-Path $scriptDir ".venv-windows"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
$reqFile = Join-Path $scriptDir "requirements.txt"

# Create venv if missing
if (-not (Test-Path $pythonExe)) {
	python -m venv $venvDir
}

if (Test-Path $pythonExe) {
	if (Test-Path $reqFile) {
		& $pythonExe -m pip install --no-cache-dir -r $reqFile
	}
	& $pythonExe (Join-Path $scriptDir "main.py") @args
	exit $LASTEXITCODE
}

# Fallback to system python
python (Join-Path $scriptDir "main.py") @args