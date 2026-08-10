#Requires -Version 5.1
<#
.SYNOPSIS
  Start AronaAI backend, GPT-SoVITS, and the desktop client; stay running until stopped.

.DESCRIPTION
  1) Start backend and GPT-SoVITS at the same time
  2) Wait until both logs show a ready signal
  3) Start the frontend client
  4) Keep this script alive; press Enter (or type q / exit) to stop all services
     and exit. Ctrl+C also stops all tracked process trees.

  Ready signals (case-insensitive substring match):
    - "启动完毕"
    - "startup complete"   (covers uvicorn "Application startup complete.")

.PARAMETER CondaEnv
  Conda env used for the backend. Default: shittim-chest

.PARAMETER TimeoutSec
  Wait timeout in seconds for both backend services to become ready. Default: 600

.PARAMETER FrontendExe
  Optional path to AronaAI_Spine_WindowsClient.exe. If omitted, auto-detect.

.PARAMETER TtsStallSec
  Passed to GPT-SoVITS watchdog (stall seconds). Default: 60

.PARAMETER TtsRestartCooldownSec
  Passed to GPT-SoVITS watchdog (restart cooldown). Default: 90

.EXAMPLE
  .\start-all.ps1
  .\start-all.ps1 -CondaEnv arona -TimeoutSec 900
#>
[CmdletBinding()]
param(
    [string]$CondaEnv = "shittim-chest",
    [int]$TimeoutSec = 600,
    [string]$FrontendExe = "",
    [int]$TtsStallSec = 60,
    [int]$TtsRestartCooldownSec = 90
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$LogDir = Join-Path $Root ".start-logs"
$ReadyPatterns = @("启动完毕", "startup complete")
$script:BackendProc = $null
$script:GptProc = $null
$script:FrontendProc = $null
$script:ServicesStopped = $false

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

function Wait-ServicesReady {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable[]]$Services,
        [int]$TimeoutSeconds
    )

    $names = ($Services | ForEach-Object { $_.Name }) -join " + "
    Write-Step "Waiting for $names ready (patterns: $($ReadyPatterns -join ' / ')) ..." Yellow
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $ready = @{}
    foreach ($svc in $Services) { $ready[$svc.Name] = $false }

    while ((Get-Date) -lt $deadline) {
        foreach ($svc in $Services) {
            if ($ready[$svc.Name]) { continue }

            $proc = $svc.Process
            if ($proc -and $proc.HasExited) {
                throw "$($svc.Name) exited early (code $($proc.ExitCode)). See log: $($svc.LogPath)"
            }
            if (Test-ReadyLog -LogPath $svc.LogPath) {
                $ready[$svc.Name] = $true
                Write-Step "$($svc.Name) is ready." Green
            }
        }

        $pending = @($ready.GetEnumerator() | Where-Object { -not $_.Value } | ForEach-Object { $_.Key })
        if ($pending.Count -eq 0) { return }

        Start-Sleep -Milliseconds 500
    }

    $stillPending = @($ready.GetEnumerator() | Where-Object { -not $_.Value } | ForEach-Object { $_.Key })
    $details = ($Services | Where-Object { $stillPending -contains $_.Name } | ForEach-Object { "$($_.Name): $($_.LogPath)" }) -join "; "
    throw "Timed out after ${TimeoutSeconds}s waiting for: $($stillPending -join ', '). See logs: $details"
}

function Stop-TrackedProcessTree {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$Label = "process"
    )

    if ($null -eq $Process) { return }

    try {
        $Process.Refresh()
    } catch {
        return
    }

    if ($Process.HasExited) {
        Write-Host ("  {0} already exited (PID {1})." -f $Label, $Process.Id) -ForegroundColor DarkGray
        return
    }

    $procId = $Process.Id
    Write-Host ("  Stopping {0} (PID {1}) and child processes ..." -f $Label, $procId) -ForegroundColor Yellow
    $taskkill = Get-Command taskkill -ErrorAction SilentlyContinue
    if ($taskkill) {
        & taskkill.exe /PID $procId /T /F 2>$null | Out-Null
    }

    try {
        $Process.Refresh()
        if (-not $Process.HasExited) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    } catch {
        # Process may already be gone.
    }
}

function Stop-AllTrackedServices {
    if ($script:ServicesStopped) { return }
    $script:ServicesStopped = $true

    Write-Step "Stopping all services ..." Yellow
    Stop-TrackedProcessTree -Process $script:BackendProc -Label "Backend"
    Stop-TrackedProcessTree -Process $script:GptProc -Label "GPT-SoVITS"
    Stop-TrackedProcessTree -Process $script:FrontendProc -Label "Frontend"

    $deadline = (Get-Date).AddSeconds(5)
    while ((Get-Date) -lt $deadline) {
        $alive = @()
        foreach ($item in @(
                @{ Name = "Backend"; Process = $script:BackendProc },
                @{ Name = "GPT-SoVITS"; Process = $script:GptProc },
                @{ Name = "Frontend"; Process = $script:FrontendProc }
            )) {
            $p = $item.Process
            if ($null -eq $p) { continue }
            try {
                $p.Refresh()
                if (-not $p.HasExited) { $alive += $item.Name }
            } catch {}
        }
        if ($alive.Count -eq 0) { break }
        Start-Sleep -Milliseconds 200
    }

    Write-Step "All tracked services stopped." Green
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

    # Escape for single-quoted PowerShell string literals inside the child script.
    $titleEsc = $Title -replace "'", "''"
    $workDirEsc = $WorkDir -replace "'", "''"
    $logPathEsc = $LogPath -replace "'", "''"
    $exeEsc = $ExePath -replace "'", "''"
    $argLiterals = @($Arguments | ForEach-Object {
            "'" + ($_ -replace "'", "''") + "'"
        }) -join ", "
    if ([string]::IsNullOrEmpty($argLiterals)) {
        $argArrayExpr = "@()"
    } else {
        $argArrayExpr = "@($argLiterals)"
    }

    # Avoid PowerShell 5.1 "& exe 2>&1" capture (mis-decodes UTF-8 Chinese).
    # Launch with ProcessStartInfo UTF-8 readers and tee to console + log.
    $psCommand = @"
`$ErrorActionPreference = 'Continue'
`$Host.UI.RawUI.WindowTitle = '$titleEsc'
try { chcp 65001 | Out-Null } catch {}
`$utf8 = New-Object System.Text.UTF8Encoding `$false
`$OutputEncoding = `$utf8
try {
    [Console]::OutputEncoding = `$utf8
    [Console]::InputEncoding = `$utf8
} catch {}
`$env:PYTHONIOENCODING = 'utf-8'
`$env:PYTHONUTF8 = '1'
`$env:PYTHONLEGACYWINDOWSSTDIO = '0'
Set-Location -LiteralPath '$workDirEsc'
`$logPath = '$logPathEsc'
`$exe = '$exeEsc'
`$argv = $argArrayExpr
Write-Host '=== $titleEsc ===' -ForegroundColor Cyan
Write-Host ("WorkDir: {0}" -f (Get-Location))
Write-Host ("Command: {0} {1}" -f `$exe, (`$argv -join ' '))
Write-Host ("Log: {0}" -f `$logPath)
Write-Host ''

function Start-Utf8StreamPump {
    param([System.IO.StreamReader]`$Reader)
    `$rs = [System.Management.Automation.Runspaces.RunspaceFactory]::CreateRunspace()
    `$rs.Open()
    `$ps = [PowerShell]::Create()
    `$ps.Runspace = `$rs
    [void]`$ps.AddScript({
        param(`$reader, `$logPath, `$utf8)
        try {
            while (`$null -ne (`$line = `$reader.ReadLine())) {
                [Console]::WriteLine(`$line)
                [System.IO.File]::AppendAllText(`$logPath, `$line + [Environment]::NewLine, `$utf8)
            }
        } catch {}
    }).AddArgument(`$Reader).AddArgument(`$logPath).AddArgument(`$utf8)
    return @{
        PowerShell = `$ps
        Runspace   = `$rs
        Handle     = `$ps.BeginInvoke()
    }
}

try {
    `$psi = New-Object System.Diagnostics.ProcessStartInfo
    `$psi.FileName = `$exe
    # Quote args that contain whitespace; keep simple tokens as-is.
    `$psi.Arguments = (`$argv | ForEach-Object {
            `$a = [string]`$_
            if (`$a -match '\s') { '"' + (`$a -replace '"', '\"') + '"' } else { `$a }
        }) -join ' '
    `$psi.WorkingDirectory = (Get-Location).Path
    `$psi.UseShellExecute = `$false
    `$psi.RedirectStandardOutput = `$true
    `$psi.RedirectStandardError = `$true
    `$psi.RedirectStandardInput = `$false
    `$psi.CreateNoWindow = `$true
    `$psi.StandardOutputEncoding = `$utf8
    `$psi.StandardErrorEncoding = `$utf8
    `$psi.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
    `$psi.EnvironmentVariables['PYTHONUTF8'] = '1'
    `$psi.EnvironmentVariables['PYTHONLEGACYWINDOWSSTDIO'] = '0'

    `$proc = New-Object System.Diagnostics.Process
    `$proc.StartInfo = `$psi
    [void]`$proc.Start()

    `$outPump = Start-Utf8StreamPump -Reader `$proc.StandardOutput
    `$errPump = Start-Utf8StreamPump -Reader `$proc.StandardError

    `$proc.WaitForExit()
    try { [void]`$outPump.PowerShell.EndInvoke(`$outPump.Handle) } catch {}
    try { [void]`$errPump.PowerShell.EndInvoke(`$errPump.Handle) } catch {}
    `$outPump.PowerShell.Dispose()
    `$errPump.PowerShell.Dispose()
    `$outPump.Runspace.Close(); `$outPump.Runspace.Dispose()
    `$errPump.Runspace.Close(); `$errPump.Runspace.Dispose()

    Write-Host ''
    Write-Host ("Process exited with code {0}." -f `$proc.ExitCode) -ForegroundColor Yellow
} catch {
    Write-Host `$_ -ForegroundColor Red
    [System.IO.File]::AppendAllText(`$logPath, `$_.ToString() + [Environment]::NewLine, `$utf8)
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
$GptWatch = Join-Path $GptDir "watch-apiv2.ps1"
$GptRuntimePy = Join-Path $GptDir "runtime\python.exe"

Assert-Path $BackendDir "backend directory"
Assert-Path (Join-Path $BackendDir "app\main.py") "backend entry"
Assert-Path $GptDir "gpt-sovits directory"
Assert-Path $GptApi "GPT-SoVITS api_v2.py"
Assert-Path $GptWatch "GPT-SoVITS watch-apiv2.ps1"

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
Write-Host "  Timeout:     ${TimeoutSec}s for backend + GPT-SoVITS"

if (Test-Path -LiteralPath $GptRuntimePy) {
    $gptExe = $GptRuntimePy
} else {
    Write-Host "  runtime\python.exe not found; falling back to python on PATH" -ForegroundColor Yellow
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { throw "Neither gpt-sovits\runtime\python.exe nor python on PATH was found." }
    $gptExe = $py.Source
}

# ---- 1) Backend + GPT-SoVITS in parallel ----
try {
    Write-Step "Starting backend and GPT-SoVITS in parallel ..."
    $script:BackendProc = Start-ServiceWindow `
        -Title "AronaAI Backend" `
        -WorkDir $BackendDir `
        -ExePath $Conda `
        -Arguments @("run", "-n", $CondaEnv, "--no-capture-output", "python", "-m", "app.main") `
        -LogPath $backendLog
    $script:GptProc = Start-ServiceWindow `
        -Title "GPT-SoVITS API (watchdog)" `
        -WorkDir $GptDir `
        -ExePath "powershell.exe" `
        -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $GptWatch,
            "-LogPath", $gptLog,
            "-StallSec", "$TtsStallSec",
            "-RestartCooldownSec", "$TtsRestartCooldownSec"
        ) `
        -LogPath (Join-Path $LogDir "gpt-sovits-watchdog.log")

    Wait-ServicesReady -TimeoutSeconds $TimeoutSec -Services @(
        @{ Name = "Backend"; LogPath = $backendLog; Process = $script:BackendProc },
        @{ Name = "GPT-SoVITS"; LogPath = $gptLog; Process = $script:GptProc }
    )

    # ---- 2) Frontend ----
    Write-Step "Starting frontend ..."
    $script:FrontendProc = Start-Process -FilePath $Frontend.Exe `
        -WorkingDirectory $Frontend.WorkDir `
        -PassThru
    Write-Step "All services launched." Green

    $backendPid = if ($script:BackendProc) { $script:BackendProc.Id } else { "n/a" }
    $gptPid = if ($script:GptProc) { $script:GptProc.Id } else { "n/a" }
    $frontendPid = if ($script:FrontendProc) { $script:FrontendProc.Id } else { "n/a" }
    Write-Host @"

Backend / GPT-SoVITS keep running in their own windows.
  Backend PID:    $backendPid
  GPT-SoVITS PID: $gptPid
  Frontend PID:   $frontendPid
  Frontend:       $($Frontend.Exe)

Logs:
  $backendLog
  $gptLog

This window stays open. Press Enter to stop all services
(or type q / exit then Enter). Ctrl+C also stops everything.
"@

    # ---- 3) Stay alive until user requests stop ----
    while ($true) {
        $answer = Read-Host "Stop all"
        $trimmed = if ($null -eq $answer) { "" } else { $answer.Trim() }
        if ($trimmed -eq "" -or $trimmed -match '^(?i)(q|quit|exit)$') {
            break
        }
        Write-Host "Unrecognized input. Press Enter (or type q / exit) to stop all services." -ForegroundColor Yellow
    }
} finally {
    Stop-AllTrackedServices
}
