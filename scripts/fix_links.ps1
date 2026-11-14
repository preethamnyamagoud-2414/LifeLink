$projDir = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { (Get-Location).Path }
$files = Get-ChildItem -Path (Join-Path $projDir "preview") -Filter *.html
foreach ($file in $files) {
    $text = [System.IO.File]::ReadAllText($file.FullName)
    $newText = $text.Replace('href="emergency-request.html"', 'href="/emergency-request"')
    if ($newText -ne $text) {
        [System.IO.File]::WriteAllText($file.FullName, $newText, [System.Text.Encoding]::UTF8)
        Write-Host "Updated $($file.Name)"
    }
}
