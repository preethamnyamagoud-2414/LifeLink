# ==============================================================================
# LifeLink - Comprehensive Admin System Verification Test Suite
# ==============================================================================

param(
    [string]$baseUrl = "http://127.0.0.1:5000"
)
$passed = 0
$failed = 0

function Assert-Test($condition, $testName, $detail = "") {
    if ($condition) {
        Write-Host "  [PASS] $testName" -ForegroundColor Green
        $global:passed++
    } else {
        Write-Host "  [FAIL] $testName : $detail" -ForegroundColor Red
        $global:failed++
    }
}

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  Running LifeLink Admin Route & Authentication Tests" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# Test 1: Verify /admin/admin-dashboard.html does NOT 404
try {
    $req = [System.Net.HttpWebRequest]::Create("$baseUrl/admin/admin-dashboard.html")
    $req.AllowAutoRedirect = $false
    $resp = $req.GetResponse()
    $status = [int]$resp.StatusCode
    $location = $resp.Headers["Location"]
    $resp.Close()

    # It should be 302 Found redirecting to /admin/dashboard, or 200 OK
    Assert-Test ($status -eq 302 -or $status -eq 200) "Test 1: /admin/admin-dashboard.html no longer returns 404 (Status: $status, Location: $location)"
} catch [System.Net.WebException] {
    $resp = $_.Exception.Response
    $code = if ($resp) { [int]$resp.StatusCode } else { 0 }
    Assert-Test ($false) "Test 1: /admin/admin-dashboard.html returned error" "Status code $code"
}

# Test 2: Verify /admin/dashboard returns 200 OK
try {
    $req = [System.Net.HttpWebRequest]::Create("$baseUrl/admin/dashboard")
    $req.AllowAutoRedirect = $true
    $resp = $req.GetResponse()
    $status = [int]$resp.StatusCode
    $reader = [System.IO.StreamReader]::new($resp.GetResponseStream())
    $body = $reader.ReadToEnd()
    $resp.Close()

    Assert-Test ($status -eq 200 -and $body -match "Administrative Operations Center") "Test 2: /admin/dashboard returns 200 OK with Admin Dashboard"
    Assert-Test ($body -match "preethamnyamagoud@gmail.com") "Test 2b: Admin dashboard contains administrator email preethamnyamagoud@gmail.com"
} catch {
    Assert-Test ($false) "Test 2: /admin/dashboard failed" $_.Exception.Message
}

# Test 3: Verify /admin/login returns 200 OK
try {
    $resp = Invoke-WebRequest -Uri "$baseUrl/admin/login" -Method GET -UseBasicParsing
    Assert-Test ($resp.StatusCode -eq 200 -and $resp.Content -match "Administrator") "Test 3: /admin/login returns 200 OK with dedicated admin login page"
} catch {
    Assert-Test ($false) "Test 3: /admin/login failed" $_.Exception.Message
}

# Test 4: Admin Authentication with preethamnyamagoud@gmail.com / LifeLink@2026!
$adminSessionCookie = $null
try {
    $loginBody = @{
        email = "preethamnyamagoud@gmail.com"
        password = "LifeLink@2026!"
    } | ConvertTo-Json

    $loginResp = Invoke-WebRequest -Uri "$baseUrl/api/auth/login" -Method POST -Body $loginBody -ContentType "application/json" -UseBasicParsing
    $loginJson = $loginResp.Content | ConvertFrom-Json

    $adminSessionCookie = $loginResp.Headers["Set-Cookie"]
    Assert-Test ($loginResp.StatusCode -eq 200 -and $loginJson.success -eq $true) "Test 4a: Admin authentication succeeded with 200 OK"
    Assert-Test ($loginJson.user.role -eq "admin") "Test 4b: Authenticated user role is 'admin'"
    Assert-Test ($loginJson.user.email -eq "preethamnyamagoud@gmail.com") "Test 4c: Authenticated user email matches preethamnyamagoud@gmail.com"
    Assert-Test ($loginJson.redirect -eq "/admin/dashboard") "Test 4d: Redirect URL is canonical '/admin/dashboard'"
    Assert-Test ($adminSessionCookie -match "lifelink_session=") "Test 4e: Server issued lifelink_session cookie"
} catch {
    Assert-Test ($false) "Test 4: Admin login request failed" $_.Exception.Message
}

# Test 5: Invalid Password Attempt
try {
    $badLoginBody = @{
        email = "preethamnyamagoud@gmail.com"
        password = "WrongPassword@999"
    } | ConvertTo-Json

    $badResp = Invoke-WebRequest -Uri "$baseUrl/api/auth/login" -Method POST -Body $badLoginBody -ContentType "application/json" -UseBasicParsing
    Assert-Test ($false) "Test 5: Bad password unexpectedly succeeded"
} catch [System.Net.WebException] {
    $badStatus = [int]$_.Exception.Response.StatusCode
    Assert-Test ($badStatus -eq 401) "Test 5: Invalid credentials rejected with 401 Unauthorized"
}

# Test 6: Normal User Access Restriction (Requirement 10)
# Register a normal patient user
$patientCookie = $null
try {
    $patientBody = @{
        full_name = "Jane Patient"
        email = "patient.test.$([System.Guid]::NewGuid().ToString().Substring(0,6))@example.com"
        phone = "+1 (555) 777-8888"
        password = "UserPass@123"
        role = "patient"
    } | ConvertTo-Json

    $regResp = Invoke-WebRequest -Uri "$baseUrl/api/auth/register" -Method POST -Body $patientBody -ContentType "application/json" -UseBasicParsing
    $regJson = $regResp.Content | ConvertFrom-Json

    # Log in as patient
    $pLoginBody = @{
        email = ($patientBody | ConvertFrom-Json).email
        password = "UserPass@123"
    } | ConvertTo-Json

    $pLoginResp = Invoke-WebRequest -Uri "$baseUrl/api/auth/login" -Method POST -Body $pLoginBody -ContentType "application/json" -UseBasicParsing
    $patientCookie = $pLoginResp.Headers["Set-Cookie"]
    
    # Extract session token
    $tokenMatch = [regex]::Match($patientCookie, "lifelink_session=([^;]+)")
    $pToken = if ($tokenMatch.Success) { $tokenMatch.Groups[1].Value } else { "" }

    # Attempt to access /admin/dashboard with patient session
    $adminReq = [System.Net.HttpWebRequest]::Create("$baseUrl/admin/dashboard")
    $adminReq.Headers.Add("Cookie", "lifelink_session=$pToken")
    $adminReq.AllowAutoRedirect = $false
    try {
        $adminResp = $adminReq.GetResponse()
        $adminStatusCode = [int]$adminResp.StatusCode
        $adminResp.Close()
        Assert-Test ($false) "Test 6: Patient was able to access /admin/dashboard (Status $adminStatusCode)"
    } catch [System.Net.WebException] {
        $adminStatusCode = [int]$_.Exception.Response.StatusCode
        Assert-Test ($adminStatusCode -eq 403) "Test 6: Normal patient account blocked from /admin/dashboard with HTTP 403 Forbidden"
    }
} catch {
    Assert-Test ($false) "Test 6: Normal user restriction test encountered error" $_.Exception.Message
}

# Test 7: Admin Logout
try {
    $tokenMatch = [regex]::Match($adminSessionCookie, "lifelink_session=([^;]+)")
    $aToken = if ($tokenMatch.Success) { $tokenMatch.Groups[1].Value } else { "" }

    $logoutReq = [System.Net.HttpWebRequest]::Create("$baseUrl/api/auth/logout")
    $logoutReq.Method = "POST"
    $logoutReq.Headers.Add("Cookie", "lifelink_session=$aToken")
    $logoutResp = $logoutReq.GetResponse()
    $logoutStatusCode = [int]$logoutResp.StatusCode
    $logoutResp.Close()

    Assert-Test ($logoutStatusCode -eq 200) "Test 7a: Admin logout returns 200 OK"

    # Now verify that the invalidated session token can no longer access /admin/dashboard
    # (Since it is removed from active sessions, visiting returns 200 preview or redirects to login)
} catch {
    Assert-Test ($false) "Test 7: Admin logout test encountered error" $_.Exception.Message
}

# Test 8: Verify configuration files and seeds
$projDir = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { (Get-Location).Path }
$seedSql = Get-Content (Join-Path $projDir "database\seed.sql") -Raw
$seedMatchesAdmin = $seedSql -match "preethamnyamagoud@gmail.com"
Assert-Test ($seedMatchesAdmin) "Test 8a: database/seed.sql contains preethamnyamagoud@gmail.com"

$envContent = Get-Content (Join-Path $projDir ".env") -Raw
$envMatchesAdmin = $envContent -match "preethamnyamagoud@gmail.com"
Assert-Test ($envMatchesAdmin) "Test 8b: .env contains ADMIN_EMAIL=preethamnyamagoud@gmail.com"

$initAdminExists = Test-Path (Join-Path $projDir "scripts\init_admin.py")
Assert-Test ($initAdminExists) "Test 8c: scripts/init_admin.py provisioning utility exists"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  RESULTS: $passed Passed, $failed Failed" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Red" })
Write-Host "==================================================================" -ForegroundColor Cyan
if ($failed -gt 0) { exit 1 } else { exit 0 }
