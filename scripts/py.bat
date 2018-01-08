cd %~dp0\..
:top
c:\Python26\python.exe -m r0c.__main__ 23 531
ping -n 2 -w 1 127.0.0.1 >NUL
python -m r0c 23 531
ping -n 2 -w 1 127.0.0.1 >NUL
goto top

