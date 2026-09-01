$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $root 'llama_cpp\bin\srv.exe'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead((Join-Path $root 'llama_cpp\llama.zip'))
$entry = $zip.Entries | Where-Object { $_.Name -eq 'llama-server.exe' }
if (-not $entry) {
    Write-Output 'ERROR: llama-server.exe no encontrado en el zip'
    $zip.Dispose()
    exit 1
}
New-Item -ItemType Directory -Force -Path (Split-Path $src) | Out-Null
[System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $src, $true)
$zip.Dispose()
if (Test-Path -LiteralPath $src) {
    Write-Output ('OK: srv.exe recuperado (' + (Get-Item $src).Length + ' bytes)')
    exit 0
}
Write-Output 'ERROR: no se pudo extraer srv.exe'
exit 1
