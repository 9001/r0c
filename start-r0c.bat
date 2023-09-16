python -m r0c.__main__ %* || pause

@REM additional arguments can be given to this batch file, for example
@REM   -pw goodpassword
@REM   -tpt 2424   (enable tls telnet on port 2424)
@REM   -tpn 1515   (enable tls netcat on port 1515)
@REM   --old-tls   (allow old/buggy software to connect (centos6, powershell))
