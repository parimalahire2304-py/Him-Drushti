# HIM-DRUSHTI Phase 7A — Laptop1 (OFFSHORE AI SERVER) MQTT broker enablement
# ========================================================================
# Purpose: enable Laptop2 (SHIP/ONBOARD DSS) to reach the Mosquitto broker
#          over the LAN. Two changes, both explicitly approved by the user:
#           1. Bind Mosquitto to all interfaces (not only loopback)
#           2. Allow inbound TCP 1883 on the local subnet through the firewall
# Requires: run in an ELEVATED PowerShell (Run as administrator).
# Idempotent: safe to re-run; existing lines/rules are not duplicated.
# ========================================================================
$ErrorActionPreference = 'Stop'

$conf = 'C:\Program Files\mosquitto\mosquitto.conf'
$marker = '# === HIM-DRUSHTI Phase 7A: bind to all interfaces (LAN two-laptop) ==='

# --- 1. Ensure mosquitto.conf binds to all interfaces -----------------------
if (Test-Path $conf) {
    if (Select-String -Path $conf -Pattern ([regex]::Escape($marker)) -Quiet) {
        Write-Host '[config] already bound to all interfaces - no change.'
    } else {
        $block = @"
$marker
listener 1883
bind_address 0.0.0.0
"@
        Add-Content -Path $conf -Value $block -Encoding ascii
        Write-Host '[config] appended listener 1883 / bind_address 0.0.0.0'
    }
} else {
    Write-Host "[config] NOT FOUND: $conf - stopping." -ForegroundColor Red
    exit 1
}

# --- 2. Restart Mosquitto to apply the config --------------------------------
Write-Host '[service] restarting Mosquitto...'
Restart-Service -Name 'Mosquitto' -Force
Start-Sleep -Seconds 2
$svc = Get-Service -Name 'Mosquitto'
Write-Host "[service] Mosquitto state: $($svc.Status)"

# --- 3. Firewall: allow inbound TCP 1883 on the local subnet ----------------
$ruleName = 'HIM-DRUSHTI MQTT 1883'
if (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue) {
    Write-Host '[firewall] rule already exists - no change.'
} else {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound `
        -Protocol TCP -LocalPort 1883 `
        -Action Allow -Profile Public -RemoteAddress LocalSubnet `
        | Out-Null
    Write-Host '[firewall] added inbound TCP 1883 (LocalSubnet, Public profile)'
}

Write-Host ''
Write-Host '=== Verify with (in elevated PS): ==='
Write-Host '  netstat -ano | findstr :1883'
Write-Host '  Get-NetFirewallRule -DisplayName "HIM-DRUSHTI MQTT 1883"'
Write-Host 'Done.'
