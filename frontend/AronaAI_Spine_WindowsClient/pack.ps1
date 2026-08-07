#Requires -Version 5.1
<#
.SYNOPSIS
  Package AronaAI_Spine_WindowsClient into a portable release folder.

.DESCRIPTION
  Copies the Release exe, runs windeployqt for Qt runtime DLLs/plugins,
  copies Assets / Config / Dict / fonts, and rewrites Config/config.json
  to use paths relative to the package root.

.PARAMETER QtBin
  Path to Qt bin directory containing windeployqt.exe.
  Default: D:\Qt68\6.5.3\msvc2019_64\bin

.PARAMETER DistDir
  Output package directory. Default: <script_dir>\dist\AronaAI_Client

.PARAMETER ExePath
  Path to Release exe. Default: <script_dir>\x64\Release\AronaAI_Spine_WindowsClient.exe

.PARAMETER KeepSecrets
  If set, keep tencent_speech_recognizer secrets from the source config.
  By default secrets are replaced with placeholders.

.EXAMPLE
  .\pack.ps1

.EXAMPLE
  .\pack.ps1 -KeepSecrets -QtBin "D:\Qt68\6.5.3\msvc2019_64\bin"
#>
[CmdletBinding()]
param(
    [string]$QtBin = "D:\Qt68\6.5.3\msvc2019_64\bin",
    [string]$DistDir = "",
    [string]$ExePath = "",
    [switch]$KeepSecrets
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
if (-not $DistDir) { $DistDir = Join-Path $Root "dist\AronaAI_Client" }
if (-not $ExePath) { $ExePath = Join-Path $Root "x64\Release\AronaAI_Spine_WindowsClient.exe" }

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-Path([string]$Path, [string]$Hint) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Hint not found: $Path"
    }
}

function Copy-Tree([string]$Source, [string]$Destination) {
    Assert-Path $Source "Source"
    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    $parent = Split-Path -Parent $Destination
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

# --- Preconditions -----------------------------------------------------------
Write-Step "Checking inputs"
Assert-Path $ExePath "Release executable"
$WinDeployQt = Join-Path $QtBin "windeployqt.exe"
Assert-Path $WinDeployQt "windeployqt.exe (pass -QtBin if Qt is elsewhere)"

$AssetsSrc = Join-Path $Root "Assets"
$ConfigSrc = Join-Path $Root "Config"
$DictSrc   = Join-Path $Root "Dict"
# Root = .../frontend/AronaAI_Spine_WindowsClient → repo root is ../..
$RepoRoot = (Resolve-Path (Join-Path $Root "..\..")).Path
$FontSrc  = Join-Path $RepoRoot "assets\font\Blueaka"

Assert-Path $AssetsSrc "Assets"
Assert-Path $ConfigSrc "Config"
Assert-Path $DictSrc "Dict"
Assert-Path $FontSrc "Blueaka font directory"

$SourceConfig = Join-Path $ConfigSrc "config.json"
if (-not (Test-Path -LiteralPath $SourceConfig)) {
    $SourceConfig = Join-Path $ConfigSrc "config.example.json"
    Write-Host "config.json missing; using config.example.json" -ForegroundColor Yellow
}
Assert-Path $SourceConfig "Config JSON"

# --- Clean / create dist -----------------------------------------------------
Write-Step "Preparing package directory: $DistDir"
if (Test-Path -LiteralPath $DistDir) {
    Remove-Item -LiteralPath $DistDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

$ExeName = Split-Path $ExePath -Leaf
Copy-Item -LiteralPath $ExePath -Destination (Join-Path $DistDir $ExeName) -Force
Write-Host "Copied $ExeName"

# --- windeployqt -------------------------------------------------------------
Write-Step "Running windeployqt"
# Help windeployqt locate VC++ redistributables when run outside a VS Developer shell.
if (-not $env:VCINSTALLDIR) {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path -LiteralPath $vswhere) {
        $vsPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null
        if ($vsPath) {
            $vcCandidates = Get-ChildItem -Path (Join-Path $vsPath "VC\Redist\MSVC") -Directory -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending
            if ($vcCandidates) {
                $env:VCINSTALLDIR = (Join-Path $vsPath "VC\")
                Write-Host "VCINSTALLDIR=$($env:VCINSTALLDIR)"
            }
        }
    }
}
$deployArgs = @(
    "--release",
    "--compiler-runtime",
    "--opengl",
    "--multimedia",
    "--websockets",
    (Join-Path $DistDir $ExeName)
)
& $WinDeployQt @deployArgs
if ($LASTEXITCODE -ne 0) {
    throw "windeployqt failed with exit code $LASTEXITCODE"
}

# --- Assets / Dict / fonts ---------------------------------------------------
Write-Step "Copying Assets, Dict, fonts"
Copy-Tree $AssetsSrc (Join-Path $DistDir "Assets")
Copy-Tree $DictSrc   (Join-Path $DistDir "Dict")
Copy-Tree $FontSrc   (Join-Path $DistDir "fonts\Blueaka")

# --- Config with relative paths ---------------------------------------------
Write-Step "Writing Config/config.json (relative paths)"
$configDir = Join-Path $DistDir "Config"
New-Item -ItemType Directory -Force -Path $configDir | Out-Null

$config = Get-Content -LiteralPath $SourceConfig -Raw -Encoding UTF8 | ConvertFrom-Json

# Preserve non-path settings from source; overwrite filesystem paths for portable use.
if (-not $config.settings) { $config | Add-Member -NotePropertyName settings -NotePropertyValue ([pscustomobject]@{}) }
$config.settings.dict_path = "Dict/dict_zh.json"
$config.settings.icon_path = "Assets/ProgramAssets/Icon.png"
$config.settings.qhotkey_path = "QHotkey"
$config.settings.text_box_path = "Assets/ProgramAssets/TextBox.png"
$config.settings.push_button_path = "Assets/ProgramAssets/PushButton.png"
$config.settings.settings_bg_path = "Assets/ProgramAssets/SettingsMainBGWidget.png"
$config.settings.close_button_path = "Assets/ProgramAssets/CloseButton.png"
$config.settings.top_information_path = "Assets/ProgramAssets/TopInformationWidget.png"
$config.settings.font_path = "fonts/Blueaka"
$config.settings.arona_ai_mode_switch_button_0 = "Assets/ProgramAssets/AronaAIModeSwitchButton_0.png"
$config.settings.arona_ai_mode_switch_button_1 = "Assets/ProgramAssets/AronaAIModeSwitchButton_1.png"
$config.settings.origin_logo_path = "Assets/ProgramAssets/BALogo.png"

if (-not $config.spine) { $config | Add-Member -NotePropertyName spine -NotePropertyValue ([pscustomobject]@{}) }
$config.spine.skelOrJson_path = "Assets/AronaSpineAssets/arona_spr.json"
$config.spine.atlas_path = "Assets/AronaSpineAssets/Arona01.atlas"

if (-not $config.tencent_speech_recognizer) {
    $config | Add-Member -NotePropertyName tencent_speech_recognizer -NotePropertyValue ([pscustomobject]@{})
}
if (-not $KeepSecrets) {
    $config.tencent_speech_recognizer.secret_id = '${TENCENT_SECRET_ID}'
    $config.tencent_speech_recognizer.secret_key = '${TENCENT_SECRET_KEY}'
    Write-Host "Sanitized tencent_speech_recognizer secrets (use -KeepSecrets to retain)." -ForegroundColor Yellow
}

# Drop machine-local program shortcuts from the portable package.
if ($config.PSObject.Properties.Name -contains "program_path") {
    $config.PSObject.Properties.Remove("program_path")
}

$outConfig = Join-Path $configDir "config.json"
$json = $config | ConvertTo-Json -Depth 20
# PowerShell ConvertTo-Json escapes non-ASCII; write UTF-8 without BOM for Qt.
[System.IO.File]::WriteAllText($outConfig, $json, (New-Object System.Text.UTF8Encoding $false))

# Keep example alongside for reference
$exampleSrc = Join-Path $ConfigSrc "config.example.json"
if (Test-Path -LiteralPath $exampleSrc) {
    Copy-Item -LiteralPath $exampleSrc -Destination (Join-Path $configDir "config.example.json") -Force
}

# --- Summary -----------------------------------------------------------------
Write-Step "Done"
Write-Host "Package ready at:" -ForegroundColor Green
Write-Host "  $DistDir"
Write-Host ""
Write-Host "Launch:"
Write-Host "  cd `"$DistDir`""
Write-Host "  .\$ExeName"
Write-Host ""
Write-Host "Edit Config\config.json for websocket_url / TTS host before distributing."
if (-not $KeepSecrets) {
    Write-Host "Fill tencent secrets in Config\config.json if ASR is needed."
}
