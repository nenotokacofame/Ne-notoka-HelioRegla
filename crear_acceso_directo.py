import os
import subprocess
from pathlib import Path


def crear_acceso_directo():
    if os.name != "nt":
        print(
            "El acceso directo solamente se crea en Windows."
        )
        return None

    base = Path(__file__).resolve().parent
    pythonw = base / ".venv" / "Scripts" / "pythonw.exe"
    aplicacion = base / "app" / "main.py"
    icono = base / "assets" / "icono_ne_notoka.ico"

    faltantes = [
        str(ruta)
        for ruta in (pythonw, aplicacion, icono)
        if not ruta.is_file()
    ]

    if faltantes:
        raise FileNotFoundError(
            "No se pudo crear el acceso directo. Faltan: "
            + ", ".join(faltantes)
        )

    entorno = os.environ.copy()
    entorno["HELIO_BASE"] = str(base)
    entorno["HELIO_PYTHONW"] = str(pythonw)
    entorno["HELIO_MAIN"] = str(aplicacion)
    entorno["HELIO_ICON"] = str(icono)
    guion = (
        "$desktop=[Environment]::GetFolderPath('Desktop');"
        "$shell=New-Object -ComObject WScript.Shell;"
        "$ruta=Join-Path $desktop "
        "'Ne-notoka HelioRegla.lnk';"
        "$acceso=$shell.CreateShortcut($ruta);"
        "$acceso.TargetPath=$env:HELIO_PYTHONW;"
        "$acceso.Arguments='\"'+$env:HELIO_MAIN+'\"';"
        "$acceso.WorkingDirectory=$env:HELIO_BASE;"
        "$acceso.IconLocation=$env:HELIO_ICON+',0';"
        "$acceso.Description='Ne-notoka HelioRegla';"
        "$acceso.Save();"
        "Write-Output $ruta"
    )
    resultado = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            guion,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=entorno,
    )
    ruta = resultado.stdout.strip()
    print(f"Acceso directo creado: {ruta}")
    return ruta


if __name__ == "__main__":
    crear_acceso_directo()
