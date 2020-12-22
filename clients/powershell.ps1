# usage:
#   powershell .\powershell.ps1 127.0.0.1:531
#   (or just doubleclick this script in win10)
#
# fix permissions on win7 by running this in a powershell console:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Unrestricted

#######################################################################

function Seppuku {
    Write-Host ""
    Write-Host -NoNewLine "press ENTER to terminate "
    $null = $Host.UI.ReadLine()
    exit 1
}

#######################################################################

function Test-IsISE {
    try {    
        return $null -ne $psISE;
    }
    catch {
        return $false;
    }
}

if (Test-IsISE) {
    Write-Host "cannot run inside Powershell ISE,"
    Write-Host "press Ctrl-Shift-P and try there"
    Seppuku
}

#######################################################################

try {
    $null = [console]::KeyAvailable
}
catch {
    Write-Host "cannot access the keyboard;"
    Write-Host "something's wrong with your shell"
    Seppuku
}

#######################################################################

$ver = [Environment]::OSVersion.Version
$ver10 = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").ReleaseId
Write-Host "Windows $ver ($ver10)"

$v1 = new-object 'Version' 10,0,10586  # OK, 1511
$v2 = new-object 'Version' 10,0,15063  # OK, 1703
$scroll_ng = $ver -gt $v1 -and $ver -lt $v2
# LTSB 2015 OK (<1511), 2016 NG (~1607), LTSC 2019 OK (1809)

#######################################################################

$r0chost = if ($args.count -ge 1) {$args[0]} else {""}
$r0cport = if ($args.count -ge 2) {$args[1]} else {""}
$arr = $r0chost.Split(":")
if ($arr.count -eq 2) {
    $r0chost = $arr[0];
    $r0cport = $arr[1];
}
if ([string]::IsNullOrEmpty($r0chost)) {
    $r0chost = Read-Host "Input r0c address, default 127.0.0.1 if blank"
    if ([string]::IsNullOrEmpty($r0chost)) {
        $r0chost = "127.0.0.1"
    }
}
if ([string]::IsNullOrEmpty($r0cport)) {
    $r0cport = Read-Host "Input r0c port, default 531 if blank"
    if ([string]::IsNullOrEmpty($r0cport)) {
        $r0cport = "531"
    }
}
$r0cport = [int]$r0cport

$socket = New-Object System.Net.Sockets.TcpClient
$socket.connect($r0chost, $r0cport)
$stream = $socket.GetStream()
$buf = New-Object byte[] 4096
$messages_lost = 0

# TODO: figure out how this works
[console]::TreatControlCAsInput = $true

while ($socket.Connected) {
    while ($stream.DataAvailable) {
        $n_read = $stream.Read($buf, 0, $buf.Length)
        $text = [System.Text.Encoding]::UTF8.GetString($buf, 0, $n_read)
        Write-Host $text -NoNewLine

        if ($scroll_ng -and $text -match '\x48\x0a\x0a\x1b\x5b\x4b') {
            $messages_lost += 1
        }
    }
    if ($messages_lost -gt 0) {
        # bad powershell ver, do full redraw
        $stream.Write([Byte[]] (0x12), 0, 1)
        $stream.Flush()
        $messages_lost = 0
    }
    while ([console]::KeyAvailable) {
    	$key = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        $kc = $key.VirtualKeyCode
        if ($kc -eq 3) {
            # TODO: doesn't work since TreatControlCAsInput does nothing
            Write-Host "`n`n*** shutting down`n`n"
            $socket.Close()
            $socket.Dispose()
            Start-Sleep -Milliseconds 200
            exit 0
        }
        $text = $key.Character
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($text)
        if ($text -split "" -contains "`n" -or
            $text -split "" -contains "`r") {
            $bytes = [Byte[]] (0x0a)
        }
        if ($kc -eq 37) { $bytes = [Byte[]] (0x1b,0x5b,0x44) }  # L
        if ($kc -eq 39) { $bytes = [Byte[]] (0x1b,0x5b,0x43) }  # R
        if ($kc -eq 38) { $bytes = [Byte[]] (0x1b,0x5b,0x41) }  # U
        if ($kc -eq 40) { $bytes = [Byte[]] (0x1b,0x5b,0x42) }  # D
        if ($kc -eq 36) { $bytes = [Byte[]] (0x1b,0x5b,0x31,0x7e) }  # Home
        if ($kc -eq 35) { $bytes = [Byte[]] (0x1b,0x5b,0x34,0x7e) }  # End
        if ($kc -eq 33) { $bytes = [Byte[]] (0x1b,0x5b,0x35,0x7e) }  # PgUp
        if ($kc -eq 34) { $bytes = [Byte[]] (0x1b,0x5b,0x36,0x7e) }  # PgDn
        if ($scroll_ng -and ($kc -eq 33 -or $kc -eq 34)) {
            $bytes += [Byte] 0x12
        }
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush()
        # 0x12 is ^R meaning we redraw the TUI on every scroll event
        # for powershell versions with busted scrolling
    }
    Start-Sleep -Milliseconds 10
}
