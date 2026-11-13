param(
    [string]$Python = 'python',
    [ValidateSet('smoke', 'full')][string]$Suite = 'full',
    [int]$MaxAttempts = 3,
    [int]$SequenceCap = 0,
    [string]$VcVarsBat = ''
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$architecture = & $Python -c "import platform; print(platform.machine().lower())"
if ($LASTEXITCODE -ne 0) { throw 'Python architecture detection failed' }
$target = if ($architecture -in @('arm64', 'aarch64')) { 'arm64' } else { 'x64' }
if ($VcVarsBat) {
    $nativeEnv = & $env:ComSpec /d /s /c ('call "' + $VcVarsBat + '" >nul && set')
    if ($LASTEXITCODE -ne 0) { throw 'Native MSVC initialization failed' }
    foreach ($line in $nativeEnv) {
        if ($line -match '^([^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
        }
    }
} else {
    $vswhere = 'C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe'
    if (-not (Test-Path $vswhere)) { throw 'Provide -VcVarsBat or install Visual Studio' }
    $component = if ($target -eq 'arm64') { 'Microsoft.VisualStudio.Component.VC.Tools.ARM64' } else { 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64' }
    $vs = & $vswhere -latest -products '*' -requires $component -property installationPath
    if ($vs) {
        Import-Module (Join-Path $vs 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
        Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments "-arch=$target -host_arch=$target"
    } else { throw "Native $target MSVC toolchain unavailable" }
}
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONUNBUFFERED = '1'
& $Python (Join-Path $PSScriptRoot 'windows_native.py') --suite $Suite --max-attempts $MaxAttempts --sequence-cap $SequenceCap
exit $LASTEXITCODE
