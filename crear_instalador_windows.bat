@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   Ne-notoka HelioRegla 1.3.0 - Constructor del instalador
echo ============================================================
echo.

if not exist "app\main.py" goto :carpeta_incorrecta
if not exist "assets\icono_ne_notoka.ico" goto :carpeta_incorrecta

set "PYTHONUTF8=1"
set "VENV=.venv_instalador"
set "PY=%VENV%\Scripts\python.exe"

if not exist "%PY%" (
    echo [1/7] Creando entorno limpio de construccion...
    py -3.13 -m venv "%VENV%" 2>nul
    if errorlevel 1 py -3 -m venv "%VENV%"
    if errorlevel 1 goto :sin_python
) else (
    echo [1/7] Reutilizando entorno limpio de construccion.
)

echo [2/7] Instalando herramientas y dependencias...
"%PY%" -m pip install --upgrade pip
if errorlevel 1 goto :error
"%PY%" -m pip install --upgrade -r requirements-instalador.txt
if errorlevel 1 goto :error

echo [3/7] Reuniendo licencias de componentes de terceros...
"%PY%" preparar_licencias_terceros.py
if errorlevel 1 goto :error

echo [4/7] Ejecutando pruebas automaticas...
"%PY%" -m unittest discover -s pruebas -v
if errorlevel 1 goto :error

echo [5/7] Construyendo aplicacion para Windows...
"%PY%" -m PyInstaller --noconfirm --clean ^
    --distpath dist --workpath build_instalador ^
    Ne-notoka_HelioRegla.spec
if errorlevel 1 goto :error

if not exist "dist\Ne-notoka HelioRegla\Ne-notoka HelioRegla.exe" (
    echo ERROR: PyInstaller no genero el ejecutable esperado.
    goto :error
)

echo [6/7] Localizando Inno Setup...
set "ISCC="
for %%I in (iscc.exe) do set "ISCC=%%~$PATH:I"
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    echo Inno Setup no esta instalado. Se instalara con winget.
    winget install --id JRSoftware.InnoSetup -e -s winget -i ^
        --accept-package-agreements --accept-source-agreements
    if errorlevel 1 goto :sin_inno
    if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
    if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
)

if not defined ISCC goto :sin_inno

echo [7/7] Creando instalador final...
"%ISCC%" "instalador\Ne-notoka_HelioRegla.iss"
if errorlevel 1 goto :error

echo.
echo ============================================================
echo INSTALADOR CREADO CORRECTAMENTE
echo dist_instalador\Ne-notoka_HelioRegla_1.3.0_Setup.exe
echo ============================================================
start "" "dist_instalador"
pause
exit /b 0

:carpeta_incorrecta
echo ERROR: Ejecuta este archivo desde la carpeta principal de HelioRegla.
goto :fin_error

:sin_python
echo ERROR: No se encontro Python mediante el comando py.
echo Instala Python 3.13 y vuelve a ejecutar este archivo.
goto :fin_error

:sin_inno
echo ERROR: No se pudo localizar Inno Setup 6.
echo Instalalo con: winget install --id JRSoftware.InnoSetup -e -s winget -i
goto :fin_error

:error
echo ERROR: La construccion se detuvo. No se genero un instalador incompleto.

:fin_error
pause
exit /b 1
