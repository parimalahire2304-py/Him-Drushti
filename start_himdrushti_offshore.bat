@echo off
setlocal
title Him-Drushti - Laptop-1 Offshore AI Server
color 0B
echo ============================================================
echo   HIM-DRUSHTI  -  LAPTOP-1  OFFSHORE / POLAR AI SERVER
echo ============================================================
echo.

REM -- Resolve project root from this .bat's own location.
REM    %%~fI normalises "..\" so no relative segments remain in paths. --
set PROJECT_ROOT=%~dp0
if not exist "%PROJECT_ROOT%scripts\communication\run_offshore_publish.py" for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI\"

REM -- [18] Duplicate-launch guard: if the publisher is already running,
REM        do NOT launch a second copy. PowerShell CIM (wmic removed on Win11).
REM        Explicit count-based exit: 0 = running, 1 = not running. --
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*run_offshore_publish*' }) { exit 0 } else { exit 1 }"
if %errorlevel% equ 0 (
    echo   [OK]  Offshore publisher already running.
    echo.
    echo   Skipping - no duplicate publisher started.
    echo   Close the existing window, then re-run, to restart it.
    echo.
    pause
    exit /b 0
)

echo [1/2] Checking Mosquitto broker...

REM -- [2] Already listening on port 1883? --
netstat -ano | findstr ":1883" | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK]  Mosquitto broker already running on port 1883.
    goto start_publisher
)

echo   [!]   Mosquitto not listening on 1883 - attempting to start it...

REM -- [4] Preferred: start the existing Mosquitto Windows service
REM        (same installation/configuration already on this PC). --
sc query Mosquitto >nul 2>&1
if %errorlevel% equ 0 (
    net start Mosquitto >nul 2>&1
    if %errorlevel% equ 0 goto wait_for_1883
    echo   [!]   Service start unsuccessful - trying direct launch instead.
)

REM -- [4/15] Fallback: launch the ONE existing broker binary with the
REM     existing config. Runs only when 1883 is free, so never a 2nd broker. --
if exist "C:\Program Files\mosquitto\mosquitto.exe" (
    echo   [!]   Launching existing broker: mosquitto.exe -c mosquitto.conf
    start "Him-Drushti Mosquitto (manual)" /min "C:\Program Files\mosquitto\mosquitto.exe" -c "C:\Program Files\mosquitto\mosquitto.conf"
    goto wait_for_1883
)

echo   [!!]  Mosquitto not found (no service, no mosquitto.exe).
echo         Start it manually, e.g.:
echo           net start Mosquitto
echo         OR
echo           "C:\Program Files\mosquitto\mosquitto.exe" -c "C:\Program Files\mosquitto\mosquitto.conf"
echo.
pause
exit /b 1

REM -- Wait up to ~12s for port 1883 to come up --
:wait_for_1883
set /a MOSQ_WAIT=0
:wait_for_1883_loop
netstat -ano | findstr ":1883" | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK]  Mosquitto broker is listening on 1883.
    goto start_publisher
)
set /a MOSQ_WAIT+=1
if %MOSQ_WAIT% geq 12 (
    echo   [!!]  Mosquitto did not start listening on 1883 within ~12s.
    echo         Check the config file and firewall rules, then start it manually.
    echo.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_for_1883_loop

:start_publisher
echo.
echo [2/2] Starting offshore MQTT publisher (Phase 3G -^> 4 -^> 5 -^> MQTT)...
echo       Publishes the 5 messages, then exits normally. No loop.
echo.

REM -- Set Python path so imports resolve --
set PYTHONPATH=%PROJECT_ROOT%scripts\communication;%PROJECT_ROOT%scripts\integration;%PROJECT_ROOT%scripts\risk;%PROJECT_ROOT%scripts\routing;%PROJECT_ROOT%scripts\ml\drifting_xgboost

REM -- [5] Run the EXISTING publisher once; it exits on its own. --
python "%PROJECT_ROOT%scripts\communication\run_offshore_publish.py"
set PUB_EXIT=%ERRORLEVEL%

echo.
echo ============================================================
if %PUB_EXIT% equ 0 (
    echo   SUCCESS - Publisher published all 5 messages and exited normally.
) else (
    echo   [!]  Publisher exited with code %PUB_EXIT%.
    echo        See the messages above, then fix and re-run.
)
echo ============================================================
pause