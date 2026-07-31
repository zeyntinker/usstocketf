$root = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Sector ETF Leadership.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
$launcher = Join-Path $root 'launcher\run_app.py'
if (-not (Test-Path -LiteralPath $pythonw)) { throw "Python runtime not found: $pythonw" }
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "`"$launcher`""
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,44"
$shortcut.Description = '42 sector ETF performance and holdings dashboard'
$shortcut.Save()
Write-Output "Created: $shortcutPath"
