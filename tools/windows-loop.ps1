param(
    [string]$Python = 'python',
    [ValidateSet('smoke', 'full')][string]$Suite = 'full',
    [int]$MaxAttempts = 3
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$vswhere = 'C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe'
if (Test-Path $vswhere) {
    $vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($vs) {
        Import-Module (Join-Path $vs 'Common7/Tools/Microsoft.VisualStudio.DevShell.dll')
        Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64'
    }
}
& $Python (Join-Path $PSScriptRoot 'windows_native.py') --suite $Suite --max-attempts $MaxAttempts
exit $LASTEXITCODE
