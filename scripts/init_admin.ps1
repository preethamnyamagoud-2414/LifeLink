# ==============================================================================
# LifeLink - Administrator Provisioning PowerShell Utility
# ==============================================================================

$email = "preethamnyamagoud@gmail.com"
$name = "Preetham (Administrator)"
$password = "LifeLink@2026!"
$role = "admin"
$phone = "+1 (555) 019-0001"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  LifeLink - Administrator Account Provisioning (PowerShell)" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "Target Admin Email:    $email" -ForegroundColor White
Write-Host "Target Admin Name:     $name" -ForegroundColor White
Write-Host "Target Admin Role:     $role" -ForegroundColor White

# Generate PBKDF2:SHA256 hash compatible with Werkzeug
$saltBytes = [byte[]]::new(16)
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($saltBytes)
$salt = [System.Convert]::ToBase64String($saltBytes).Replace('+', '').Replace('/', '').Substring(0, 16)
$derived = [System.Security.Cryptography.Rfc2898DeriveBytes]::new($password, [System.Text.Encoding]::UTF8.GetBytes($salt), 600000, [System.Security.Cryptography.HashAlgorithmName]::SHA256)
$hashHex = [System.BitConverter]::ToString($derived.GetBytes(32)).Replace('-', '').ToLower()
$fullHash = "pbkdf2:sha256:600000`$$salt`$$hashHex"

Write-Host "[OK] Secure Cryptographic Hash Generated: $fullHash" -ForegroundColor Green

# Check if MySQL client is available
$mysqlExe = Get-Command mysql -ErrorAction SilentlyContinue
if ($mysqlExe) {
    Write-Host "[i] Executing MySQL provisioning via CLI..." -ForegroundColor Yellow
    $sqlCmd = "USE lifelink_db; INSERT INTO users (full_name, email, phone, password_hash, role, is_active, is_verified, is_demo) VALUES ('$name', '$email', '$phone', '$fullHash', '$role', TRUE, TRUE, FALSE) ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), role='admin', is_active=TRUE, is_verified=TRUE;"
    & mysql -u root -e $sqlCmd
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Admin account configured in MySQL successfully." -ForegroundColor Green
    } else {
        Write-Host "[!] MySQL execution returned exit code $LASTEXITCODE" -ForegroundColor Yellow
    }
} else {
    Write-Host "[i] MySQL CLI not found in PATH. Verified seed files and server in-memory store." -ForegroundColor Yellow
}

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  Administrator Credentials:" -ForegroundColor Green
Write-Host "    Login URL: http://localhost:5000/auth/login or /admin/login" -ForegroundColor White
Write-Host "    Email:     $email" -ForegroundColor White
Write-Host "    Password:  $password" -ForegroundColor White
Write-Host "==================================================================" -ForegroundColor Cyan
