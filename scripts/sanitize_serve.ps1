$projDir = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { (Get-Location).Path }
$serveFile = Join-Path $projDir "serve.ps1"
$content = [System.IO.File]::ReadAllText($serveFile, [System.Text.Encoding]::UTF8)
$clean = [System.Text.RegularExpressions.Regex]::Replace($content, '[^\x00-\x7F]', '-')
[System.IO.File]::WriteAllText($serveFile, $clean, [System.Text.Encoding]::ASCII)
Write-Host "serve.ps1 converted to clean ASCII successfully."
