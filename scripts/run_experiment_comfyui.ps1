# Run the formal experiment inside the venv/conda python env.
# Prereq: install_env_venv.ps1 done AND run_comfyui.ps1 is running (port 8188).

# Switch to project root so relative paths (config, runs) resolve correctly
Set-Location (Join-Path $PSScriptRoot "..")

$VENV_PY   = "D:\comfyui_env\Scripts\python.exe"
$CONDA_PY1 = "D:\Anaconda_envs\envs\comfyui\python.exe"
$CONDA_PY2 = "C:\Users\32089\anaconda3\envs\comfyui\python.exe"

if (Test-Path $VENV_PY) { $ENV_PY = $VENV_PY }
elseif (Test-Path $CONDA_PY1) { $ENV_PY = $CONDA_PY1 }
elseif (Test-Path $CONDA_PY2) { $ENV_PY = $CONDA_PY2 }
else {
    Write-Host "No python env found. Create conda env 'comfyui' or run install_env_venv.ps1." -ForegroundColor Red
    exit 1
}

Write-Host "Using python: $ENV_PY"
& $ENV_PY run_experiment.py --config config\comfyui_experiment_config.json
