import json
import os
from pathlib import Path
from i18n import tr


VERSION_FORMATO = 1


class ErrorProyecto(ValueError):
    pass


def guardar_proyecto(ruta, datos):
    ruta = Path(ruta)
    contenido = dict(datos)
    contenido["formato_helio"] = VERSION_FORMATO
    ruta.write_text(
        json.dumps(
            contenido,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def leer_proyecto(ruta):
    ruta = Path(ruta)

    try:
        datos = json.loads(
            ruta.read_text(encoding="utf-8-sig")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ErrorProyecto(
            tr("project_invalid_file")
        ) from error

    if not isinstance(datos, dict):
        raise ErrorProyecto(
            tr("project_invalid_structure")
        )

    if datos.get("formato_helio") != VERSION_FORMATO:
        raise ErrorProyecto(
            tr("project_version_incompatible")
        )

    if not isinstance(datos.get("imagen"), dict):
        raise ErrorProyecto(
            tr("project_missing_image")
        )

    return datos


def referencias_imagen(ruta_proyecto, ruta_imagen):
    ruta_proyecto = Path(ruta_proyecto).resolve()
    ruta_imagen = Path(ruta_imagen).resolve()

    try:
        relativa = os.path.relpath(
            ruta_imagen,
            ruta_proyecto.parent,
        )
    except ValueError:
        relativa = ruta_imagen.name

    return {
        "absoluta": str(ruta_imagen),
        "relativa": relativa,
    }


def resolver_imagen(ruta_proyecto, referencia):
    ruta_proyecto = Path(ruta_proyecto).resolve()
    relativa = referencia.get("relativa")
    absoluta = referencia.get("absoluta")
    candidatas = []

    if relativa:
        candidatas.append(
            (ruta_proyecto.parent / relativa).resolve()
        )

    if absoluta:
        candidatas.append(Path(absoluta))

    for candidata in candidatas:
        if candidata.is_file():
            return candidata

    return None
