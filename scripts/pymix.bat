cd ..
:top
c:\Python26\python.exe r0c.py 23 531
ping -n 2 -w 1 127.0.0.1 >NUL
python r0c.py 23 531
ping -n 2 -w 1 127.0.0.1 >NUL
goto top
