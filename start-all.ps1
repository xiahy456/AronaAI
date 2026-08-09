#Requires -Version 5.1
<#
.SYNOPSIS
  Sequentially start AronaAI backend, GPT-SoVITS, then the desktop client.

.DESCRIPTION
  1) Start backend and wait until its log shows a ready signal
  2) Start GPT-SoVITS and wait until its log shows a ready signal
  3) Start the frontend client

  Ready signals (case-insensitive substring match):
    - "启动完毕"
    - "startup complete"   (covers uvicorn "Application startup complete.")

.PARAMETER CondaEnv
  Conda env used for the backend. Default: shittim-chest

.PARAMETER TimeoutSec
  Per-service wait timeout in seconds. Default: 600

.PARAMETER FrontendExe
  Optional path to AronaAI_Spine_WindowsClient.exe. If omitted, auto-detect.

.EXAMPLE
  .\start-all.ps1
  .\start-all.ps1 -CondaEnv arona -TimeoutSec 900
#>
[CmdletBinding()]
param(
    [string]$CondaEnv = "shittim-chest",
    [int]$TimeoutSec = 600,
    [string]$FrontendExe = ""
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$LogDir = Join-Path $Root ".start-logs"
$ReadyPatterns = @("启动完毕", "startup complete")

function Write-Step {
    param([string]$Message, [ConsoleColor]$Color = [ConsoleColor]::Cyan)
    Write-Host ""
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message) -ForegroundColor $Color
}

function Assert-Path {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing ${Label}: $Path"
    }
}

function Resolve-CondaCmd {
    $cmd = Get-Command conda -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        (Join-Path $env:USERPROFILE "Miniconda3\Scripts\conda.exe"),
        (Join-Path $env:USERPROFILE "anaconda3\Scripts\conda.exe"),
        "D:\Miniconda\Scripts\conda.exe",
        "C:\Miniconda3\Scripts\conda.exe",
        "C:\ProgramData\miniconda3\Scripts\conda.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return $c }
    }
    throw "conda not found. Install Miniconda/Anaconda or add conda to PATH."
}

function Resolve-Frontend {
    param([string]$Explicit)

    if ($Explicit) {
        Assert-Path $Explicit "frontend executable"
        $dir = Split-Path -Parent $Explicit
        return @{ Exe = (Resolve-Path $Explicit).Path; WorkDir = $dir }
    }

    $workDir = Join-Path $Root "frontend\AronaAI_Spine_WindowsClient\dist\AronaAI_Client"
    $exe = Join-Path $workDir "AronaAI_Spine_WindowsClient.exe"
    Assert-Path $exe "frontend executable"
    return @{
        Exe     = (Resolve-Path $exe).Path
        WorkDir = (Resolve-Path $workDir).Path
    }
}

function Test-ReadyLog {
    param([string]$LogPath)

    if (-not (Test-Path -LiteralPath $LogPath)) { return $false }
    try {
        # FileShare.ReadWrite so the writer can keep appending
        $fs = [System.IO.File]::Open(
            $LogPath,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite
        )
        try {
            $reader = New-Object System.IO.StreamReader($fs, [System.Text.Encoding]::UTF8, $true)
            $text = $reader.ReadToEnd()
            $reader.Dispose()
        } finally {
            $fs.Dispose()
        }
    } catch {
        return $false
    }

    if ([string]::IsNullOrWhiteSpace($text)) { return $false }
    if ($text -match "启动完毕") { return $true }
    if ($text -match "(?i)startup\s+complete") { return $true }
    return $false
}

function Wait-ServiceReady {
    param(
        [string]$Name,
        [string]$LogPath,
        [System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds
    )

    Write-Step "Waiting for $Name ready (patterns: $($ReadyPatterns -join ' / ')) ..." Yellow
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        if ($Process -and $Process.HasExited) {
            throw "$Name exited early (code $($Process.ExitCode)). See log: $LogPath"
        }
        if (Test-ReadyLog -LogPath $LogPath) {
            Write-Step "$Name is ready." Green
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Timed out after ${TimeoutSeconds}s waiting for $Name. See log: $LogPath"
}

function Start-ServiceWindow {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][string]$WorkDir,
        [Parameter(Mandatory = $true)][string]$ExePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$LogPath
    )

    if (Test-Path -LiteralPath $LogPath) {
        Remove-Item -LiteralPath $LogPath -Force
    }
    New-Item -ItemType File -Path $LogPath -Force | Out-Null

    # Serialize args for the child PowerShell as a single-quoted list literal.
    $argLiterals = @($Arguments | ForEach-Object {
            "'" + ($_ -replace "'", "''") + "'"
        }) -join ", "
    if ([string]::IsNullOrEmpty($argLiterals)) {
        $argArrayExpr = "@()"
    } else {
        $argArrayExpr = "@($argLiterals)"
    }

    $psCommand = @"
`$ErrorActionPreference = 'Continue'
`$Host.UI.RawUI.WindowTitle = '$($Title -replace "'", "''")'
Set-Location -LiteralPath '$($WorkDir -replace "'", "''")'
`$logPath = '$($LogPath -replace "'", "''")'
`$exe = '$($ExePath -replace "'", "''")'
`$argv = $argArrayExpr
Write-Host '=== $Title ===' -ForegroundColor Cyan
Write-Host ("WorkDir: {0}" -f (Get-Location))
Write-Host ("Command: {0} {1}" -f `$exe, (`$argv -join ' '))
Write-Host ("Log: {0}" -f `$logPath)
Write-Host ''
try {
    & `$exe @argv 2>&1 | ForEach-Object {
        `$line = `$_.ToString()
        Write-Host `$line
        [System.IO.File]::AppendAllText(`$logPath, `$line + [Environment]::NewLine, [System.Text.UTF8Encoding]::new(`$false))
    }
    Write-Host ''
    Write-Host ("Process exited with code {0}." -f `$LASTEXITCODE) -ForegroundColor Yellow
} catch {
    Write-Host `$_ -ForegroundColor Red
    [System.IO.File]::AppendAllText(`$logPath, `$_.ToString() + [Environment]::NewLine, [System.Text.UTF8Encoding]::new(`$false))
}
Write-Host 'Close this window when done.' -ForegroundColor Yellow
pause
"@

    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($psCommand))
    return Start-Process -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encoded) `
        -PassThru `
        -WindowStyle Normal
}

# ---- prep ----
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$BackendDir = Join-Path $Root "backend"
$GptDir = Join-Path $Root "gpt-sovits"
$GptApi = Join-Path $GptDir "api_v2.py"
$GptRuntimePy = Join-Path $GptDir "runtime\python.exe"

Assert-Path $BackendDir "backend directory"
Assert-Path (Join-Path $BackendDir "app\main.py") "backend entry"
Assert-Path $GptDir "gpt-sovits directory"
Assert-Path $GptApi "GPT-SoVITS api_v2.py"

$Conda = Resolve-CondaCmd
$Frontend = Resolve-Frontend -Explicit $FrontendExe

$backendLog = Join-Path $LogDir "backend.log"
$gptLog = Join-Path $LogDir "gpt-sovits.log"

Write-Step "AronaAI start-all"
Write-Host "  Root:        $Root"
Write-Host "  Conda:       $Conda"
Write-Host "  CondaEnv:    $CondaEnv"
Write-Host "  Frontend:    $($Frontend.Exe)"
Write-Host "  FrontendCwd: $($Frontend.WorkDir)"
Write-Host "  Logs:        $LogDir"
Write-Host "  Timeout:     ${TimeoutSec}s per service"

# ---- 1) Backend ----
Write-Step "Starting backend ..."
$backendProc = Start-ServiceWindow `
    -Title "AronaAI Backend" `
    -WorkDir $BackendDir `
    -ExePath $Conda `
    -Arguments @("run", "-n", $CondaEnv, "--no-capture-output", "python", "-m", "app.main") `
    -LogPath $backendLog
Wait-ServiceReady -Name "Backend" -LogPath $backendLog -Process $backendProc -TimeoutSeconds $TimeoutSec

# ---- 2) GPT-SoVITS ----
Write-Step "Starting GPT-SoVITS ..."
if (Test-Path -LiteralPath $GptRuntimePy) {
    $gptExe = $GptRuntimePy
} else {
    Write-Host "  runtime\python.exe not found; falling back to python on PATH" -ForegroundColor Yellow
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { throw "Neither gpt-sovits\runtime\python.exe nor python on PATH was found." }
    $gptExe = $py.Source
}
$gptProc = Start-ServiceWindow `
    -Title "GPT-SoVITS API" `
    -WorkDir $GptDir `
    -ExePath $gptExe `
    -Arguments @("-I", "api_v2.py") `
    -LogPath $gptLog
Wait-ServiceReady -Name "GPT-SoVITS" -LogPath $gptLog -Process $gptProc -TimeoutSeconds $TimeoutSec

# ---- 3) Frontend ----
Write-Step "Starting frontend ..."
Start-Process -FilePath $Frontend.Exe -WorkingDirectory $Frontend.WorkDir | Out-Null
Write-Step "All services launched." Green
Write-Host @"

Backend / GPT-SoVITS keep running in their own windows.
Frontend: $($Frontend.Exe)

Logs:
  $backendLog
  $gptLog
"@
