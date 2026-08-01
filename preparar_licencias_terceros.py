import importlib.metadata
import re
import shutil
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parent
DESTINO = BASE / "licencias_terceros"
PAQUETES = (
    "PySide6",
    "PySide6_Addons",
    "PySide6_Essentials",
    "shiboken6",
    "numpy",
    "Pillow",
    "opencv-python-headless",
    "pyinstaller",
    "pyinstaller-hooks-contrib",
)
PALABRAS = ("license", "licence", "copying", "notice", "authors")


def nombre_seguro(texto):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", texto).strip("_")


def archivos_licencia(distribucion):
    for archivo in distribucion.files or ():
        nombre = Path(str(archivo)).name.lower()
        if any(palabra in nombre for palabra in PALABRAS):
            ruta = Path(distribucion.locate_file(archivo))
            if ruta.is_file():
                yield ruta


def copiar_licencias():
    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    DESTINO.mkdir(parents=True)
    resumen = [
        "Licencias copiadas durante la construcción de HelioRegla 1.0.0",
        "",
    ]

    for paquete in PAQUETES:
        try:
            distribucion = importlib.metadata.distribution(paquete)
        except importlib.metadata.PackageNotFoundError:
            resumen.append(f"{paquete}: NO INSTALADO")
            continue

        version = distribucion.version
        resumen.append(f"{paquete}: {version}")
        vistos = set()
        for indice, origen in enumerate(archivos_licencia(distribucion), 1):
            contenido = origen.read_bytes()
            if contenido in vistos:
                continue
            vistos.add(contenido)
            nombre = (
                f"{nombre_seguro(paquete)}_{indice:02d}_"
                f"{nombre_seguro(origen.name)}"
            )
            (DESTINO / nombre).write_bytes(contenido)

    for candidato in (
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
    ):
        if candidato.is_file():
            shutil.copy2(candidato, DESTINO / "Python_LICENSE.txt")
            break

    (DESTINO / "VERSIONES.txt").write_text(
        "\n".join(resumen) + "\n",
        encoding="utf-8",
    )
    print(f"Avisos preparados en: {DESTINO}")


if __name__ == "__main__":
    copiar_licencias()
