# Construcción del instalador de Windows

## Resultado

El proceso crea:

`dist_instalador\Ne-notoka_HelioRegla_1.3.0_Setup.exe`

Es un instalador bilingüe para Windows 10 y Windows 11 de 64 bits. Instala el
programa por usuario, no necesita permisos de administrador, crea entradas en
el menú Inicio, ofrece un acceso directo en el escritorio e incluye
desinstalador.

## Construcción automática

1. Abre la carpeta principal de HelioRegla.
2. Haz doble clic en `crear_instalador_windows.bat`.
3. El constructor crea un entorno aislado, instala las dependencias, copia los
   avisos de terceros, ejecuta las pruebas, genera la aplicación con PyInstaller
   y finalmente compila el instalador con Inno Setup.
4. Si Inno Setup 6 no está presente, el mismo proceso intenta instalarlo con
   `winget`.

PyInstaller no es un compilador cruzado: el instalador de Windows debe
construirse desde Windows. El usuario final no necesita Python, Visual Studio
Code ni las dependencias de desarrollo.

## Archivos de construcción

- `requirements-instalador.txt`: dependencias aisladas.
- `preparar_licencias_terceros.py`: recopila licencias de las versiones
  realmente empaquetadas.
- `Ne-notoka_HelioRegla.spec`: configuración de PyInstaller.
- `instalador/Ne-notoka_HelioRegla.iss`: configuración de Inno Setup.
- `instalador/version_info.txt`: metadatos del ejecutable.

## Firma digital

La versión 1.3.0 puede distribuirse sin firma, aunque Windows SmartScreen
podría mostrar una advertencia por ser una aplicación nueva. Una firma de
código Authenticode podrá incorporarse posteriormente sin modificar el
programa.
