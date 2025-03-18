@echo off
color 02
:loop
echo ====================================
echo Server Checking Devices...
echo ====================================

echo Pinging ESP-1FA794 (172.20.10.3)...
ping -n 2 172.20.10.3 >nul && echo ESP-1FA794 is ONLINE || echo ESP-1FA794 is OFFLINE

echo Pinging esp32-A252E4 (172.20.10.4)...
ping -n 2 172.20.10.4 >nul && echo esp32-A252E4 is ONLINE || echo esp32-A252E4 is OFFLINE

echo Pinging LAPTOP-5RC76J9R (172.20.10.5)...
ping -n 2 172.20.10.5 >nul && echo Main Server is ONLINE || echo Main Server is OFFLINE

echo ====================================
echo Waiting for 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
