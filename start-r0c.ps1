try {
    Invoke-Expression "python -m r0c.__main__ 23 531 $args"
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

# if an argument is provided to this ps1 file,
# it will be used as the admin password.
#
# "r0c.__main__" is required by python 2.6;
# all other python versions are happy with:
#   python -m r0c 23 531
