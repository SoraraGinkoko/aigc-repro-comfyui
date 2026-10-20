# Start ComfyUI server (default http://127.0.0.1:8188)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\run_comfyui.ps1

$VENV_PY   = "D:\comfyui_env\Scripts\python.exe"
$CONDA_PY1 = "D:\Anaconda_envs\envs\comfyui\python.exe"
$CONDA_PY2 = "C:\Users\32089\anaconda3\envs\comfyui\python.exe"
$COMFY_DIR = "D:\ComfyUI"
$COMFY    = "$COMFY_DIR\main.py"

if (Test-Path $VENV_PY) { $ENV_PY = $VENV_PY }
elseif (Test-Path $CONDA_PY1) { $ENV_PY = $CONDA_PY1 }
elseif (Test-Path $CONDA_PY2) { $ENV_PY = $CONDA_PY2 }
else {
    Write-Host "No python env found. Create conda env 'comfyui' or run install_env_venv.ps1." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $COMFY)) {
    Write-Host "ComfyUI not found: $COMFY -- run install_comfyui.ps1 first." -ForegroundColor Red
    exit 1
}

# Run inside ComfyUI dir so its relative paths (models/input/output) resolve correctly
Set-Location $COMFY_DIR
Write-Host "Using python: $ENV_PY"
Write-Host "Starting ComfyUI: http://127.0.0.1:8188 (Ctrl+C to stop)" -ForegroundColor Cyan
& $ENV_PY $COMFY --port 8188
