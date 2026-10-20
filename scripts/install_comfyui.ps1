# ComfyUI + SD1.5 + Canny ControlNet installer (Windows / NVIDIA)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install_comfyui.ps1
#
# - Installs ComfyUI to D:\ComfyUI, conda env "comfyui" (Python 3.12)
# - Downloads SD1.5 + Canny ControlNet (HuggingFace official), prints SHA-256
# - Does NOT modify system PATH/env vars; only creates one conda env.

$ErrorActionPreference = "Stop"

$COMFY_DIR   = "D:\ComfyUI"
$CONDA_ENV   = "comfyui"
$PY_VER      = "3.12"
$CONDA_EXE   = "C:\Users\32089\anaconda3\Scripts\conda.exe"
$TORCH_INDEX = "https://download.pytorch.org/whl/cu121"

function Step($msg) { Write-Host "`n===== $msg =====" -ForegroundColor Cyan }

Step "1/8 check conda"
if (-not (Test-Path $CONDA_EXE)) {
    Write-Error "conda not found: $CONDA_EXE -- edit CONDA_EXE in this script and retry."
}

Step "2/8 git clone ComfyUI"
if (-not (Test-Path $COMFY_DIR)) {
    git clone https://github.com/comfyanonymous/ComfyUI.git $COMFY_DIR
} else {
    Write-Host "$COMFY_DIR already exists, skip clone"
}

Step "3/8 create conda env $CONDA_ENV (Python $PY_VER)"
& $CONDA_EXE create -n $CONDA_ENV python=$PY_VER -y

Step "4/8 install PyTorch (CUDA 121) + torchvision + torchaudio"
& $CONDA_EXE run -n $CONDA_ENV python -m pip install --upgrade pip
& $CONDA_EXE run -n $CONDA_ENV python -m pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url $TORCH_INDEX

Step "5/8 install ComfyUI requirements"
& $CONDA_EXE run -n $CONDA_ENV python -m pip install -r "$COMFY_DIR\requirements.txt"

Step "6/8 install extra deps (scikit-image for SSIM, lpips for LPIPS)"
& $CONDA_EXE run -n $CONDA_ENV python -m pip install scikit-image lpips

Step "7/8 download models (HuggingFace official)"
$CKPT_DIR = "$COMFY_DIR\models\checkpoints"
$CTRL_DIR = "$COMFY_DIR\models\controlnet"
New-Item -ItemType Directory -Force -Path $CKPT_DIR, $CTRL_DIR | Out-Null

$sd15 = "$CKPT_DIR\v1-5-pruned-emaonly.safetensors"
if (-not (Test-Path $sd15)) {
    Invoke-WebRequest -Uri "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors" -OutFile $sd15
} else { Write-Host "SD1.5 exists, skip download" }

$canny = "$CTRL_DIR\control_v11p_sd15_canny.pth"
if (-not (Test-Path $canny)) {
    Invoke-WebRequest -Uri "https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_canny.pth" -OutFile $canny
} else { Write-Host "ControlNet exists, skip download" }

Step "8/8 copy control image + print model SHA-256 (record for the paper)"
Copy-Item "$PSScriptRoot\..\assets\control_image.png" "$COMFY_DIR\input\control_image.png" -Force
Write-Host ("SD1.5  SHA-256: " + (Get-FileHash $sd15 -Algorithm SHA256).Hash)
Write-Host ("ControlNet SHA-256: " + (Get-FileHash $canny -Algorithm SHA256).Hash)

Write-Host "`nInstall done. Next: run scripts\run_comfyui.ps1 to start the server." -ForegroundColor Green
