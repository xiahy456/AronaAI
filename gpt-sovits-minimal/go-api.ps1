#Requires -Version 5.1
# Start GPT-SoVITS minimal_inference API with watchdog (auto-restart on crash)
$ErrorActionPreference = "Stop"
$Watch = Join-Path $PSScriptRoot "watch-api.ps1"
if (-not (Test-Path -LiteralPath $Watch)) {
    throw "watch-api.ps1 not found in $PSScriptRoot"
}
& $Watch @args
