param(
    [string]$IpLocal
)

$ErrorActionPreference = "Stop"
$raizProyecto = Split-Path -Parent $PSScriptRoot
$python = Join-Path $raizProyecto "venv\Scripts\python.exe"

Set-Location $raizProyecto

if (-not (Test-Path -LiteralPath $python)) {
    throw "No se encontro el entorno virtual en $python"
}

if (-not $IpLocal) {
    $configuracion = Get-NetIPConfiguration |
        Where-Object { $_.IPv4DefaultGateway -and $_.IPv4Address } |
        Sort-Object { $_.NetAdapter.InterfaceMetric } |
        Select-Object -First 1

    if ($configuracion) {
        $IpLocal = @($configuracion.IPv4Address)[0].IPAddress
    }
}

if (-not $IpLocal) {
    throw "No se pudo detectar la IP local. Use -IpLocal 192.168.x.x"
}

$codigoImages = & curl.exe -sS -o NUL -w "%{http_code}" `
    "http://127.0.0.1:8001/api_images/saludo/"

if ($codigoImages -notin @("200", "401")) {
    throw (
        "SIWIH Images no responde por el tunel local (HTTP $codigoImages). " +
        "Inicie el servidor remoto y el tunel SSH antes de la demo."
    )
}

if (Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue) {
    throw "El puerto 8000 ya esta ocupado. Cierre el servidor anterior."
}

# Estas variables solo viven mientras la terminal de demostracion esta abierta.
$env:IMAGE_SERVER_URL = "http://127.0.0.1:8001"
$env:ALLOWED_HOSTS = "SIWIH,localhost,127.0.0.1,$IpLocal"
$env:EQUIPOS_QR_BASE_URL = "http://${IpLocal}:8000"

Write-Host ""
Write-Host "Demo de Equipos preparada" -ForegroundColor Green
Write-Host "Tablet o telefono: http://${IpLocal}:8000/" -ForegroundColor Cyan
Write-Host "La laptop y el dispositivo deben usar la misma red."
Write-Host "Mantenga esta terminal abierta durante la presentacion."
Write-Host ""

& $python manage.py check
if ($LASTEXITCODE -ne 0) {
    throw "Django no supero manage.py check"
}

& $python manage.py runserver 0.0.0.0:8000 --noreload
