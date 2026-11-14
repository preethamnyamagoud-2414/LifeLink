# ==============================================================================
# LifeLink - Zero-Dependency Local Web Server + JSON API
# Uses raw .NET sockets (TcpListener). Works on any Windows PC with PowerShell 5.1+.
# Data is persisted to data\lifelink-data.json so it survives restarts.
# ==============================================================================

param(
    [int]$Port = 5000
)

$ErrorActionPreference = "Stop"

# PowerShell 5.1 adds an ETS "Count" property to arrays that corrupts ConvertTo-Json output.
Remove-TypeData -TypeName System.Array -ErrorAction SilentlyContinue

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $rootDir) { $rootDir = (Get-Location).Path }
$previewDir = Join-Path $rootDir "preview"
$staticDir  = Join-Path $rootDir "app\static"
$dataDir    = Join-Path $rootDir "data"
$dataFile   = Join-Path $dataDir "lifelink-data.json"
$Utf8NoBom  = New-Object System.Text.UTF8Encoding($false)
$Invariant  = [System.Globalization.CultureInfo]::InvariantCulture

$BloodGroups = @('O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+')
# Recipient blood group -> donor groups whose red cells are compatible
$CanReceiveFrom = @{
    'O-'  = @('O-')
    'O+'  = @('O-', 'O+')
    'A-'  = @('O-', 'A-')
    'A+'  = @('O-', 'O+', 'A-', 'A+')
    'B-'  = @('O-', 'B-')
    'B+'  = @('O-', 'O+', 'B-', 'B+')
    'AB-' = @('O-', 'A-', 'B-', 'AB-')
    'AB+' = @('O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+')
}

# Health screening questions. "days" = deferral counted from the screening date (0 = until re-screened).
$ScreeningRules = @(
    @{ key = 'unwell';         kind = 'temporary'; days = 7;   msg = 'Fever, cold, flu or feeling unwell recently - wait 7 days after full recovery.' },
    @{ key = 'antibiotics';    kind = 'temporary'; days = 7;   msg = 'Taking antibiotics - wait 7 days after the last dose.' },
    @{ key = 'tattoo';         kind = 'temporary'; days = 365; msg = 'Tattoo, piercing or acupuncture in the last 12 months.' },
    @{ key = 'surgery';        kind = 'temporary'; days = 180; msg = 'Major surgery in the last 6 months.' },
    @{ key = 'malaria';        kind = 'temporary'; days = 90;  msg = 'Malaria in the last 3 months.' },
    @{ key = 'pregnant';       kind = 'temporary'; days = 0;   msg = 'Pregnant, or gave birth / breastfeeding in the last 12 months.' },
    @{ key = 'blood_pressure'; kind = 'temporary'; days = 0;   msg = 'Uncontrolled high or low blood pressure.' },
    @{ key = 'infection';      kind = 'permanent'; days = 0;   msg = 'History of HIV, Hepatitis B, Hepatitis C or syphilis.' },
    @{ key = 'chronic';        kind = 'permanent'; days = 0;   msg = 'Heart disease, cancer, kidney or liver disease, epilepsy or a bleeding disorder.' },
    @{ key = 'insulin';        kind = 'permanent'; days = 0;   msg = 'Diabetes treated with insulin.' }
)

$Collections = @('users', 'requests', 'responses', 'notifications', 'audit', 'sessions', 'resets')

# ------------------------------------------------------------------------------
# Generic helpers
# ------------------------------------------------------------------------------
function Set-P($o, [string]$n, $v) { Add-Member -InputObject $o -NotePropertyName $n -NotePropertyValue $v -Force }
function Get-P($o, [string]$n) {
    if ($null -eq $o) { return $null }
    $p = $o.PSObject.Properties[$n]
    if ($null -ne $p) { return , $p.Value }
    return $null
}
function To-List($x) {
    $l = New-Object System.Collections.ArrayList
    if ($null -ne $x) { foreach ($i in $x) { if ($null -ne $i) { [void]$l.Add($i) } } }
    return , $l
}
function S($v) { if ($null -eq $v) { return '' }; return ([string]$v).Trim() }
function To-Num($v) {
    if ($null -eq $v) { return $null }
    $s = "$v".Trim()
    if ($s -eq '') { return $null }
    $x = 0.0
    if ([double]::TryParse($s, [System.Globalization.NumberStyles]::Float, $Invariant, [ref]$x)) { return $x }
    return $null
}
function Now-Str { (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }
function Today-Str { (Get-Date).ToString('yyyy-MM-dd') }
function Parse-Date([string]$s) {
    if (-not $s -or $s.Length -lt 10) { return $null }
    $dt = [datetime]::MinValue
    if ([datetime]::TryParseExact($s.Substring(0, 10), 'yyyy-MM-dd', $Invariant, [System.Globalization.DateTimeStyles]::None, [ref]$dt)) { return $dt }
    return $null
}
function Req-Code($id) { 'REQ-' + ([int]$id).ToString('D4') }
function Mask-Name([string]$n) {
    $parts = @(($n.Trim()) -split '\s+' | Where-Object { $_ })
    if ($parts.Count -eq 0) { return 'Donor' }
    if ($parts.Count -eq 1) { return $parts[0] }
    return "$($parts[0]) $($parts[-1].Substring(0,1))."
}
function Mask-Phone([string]$p) {
    $digits = ($p -replace '[^0-9]', '')
    if ($digits.Length -lt 4) { return 'xxxxxx' }
    return 'xxxxx xx' + $digits.Substring($digits.Length - 4)
}
function Get-Km($lat1, $lng1, $lat2, $lng2) {
    if ($null -eq $lat1 -or $null -eq $lng1 -or $null -eq $lat2 -or $null -eq $lng2) { return $null }
    $r = [Math]::PI / 180
    $la1 = [double]$lat1; $la2 = [double]$lat2; $lo1 = [double]$lng1; $lo2 = [double]$lng2
    $dLat = ($la2 - $la1) * $r
    $dLng = ($lo2 - $lo1) * $r
    $a = [Math]::Sin($dLat / 2) * [Math]::Sin($dLat / 2) + [Math]::Cos($la1 * $r) * [Math]::Cos($la2 * $r) * [Math]::Sin($dLng / 2) * [Math]::Sin($dLng / 2)
    return [Math]::Round(6371 * 2 * [Math]::Atan2([Math]::Sqrt($a), [Math]::Sqrt(1 - $a)), 1)
}
function Valid-Coords($lat, $lng) {
    return ($null -ne $lat -and $null -ne $lng -and $lat -ge -90 -and $lat -le 90 -and $lng -ge -180 -and $lng -le 180)
}

# ------------------------------------------------------------------------------
# Password hashing (PBKDF2) & tokens
# ------------------------------------------------------------------------------
function New-Salt {
    $b = New-Object byte[] 16
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    return [Convert]::ToBase64String($b)
}
function Hash-Password([string]$pw, [string]$salt) {
    $kdf = [System.Security.Cryptography.Rfc2898DeriveBytes]::new($pw, [Convert]::FromBase64String($salt), 20000)
    return [Convert]::ToBase64String($kdf.GetBytes(32))
}
function New-Token { [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N') }

# ------------------------------------------------------------------------------
# Persistent data store
# ------------------------------------------------------------------------------
function New-Db {
    $db = [pscustomobject]@{
        version = 1
        seq     = [pscustomobject]@{ user = 0; request = 0; response = 0; notification = 0; audit = 0; donation = 0 }
    }
    foreach ($c in $Collections) { Set-P $db $c (New-Object System.Collections.ArrayList) }
    return $db
}

function Next-Id([string]$name) {
    $v = [int](Get-P $global:DB.seq $name) + 1
    Set-P $global:DB.seq $name $v
    return $v
}

function Save-Db {
    if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir | Out-Null }
    $json = ConvertTo-Json -InputObject $global:DB -Depth 12
    $tmp = "$dataFile.tmp"
    [System.IO.File]::WriteAllText($tmp, $json, $Utf8NoBom)
    [System.IO.File]::Copy($tmp, $dataFile, $true)
    [System.IO.File]::Delete($tmp)
}

function Add-SeedAdmin([string]$name, [string]$email, [string]$phone, [string]$password) {
    $salt = New-Salt
    $u = [pscustomobject]@{
        id            = (Next-Id 'user')
        full_name     = $name
        email         = $email
        phone         = $phone
        password_salt = $salt
        password_hash = (Hash-Password $password $salt)
        role          = 'admin'
        city          = ''
        district      = ''
        is_active     = $true
        created_at    = (Now-Str)
        donor         = $null
    }
    [void]$global:DB.users.Add($u)
}

function Load-Db {
    if (Test-Path $dataFile) {
        try {
            $raw = [System.IO.File]::ReadAllText($dataFile, $Utf8NoBom)
            $db = ConvertFrom-Json $raw
            foreach ($c in $Collections) { Set-P $db $c (To-List (Get-P $db $c)) }
            if (-not (Get-P $db 'seq')) { Set-P $db 'seq' ([pscustomobject]@{}) }
            foreach ($k in @('user', 'request', 'response', 'notification', 'audit', 'donation')) {
                if ($null -eq (Get-P $db.seq $k)) { Set-P $db.seq $k 0 }
            }
            foreach ($u in $db.users) {
                $d = Get-P $u 'donor'
                if ($d) { Set-P $d 'donations' (To-List (Get-P $d 'donations')) }
            }
            $global:DB = $db
            return
        } catch {
            $bad = "$dataFile.corrupt-" + (Get-Date).ToString('yyyyMMddHHmmss')
            Copy-Item $dataFile $bad -ErrorAction SilentlyContinue
            Write-Host "[!] Could not read data file ($($_.Exception.Message)). Backed it up to $bad and started fresh." -ForegroundColor Yellow
        }
    }
    $global:DB = New-Db
    # Administrator accounts cannot be registered publicly; they are seeded here.
    Add-SeedAdmin 'Preetham (Administrator)' 'preethamnyamagoud@gmail.com' '+1 (555) 019-0001' 'LifeLink@2026!'
    Add-SeedAdmin 'System Administrator' 'admin@lifelink.local' '+1 (555) 000-0001' 'Admin@2026!'
    Save-Db
}

function Find-User($id) { foreach ($u in $global:DB.users) { if ($u.id -eq $id) { return $u } }; return $null }
function Find-UserByEmail([string]$email) { foreach ($u in $global:DB.users) { if ($u.email -eq $email) { return $u } }; return $null }
function Find-Request($id) { foreach ($r in $global:DB.requests) { if ($r.id -eq $id) { return $r } }; return $null }
function Find-Response($id) { foreach ($r in $global:DB.responses) { if ($r.id -eq $id) { return $r } }; return $null }

function Add-Notification($userId, [string]$type, [string]$title, [string]$body, [string]$link) {
    [void]$global:DB.notifications.Add([pscustomobject]@{
        id         = (Next-Id 'notification')
        user_id    = $userId
        type       = $type
        title      = $title
        body       = $body
        link       = $link
        is_read    = $false
        created_at = (Now-Str)
    })
}

function Add-Audit([string]$action, [string]$target, [string]$desc) {
    [void]$global:DB.audit.Add([pscustomobject]@{
        id          = (Next-Id 'audit')
        action      = $action
        target      = $target
        description = $desc
        ip          = '127.0.0.1'
        created_at  = (Now-Str)
    })
}

# ------------------------------------------------------------------------------
# Donor eligibility (preliminary self-screening; the blood bank does the final check)
# ------------------------------------------------------------------------------
function Add-Defer($st, [string]$kind, [string]$msg, $until) {
    $untilStr = $null
    if ($until) { $untilStr = $until.ToString('yyyy-MM-dd') }
    [void]$st.reasons.Add([pscustomobject]@{ type = $kind; message = $msg; until = $untilStr })
    if ($kind -eq 'permanent') { $st.perm = $true; return }
    $st.temp = $true
    if ($until) {
        if (-not $st.until -or $until -gt $st.until) { $st.until = $until }
    } else {
        $st.undated = $true
    }
}

function Get-Eligibility($d) {
    $today = (Get-Date).Date
    $st = @{ perm = $false; temp = $false; undated = $false; until = $null; reasons = (New-Object System.Collections.ArrayList) }
    $gender = S (Get-P $d 'gender')

    $dob = Parse-Date (S (Get-P $d 'dob'))
    if (-not $dob) {
        Add-Defer $st 'temporary' 'Date of birth is missing.' $null
    } else {
        $age = $today.Year - $dob.Year
        if ($dob.Date -gt $today.AddYears(-$age)) { $age-- }
        if ($age -lt 18) { Add-Defer $st 'temporary' "Donors must be at least 18 years old (you are $age)." $dob.AddYears(18) }
        elseif ($age -gt 65) { Add-Defer $st 'permanent' "Donors must be 65 years old or younger (you are $age)." $null }
    }

    $w = To-Num (Get-P $d 'weight_kg')
    if ($null -eq $w) { Add-Defer $st 'temporary' 'Body weight is missing.' $null }
    elseif ($w -lt 45) { Add-Defer $st 'temporary' "Minimum body weight is 45 kg (you entered $w kg)." $null }

    $hb = To-Num (Get-P $d 'hemoglobin')
    if ($null -ne $hb -and $hb -lt 12.5) { Add-Defer $st 'temporary' "Hemoglobin must be at least 12.5 g/dL (you entered $hb)." $null }

    $last = Parse-Date (S (Get-P $d 'last_donation_date'))
    if ($last) {
        $gap = 90
        if ($gender -eq 'female') { $gap = 120 }
        $next = $last.AddDays($gap)
        if ($next -gt $today) { Add-Defer $st 'temporary' "At least $gap days are needed between whole-blood donations (last donation $($last.ToString('yyyy-MM-dd')))." $next }
    }

    $screening = Get-P $d 'screening'
    $answers = Get-P $screening 'answers'
    $screenedAt = Parse-Date (S (Get-P $screening 'screened_at'))
    if (-not $screenedAt) { $screenedAt = $today }
    if (-not $answers) {
        Add-Defer $st 'temporary' 'Health screening questionnaire has not been completed.' $null
    } else {
        foreach ($q in $ScreeningRules) {
            if ((Get-P $answers $q.key) -ne $true) { continue }
            if ($q.key -eq 'pregnant' -and $gender -ne 'female') { continue }
            if ($q.kind -eq 'permanent') { Add-Defer $st 'permanent' $q.msg $null; continue }
            if ($q.days -gt 0) {
                $until = $screenedAt.AddDays($q.days)
                if ($until -gt $today) { Add-Defer $st 'temporary' $q.msg $until }
            } else {
                Add-Defer $st 'temporary' $q.msg $null
            }
        }
    }

    $status = 'ELIGIBLE'
    if ($st.perm) { $status = 'PERMANENT_DEFERRAL' } elseif ($st.temp) { $status = 'TEMPORARY_DEFERRAL' }
    $from = $null
    if ($status -eq 'TEMPORARY_DEFERRAL' -and -not $st.undated -and $st.until) { $from = $st.until.ToString('yyyy-MM-dd') }
    return [pscustomobject]@{
        status        = $status
        eligible      = ($status -eq 'ELIGIBLE')
        eligible_from = $from
        reasons       = $st.reasons
    }
}

# ------------------------------------------------------------------------------
# View models (never expose password hashes or other users' exact coordinates)
# ------------------------------------------------------------------------------
function Get-SafeUser($u) {
    $d = Get-P $u 'donor'
    $bg = $null
    if ($d) { $bg = $d.blood_group }
    return [pscustomobject]@{
        id          = $u.id
        full_name   = $u.full_name
        email       = $u.email
        phone       = $u.phone
        role        = $u.role
        city        = (S (Get-P $u 'city'))
        district    = (S (Get-P $u 'district'))
        is_active   = [bool]$u.is_active
        created_at  = $u.created_at
        is_donor    = [bool]$d
        blood_group = $bg
    }
}

function Get-DonorView($u) {
    $d = Get-P $u 'donor'
    if (-not $d) { return $null }
    $donations = @($d.donations | Sort-Object { $_.date } -Descending)
    $hasLoc = Valid-Coords (To-Num (Get-P $d 'lat')) (To-Num (Get-P $d 'lng'))
    return [pscustomobject]@{
        blood_group         = $d.blood_group
        gender              = (Get-P $d 'gender')
        dob                 = (Get-P $d 'dob')
        weight_kg           = (Get-P $d 'weight_kg')
        hemoglobin          = (Get-P $d 'hemoglobin')
        city                = (Get-P $d 'city')
        district            = (Get-P $d 'district')
        lat                 = (Get-P $d 'lat')
        lng                 = (Get-P $d 'lng')
        has_location        = $hasLoc
        location_updated_at = (Get-P $d 'location_updated_at')
        is_available        = [bool](Get-P $d 'is_available')
        last_donation_date  = (Get-P $d 'last_donation_date')
        screening           = (Get-P $d 'screening')
        donations           = (To-List $donations)
        donations_count     = $donations.Count
        eligibility         = (Get-Eligibility $d)
    }
}

function Get-RequestView($r, $viewer) {
    $isOwner = ($null -ne $viewer -and $r.requester_user_id -eq $viewer.id)
    $isAdmin = ($null -ne $viewer -and $viewer.role -eq 'admin')
    $active = 0; $donated = 0; $mine = $null
    foreach ($resp in $global:DB.responses) {
        if ($resp.request_id -ne $r.id) { continue }
        if ($resp.status -ne 'WITHDRAWN') { $active++ }
        if ($resp.status -eq 'DONATED') { $donated++ }
        if ($null -ne $viewer -and $resp.donor_user_id -eq $viewer.id) { $mine = $resp }
    }
    $phone = $r.contact_phone; $email = $r.contact_email
    if ($null -eq $viewer) { $phone = Mask-Phone $r.contact_phone; $email = '' }

    $distance = $null; $compatible = $null
    $vd = $null
    if ($viewer) { $vd = Get-P $viewer 'donor' }
    if ($vd) {
        $distance = Get-Km (To-Num (Get-P $vd 'lat')) (To-Num (Get-P $vd 'lng')) (To-Num (Get-P $r 'lat')) (To-Num (Get-P $r 'lng'))
        $compatible = ($CanReceiveFrom[$r.blood_group] -contains $vd.blood_group)
    }
    $myResp = $null
    if ($mine) { $myResp = [pscustomobject]@{ id = $mine.id; status = $mine.status; message = $mine.message; created_at = $mine.created_at } }

    return [pscustomobject]@{
        id                       = $r.id
        code                     = (Req-Code $r.id)
        patient_name             = $r.patient_name
        blood_group              = $r.blood_group
        units_needed             = $r.units_needed
        urgency_level            = $r.urgency_level
        hospital_name            = $r.hospital_name
        hospital_area            = $r.hospital_area
        city                     = $r.city
        state                    = (Get-P $r 'state')
        hospital_address         = $r.hospital_address
        required_date            = $r.required_date
        doctor_name              = $r.doctor_name
        additional_notes         = $r.additional_notes
        preferred_contact_method = $r.preferred_contact_method
        contact_person           = $r.contact_person
        contact_phone            = $phone
        contact_email            = $email
        contact_visible          = ($null -ne $viewer)
        status                   = $r.status
        created_at               = $r.created_at
        closed_at                = (Get-P $r 'closed_at')
        has_location             = (Valid-Coords (To-Num (Get-P $r 'lat')) (To-Num (Get-P $r 'lng')))
        responses_count          = $active
        donated_count            = $donated
        is_owner                 = $isOwner
        can_manage               = ($isOwner -or $isAdmin)
        distance_km              = $distance
        compatible               = $compatible
        my_response              = $myResp
    }
}

function Get-ResponseViews($r, $viewer) {
    $canSeeContact = ($null -ne $viewer -and ($r.requester_user_id -eq $viewer.id -or $viewer.role -eq 'admin'))
    $list = New-Object System.Collections.ArrayList
    foreach ($resp in $global:DB.responses) {
        if ($resp.request_id -ne $r.id) { continue }
        $du = Find-User $resp.donor_user_id
        if (-not $du) { continue }
        $dd = Get-P $du 'donor'
        $name = Mask-Name $du.full_name
        $phone = $null
        if ($canSeeContact) {
            $name = $du.full_name
            if ($resp.status -ne 'WITHDRAWN') { $phone = $du.phone }
        }
        $bg = $null; $city = ''; $district = ''; $dist = $null
        if ($dd) {
            $bg = $dd.blood_group; $city = S (Get-P $dd 'city'); $district = S (Get-P $dd 'district')
            $dist = Get-Km (To-Num (Get-P $dd 'lat')) (To-Num (Get-P $dd 'lng')) (To-Num (Get-P $r 'lat')) (To-Num (Get-P $r 'lng'))
        }
        [void]$list.Add([pscustomobject]@{
            id            = $resp.id
            request_id    = $r.id
            request_code  = (Req-Code $r.id)
            patient_name  = $r.patient_name
            donor_user_id = $resp.donor_user_id
            donor_name    = $name
            donor_phone   = $phone
            blood_group   = $bg
            city          = $city
            district      = $district
            distance_km   = $dist
            status        = $resp.status
            message       = $resp.message
            created_at    = $resp.created_at
            is_me         = ($null -ne $viewer -and $viewer.id -eq $resp.donor_user_id)
        })
    }
    return , $list
}

# ------------------------------------------------------------------------------
# Donor profile validation
# ------------------------------------------------------------------------------
function Build-DonorProfile($src, $existing) {
    # Returns @{ ok = $true; donor = <obj> } or @{ ok = $false; message = '...' }
    $bg = S (Get-P $src 'blood_group')
    if ($BloodGroups -notcontains $bg) { return @{ ok = $false; message = 'Please choose a valid blood group.' } }
    $gender = S (Get-P $src 'gender')
    if (@('male', 'female', 'other') -notcontains $gender) { return @{ ok = $false; message = 'Please choose your gender.' } }
    $dob = S (Get-P $src 'dob')
    if (-not (Parse-Date $dob)) { return @{ ok = $false; message = 'Please enter your date of birth.' } }
    $w = To-Num (Get-P $src 'weight_kg')
    if ($null -eq $w -or $w -lt 20 -or $w -gt 300) { return @{ ok = $false; message = 'Please enter your body weight in kg.' } }
    $hb = To-Num (Get-P $src 'hemoglobin')
    if ($null -ne $hb -and ($hb -lt 3 -or $hb -gt 25)) { return @{ ok = $false; message = 'Hemoglobin should be in g/dL (for example 13.5).' } }
    $last = S (Get-P $src 'last_donation_date')
    if ($last) {
        $ld = Parse-Date $last
        if (-not $ld) { return @{ ok = $false; message = 'Last donation date is not valid.' } }
        if ($ld -gt (Get-Date).Date) { return @{ ok = $false; message = 'Last donation date cannot be in the future.' } }
    }
    $city = S (Get-P $src 'city')
    if (-not $city) { return @{ ok = $false; message = 'Please enter your city / town.' } }
    $lat = To-Num (Get-P $src 'lat'); $lng = To-Num (Get-P $src 'lng')
    if (-not (Valid-Coords $lat $lng)) {
        if ($existing -and (Valid-Coords (To-Num (Get-P $existing 'lat')) (To-Num (Get-P $existing 'lng')))) {
            $lat = To-Num $existing.lat; $lng = To-Num $existing.lng
        } else {
            return @{ ok = $false; message = 'Location access is required so patients nearby can find you. Click "Share my location".' }
        }
    }
    $answersIn = Get-P $src 'answers'
    $answers = [pscustomobject]@{}
    foreach ($q in $ScreeningRules) {
        $v = Get-P $answersIn $q.key
        if ($v -isnot [bool]) { return @{ ok = $false; message = 'Please answer every health screening question (Yes or No).' } }
        Set-P $answers $q.key $v
    }
    if ((Get-P $src 'consent') -ne $true) { return @{ ok = $false; message = 'Please confirm that your health answers are true.' } }

    $donations = New-Object System.Collections.ArrayList
    $available = $true
    $locAt = Now-Str
    if ($existing) {
        $donations = To-List (Get-P $existing 'donations')
        $available = [bool](Get-P $existing 'is_available')
        if ((To-Num (Get-P $existing 'lat')) -eq $lat -and (To-Num (Get-P $existing 'lng')) -eq $lng) { $locAt = Get-P $existing 'location_updated_at' }
    }
    $donor = [pscustomobject]@{
        blood_group         = $bg
        gender              = $gender
        dob                 = $dob
        weight_kg           = $w
        hemoglobin          = $hb
        last_donation_date  = $(if ($last) { $last } else { $null })
        city                = $city
        district            = (S (Get-P $src 'district'))
        lat                 = $lat
        lng                 = $lng
        location_updated_at = $locAt
        is_available        = $available
        screening           = [pscustomobject]@{ answers = $answers; screened_at = (Now-Str) }
        donations           = $donations
    }
    return @{ ok = $true; donor = $donor }
}

# ------------------------------------------------------------------------------
# HTTP plumbing
# ------------------------------------------------------------------------------
$mimeTypes = @{
    ".html" = "text/html; charset=utf-8"; ".css" = "text/css; charset=utf-8"; ".js" = "application/javascript; charset=utf-8"
    ".json" = "application/json; charset=utf-8"; ".png" = "image/png"; ".jpg" = "image/jpeg"; ".jpeg" = "image/jpeg"
    ".svg" = "image/svg+xml"; ".ico" = "image/x-icon"; ".woff" = "font/woff"; ".woff2" = "font/woff2"; ".map" = "application/json"
}
$reasonPhrases = @{ 200 = 'OK'; 201 = 'Created'; 302 = 'Found'; 400 = 'Bad Request'; 401 = 'Unauthorized'; 403 = 'Forbidden'; 404 = 'Not Found'; 405 = 'Method Not Allowed'; 500 = 'Internal Server Error' }

function Send-Bytes([int]$code, [string]$ctype, [byte[]]$bytes, $extra = @()) {
    $reason = $reasonPhrases[$code]
    if (-not $reason) { $reason = 'OK' }
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append("HTTP/1.1 $code $reason`r`n")
    [void]$sb.Append("Content-Type: $ctype`r`n")
    [void]$sb.Append("Content-Length: $($bytes.Length)`r`n")
    [void]$sb.Append("Cache-Control: no-store`r`n")
    [void]$sb.Append("Connection: close`r`n")
    foreach ($e in $extra) { [void]$sb.Append("$e`r`n") }
    [void]$sb.Append("`r`n")
    $h = [System.Text.Encoding]::ASCII.GetBytes($sb.ToString())
    $script:Stream.Write($h, 0, $h.Length)
    if ($bytes.Length -gt 0) { $script:Stream.Write($bytes, 0, $bytes.Length) }
    $script:Stream.Flush()
    $script:Responded = $true
}
function Send-Json([int]$code, $obj, $extra = @()) {
    $json = ConvertTo-Json -InputObject $obj -Depth 12 -Compress
    Send-Bytes $code 'application/json; charset=utf-8' ($Utf8NoBom.GetBytes($json)) $extra
}
function Send-Err([int]$code, [string]$msg) { Send-Json $code ([pscustomobject]@{ success = $false; message = $msg }) }
function Send-Redirect([string]$to, $extra = @()) {
    $html = "<html><head><meta http-equiv='refresh' content='0;url=$to'></head><body>Redirecting...</body></html>"
    Send-Bytes 302 'text/html; charset=utf-8' ($Utf8NoBom.GetBytes($html)) (@("Location: $to") + $extra)
}

function Parse-Pairs([string]$s) {
    $h = @{}
    if (-not $s) { return $h }
    foreach ($pair in $s.Split('&')) {
        if (-not $pair) { continue }
        $kv = $pair.Split([char[]]'=', 2)
        $k = [Uri]::UnescapeDataString($kv[0].Replace('+', ' '))
        $v = ''
        if ($kv.Length -gt 1) { $v = [Uri]::UnescapeDataString($kv[1].Replace('+', ' ')) }
        $h[$k] = $v
    }
    return $h
}

function Get-Body {
    $text = $script:BodyText
    if (-not $text) { return [pscustomobject]@{} }
    $ct = ''
    if ($script:Headers.ContainsKey('content-type')) { $ct = $script:Headers['content-type'] }
    if ($ct -like '*application/x-www-form-urlencoded*') { return [pscustomobject](Parse-Pairs $text) }
    try {
        $o = ConvertFrom-Json $text
        if ($null -eq $o) { return [pscustomobject]@{} }
        return $o
    } catch { return [pscustomobject]@{} }
}

function Session-Cookie([string]$token) { "Set-Cookie: lifelink_session=$token; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000" }
$ExpiredCookie = "Set-Cookie: lifelink_session=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT"

function Start-Session($u) {
    $token = New-Token
    [void]$global:DB.sessions.Add([pscustomobject]@{ token = $token; user_id = $u.id; created_at = (Now-Str) })
    return $token
}

function Dashboard-For($u) {
    if ($u.role -eq 'admin') { return '/admin/dashboard' }
    if ($u.role -eq 'donor') { return '/donor/dashboard' }
    return '/patient/dashboard'
}

# ------------------------------------------------------------------------------
# Blood request creation (shared by JSON API and classic form POST)
# ------------------------------------------------------------------------------
function New-BloodRequest($data, $user) {
    $patient = S (Get-P $data 'patient_name')
    $bg = S (Get-P $data 'blood_group')
    $phone = S (Get-P $data 'contact_phone')
    $hospital = S (Get-P $data 'hospital_name')
    $city = S (Get-P $data 'city')
    if (-not $patient -or -not $phone -or -not $hospital -or -not $city) {
        return @{ ok = $false; message = 'Patient name, contact phone, hospital name and city are required.' }
    }
    if ($BloodGroups -notcontains $bg) { return @{ ok = $false; message = 'Please choose the required blood group.' } }
    $units = 1
    [void][int]::TryParse((S (Get-P $data 'units_needed')), [ref]$units)
    if ($units -lt 1) { $units = 1 }
    if ($units -gt 20) { $units = 20 }
    $urgency = (S (Get-P $data 'urgency_level')).ToUpper()
    if (@('CRITICAL', 'URGENT', 'NORMAL') -notcontains $urgency) { $urgency = 'URGENT' }
    $lat = To-Num (Get-P $data 'lat'); $lng = To-Num (Get-P $data 'lng')
    if (-not (Valid-Coords $lat $lng)) { $lat = $null; $lng = $null }
    $reqDate = S (Get-P $data 'required_date')
    if (-not (Parse-Date $reqDate)) { $reqDate = Today-Str }
    $contactPerson = S (Get-P $data 'contact_person')
    if (-not $contactPerson) { $contactPerson = $user.full_name }
    $contactEmail = S (Get-P $data 'contact_email')
    if (-not $contactEmail) { $contactEmail = $user.email }
    $method = S (Get-P $data 'preferred_contact_method')
    if (-not $method) { $method = 'phone' }

    $r = [pscustomobject]@{
        id                       = (Next-Id 'request')
        patient_name             = $patient
        contact_person           = $contactPerson
        contact_phone            = $phone
        contact_email            = $contactEmail
        preferred_contact_method = $method
        blood_group              = $bg
        units_needed             = $units
        urgency_level            = $urgency
        hospital_name            = $hospital
        hospital_area            = (S (Get-P $data 'hospital_area'))
        city                     = $city
        state                    = (S (Get-P $data 'state'))
        hospital_address         = (S (Get-P $data 'hospital_address'))
        required_date            = $reqDate
        doctor_name              = (S (Get-P $data 'doctor_name'))
        additional_notes         = (S (Get-P $data 'additional_notes'))
        lat                      = $lat
        lng                      = $lng
        status                   = 'ACTIVE'
        created_at               = (Now-Str)
        closed_at                = $null
        closed_by                = $null
        requester_user_id        = $user.id
    }
    [void]$global:DB.requests.Add($r)

    # Alert nearby compatible, eligible, available donors (within 50 km, or same city if no coordinates)
    $alerted = 0
    $compatibleGroups = $CanReceiveFrom[$bg]
    foreach ($u in $global:DB.users) {
        if ($u.id -eq $user.id -or -not $u.is_active) { continue }
        $d = Get-P $u 'donor'
        if (-not $d -or -not (Get-P $d 'is_available')) { continue }
        if ($compatibleGroups -notcontains $d.blood_group) { continue }
        if (-not (Get-Eligibility $d).eligible) { continue }
        $km = Get-Km (To-Num (Get-P $d 'lat')) (To-Num (Get-P $d 'lng')) $lat $lng
        $near = $false
        if ($null -ne $km) { $near = ($km -le 50) } else { $near = ((S (Get-P $d 'city')) -eq $city) }
        if (-not $near) { continue }
        $where = $hospital
        if ($null -ne $km) { $where = "$hospital ($km km away)" }
        Add-Notification $u.id 'request' "$urgency need: $bg blood for $patient" "$units unit(s) needed at $where. Your $($d.blood_group) blood is compatible." "/track-request?id=$($r.id)"
        $alerted++
    }
    Add-Audit 'REQUEST_CREATED' 'blood_requests' "$(Req-Code $r.id) created by $($user.email) for $patient ($bg, $units unit(s)). $alerted donor(s) alerted."
    Write-Host "[+] $(Req-Code $r.id) $urgency $bg for $patient by $($user.email) - $alerted donor(s) alerted" -ForegroundColor Green
    return @{ ok = $true; request = $r; alerted = $alerted }
}

# ------------------------------------------------------------------------------
# API router. Returns $true if the path was an API route.
# ------------------------------------------------------------------------------
function Handle-Api {
    $p = $script:Path
    $m = $script:Method
    $me = $script:Me
    $q = $script:Query

    if (-not $p.StartsWith('/api/') -and $p -ne '/donor/availability' -and -not ($m -eq 'POST' -and @('/emergency-request', '/emergency-request.html', '/requests/new', '/requests/create') -contains $p)) {
        return $false
    }

    # ---------------- AUTH ----------------
    if ($p -eq '/api/auth/register' -and $m -eq 'POST') {
        $b = Get-Body
        $name = S (Get-P $b 'full_name'); $email = (S (Get-P $b 'email')).ToLower(); $phone = S (Get-P $b 'phone'); $pw = [string](Get-P $b 'password')
        if (-not $name -or -not $email -or -not $phone -or -not $pw) { Send-Err 400 'Full name, email, mobile number and password are required.'; return $true }
        if ($email -notmatch '^[^@\s]+@[^@\s]+\.[^@\s]+$') { Send-Err 400 'Please enter a valid email address.'; return $true }
        if ($pw.Length -lt 8 -or $pw -notmatch '[A-Za-z]' -or $pw -notmatch '[0-9]') { Send-Err 400 'Password must be at least 8 characters and contain letters and numbers.'; return $true }
        if (Find-UserByEmail $email) { Send-Err 400 'An account with this email address already exists. Please sign in.'; return $true }

        $donor = $null
        if ((Get-P $b 'become_donor') -eq $true) {
            $res = Build-DonorProfile (Get-P $b 'donor') $null
            if (-not $res.ok) { Send-Err 400 $res.message; return $true }
            $donor = $res.donor
        }
        $salt = New-Salt
        $u = [pscustomobject]@{
            id            = (Next-Id 'user')
            full_name     = $name
            email         = $email
            phone         = $phone
            password_salt = $salt
            password_hash = (Hash-Password $pw $salt)
            role          = $(if ($donor) { 'donor' } else { 'patient' })
            city          = $(if ($donor) { $donor.city } else { S (Get-P $b 'city') })
            district      = $(if ($donor) { $donor.district } else { '' })
            is_active     = $true
            created_at    = (Now-Str)
            donor         = $donor
        }
        [void]$global:DB.users.Add($u)
        $token = Start-Session $u
        Add-Audit 'USER_REGISTERED' 'users' "New $($u.role) account $email registered."
        if ($donor) {
            $el = Get-Eligibility $donor
            if ($el.eligible) {
                Add-Notification $u.id 'welcome' 'Welcome, you are eligible to donate' 'Your health screening passed. Patients nearby can now find you in donor search.' '/donor/dashboard'
            } else {
                Add-Notification $u.id 'eligibility' 'You are not eligible to donate right now' 'Your account is created, but you are hidden from donor search until you are eligible. See the reasons on your dashboard.' '/donor/dashboard#eligibility-section'
            }
        }
        Save-Db
        Write-Host "[+] Registered $email as $($u.role)" -ForegroundColor Green
        Send-Json 201 ([pscustomobject]@{ success = $true; message = 'Account created successfully.'; user = (Get-SafeUser $u); donor = (Get-DonorView $u); redirect = (Dashboard-For $u) }) @((Session-Cookie $token))
        return $true
    }

    if ($p -eq '/api/auth/login' -and $m -eq 'POST') {
        $b = Get-Body
        $email = (S (Get-P $b 'email')).ToLower(); $pw = [string](Get-P $b 'password')
        $u = Find-UserByEmail $email
        if (-not $u -or (Hash-Password $pw $u.password_salt) -ne $u.password_hash) { Send-Err 401 'Invalid email or password. Please check your details.'; return $true }
        if (-not $u.is_active) { Send-Err 403 'This account has been deactivated by an administrator.'; return $true }
        $token = Start-Session $u
        Save-Db
        Send-Json 200 ([pscustomobject]@{ success = $true; redirect = (Dashboard-For $u); user = (Get-SafeUser $u) }) @((Session-Cookie $token))
        return $true
    }

    if ($p -eq '/api/auth/logout') {
        if ($script:Token) {
            foreach ($s in @($global:DB.sessions)) { if ($s.token -eq $script:Token) { $global:DB.sessions.Remove($s) } }
            Save-Db
        }
        Send-Json 200 ([pscustomobject]@{ success = $true; message = 'Signed out.' }) @($ExpiredCookie)
        return $true
    }

    if ($p -eq '/api/auth/me') {
        if (-not $me) { Send-Err 401 'Not signed in.'; return $true }
        $unread = 0
        foreach ($n in $global:DB.notifications) { if ($n.user_id -eq $me.id -and -not $n.is_read) { $unread++ } }
        Send-Json 200 ([pscustomobject]@{ success = $true; user = (Get-SafeUser $me); donor = (Get-DonorView $me); unread_notifications = $unread; dashboard = (Dashboard-For $me) })
        return $true
    }

    if ($p -eq '/api/auth/forgot' -and $m -eq 'POST') {
        $b = Get-Body
        $email = (S (Get-P $b 'email')).ToLower()
        $u = Find-UserByEmail $email
        $link = $null
        if ($u) {
            $token = New-Token
            [void]$global:DB.resets.Add([pscustomobject]@{ token = $token; user_id = $u.id; expires_at = (Get-Date).AddMinutes(30).ToString('yyyy-MM-dd HH:mm:ss'); used = $false })
            Save-Db
            $link = "/reset-password?token=$token"
            Write-Host "[i] Password reset link for $email : http://localhost:$Port$link" -ForegroundColor Cyan
        }
        # No email service is configured, so the link is returned for local use.
        Send-Json 200 ([pscustomobject]@{ success = $true; message = 'If an account exists for that email, a reset link has been created.'; reset_url = $link })
        return $true
    }

    if ($p -eq '/api/auth/reset' -and $m -eq 'POST') {
        $b = Get-Body
        $token = S (Get-P $b 'token'); $pw = [string](Get-P $b 'password')
        if ($pw.Length -lt 8 -or $pw -notmatch '[A-Za-z]' -or $pw -notmatch '[0-9]') { Send-Err 400 'Password must be at least 8 characters and contain letters and numbers.'; return $true }
        $rs = $null
        foreach ($x in $global:DB.resets) { if ($x.token -eq $token) { $rs = $x } }
        if (-not $rs -or $rs.used -or [datetime]::ParseExact($rs.expires_at, 'yyyy-MM-dd HH:mm:ss', $Invariant) -lt (Get-Date)) { Send-Err 400 'This reset link is invalid or has expired. Please request a new one.'; return $true }
        $u = Find-User $rs.user_id
        $salt = New-Salt
        Set-P $u 'password_salt' $salt
        Set-P $u 'password_hash' (Hash-Password $pw $salt)
        Set-P $rs 'used' $true
        Add-Audit 'PASSWORD_RESET' 'users' "Password reset for $($u.email)."
        Save-Db
        Send-Json 200 ([pscustomobject]@{ success = $true; message = 'Password updated. Please sign in.' })
        return $true
    }

    # ---------------- PUBLIC STATS ----------------
    if ($p -eq '/api/public/stats') {
        $counts = [ordered]@{}
        foreach ($g in $BloodGroups) { $counts[$g] = 0 }
        $eligible = 0
        foreach ($u in $global:DB.users) {
            $d = Get-P $u 'donor'
            if (-not $d -or -not $u.is_active) { continue }
            if ((Get-Eligibility $d).eligible) { $counts[$d.blood_group]++; $eligible++ }
        }
        $active = @($global:DB.requests | Where-Object { $_.status -eq 'ACTIVE' }).Count
        $fulfilled = @($global:DB.requests | Where-Object { $_.status -eq 'FULFILLED' }).Count
        Send-Json 200 ([pscustomobject]@{ success = $true; eligible_donors = $eligible; by_group = [pscustomobject]$counts; active_requests = $active; fulfilled_requests = $fulfilled })
        return $true
    }

    # ---------------- DONOR SEARCH (public) ----------------
    if ($p -eq '/api/donors/search') {
        $bg = S $q['blood_group']
        $compatible = ($q['compatible'] -ne '0')
        $availableOnly = ($q['available_only'] -ne '0')
        $lat = To-Num $q['lat']; $lng = To-Num $q['lng']
        $hasCoords = Valid-Coords $lat $lng
        $radius = To-Num $q['radius_km']
        $text = (S $q['location']).ToLower()
        $groups = $BloodGroups
        if ($bg -and $bg -ne 'ALL' -and $CanReceiveFrom.ContainsKey($bg)) {
            if ($compatible) { $groups = $CanReceiveFrom[$bg] } else { $groups = @($bg) }
        }
        $results = New-Object System.Collections.ArrayList
        foreach ($u in $global:DB.users) {
            if (-not $u.is_active) { continue }
            if ($me -and $u.id -eq $me.id) { continue }
            $d = Get-P $u 'donor'
            if (-not $d) { continue }
            if ($groups -notcontains $d.blood_group) { continue }
            $el = Get-Eligibility $d
            if (-not $el.eligible) { continue }   # deferred donors are hidden from search
            $avail = [bool](Get-P $d 'is_available')
            if ($availableOnly -and -not $avail) { continue }
            $km = $null
            if ($hasCoords) {
                $km = Get-Km $lat $lng (To-Num (Get-P $d 'lat')) (To-Num (Get-P $d 'lng'))
                if ($null -ne $radius -and $radius -gt 0 -and ($null -eq $km -or $km -gt $radius)) { continue }
            } elseif ($text) {
                $hay = ((S (Get-P $d 'city')) + ' ' + (S (Get-P $d 'district'))).ToLower()
                if (-not $hay.Contains($text)) { continue }
            }
            $pref = 'phone'
            [void]$results.Add([pscustomobject]@{
                user_id         = $u.id
                display_name    = (Mask-Name $u.full_name)
                blood_group     = $d.blood_group
                exact_match     = ($d.blood_group -eq $bg)
                city            = (S (Get-P $d 'city'))
                district        = (S (Get-P $d 'district'))
                is_available    = $avail
                distance_km     = $km
                donations_count = @($d.donations).Count
                is_verified     = $true
                contact_preference = $pref
            })
        }
        $sorted = @($results | Sort-Object @{ Expression = { if ($null -eq $_.distance_km) { 1e9 } else { $_.distance_km } } }, @{ Expression = { -not $_.exact_match } })
        Send-Json 200 ([pscustomobject]@{ success = $true; count = $sorted.Count; donors = (To-List $sorted); used_location = $hasCoords })
        return $true
    }

    if ($p -eq '/api/donors/contact-request' -and $m -eq 'POST') {
        $b = Get-Body
        $donorId = To-Num (Get-P $b 'donor_user_id')
        $du = $null
        if ($null -ne $donorId) { $du = Find-User ([int]$donorId) }
        if (-not $du -or -not (Get-P $du 'donor') -or -not $du.is_active) { Send-Err 404 'This donor is no longer available.'; return $true }
        $rname = S (Get-P $b 'requester_name'); $rphone = S (Get-P $b 'requester_phone'); $notes = S (Get-P $b 'case_notes')
        if (-not $rname -or -not $rphone) { Send-Err 400 'Please enter your name and a callback phone number.'; return $true }
        $body = "$rname needs your help. Call back on $rphone."
        if ($notes) { $body += " Notes: $notes" }
        Add-Notification $du.id 'contact' 'Someone needs your blood - please call back' $body ''
        Add-Audit 'CONTACT_REQUEST' 'donor_profiles' "Contact request sent to donor #$($du.id) by $rname."
        Save-Db
        Send-Json 200 ([pscustomobject]@{ success = $true; message = "Sent! $(Mask-Name $du.full_name) has your callback number and can call you." })
        return $true
    }

    # ---------------- EVERYTHING BELOW REQUIRES SIGN-IN ----------------
    $isCreate = ($m -eq 'POST' -and (@('/emergency-request', '/emergency-request.html', '/requests/new', '/requests/create', '/api/requests', '/api/requests/create') -contains $p))
    $isPublicRead = ($m -eq 'GET' -and ($p -match '^/api/requests/\d+$' -or $p -eq '/api/requests' -or ($p -eq '/api/requests' -and $q['scope'] -eq 'open')))
    if (-not $me -and -not $isPublicRead) {
        if ($isCreate -and $p -notlike '/api/*') { Send-Redirect '/auth/login?next=/emergency-request'; return $true }
        Send-Err 401 'Please sign in first.'
        return $true
    }

    # ---------------- PROFILE ----------------
    if ($p -eq '/api/profile' -and $m -eq 'POST') {
        $b = Get-Body
        $name = S (Get-P $b 'full_name'); $phone = S (Get-P $b 'phone')
        if (-not $name -or -not $phone) { Send-Err 400 'Name and mobile number are required.'; return $true }
        Set-P $me 'full_name' $name
        Set-P $me 'phone' $phone
        Set-P $me 'city' (S (Get-P $b 'city'))
        Set-P $me 'district' (S (Get-P $b 'district'))
        $d = Get-P $me 'donor'
        if ($d) { Set-P $d 'city' (S (Get-P $b 'city')); Set-P $d 'district' (S (Get-P $b 'district')) }
        Save-Db
        Send-Json 200 ([pscustomobject]@{ success = $true; message = 'Profile updated.'; user = (Get-SafeUser $me) })
        return $true
    }

    # ---------------- DONOR SELF-SERVICE ----------------
    if ($p -eq '/api/donor/profile' -and $m -eq 'POST') {
        $existing = Get-P $me 'donor'
        $res = Build-DonorProfile (Get-Body) $existing
        if (-not $res.ok) { Send-Err 400 $res.message; return $true }
        Set-P $me 'donor' $res.donor
        if ($me.role -eq 'patient') { Set-P $me 'role' 'donor' }
        Set-P $me 'city' $res.donor.city
        Set-P $me 'district' $res.donor.district
        $el = Get-Eligibility $res.donor
        $msg = 'Health screening saved. You are eligible to donate and visible in donor search.'
        if (-not $el.eligible) { $msg = 'Health screening saved. You are not eligible right now, so you are hidden from donor search.' }
        Add-Audit 'DONOR_SCREENED' 'donor_profiles' "$($me.email) completed health screening: $($el.status)."
        Save-Db
        Send-Json 200 ([pscustomobject]@{ success = $true; message = $msg; user = (Get-SafeUser $me); donor = (Get-DonorView $me) })
        return $true
    }

    $myDonor = Get-P $me 'donor'

    if ($p -eq '/api/donor/location' -and $m -eq 'POST') {
        if (-not $myDonor) { Send-Err 400 'Complete your donor profile first.'; return $true }
        $b = Get-Body
        $lat = To-Num (Get-P $b 'lat'); $lng = To-Num (Get-P $b 'lng')
        if (-not (Valid-Coords $lat $lng)) { Send-Err 400 'Location was not received. Please allow location access and try again.'; return $true }
        Set-P $myDonor 'lat' $lat
        Set-P $myDonor 'lng' $lng
        Set-P $myDonor 'location_updated_at' (Now-Str)
        Save-Db
        Send-Json 200 ([pscustomobject]@{ success = $true; message = 'Location updated.'; donor = (Get-DonorView $me) })
        return $true
    }

    if (($p -eq '/api/donor/availability' -or $p -eq '/donor/availability') -and $m -eq 'POST') {
        if (-not $myDonor) { Send-Err 400 'Complete your donor profile first.'; return $true }
        $b = Get-Body
        $val = ((Get-P $b 'is_available') -eq $true)
        Set-P $myDonor 'is_available' $val
        Save-Db
        $msg = 'You are now available for urgent requests.'
        if (-not $val) { $msg = 'Alerts paused. You are hidden from "available now" searches.' }
        Send-Json 200 ([pscustomobject]@{ success = $true; is_available = $val; message = $msg })
        return $true
    }

    if ($p -eq '/api/donor/donations' -and $m -eq 'POST') {
        if (-not $myDonor) { Send-Err 400 'Complete your donor profile first.'; return $true }
        $b = Get-Body
        $date = S (Get-P $b 'date'); $center = S (Get-P $b 'center')
        $dt = Parse-Date $date
        if (-not $dt) { Send-Err 400 'Please enter the donation date.'; return $true }
        if ($dt -gt (Get-Date).Date) { Send-Err 400 'Donation date cannot be in the future.'; return $true }
        if (-not $center) { Send-Err 400 'Please enter the hospital or blood bank name.'; return $true }
        $units = 1
        [void][int]::TryParse((S (Get-P $b 'units')), [ref]$units)
        if ($units -lt 1) { $units = 1 }
        [void]$myDonor.donations.Add([pscustomobject]@{ id = (Next-Id 'donation'); date = $date; center = $center; units = $units; type = 'Whole blood'; request_id = $null; source = 'self' })
        $lastCur = Parse-Date (S (Get-P $myDonor 'last_donation_date'))
        if (-not $lastCur -or $dt -gt $lastCur) { Set-P $myDonor 'last_donation_date' $date }
        Save-Db
        Send-Json 200 ([pscustomobject]@{ success = $true; message = 'Donation added to your record.'; donor = (Get-DonorView $me) })
        return $true
    }

    # ---------------- NOTIFICATIONS ----------------
    if ($p -eq '/api/notifications') {
        $list = @($global:DB.notifications | Where-Object { $_.user_id -eq $me.id } | Sort-Object { $_.id } -Descending | Select-Object -First 50)
        $unread = @($list | Where-Object { -not $_.is_read }).Count
        Send-Json 200 ([pscustomobject]@{ success = $true; unread = $unread; notifications = (To-List $list) })
        return $true
    }
    if ($p -eq '/api/notifications/read-all' -and $m -eq 'POST') {
        foreach ($n in $global:DB.notifications) { if ($n.user_id -eq $me.id) { Set-P $n 'is_read' $true } }
        Save-Db
        Send-Json 200 ([pscustomobject]@{ success = $true; message = 'All notifications marked as read.' })
        return $true
    }

    # ---------------- BLOOD REQUESTS ----------------
    if ($isCreate) {
        $data = Get-Body
        $res = New-BloodRequest $data $me
        $isJson = ($script:Headers['content-type'] -like '*application/json*')
        if (-not $res.ok) {
            if ($isJson) { Send-Err 400 $res.message } else { Send-Bytes 400 'text/html; charset=utf-8' ($Utf8NoBom.GetBytes("<script>alert('$($res.message)'); history.back();</script>")) }
            return $true
        }
        Save-Db
        $id = $res.request.id
        if ($isJson) {
            Send-Json 201 ([pscustomobject]@{ success = $true; request_id = $id; code = (Req-Code $id); alerted = $res.alerted; redirect = "/track-request?id=$id"; request = (Get-RequestView $res.request $me) })
        } else {
            Send-Redirect "/track-request?id=$id"
        }
        return $true
    }

    if ($p -eq '/api/requests' -or $p -eq '/api/requests/list') {
        $scope = S $q['scope']
        if (-not $scope) {
            $scope = if ($me) { 'mine' } else { 'open' }
        }
        if ($scope -eq 'all' -and (-not $me -or $me.role -ne 'admin')) { Send-Err 403 'Administrator access required.'; return $true }
        $list = New-Object System.Collections.ArrayList
        foreach ($r in $global:DB.requests) {
            if ($scope -eq 'mine' -and $r.requester_user_id -ne $me.id) { continue }
            if ($scope -eq 'open' -and $r.status -ne 'ACTIVE') { continue }
            [void]$list.Add((Get-RequestView $r $me))
        }
        $urgRank = @{ 'CRITICAL' = 0; 'URGENT' = 1; 'NORMAL' = 2 }
        $sorted = @($list | Sort-Object @{ Expression = { $urgRank[$_.urgency_level] } }, @{ Expression = { $_.id }; Descending = $true })
        if ($scope -ne 'open') { $sorted = @($list | Sort-Object @{ Expression = { $_.id }; Descending = $true }) }
        Send-Json 200 ([pscustomobject]@{ success = $true; count = $sorted.Count; requests = (To-List $sorted) })
        return $true
    }

    if ($p -match '^/api/requests/(\d+)$' -and $m -eq 'GET') {
        $r = Find-Request ([int]$Matches[1])
        if (-not $r) { Send-Err 404 'No request found with that ID.'; return $true }
        Send-Json 200 ([pscustomobject]@{ success = $true; request = (Get-RequestView $r $me); responses = (Get-ResponseViews $r $me) })
        return $true
    }

    if ($p -match '^/api/requests/(\d+)/status$' -and $m -eq 'POST') {
        $r = Find-Request ([int]$Matches[1])
        if (-not $r) { Send-Err 404 'Request not found.'; return $true }
        if ($r.requester_user_id -ne $me.id -and $me.role -ne 'admin') { Send-Err 403 'Only the person who posted this request (or an admin) can change it.'; return $true }
        $new = (S (Get-P (Get-Body) 'status')).ToUpper()
        if (@('FULFILLED', 'CANCELLED', 'ACTIVE') -notcontains $new) { Send-Err 400 'Unknown status.'; return $true }
        $old = $r.status
        Set-P $r 'status' $new
        if ($new -eq 'ACTIVE') { Set-P $r 'closed_at' $null; Set-P $r 'closed_by' $null }
        else { Set-P $r 'closed_at' (Now-Str); Set-P $r 'closed_by' $me.id }
        $word = @{ 'FULFILLED' = 'fulfilled'; 'CANCELLED' = 'cancelled'; 'ACTIVE' = 're-opened' }[$new]
        foreach ($resp in $global:DB.responses) {
            if ($resp.request_id -eq $r.id -and $resp.status -ne 'WITHDRAWN') {
                Add-Notification $resp.donor_user_id 'request_status' "$(Req-Code $r.id) was $word" "The request for $($r.patient_name) at $($r.hospital_name) was marked $word. Thank you for responding." "/track-request?id=$($r.id)"
            }
        }
        Add-Audit "REQUEST_$new" 'blood_requests' "$(Req-Code $r.id) changed from $old to $new by $($me.email)."
        Save-Db
        Send-Json 200 ([pscustomobject]@{ success = $true; message = "$(Req-Code $r.id) marked as $word."; request = (Get-RequestView $r $me) })
        return $true
    }

    if ($p -match '^/api/requests/(\d+)/respond$' -and $m -eq 'POST') {
        $r = Find-Request ([int]$Matches[1])
        if (-not $r) { Send-Err 404 'Request not found.'; return $true }
        if ($r.status -ne 'ACTIVE') { Send-Err 400 'This request is no longer active.'; return $true }
        if (-not $myDonor) { Send-Err 400 'Complete your donor profile and health screening before volunteering.'; return $true }
        if ($r.requester_user_id -eq $me.id) { Send-Err 400 'You cannot volunteer for your own request.'; return $true }
        $el = Get-Eligibility $myDonor
        if (-not $el.eligible) { Send-Err 400 ('You are not eligible to donate right now: ' + (($el.reasons | ForEach-Object { $_.message }) -join ' ')); return $true }
        if ($CanReceiveFrom[$r.blood_group] -notcontains $myDonor.blood_group) { Send-Err 400 "Your blood group ($($myDonor.blood_group)) is not compatible with $($r.blood_group)."; return $true }
        $msg = S (Get-P (Get-Body) 'message')
        if (-not $msg) { $msg = 'I can donate. Please contact me.' }
        $existing = $null
        foreach ($resp in $global:DB.responses) { if ($resp.request_id -eq $r.id -and $resp.donor_user_id -eq $me.id) { $existing = $resp } }
        if ($existing -and $existing.status -ne 'WITHDRAWN') { Send-Err 400 'You have already volunteered for this request.'; return $true }
        if ($existing) {
            Set-P $existing 'status' 'OFFERED'; Set-P $existing 'message' $msg; Set-P $existing 'created_at' (Now-Str)
        } else {
            [void]$global:DB.responses.Add([pscustomobject]@{ id = (Next-Id 'response'); request_id = $r.id; donor_user_id = $me.id; status = 'OFFERED'; message = $msg; created_at = (Now-Str) })
        }
        Add-Notification $r.requester_user_id 'response' "A $($myDonor.blood_group) donor volunteered for $(Req-Code $r.id)" "$($me.full_name) ($($me.phone)) says: `"$msg`"" '/patient/dashboard#donor-responses-section'
        Save-Db
        Send-Json 200 ([pscustomobject]@{ success = $true; message = 'Thank you! The patient''s family has been notified and will contact you.'; request = (Get-RequestView $r $me) })
        return $true
    }

    if ($p -match '^/api/responses/(\d+)/withdraw$' -and $m -eq 'POST') {
        $resp = Find-Response ([int]$Matches[1])
        if (-not $resp -or $resp.donor_user_id -ne $me.id) { Send-Err 404 'Response not found.'; return $true }
        if ($resp.status -eq 'DONATED') { Send-Err 400 'This donation is already confirmed.'; return $true }
        Set-P $resp 'status' 'WITHDRAWN'
        $r = Find-Request $resp.request_id
        if ($r) { Add-Notification $r.requester_user_id 'response' "A donor withdrew from $(Req-Code $r.id)" "$($me.full_name) can no longer donate for $($r.patient_name)." '/patient/dashboard#donor-responses-section' }
        Save-Db
        Send-Json 200 ([pscustomobject]@{ success = $true; message = 'Your offer was withdrawn.' })
        return $true
    }

    if ($p -match '^/api/responses/(\d+)/donated$' -and $m -eq 'POST') {
        $resp = Find-Response ([int]$Matches[1])
        if (-not $resp) { Send-Err 404 'Response not found.'; return $true }
        $r = Find-Request $resp.request_id
        if (-not $r -or ($r.requester_user_id -ne $me.id -and $me.role -ne 'admin')) { Send-Err 403 'Only the requester can confirm a donation.'; return $true }
        if ($resp.status -eq 'DONATED') { Send-Err 400 'Already confirmed.'; return $true }
        Set-P $resp 'status' 'DONATED'
        $du = Find-User $resp.donor_user_id
        $dd = Get-P $du 'donor'
        if ($dd) {
            $today = Today-Str
            [void]$dd.donations.Add([pscustomobject]@{ id = (Next-Id 'donation'); date = $today; center = $r.hospital_name; units = 1; type = 'Whole blood'; request_id = $r.id; source = 'request' })
            Set-P $dd 'last_donation_date' $today
            Add-Notification $du.id 'donated' "Donation confirmed for $(Req-Code $r.id)" "Thank you for donating for $($r.patient_name). It has been added to your donation record; your next eligible date was updated." '/donor/dashboard#donations-history'
        }
        Add-Audit 'DONATION_CONFIRMED' 'donor_responses' "Donation by $($du.email) for $(Req-Code $r.id) confirmed by $($me.email)."
        Save-Db
        Send-Json 200 ([pscustomobject]@{ success = $true; message = "Donation by $($du.full_name) confirmed." })
        return $true
    }

    if ($p -eq '/api/my/responses') {
        $list = New-Object System.Collections.ArrayList
        foreach ($resp in $global:DB.responses) {
            if ($resp.donor_user_id -ne $me.id) { continue }
            $r = Find-Request $resp.request_id
            if (-not $r) { continue }
            [void]$list.Add([pscustomobject]@{ id = $resp.id; status = $resp.status; message = $resp.message; created_at = $resp.created_at; request = (Get-RequestView $r $me) })
        }
        $sorted = @($list | Sort-Object { $_.id } -Descending)
        Send-Json 200 ([pscustomobject]@{ success = $true; responses = (To-List $sorted) })
        return $true
    }

    if ($p -eq '/api/my/request-responses') {
        # All donor responses to requests I posted
        $list = New-Object System.Collections.ArrayList
        foreach ($r in $global:DB.requests) {
            if ($r.requester_user_id -ne $me.id) { continue }
            foreach ($v in (Get-ResponseViews $r $me)) { Set-P $v 'request_status' $r.status; [void]$list.Add($v) }
        }
        $sorted = @($list | Sort-Object { $_.id } -Descending)
        Send-Json 200 ([pscustomobject]@{ success = $true; responses = (To-List $sorted) })
        return $true
    }

    # ---------------- ADMIN ----------------
    if ($p.StartsWith('/api/admin/')) {
        if ($me.role -ne 'admin') { Send-Err 403 'Administrator access required.'; return $true }

        if ($p -eq '/api/admin/overview') {
            $users = New-Object System.Collections.ArrayList
            $dist = [ordered]@{}
            foreach ($g in $BloodGroups) { $dist[$g] = 0 }
            $donors = 0; $eligible = 0; $available = 0
            foreach ($u in $global:DB.users) {
                $su = Get-SafeUser $u
                $d = Get-P $u 'donor'
                $status = $null
                if ($d) {
                    $donors++
                    $el = Get-Eligibility $d
                    $status = $el.status
                    if ($el.eligible) { $eligible++; $dist[$d.blood_group]++ ; if (Get-P $d 'is_available') { $available++ } }
                }
                Set-P $su 'eligibility_status' $status
                [void]$users.Add($su)
            }
            $active = 0; $fulfilled = 0; $cancelled = 0; $critical = 0
            $reqs = New-Object System.Collections.ArrayList
            foreach ($r in $global:DB.requests) {
                if ($r.status -eq 'ACTIVE') { $active++; if ($r.urgency_level -eq 'CRITICAL') { $critical++ } }
                elseif ($r.status -eq 'FULFILLED') { $fulfilled++ }
                elseif ($r.status -eq 'CANCELLED') { $cancelled++ }
                [void]$reqs.Add((Get-RequestView $r $me))
            }
            $distList = New-Object System.Collections.ArrayList
            foreach ($k in $dist.Keys) { [void]$distList.Add([pscustomobject]@{ blood_group = $k; count = $dist[$k] }) }
            $audit = @($global:DB.audit | Sort-Object { $_.id } -Descending | Select-Object -First 50)
            Send-Json 200 ([pscustomobject]@{
                success = $true
                stats = [pscustomobject]@{ users = $global:DB.users.Count; donors = $donors; eligible_donors = $eligible; available_donors = $available; active_requests = $active; critical_requests = $critical; fulfilled = $fulfilled; cancelled = $cancelled }
                users = $users
                requests = (To-List @($reqs | Sort-Object { $_.id } -Descending))
                blood_distribution = $distList
                audit = (To-List $audit)
            })
            return $true
        }

        if ($p -match '^/api/admin/users/(\d+)/toggle$' -and $m -eq 'POST') {
            $u = Find-User ([int]$Matches[1])
            if (-not $u) { Send-Err 404 'User not found.'; return $true }
            if ($u.role -eq 'admin') { Send-Err 400 'Administrator accounts cannot be deactivated here.'; return $true }
            $new = -not [bool]$u.is_active
            Set-P $u 'is_active' $new
            if (-not $new) { foreach ($s in @($global:DB.sessions)) { if ($s.user_id -eq $u.id) { $global:DB.sessions.Remove($s) } } }
            $word = 'deactivated'
            if ($new) { $word = 'activated' }
            Add-Audit "USER_$($word.ToUpper())" 'users' "$($u.email) $word by $($me.email)."
            Save-Db
            Send-Json 200 ([pscustomobject]@{ success = $true; message = "$($u.full_name) $word."; is_active = $new })
            return $true
        }
    }

    Send-Err 404 "Unknown API endpoint: $m $p"
    return $true
}

# ------------------------------------------------------------------------------
# Static pages
# ------------------------------------------------------------------------------
function Handle-Static {
    $urlPath = $script:Path
    $me = $script:Me
    $filePath = $null

    $routes = @{
        '/' = 'index.html'; '/index.html' = 'index.html'; '/about' = 'index.html'; '/about.html' = 'index.html'
        '/login' = 'login.html'; '/auth/login' = 'login.html'; '/login.html' = 'login.html'
        '/register' = 'register.html'; '/auth/register' = 'register.html'; '/register.html' = 'register.html'
        '/find-donors' = 'search.html'; '/search' = 'search.html'; '/search.html' = 'search.html'
        '/emergency-request' = 'emergency-request.html'; '/emergency-request.html' = 'emergency-request.html'; '/requests/new' = 'emergency-request.html'; '/requests/create' = 'emergency-request.html'
        '/track-request' = 'track-request.html'; '/track-request.html' = 'track-request.html'; '/requests/lookup' = 'track-request.html'
        '/dashboard' = 'dashboard.html'; '/dashboard.html' = 'dashboard.html'; '/donor/dashboard' = 'dashboard.html'
        '/patient/dashboard' = 'patient-dashboard.html'; '/patient-dashboard.html' = 'patient-dashboard.html'
        '/admin/login' = 'admin-login.html'; '/admin-login.html' = 'admin-login.html'
        '/forgot-password' = 'forgot-password.html'; '/auth/forgot-password' = 'forgot-password.html'; '/forgot-password.html' = 'forgot-password.html'
        '/reset-password' = 'reset-password.html'; '/auth/reset-password' = 'reset-password.html'; '/reset-password.html' = 'reset-password.html'
    }

    if ($urlPath -eq '/auth/logout' -or $urlPath -eq '/logout') {
        if ($script:Token) { foreach ($s in @($global:DB.sessions)) { if ($s.token -eq $script:Token) { $global:DB.sessions.Remove($s) } }; Save-Db }
        Send-Redirect '/auth/login' @($ExpiredCookie)
        return
    }

    if ($urlPath -eq '/patient/emergency-request.html' -or $urlPath -eq '/patient/emergency-request') {
        Send-Redirect '/emergency-request'
        return
    }

    if ($urlPath -eq '/admin/admin-dashboard.html') {
        Send-Redirect '/admin/dashboard'
        return
    }

    if ($urlPath -in @('/admin', '/admin/', '/admin/dashboard', '/admin-dashboard.html')) {
        if ($me -and $me.role -ne 'admin') {
            $html = "<!DOCTYPE html><html><head><meta charset='utf-8'><title>403 - Forbidden | LifeLink</title></head><body style='padding:4rem 1rem;text-align:center;font-family:Inter,Arial,sans-serif;background:#0F172A;color:#F8FAFC'><div style='max-width:520px;margin:4rem auto;background:#1E293B;padding:2.5rem;border-radius:12px;border:1px solid #334155'><h1 style='color:#EF4444'>403 - Access denied</h1><p style='color:#94A3B8'>Your account does not have administrator access.</p><a href='$(Dashboard-For $me)' style='display:inline-block;margin-top:1rem;padding:.65rem 1.5rem;background:#C62828;color:#fff;text-decoration:none;border-radius:6px;font-weight:600'>Go to my dashboard</a></div></body></html>"
            Send-Bytes 403 'text/html; charset=utf-8' ($Utf8NoBom.GetBytes($html))
            return
        }
        $filePath = Join-Path $previewDir 'admin-dashboard.html'
    } elseif ($routes.ContainsKey($urlPath)) {
        $filePath = Join-Path $previewDir $routes[$urlPath]
    } elseif ($urlPath.StartsWith('/requests/track/') -or $urlPath.StartsWith('/track/')) {
        $filePath = Join-Path $previewDir 'track-request.html'
    } elseif ($urlPath.StartsWith('/app/static/')) {
        $filePath = Join-Path $staticDir ($urlPath.Substring(12).Replace('/', '\'))
    } elseif ($urlPath.StartsWith('/static/')) {
        $filePath = Join-Path $staticDir ($urlPath.Substring(8).Replace('/', '\'))
    } elseif ($urlPath.StartsWith('/preview/')) {
        $filePath = Join-Path $previewDir ($urlPath.Substring(9).Replace('/', '\'))
    } else {
        $clean = $urlPath.TrimStart('/').Replace('/', '\')
        $candidate = Join-Path $previewDir $clean
        if ($clean -and (Test-Path -LiteralPath $candidate -PathType Leaf)) { $filePath = $candidate }
        else {
            # Relative links from nested routes (e.g. /donor/search.html) -> resolve by file name
            $leaf = Split-Path $clean -Leaf
            if ($leaf) {
                if ($routes.ContainsKey("/$leaf")) { $filePath = Join-Path $previewDir $routes["/$leaf"] }
                elseif (Test-Path -LiteralPath (Join-Path $previewDir $leaf) -PathType Leaf) { $filePath = Join-Path $previewDir $leaf }
            }
        }
    }

    # Prevent path traversal outside the project folder
    if ($filePath) {
        $full = [System.IO.Path]::GetFullPath($filePath)
        if (-not $full.StartsWith($rootDir, [System.StringComparison]::OrdinalIgnoreCase)) { $filePath = $null }
    }

    if ($filePath -and (Test-Path -LiteralPath $filePath -PathType Leaf)) {
        $ext = [System.IO.Path]::GetExtension($filePath).ToLower()
        $mime = 'application/octet-stream'
        if ($mimeTypes.ContainsKey($ext)) { $mime = $mimeTypes[$ext] }
        Send-Bytes 200 $mime ([System.IO.File]::ReadAllBytes($filePath))
    } else {
        $safe = [System.Net.WebUtility]::HtmlEncode($urlPath)
        $html = "<!DOCTYPE html><html><head><meta charset='utf-8'><title>404 - Not Found | LifeLink</title><link rel='stylesheet' href='/app/static/css/main.css'><link rel='stylesheet' href='/app/static/css/components.css'></head><body style='padding:4rem 1rem;text-align:center'><div style='max-width:520px;margin:0 auto'><h1 style='color:#C62828;margin-bottom:1rem'>Page not found</h1><p style='margin-bottom:2rem'>The page <code>$safe</code> does not exist.</p><a href='/' class='btn btn-primary'>Return to Home</a></div></body></html>"
        Send-Bytes 404 'text/html; charset=utf-8' ($Utf8NoBom.GetBytes($html))
    }
}

# ------------------------------------------------------------------------------
# Connection handling
# ------------------------------------------------------------------------------
function Handle-Client($client) {
    $script:Responded = $false
    try {
        $client.ReceiveTimeout = 3000
        $client.SendTimeout = 5000
        $stream = $client.GetStream()
        $script:Stream = $stream

        # Read header bytes until CRLFCRLF
        $ms = New-Object System.IO.MemoryStream
        $state = 0
        while ($state -lt 4) {
            $b = $stream.ReadByte()
            if ($b -lt 0) { break }
            $ms.WriteByte([byte]$b)
            if ($b -eq 13) { if ($state -eq 0 -or $state -eq 2) { $state++ } else { $state = 1 } }
            elseif ($b -eq 10) { if ($state -eq 1 -or $state -eq 3) { $state++ } else { $state = 0 } }
            else { $state = 0 }
            if ($ms.Length -gt 65536) { break }
        }
        if ($state -lt 4) { return }

        $lines = [System.Text.Encoding]::ASCII.GetString($ms.ToArray()) -split "`r`n"
        $parts = $lines[0].Split(' ')
        if ($parts.Length -lt 2) { return }
        $script:Method = $parts[0].ToUpper()
        $rawUrl = $parts[1]
        $qi = $rawUrl.IndexOf('?')
        $pathPart = $rawUrl; $qs = ''
        if ($qi -ge 0) { $pathPart = $rawUrl.Substring(0, $qi); $qs = $rawUrl.Substring($qi + 1) }
        $script:Path = [Uri]::UnescapeDataString($pathPart)
        if ($script:Path.Length -gt 1) { $script:Path = $script:Path.TrimEnd('/') }
        $script:Query = Parse-Pairs $qs

        $script:Headers = @{}
        for ($i = 1; $i -lt $lines.Length; $i++) {
            $line = $lines[$i]
            $c = $line.IndexOf(':')
            if ($c -gt 0) { $script:Headers[$line.Substring(0, $c).Trim().ToLower()] = $line.Substring($c + 1).Trim() }
        }

        $len = 0
        if ($script:Headers.ContainsKey('content-length')) { [void][int]::TryParse($script:Headers['content-length'], [ref]$len) }
        $script:BodyText = ''
        if ($len -gt 0 -and $len -lt 5MB) {
            $buf = New-Object byte[] $len
            $read = 0
            while ($read -lt $len) {
                $n = $stream.Read($buf, $read, $len - $read)
                if ($n -le 0) { break }
                $read += $n
            }
            $script:BodyText = $Utf8NoBom.GetString($buf, 0, $read)
        }

        # Session
        $script:Token = ''
        $script:Me = $null
        if ($script:Headers.ContainsKey('cookie')) {
            foreach ($pair in $script:Headers['cookie'].Split(';')) {
                $kv = $pair.Trim().Split([char[]]'=', 2)
                if ($kv[0] -eq 'lifelink_session' -and $kv.Length -gt 1) { $script:Token = $kv[1].Trim() }
            }
        }
        if ($script:Token) {
            foreach ($s in $global:DB.sessions) {
                if ($s.token -eq $script:Token) {
                    $u = Find-User $s.user_id
                    if ($u -and $u.is_active) { $script:Me = $u }
                    break
                }
            }
        }

        if (-not (Handle-Api)) { Handle-Static }
    } catch {
        $err = $_
        Write-Host "[X] $($script:Method) $($script:Path) failed: $($err.Exception.Message) (line $($err.InvocationInfo.ScriptLineNumber))" -ForegroundColor Red
        if (-not $script:Responded) {
            try { Send-Err 500 "Server error: $($err.Exception.Message)" } catch {}
        }
    } finally {
        try { $client.Close() } catch {}
    }
}

# ------------------------------------------------------------------------------
# Startup
# ------------------------------------------------------------------------------
Load-Db

$tcpListener = $null
foreach ($p in @($Port, 5000, 5050, 8080, 8888)) {
    try {
        $candidate = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $p)
        $candidate.Start()
        $tcpListener = $candidate
        $Port = $p
        break
    } catch { }
}
if (-not $tcpListener) {
    Write-Host "[X] Fatal: Unable to bind to any local port." -ForegroundColor Red
    exit 1
}

$prefix = "http://localhost:$Port/"
Write-Host ""
Write-Host "==================================================================" -ForegroundColor Red
Write-Host "  LifeLink - Smart Blood Donor & Emergency Availability Portal" -ForegroundColor White
Write-Host "==================================================================" -ForegroundColor Red
Write-Host "  Web Server is LIVE at: " -NoNewline -ForegroundColor Green
Write-Host $prefix -ForegroundColor Cyan
Write-Host "  Data file: $dataFile" -ForegroundColor Gray
Write-Host "  Users: $($global:DB.users.Count)   Requests: $($global:DB.requests.Count)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Press Ctrl+C to stop the server." -ForegroundColor Yellow
Write-Host "==================================================================" -ForegroundColor Red
Write-Host ""

if (-not $env:LIFELINK_NO_BROWSER) {
    try { Start-Process $prefix } catch {}
}

# Accept connections without letting idle (pre-connect) sockets block the server.
$pending = New-Object System.Collections.ArrayList
while ($true) {
    try {
        while ($tcpListener.Pending()) {
            [void]$pending.Add(@{ client = $tcpListener.AcceptTcpClient(); at = [DateTime]::UtcNow })
        }
        $handled = $false
        foreach ($pc in @($pending)) {
            $c = $pc.client
            $ready = $false
            try { $ready = ($c.Available -gt 0) } catch { $ready = $false }
            if ($ready) {
                $pending.Remove($pc)
                Handle-Client $c
                $handled = $true
            } elseif (([DateTime]::UtcNow - $pc.at).TotalSeconds -gt 15 -or -not $c.Connected) {
                $pending.Remove($pc)
                try { $c.Close() } catch {}
            }
        }
        if (-not $handled) { Start-Sleep -Milliseconds 5 }
    } catch {
        Write-Host "[!] Connection loop error: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}
