if ($args.count -ne 2) {
    Write-Host "Need argument 1:  Host IP or Hostname"
    Write-Host "Need argument 2:  Host Port"
    exit 1
}

$socket = New-Object System.Net.Sockets.TcpClient
$socket.connect($args[0], [int]$args[1])
$stream = $socket.GetStream()
$buf = New-Object byte[] 4096

while ($socket.Connected) {
    while ($stream.DataAvailable) {
        $n_read = $stream.Read($buf, 0, $buf.Length)
        $text = [System.Text.Encoding]::UTF8.GetString($buf, 0, $n_read)
        Write-Host $text -NoNewLine
    }
    while ([console]::KeyAvailable) {
    	$key = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        $text = $key.Character
        $kc = $key.VirtualKeyCode
    	$bytes = [System.Text.Encoding]::UTF8.GetBytes($text)
        if ($text -split "" -contains "`n" -or
            $text -split "" -contains "`r") {
            $bytes = [Byte[]] (0x0a,0x12)
        }
        if ($kc -eq 37) { $bytes = [Byte[]] (0x1b,0x5b,0x44) }  # L
        if ($kc -eq 39) { $bytes = [Byte[]] (0x1b,0x5b,0x43) }  # R
        if ($kc -eq 38) { $bytes = [Byte[]] (0x1b,0x5b,0x41) }  # U
        if ($kc -eq 40) { $bytes = [Byte[]] (0x1b,0x5b,0x42) }  # D
        if ($kc -eq 36) { $bytes = [Byte[]] (0x1b,0x5b,0x31,0x7e) }  # Home
        if ($kc -eq 35) { $bytes = [Byte[]] (0x1b,0x5b,0x34,0x7e) }  # End
        if ($kc -eq 33) { $bytes = [Byte[]] (0x1b,0x5b,0x35,0x7e,0x12) }  # PgUp
        if ($kc -eq 34) { $bytes = [Byte[]] (0x1b,0x5b,0x36,0x7e,0x12) }  # PgDn
        $stream.Write($bytes, 0, $bytes.Length)
    	$stream.Flush()
        # TODO:
        #   0x12 is ^R meaning we redraw the TUI a whole lot
        #   because each and every time you run this script
        #   scrolling behaves vastly differently
    }
    Start-Sleep -Milliseconds 10
}
