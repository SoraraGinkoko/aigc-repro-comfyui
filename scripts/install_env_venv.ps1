# Create a standalone venv (D:\comfyui_env) and install torch + ComfyUI deps.
# Bypasses conda entirely (conda's CUDA plugin can crash on Windows).
# Reuses the already-cloned ComfyUI and downloaded models.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install_env_venv.ps1

$ErrorActionPreference = "Stop"

$BASE_PY     = "C:\Users\32089\anaconda3\python.exe"
$VENV_DIR    = "D:\comfyui_env"
$VENV_PY     = "$VENV_DIR\Scripts\python.exe"
$COMFY_DIR   = "D:\ComfyUI"
$TORCH_INDEX = "https://download.pytorch.org/whl/cu121"

function Step($msg) { Write-Host "`n===== $msg =====" -ForegroundColor Cyan }
function Check($step) { if ($LASTEXITCODE -ne 0) { throw "$step failed (exit $LASTEXITCODE)" } }

if (-not (Test-Path $BASE_PY)) {
    throw "Anaconda python not found: $BASE_PY -- edit BASE_PY in this script."
}

Step "1/5 create venv at $VENV_DIR"
if (-not (Test-Path $VENV_PY)) {
    & $BASE_PY -m venv $VENV_DIR
    Check "venv creation"
} else {
    Write-Host "venv exists, skip"
}

Step "2/5 upgrade pip"
& $VENV_PY -m pip install --upgrade pip
Check "pip upgrade"

Step "3/5 install PyTorch (CUDA 121) + torchvision + torchaudio"
& $VENV_PY -m pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url $TORCH_INDEX
Check "torch install"

Step "4/5 install ComfyUI requirements"
& $VENV_PY -m pip install -r "$COMFY_DIR\requirements.txt"
Check "ComfyUI requirements"

Step "5/5 install extra deps (scikit-image for SSIM, lpips for LPIPS)"
& $VENV_PY -m pip install scikit-image lpips
Check "extra deps"

Write-Host "`nvenv ready at $VENV_DIR. Next: run scripts\run_comfyui.ps1" -ForegroundColor Green
