param(
    [string]$Servidor = $env:SIWI_IMAGES_SSH_HOST,
    [string]$Usuario = "sid280"
)

$ErrorActionPreference = "Stop"

if (-not $Servidor) {
    throw (
        "Indique el servidor, por ejemplo: " +
        ".\scripts\iniciar_tunel_imagenes.ps1 -Servidor 192.168.88.199"
    )
}

if (Get-NetTCPConnection -State Listen -LocalPort 8001 -ErrorAction SilentlyContinue) {
    throw "El puerto 8001 ya esta ocupado por otro tunel o proceso."
}

Write-Host "Abriendo tunel hacia $Usuario@$Servidor" -ForegroundColor Cyan
Write-Host "Mantenga esta terminal abierta durante la presentacion."

& ssh `
    -N `
    -o ExitOnForwardFailure=yes `
    -o ServerAliveInterval=30 `
    -o ServerAliveCountMax=3 `
    -L 8001:127.0.0.1:8001 `
    "$Usuario@$Servidor"
