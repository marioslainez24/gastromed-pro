# NeuroMed Pro - Instalador para Windows 11
# Lo ejecuta INSTALAR.bat. Puede volver a ejecutarse para ACTUALIZAR: conserva datos, claves y usuarios.

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "Instalador de NeuroMed Pro"

$Root      = "C:\NeuroMed"
$AppDir    = Join-Path $Root "programa"
$DataDir   = Join-Path $Root "datos"
$BackupDir = Join-Path $Root "respaldos"
$DemoDir   = Join-Path $Root "demostracion"
$Source    = Split-Path -Parent $PSScriptRoot
$Desktop   = [Environment]::GetFolderPath("Desktop")
$Startup   = [Environment]::GetFolderPath("Startup")

function Paso($n, $texto) { Write-Host ""; Write-Host "[$n/9] $texto" -ForegroundColor Cyan }
function Ok($texto)      { Write-Host "      OK  $texto" -ForegroundColor Green }
function Aviso($texto)   { Write-Host "      !!  $texto" -ForegroundColor Yellow }
function Falla($texto)   {
    Write-Host ""; Write-Host "ERROR: $texto" -ForegroundColor Red
    Write-Host "No se hicieron cambios en sus datos. Tome una foto de esta pantalla y compártala para revisarlo."
    Read-Host "Pulse Enter para cerrar"; exit 1
}
function SiNo($pregunta, $porDefecto = "S") {
    $r = Read-Host "$pregunta (S/N) [$porDefecto]"
    if ([string]::IsNullOrWhiteSpace($r)) { $r = $porDefecto }
    return $r.Trim().ToUpper().StartsWith("S")
}

Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "   Instalacion de NeuroMed Pro en esta PC (servidor privado)" -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "Programa:  $AppDir"
Write-Host "Datos:     $DataDir"
Write-Host "Respaldos: $BackupDir"

if (-not (Test-Path (Join-Path $Source "servidor.py"))) { Falla "No se encuentra el programa. Descomprima el ZIP completo y ejecute INSTALAR.bat desde esa carpeta." }
if ($Source.TrimEnd('\') -ieq $AppDir) { Falla "Ejecute INSTALAR.bat desde la carpeta descomprimida, no desde $AppDir." }

# ---------------------------------------------------------------- 1. Python
Paso 1 "Buscando Python 3.13"
function Buscar-Python {
    $candidatos = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
        "C:\Program Files\Python313\python.exe"
    )
    foreach ($c in $candidatos) { if (Test-Path $c) { return $c } }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        $p = & py.exe -3.13 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $p) { return $p.Trim() }
    }
    return $null
}
$Python = Buscar-Python
if (-not $Python) {
    Write-Host "      Python no esta instalado. Se instalara Python 3.13 (oficial, python.org) con winget."
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        Falla "No se encontro 'winget'. Abra Microsoft Store, actualice 'Instalador de aplicacion' y ejecute de nuevo INSTALAR.bat."
    }
    winget install --id Python.Python.3.13 -e --scope user --silent --accept-package-agreements --accept-source-agreements
    $Python = Buscar-Python
    if (-not $Python) { Falla "No se pudo instalar Python automaticamente. Instale Python 3.13 desde https://www.python.org/downloads/windows/ y ejecute de nuevo INSTALAR.bat." }
}
Ok "Python: $Python"

# ---------------------------------------------------------------- 2. Respaldo previo (si es actualizacion)
Paso 2 "Revisando instalacion anterior"
$EnvFile = Join-Path $DataDir "neuromed.env"
$VenvPy  = Join-Path $AppDir ".venv\Scripts\python.exe"
if ((Test-Path $EnvFile) -and (Test-Path $VenvPy)) {
    Write-Host "      Instalacion existente: se hara un respaldo antes de actualizar."
    $env:GASTROMED_ENV_FILE = $EnvFile
    Push-Location $AppDir
    & $VenvPy "scripts\respaldo.py" "automatico"
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { Falla "El respaldo previo a la actualizacion fallo. No se actualizo nada." }
    Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$AppDir*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Ok "Respaldo previo creado"
} else { Ok "Instalacion nueva" }

# ---------------------------------------------------------------- 3. Copiar programa
Paso 3 "Copiando el programa"
New-Item -ItemType Directory -Force -Path $AppDir, $DataDir, $BackupDir | Out-Null
robocopy $Source $AppDir /MIR /XD ".venv" "instance" "respaldos" ".git" "__pycache__" ".pytest_cache" /XF ".env" /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Falla "No se pudieron copiar los archivos del programa (robocopy codigo $LASTEXITCODE)." }
Ok "Programa copiado en $AppDir"

# ---------------------------------------------------------------- 4. Dependencias
Paso 4 "Instalando componentes (requiere internet; puede tardar unos minutos)"
if (-not (Test-Path $VenvPy)) { & $Python -m venv (Join-Path $AppDir ".venv"); if ($LASTEXITCODE -ne 0) { Falla "No se pudo crear el entorno de Python." } }
& $VenvPy -m pip install --upgrade pip --quiet --disable-pip-version-check
$TieneTests = Test-Path (Join-Path $AppDir "tests")
$Req = if ($TieneTests) { "requirements-dev.txt" } else { "requirements.txt" }   # paquete sin extras: solo lo necesario
& $VenvPy -m pip install -r (Join-Path $AppDir $Req) --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Falla "No se pudieron instalar los componentes. Revise la conexion a internet y ejecute de nuevo INSTALAR.bat." }
Ok "Componentes instalados"

# ---------------------------------------------------------------- 5. Configuracion, claves y cuenta
Paso 5 "Configuracion inicial, claves de cifrado y su cuenta"
Push-Location $AppDir
& $VenvPy "windows\configurar.py" --datos $DataDir --respaldos $BackupDir --escritorio $Desktop
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { Falla "La configuracion inicial no termino." }

# Solo este usuario de Windows, el sistema y los administradores pueden leer los datos.
$yo = "$env:USERDOMAIN\$env:USERNAME"
icacls $DataDir /inheritance:r /grant:r "${yo}:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" /T /Q | Out-Null
icacls $BackupDir /inheritance:r /grant:r "${yo}:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" /T /Q | Out-Null
Ok "Permisos de carpeta restringidos a $yo"

# ---------------------------------------------------------------- 6. Comprobacion
Paso 6 "Comprobando el programa"
Push-Location $AppDir
if ($TieneTests) {
    Remove-Item Env:GASTROMED_ENV_FILE -ErrorAction SilentlyContinue   # las pruebas usan datos temporales, nunca los reales
    & $VenvPy -m pytest -q -p no:cacheprovider tests
} else {
    # Paquete sin extras: comprobacion rapida de que el programa arranca con su configuracion real
    $env:GASTROMED_ENV_FILE = $EnvFile
    & $VenvPy -c "from app import create_app; a = create_app(); print('      Programa listo, modo', a.config['GM'].ENV)"
}
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { Aviso "La comprobacion fallo en esta PC. El sistema puede tener problemas: comparta una foto de esta pantalla." }
else { Ok "Comprobacion correcta" }

# ---------------------------------------------------------------- 7. Accesos directos
Paso 7 "Creando accesos directos"
$sh = New-Object -ComObject WScript.Shell
function Acceso($nombre, $bat, $carpeta, $icono) {
    $lnk = $sh.CreateShortcut((Join-Path $carpeta "$nombre.lnk"))
    $lnk.TargetPath = Join-Path $AppDir "windows\$bat"
    $lnk.WorkingDirectory = $AppDir
    $lnk.IconLocation = "$env:SystemRoot\System32\imageres.dll,$icono"
    if ($bat -eq "iniciar.bat") { $lnk.WindowStyle = 7 }   # minimizada
    $lnk.Save()
}
Acceso "NeuroMed Pro" "iniciar.bat" $Desktop 21
Acceso "NeuroMed Pro - Verificar estado" "verificar.bat" $Desktop 76
Acceso "NeuroMed Pro - DEMOSTRACION" "demo.bat" $Desktop 22
Ok "Accesos directos en el escritorio"
if (SiNo "      Iniciar NeuroMed Pro automaticamente al encender esta PC?" "S") {
    Acceso "NeuroMed Pro" "iniciar-sin-navegador.bat" $Startup 21
    Ok "Inicio automatico activado"
}

# ---------------------------------------------------------------- 8. Respaldo diario
Paso 8 "Programando respaldo diario (21:00; si la PC esta apagada, se hace al encenderla)"
$accion   = New-ScheduledTaskAction -Execute (Join-Path $AppDir "windows\respaldo.bat") -WorkingDirectory $AppDir
$trigger  = New-ScheduledTaskTrigger -Daily -At "21:00"
$opciones = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "NeuroMed Pro - Respaldo diario" -Action $accion -Trigger $trigger -Settings $opciones -Description "Respaldo cifrado y verificado de NeuroMed Pro" -Force | Out-Null
Ok "Tarea programada creada"
$env:GASTROMED_ENV_FILE = $EnvFile
Push-Location $AppDir
& $VenvPy "scripts\respaldo.py" "automatico"
Pop-Location
if ($LASTEXITCODE -eq 0) { Ok "Primer respaldo creado y verificado" } else { Aviso "El primer respaldo fallo; revise con 'NeuroMed Pro - Verificar estado'." }

# ---------------------------------------------------------------- 9. Acceso desde el celular
Paso 9 "Acceso desde el celular (mismo Wi-Fi)"
Write-Host "      Para usarlo desde el celular, Windows debe permitir conexiones al puerto 8100 en redes PRIVADAS."
Write-Host "      Esto requiere permiso de administrador (aparecera una ventana de confirmacion)."
if (SiNo "      Permitir acceso desde el celular?" "S") {
    $cmd = "Remove-NetFirewallRule -DisplayName 'NeuroMed Pro' -ErrorAction SilentlyContinue; " +
           "New-NetFirewallRule -DisplayName 'NeuroMed Pro' -Direction Inbound -Protocol TCP -LocalPort 8100 -Profile Private -Action Allow | Out-Null"
    try {
        Start-Process powershell.exe -Verb RunAs -Wait -ArgumentList "-NoProfile -Command $cmd"
        Ok "Regla de firewall creada (solo redes privadas)"
        $perfil = (Get-NetConnectionProfile | Select-Object -First 1).NetworkCategory
        if ($perfil -ne "Private") { Aviso "Su red esta marcada como '$perfil'. En Configuracion > Red e Internet > Wi-Fi > (su red), elija 'Red privada'." }
    } catch { Aviso "No se concedio el permiso. Puede repetir la instalacion mas tarde para habilitarlo." }
}

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Green
Write-Host "   Instalacion terminada" -ForegroundColor Green
Write-Host "==============================================================" -ForegroundColor Green
Write-Host " - Para usar el sistema: doble clic en 'NeuroMed Pro' (escritorio)."
Write-Host " - Para practicar con pacientes ficticios: 'NeuroMed Pro - DEMOSTRACION'."
Write-Host " - IMPORTANTE: copie a una USB el archivo de CLAVES que quedo en el escritorio y luego borrelo."
Write-Host ""
if (SiNo "Abrir NeuroMed Pro ahora?" "S") { Start-Process (Join-Path $AppDir "windows\iniciar.bat") -WindowStyle Minimized }
Read-Host "Pulse Enter para cerrar el instalador"
