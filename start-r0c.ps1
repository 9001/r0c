try {
    Invoke-Expression "python -m r0c.__main__ $args"
}
catch {
    Write-Host -NoNewLine "press ENTER to terminate "
    $null = $Host.UI.ReadLine()
    exit 1
}

if ($LASTEXITCODE -ne 0) {
    Write-Host -NoNewLine "press ENTER to terminate "
    $null = $Host.UI.ReadLine()
    exit 1
}

# additional arguments can be given to this batch file, for example
#   -pw goodpassword
#   -tpt 2424   (enable tls telnet on port 2424)
#   -tpn 1515   (enable tls netcat on port 1515)
#   --old-tls   (allow old/buggy software to connect (centos6, powershell))
