$projDir = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { (Get-Location).Path }
$raw = [System.IO.File]::ReadAllText((Join-Path $projDir "serve.ps1"))
$errors = $null
$tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($raw, [ref]$tokens, [ref]$errors)
if ($errors.Count -eq 0) {
    Write-Host "SUCCESS: serve.ps1 has NO syntax errors!" -ForegroundColor Green
} else {
    Write-Host "ERRORS found in serve.ps1:" -ForegroundColor Red
    foreach ($e in $errors) {
        Write-Host "Line $($e.Extent.StartLineNumber): $($e.Message)" -ForegroundColor Yellow
    }
}
