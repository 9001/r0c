@echo off

rem  launches r0c and the webserver in two different windows;
rem  will listen on port 23 (telnet), 531 (netcat), and
rem  http://127.0.0.1:8023/

telnet /? >nul
if %errorlevel% neq -1 (
  echo(
  echo error: you must enable telnet-client in windows settings
  pause
  exit /b
)

start python r0c.py ^
  --ara

set ttyd=ttyd.exe
if exist ttyd.win10.exe set ttyd=ttyd.win10.exe
if exist ttyd.win32.exe set ttyd=ttyd.win32.exe

%ttyd% ^
  -W -p 8023 ^
  -i 0.0.0.0 ^
  -t disableReconnect=true ^
  -t rendererType=dom ^
  -t titleFixed=r0c ^
  -t enableSixel=false ^
  -t enableTrzsz=false ^
  -t enableZmodem=false ^
  -t disableResizeOverlay=true ^
  telnet 127.0.0.1 23

pause
