# ==============================================================================
# LifeLink — Emergency Blood Request Automated Verification Suite
# ==============================================================================

$baseUrl = "http://localhost:5000"
$passCount = 0
$failCount = 0

function Assert-Test([string]$name, [bool]$condition, [string]$detail = "") {
    if ($condition) {
        Write-Host " [PASS] $name" -ForegroundColor Green
        if ($detail) { Write-Host "        $detail" -ForegroundColor DarkGray }
        $global:passCount++
    } else {
        Write-Host " [FAIL] $name" -ForegroundColor Red
        if ($detail) { Write-Host "        Error: $detail" -ForegroundColor Yellow }
        $global:failCount++
    }
}

Write-Host "`n=== LIFELINK EMERGENCY REQUEST VERIFICATION ===" -ForegroundColor Cyan

# Test 1: GET /emergency-request returns 200 OK (No 404!)
try {
    $res1 = Invoke-WebRequest -Uri "$baseUrl/emergency-request" -UseBasicParsing -TimeoutSec 5
    Assert-Test "GET /emergency-request returns 200 OK" ($res1.StatusCode -eq 200) "Status: $($res1.StatusCode)"
} catch {
    Assert-Test "GET /emergency-request returns 200 OK" $false $_.Message
}

# Test 2: GET /emergency-request.html returns 200 OK
try {
    $res2 = Invoke-WebRequest -Uri "$baseUrl/emergency-request.html" -UseBasicParsing -TimeoutSec 5
    Assert-Test "GET /emergency-request.html returns 200 OK" ($res2.StatusCode -eq 200) "Status: $($res2.StatusCode)"
} catch {
    Assert-Test "GET /emergency-request.html returns 200 OK" $false $_.Message
}

# Test 3: Subpath link /patient/emergency-request.html redirects cleanly to /emergency-request
try {
    $req3 = [System.Net.HttpWebRequest]::Create("$baseUrl/patient/emergency-request.html")
    $req3.AllowAutoRedirect = $false
    $res3 = $req3.GetResponse()
    $loc3 = $res3.GetResponseHeader("Location")
    Assert-Test "GET /patient/emergency-request.html redirects to canonical route" ($loc3 -eq "/emergency-request") "Location: $loc3"
    $res3.Close()
} catch {
    Assert-Test "GET /patient/emergency-request.html redirects to canonical route" $false $_.Message
}

# Test 4: Form content verification: All 11 required fields present in template
try {
    $content = $res1.Content
    $hasPatientName   = $content.Contains('name="patient_name"')
    $hasBloodGroup     = $content.Contains('name="blood_group"')
    $hasContactPerson  = $content.Contains('name="contact_person"')
    $hasContactPhone   = $content.Contains('name="contact_phone"')
    $hasContactEmail   = $content.Contains('name="contact_email"')
    $hasUnitsNeeded    = $content.Contains('name="units_needed"')
    $hasRequiredDate   = $content.Contains('name="required_date"')
    $hasUrgencyLevel   = $content.Contains('name="urgency_level"')
    $hasHospitalName   = $content.Contains('name="hospital_name"')
    $hasHospitalCity   = $content.Contains('name="city"')
    $hasHospitalAddress= $content.Contains('name="hospital_address"')
    $hasNotes          = $content.Contains('name="additional_notes"')

    $allFieldsPresent = $hasPatientName -and $hasBloodGroup -and $hasContactPerson -and $hasContactPhone -and `
                        $hasContactEmail -and $hasUnitsNeeded -and $hasRequiredDate -and $hasUrgencyLevel -and `
                        $hasHospitalName -and $hasHospitalCity -and $hasHospitalAddress -and $hasNotes

    Assert-Test "Form includes all 11 required emergency request fields" $allFieldsPresent "11 Form fields verified in DOM"
} catch {
    Assert-Test "Form includes all 11 required emergency request fields" $false $_.Message
}

# Test 5: Unauthenticated submission is protected
try {
    $unauthPayload = @{
        patient_name = "Anonymous Test"
        blood_group = "O+"
        contact_phone = "+1 555 0000"
        hospital_name = "General Hospital"
        city = "Metro"
    } | ConvertTo-Json

    $unauthRes = Invoke-RestMethod -Uri "$baseUrl/api/requests/create" -Method Post -Body $unauthPayload -ContentType "application/json" -ErrorAction Stop
    Assert-Test "Unauthenticated request should be rejected" $false "Server accepted unauthenticated request!"
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Assert-Test "Unauthenticated request is properly blocked" ($statusCode -eq 401 -or $statusCode -eq 302) "HTTP Status: $statusCode"
}

# Test 6: Sign in as registered user/admin and submit emergency request
$sessionCookie = ""
try {
    $loginBody = @{
        email = "preethamnyamagoud@gmail.com"
        password = "LifeLink@2026!"
    } | ConvertTo-Json

    $loginReq = [System.Net.HttpWebRequest]::Create("$baseUrl/api/auth/login")
    $loginReq.Method = "POST"
    $loginReq.ContentType = "application/json"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($loginBody)
    $loginReq.ContentLength = $bytes.Length
    $stream = $loginReq.GetRequestStream()
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Close()

    $loginResp = $loginReq.GetResponse()
    $cookieHeader = $loginResp.Headers["Set-Cookie"]
    if ($cookieHeader -match "lifelink_session=([^;]+)") {
        $sessionCookie = $matches[1]
    }
    $loginResp.Close()

    Assert-Test "Authentication succeeded and session token issued" ([string]::IsNullOrWhiteSpace($sessionCookie) -eq $false) "Session: lifelink_session=$sessionCookie"
} catch {
    Assert-Test "Authentication succeeded and session token issued" $false $_.Message
}

# Test 7: Submit new Emergency Request with all 11 fields as authenticated user
$createdReqId = 0
try {
    $newRequestPayload = @{
        patient_name = "Aarav Sharma"
        blood_group = "B+"
        contact_person = "Priya Sharma (Relative)"
        contact_phone = "+91 98765 43210"
        contact_email = "priya.sharma@apollohealth.org"
        preferred_contact_method = "phone"
        units_needed = 3
        required_date = "2026-11-15"
        urgency_level = "CRITICAL"
        hospital_name = "Apollo Multispecialty Hospital"
        hospital_area = "Bannerghatta Main Rd"
        city = "Bengaluru"
        hospital_address = "Ward 4, Critical Care Bed 9, Opp. IIM"
        doctor_name = "Dr. K. Aris (Trauma)"
        additional_notes = "Emergency platelet requirement for Dengue severe thrombocytopenia"
    } | ConvertTo-Json

    $createReq = [System.Net.HttpWebRequest]::Create("$baseUrl/api/requests/create")
    $createReq.Method = "POST"
    $createReq.ContentType = "application/json"
    $createReq.Headers["Cookie"] = "lifelink_session=$sessionCookie"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($newRequestPayload)
    $createReq.ContentLength = $bytes.Length
    $stream = $createReq.GetRequestStream()
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Close()

    $createResp = $createReq.GetResponse()
    $reader = New-Object System.IO.StreamReader($createResp.GetResponseStream())
    $createJson = $reader.ReadToEnd() | ConvertFrom-Json
    $createdReqId = $createJson.request_id
    $createResp.Close()

    Assert-Test "Emergency Blood Request created and assigned unique ID" ($createJson.success -eq $true -and $createdReqId -gt 0) "Assigned Request ID: #REQ-$($createdReqId.ToString('D4'))"
} catch {
    Assert-Test "Emergency Blood Request created and assigned unique ID" $false $_.Message
}

# Test 8: Verify request appears in /api/requests list
try {
    $listRes = Invoke-RestMethod -Uri "$baseUrl/api/requests" -Method Get
    $found = $listRes.requests | Where-Object { $_.id -eq $createdReqId }
    Assert-Test "New request appears in active requests directory" ($found -ne $null -and $found.patient_name -eq "Aarav Sharma") "Patient: $($found.patient_name), Group: $($found.blood_group), Urgency: $($found.urgency_level)"
} catch {
    Assert-Test "New request appears in active requests directory" $false $_.Message
}

# Test 9: Verify tracking page /track-request?id=<id> renders 200 OK
try {
    $trackRes = Invoke-WebRequest -Uri "$baseUrl/track-request?id=$createdReqId" -UseBasicParsing -TimeoutSec 5
    Assert-Test "Dedicated tracking page /track-request?id=$createdReqId loads successfully" ($trackRes.StatusCode -eq 200) "Status: $($trackRes.StatusCode)"
} catch {
    Assert-Test "Dedicated tracking page /track-request?id=$createdReqId loads successfully" $false $_.Message
}

# Test 10: Verify patient privacy protection (masking contact info for unauthenticated visitors)
try {
    $trackHtml = $trackRes.Content
    $hasPrivacyElements = $trackHtml.Contains('trackContactMasked') -and $trackHtml.Contains('Sign In to View Contact')
    Assert-Test "Patient contact details are privacy-protected for anonymous public viewers" $hasPrivacyElements "Privacy mask DOM container confirmed"
} catch {
    Assert-Test "Patient contact details are privacy-protected for anonymous public viewers" $false $_.Message
}

Write-Host "`n===============================================" -ForegroundColor Cyan
Write-Host " RESULTS: $passCount Passed, $failCount Failed" -ForegroundColor $(if ($failCount -eq 0) { "Green" } else { "Red" })
Write-Host "===============================================`n" -ForegroundColor Cyan

if ($failCount -gt 0) { exit 1 } else { exit 0 }
