#Requires -Version 5.1
<#
.SYNOPSIS
  Create the minimal conda env used to pack the Windows backend portable directory.

.DESCRIPTION
  Builds env "arona-backend" (override with -EnvName) with:
    - Python 3.10 (matches the existing backend conda envs on this project)
    - CPU PyTorch (BGE embeddings; do not use the Unsloth training CUDA torch)
    - backend/requirements.txt
    - CUDA llama-cpp-python from the abetlen extra index (default cu118)

  If `conda create` cannot reach Anaconda mirrors, the script falls back to
  `python -m venv --copies` using an existing 3.10 interpreter (arona /
  shittim-chest), then pip-installs only runtime deps into that prefix.

  Do NOT pack shittim-chest itself if it contains Unsloth / CUDA PyTorch.
  After this succeeds, run pack-backend.ps1.

.PARAMETER EnvName
  Conda environment name. Default: arona-backend

.PARAMETER PythonVersion
  CPython version for conda create. Must match what pack-backend.ps1 copies.
  Default: 3.10

.PARAMETER SeedPython
  Interpreter used when conda create fails. Default: auto-detect arona or
  shittim-chest python.exe.

.PARAMETER CudaTag
  llama-cpp-python extra-index tag: cu118, cu121, cu122, cu124, cpu.
  Default: cu118 (matches root README CUDA 11.8).

.PARAMETER Recreate
  Remove the env first if it already exists.

.EXAMPLE
  .\setup-backend-pack-env.ps1
  .\setup-backend-pack-env.ps1 -CudaTag cu121 -Recreate
#>
[CmdletBinding()]
param(
    [string]$EnvName = "arona-backend",
    [string]$PythonVersion = "3.10",
    [ValidateSet("cu118", "cu121", "cu122", "cu124", "cpu")]
    [string]$CudaTag = "cu118",
    [string]$SeedPython = "",
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Requirements = Join-Path $Root "backend\requirements.txt"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message) -ForegroundColor Cyan
}

function Get-CondaExe {
    $cmd = Get-Command conda -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        return $cmd.Source
    }
    $candidates = @(
        (Join-Path $env:USERPROFILE "miniconda3\Scripts\conda.exe"),
        (Join-Path $env:USERPROFILE "anaconda3\Scripts\conda.exe"),
        (Join-Path $env:USERPROFILE "Miniconda3\Scripts\conda.exe"),
        "C:\ProgramData\miniconda3\Scripts\conda.exe",
        "C:\ProgramData\anaconda3\Scripts\conda.exe",
        "D:\miniconda3\Scripts\conda.exe",
        "D:\Miniconda3\Scripts\conda.exe",
        "D:\Miniconda\Scripts\conda.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path -LiteralPath $p)) {
            return $p
        }
    }
    throw "conda.exe not found. Install Miniconda / Anaconda and retry."
}

function Get-CondaBase {
    param([string]$CondaExe)
    $info = & $CondaExe info --json | ConvertFrom-Json
    if ($info.root_prefix) {
        return $info.root_prefix
    }
    return (Split-Path (Split-Path $CondaExe -Parent) -Parent)
}

function Find-SeedPython {
    param([string]$CondaBase, [string]$Explicit)
    if ($Explicit -and (Test-Path -LiteralPath $Explicit)) {
        return $Explicit
    }
    foreach ($name in @("arona", "shittim-chest")) {
        $candidate = Join-Path $CondaBase "envs\$name\python.exe"
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return $null
}

if (-not (Test-Path -LiteralPath $Requirements)) {
    throw "Missing $Requirements"
}

$Conda = Get-CondaExe
$CondaBase = Get-CondaBase -CondaExe $Conda
$Prefix = Join-Path $CondaBase "envs\$EnvName"
Write-Host "conda:  $Conda"
Write-Host "prefix: $Prefix"
Write-Host "env:    $EnvName  python=$PythonVersion  llama-cpp=$CudaTag"

$envList = & $Conda env list --json | ConvertFrom-Json
$existing = @($envList.envs) | Where-Object {
    [IO.Path]::GetFileName($_) -eq $EnvName
}

if ((Test-Path -LiteralPath $Prefix) -and $Recreate) {
    Write-Step "Removing existing prefix $Prefix"
    if ($existing) {
        & $Conda env remove -n $EnvName -y
    }
    if (Test-Path -LiteralPath $Prefix) {
        Remove-Item -LiteralPath $Prefix -Recurse -Force
    }
    $existing = $null
}

if (-not (Test-Path -LiteralPath (Join-Path $Prefix "python.exe"))) {
    $seed = Find-SeedPython -CondaBase $CondaBase -Explicit $SeedPython
    if ($seed) {
        Write-Step "Creating venv --copies at $Prefix"
        Write-Host "seed python: $seed"
        if (Test-Path -LiteralPath $Prefix) {
            Remove-Item -LiteralPath $Prefix -Recurse -Force
        }
        New-Item -ItemType Directory -Force -Path (Split-Path $Prefix) | Out-Null
        & $seed -m venv --copies $Prefix
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $Prefix "python.exe"))) {
            throw "python -m venv failed"
        }
    }
    else {
        Write-Step "Creating conda env $EnvName (python=$PythonVersion)"
        & $Conda create -n $EnvName "python=$PythonVersion" pip -y
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $Prefix "python.exe"))) {
            throw "conda create failed and no seed python.exe for venv. Pass -SeedPython."
        }
    }
}
else {
    Write-Host "Env already exists: $Prefix"
    Write-Host "Use -Recreate to build it from scratch."
}

$EnvPython = Join-Path $Prefix "python.exe"
if (-not (Test-Path -LiteralPath $EnvPython)) {
    throw "Missing $EnvPython"
}

function Invoke-EnvPip {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$PipArgs)
    Write-Host ("pip {0}" -f ($PipArgs -join " "))
    & $EnvPython -m pip @PipArgs
    if ($LASTEXITCODE -ne 0) {
        throw "pip failed: $($PipArgs -join ' ')"
    }
}

Write-Step "Installing CPU PyTorch"
Invoke-EnvPip install --upgrade pip
Invoke-EnvPip install torch --index-url "https://download.pytorch.org/whl/cpu"

Write-Step "Installing backend/requirements.txt"
Invoke-EnvPip install -r $Requirements

if ($CudaTag -eq "cpu") {
    Write-Host "Keeping pip llama-cpp-python (CPU)."
}
else {
    Write-Step "Reinstalling llama-cpp-python ($CudaTag wheel)"
    $extra = "https://abetlen.github.io/llama-cpp-python/whl/$CudaTag"
    try {
        Invoke-EnvPip install llama-cpp-python --force-reinstall --no-cache-dir --extra-index-url $extra
    }
    catch {
        Write-Host "CUDA wheel install failed; leaving the requirements.txt llama-cpp-python build." -ForegroundColor Yellow
        Write-Host $_
    }
}

Write-Step "Sanity imports"
& $EnvPython -c @"
import fastapi, uvicorn, yaml, pydantic, httpx, jieba, chromadb, sentence_transformers
from llama_cpp import Llama
import torch
print('ok', 'python', __import__('sys').version.split()[0], 'torch', torch.__version__, 'cuda_torch', torch.cuda.is_available())
"@
if ($LASTEXITCODE -ne 0) {
    throw "Sanity import failed"
}

Write-Host ""
Write-Host ("[{0}] Env {1} is ready. Next: .\pack-backend.ps1" -f (Get-Date -Format "HH:mm:ss"), $EnvName) -ForegroundColor Green
