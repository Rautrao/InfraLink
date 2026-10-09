$ErrorActionPreference = 'Stop'
$base = 'http://localhost:8000/api/v1'

$residentPhone = '9000000001'
Invoke-RestMethod -Method Post -Uri "$base/auth/otp/request" -ContentType 'application/json' -Body (@{ phone = $residentPhone } | ConvertTo-Json) | Out-Null
$residentLogin = Invoke-RestMethod -Method Post -Uri "$base/auth/otp/verify" -ContentType 'application/json' -Body (@{ phone = $residentPhone; otp = '123456' } | ConvertTo-Json)
$residentHeaders = @{ Authorization = "Bearer $($residentLogin.access_token)" }
$staffLogin = Invoke-RestMethod -Method Post -Uri "$base/auth/login" -ContentType 'application/json' -Body (@{ email = 'admin@demo.city'; password = 'demo1234' } | ConvertTo-Json)
$staffHeaders = @{ Authorization = "Bearer $($staffLogin.access_token)" }

$work = (Invoke-RestMethod -Uri "$base/works?page_size=1").items | Select-Object -First 1
if (-not $work) { throw 'No public work exists. Run the seed command first.' }
$feedback = Invoke-RestMethod -Method Post -Uri "$base/works/$($work.id)/feedback" -Headers $residentHeaders -ContentType 'application/x-www-form-urlencoded' -Body @{ kind = 'complaint'; text = 'The road work appears inactive; please confirm the current schedule.' }
Write-Host "Submitted $($feedback.ref_no) about $($work.ref_no)"

foreach ($step in @(@{ Days = 3; Level = 2; Officer = 'AE' }, @{ Days = 7; Level = 3; Officer = 'EE' }, @{ Days = 14; Level = 4; Officer = 'SE' })) {
    Invoke-RestMethod -Method Post -Uri "$base/dev/advance-time" -ContentType 'application/json' -Body (@{ days = $step.Days } | ConvertTo-Json) | Out-Null
    $tickets = (Invoke-RestMethod -Uri "$base/staff/feedback?awaiting=true&level=$($step.Level)" -Headers $staffHeaders).items
    $ticket = $tickets | Where-Object ref_no -eq $feedback.ref_no | Select-Object -First 1
    if (-not $ticket) { throw "Expected $($feedback.ref_no) in the $($step.Officer) inbox at level $($step.Level)." }
    Write-Host "$($step.Officer) inbox: $($ticket.ref_no), level $($ticket.current_level), age $([math]::Round($ticket.sla_age_days, 1)) days"
}
