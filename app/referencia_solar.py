from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from catalogo_regiones import (
    coordenadas_catalogo_normalizadas,
    coordenadas_normalizadas,
    tamano_region_en_imagen,
)
from i18n import tr


HELIOVIEWER_CAPTURA = "https://api.helioviewer.org/v2/takeScreenshot/"
AGENTE = "Ne-notoka-HelioRegla/1.0.0"
TAMANO_REFERENCIA = 1024
ESCALA_REFERENCIA = 2.0


@dataclass(frozen=True)
class FuenteReferencia:
    identificador: int
    clave: str
    nombre: str


FUENTES_REFERENCIA = (
    FuenteReferencia(18, "hmi_continuum", "SDO/HMI continuum"),
    FuenteReferencia(94, "gong_halpha", "GONG H-alpha"),
    FuenteReferencia(
        16,
        "aia_1700",
        "SDO/AIA 1700 Å (aproximación a CaK)",
    ),
)
FUENTES_POR_CLAVE = {
    fuente.clave: fuente for fuente in FUENTES_REFERENCIA
}


@dataclass
class ReferenciaSolar:
    ruta: Path
    fuente: FuenteReferencia
    instante: datetime


@dataclass
class ResultadoRegistro:
    rotacion: float
    espejo_horizontal: bool
    espejo_vertical: bool
    puntuacion: float
    confianza: str
    referencia: ReferenciaSolar
    evidencia: int = 0
    separacion: float = 0.0


class ErrorReferenciaSolar(RuntimeError):
    pass


def _carpeta_cache():
    carpeta = (
        Path.home()
        / ".nenotoka_helioregla"
        / "cache"
        / "referencias_solares"
    )
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _nombre_cache(instante, fuente):
    instante = instante.astimezone(timezone.utc)
    bloque_minutos = (instante.minute // 10) * 10
    instante = instante.replace(
        minute=bloque_minutos,
        second=0,
        microsecond=0,
    )
    identidad = (
        f"{instante.isoformat()}-{fuente.identificador}-"
        f"{ESCALA_REFERENCIA}-{TAMANO_REFERENCIA}"
    )
    huella = hashlib.sha1(identidad.encode("utf-8")).hexdigest()[:12]
    return f"{instante:%Y%m%d_%H%M}_{fuente.clave}_{huella}.png"


def descargar_referencia(instante, fuente, espera=25):
    instante = instante.astimezone(timezone.utc)
    destino = _carpeta_cache() / _nombre_cache(instante, fuente)
    if destino.exists():
        try:
            with Image.open(destino) as imagen:
                imagen.verify()
            return ReferenciaSolar(destino, fuente, instante)
        except (OSError, SyntaxError):
            destino.unlink(missing_ok=True)

    parametros = urlencode(
        {
            "date": instante.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "imageScale": ESCALA_REFERENCIA,
            "layers": f"[{fuente.identificador},1,100]",
            "x0": 0,
            "y0": 0,
            "width": TAMANO_REFERENCIA,
            "height": TAMANO_REFERENCIA,
            "display": "true",
            "watermark": "false",
        }
    )
    solicitud = Request(
        f"{HELIOVIEWER_CAPTURA}?{parametros}",
        headers={
            "User-Agent": AGENTE,
            "Accept": "image/png,image/jpeg,*/*",
        },
    )
    try:
        with urlopen(solicitud, timeout=espera) as respuesta:
            contenido = respuesta.read()
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise ErrorReferenciaSolar(
            f"No se pudo descargar {fuente.nombre}: {error}"
        ) from error

    temporal = destino.with_suffix(".tmp")
    try:
        temporal.write_bytes(contenido)
        with Image.open(temporal) as imagen:
            imagen.load()
            imagen.convert("RGB").save(destino, "PNG")
    except (OSError, SyntaxError) as error:
        raise ErrorReferenciaSolar(
            f"Helioviewer no devolvió una imagen válida para "
            f"{fuente.nombre}."
        ) from error
    finally:
        temporal.unlink(missing_ok=True)

    return ReferenciaSolar(destino, fuente, instante)


def descargar_referencias(instante, clave_fuente="automatica"):
    referencias = []
    errores = []
    fuentes = FUENTES_REFERENCIA
    if clave_fuente != "automatica":
        fuente = FUENTES_POR_CLAVE.get(clave_fuente)
        if fuente is None:
            raise ErrorReferenciaSolar(
                f"Fuente de referencia desconocida: {clave_fuente}"
            )
        fuentes = (fuente,)

    for fuente in fuentes:
        try:
            referencias.append(
                descargar_referencia(instante, fuente)
            )
        except ErrorReferenciaSolar as error:
            errores.append(str(error))
    if not referencias:
        raise ErrorReferenciaSolar("\n".join(errores))
    return referencias, errores


def refinar_posiciones_regiones(
    referencia,
    regiones,
    instante,
):
    """Ajusta cada AR dentro de una vecindad de su posición catalogada.

    No es un detector global de manchas: el catálogo sigue decidiendo
    qué regiones existen y limita estrictamente el área de búsqueda.
    """
    with Image.open(referencia.ruta) as original:
        grises = Image.fromarray(_a_grises_normalizados(original))

    cx, cy, radio = _detectar_disco_referencia(grises)
    arreglo = np.asarray(grises, dtype=np.float32) / 255.0
    base = np.asarray(
        grises.filter(
            ImageFilter.GaussianBlur(
                radius=max(10.0, radio * 0.035)
            )
        ),
        dtype=np.float32,
    ) / 255.0

    if referencia.fuente.clave == "hmi_continuum":
        respuesta = np.maximum(base - arreglo, 0)
    elif referencia.fuente.clave == "aia_1700":
        respuesta = np.maximum(arreglo - base, 0)
        respuesta += 0.35 * np.abs(arreglo - base)
    else:
        respuesta = np.abs(arreglo - base)

    respuesta = np.asarray(
        Image.fromarray(
            np.asarray(
                np.clip(respuesta * 255 * 4, 0, 255),
                dtype=np.uint8,
            )
        ).filter(ImageFilter.GaussianBlur(radius=3.0)),
        dtype=np.float32,
    )
    yy, xx = np.indices(respuesta.shape)
    mascara_disco = (
        (xx - cx) ** 2 + (yy - cy) ** 2
    ) <= (radio * 0.96) ** 2
    respuesta[~mascara_disco] = 0

    regiones_refinadas = 0
    ocupadas = []
    for region in sorted(
        regiones,
        key=lambda valor: -(valor.area or 0),
    ):
        region.refinado_x = None
        region.refinado_y = None
        region.confianza_refinado = None
        posicion = coordenadas_catalogo_normalizadas(
            region,
            instante,
        )
        if posicion is None:
            continue

        esperado_x = cx + posicion[0] * radio
        esperado_y = cy - posicion[1] * radio
        ancho_region, _ = tamano_region_en_imagen(
            region,
            radio,
        )
        # La posición SRS ya es una estimación física sólida. La
        # búsqueda local solo puede afinar dentro de la propia región,
        # no saltar hacia una estructura vecina de alto contraste.
        busqueda = int(
            max(
                20,
                min(
                    max(ancho_region * 0.65, radio * 0.04),
                    radio * 0.085,
                    70,
                ),
            )
        )
        x0 = max(0, int(esperado_x - busqueda))
        x1 = min(arreglo.shape[1], int(esperado_x + busqueda + 1))
        y0 = max(0, int(esperado_y - busqueda))
        y1 = min(arreglo.shape[0], int(esperado_y + busqueda + 1))
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue

        ventana = respuesta[y0:y1, x0:x1].copy()
        vy, vx = np.indices(ventana.shape)
        dx = vx + x0 - esperado_x
        dy = vy + y0 - esperado_y
        sigma = max(busqueda * 0.55, 1.0)
        prioridad = np.exp(
            -(dx * dx + dy * dy) / (2 * sigma * sigma)
        )
        puntaje = ventana * (0.45 + 0.55 * prioridad)

        for ocupado_x, ocupado_y in ocupadas:
            distancia = np.hypot(
                vx + x0 - ocupado_x,
                vy + y0 - ocupado_y,
            )
            puntaje[distancia < max(16, radio * 0.025)] *= 0.15

        valores = ventana[ventana > 0]
        if valores.size < 20:
            continue
        mediana = float(np.median(valores))
        dispersion = float(
            np.median(np.abs(valores - mediana))
        ) * 1.4826
        indice = np.unravel_index(
            int(np.argmax(puntaje)),
            puntaje.shape,
        )
        maximo = float(ventana[indice])
        umbral = mediana + max(0.65 * dispersion, 2.0)
        if maximo < umbral:
            continue

        candidato_x = x0 + indice[1]
        candidato_y = y0 + indice[0]
        desplazamiento = math.hypot(
            candidato_x - esperado_x,
            candidato_y - esperado_y,
        )
        if desplazamiento > busqueda * 0.82:
            continue
        radio_centroide = max(8, int(radio * 0.018))
        distancia_candidato = np.hypot(
            vx + x0 - candidato_x,
            vy + y0 - candidato_y,
        )
        mascara = (
            (distancia_candidato <= radio_centroide)
            & (ventana >= maximo * 0.58)
        )
        pesos = ventana * mascara
        suma = float(pesos.sum())
        if suma > 0:
            candidato_x = float(
                ((vx + x0) * pesos).sum() / suma
            )
            candidato_y = float(
                ((vy + y0) * pesos).sum() / suma
            )

        region.refinado_x = (candidato_x - cx) / radio
        region.refinado_y = -(candidato_y - cy) / radio
        region.confianza_refinado = min(
            1.0,
            maximo / max(umbral, 1e-6) - 0.15,
        )
        if region.confianza_refinado < 0.20:
            region.refinado_x = None
            region.refinado_y = None
            region.confianza_refinado = None
            continue
        ocupadas.append((candidato_x, candidato_y))
        regiones_refinadas += 1

    return regiones_refinadas


def _a_grises_normalizados(imagen):
    imagen = ImageOps.exif_transpose(imagen).convert("L")
    arreglo = np.asarray(imagen, dtype=np.float32)
    finitos = arreglo[np.isfinite(arreglo)]
    if finitos.size == 0:
        return np.zeros(arreglo.shape, dtype=np.uint8)
    minimo, maximo = np.percentile(finitos, (0.5, 99.5))
    if maximo <= minimo:
        return np.zeros(arreglo.shape, dtype=np.uint8)
    arreglo = np.clip((arreglo - minimo) / (maximo - minimo), 0, 1)
    return np.asarray(arreglo * 255, dtype=np.uint8)


def _disco_usuario(ruta, centro_x, centro_y, radio, tamano=192):
    with Image.open(ruta) as original:
        imagen = Image.fromarray(_a_grises_normalizados(original))

    margen = radio * 1.02
    recorte = imagen.crop(
        (
            centro_x - margen,
            centro_y - margen,
            centro_x + margen,
            centro_y + margen,
        )
    )
    return recorte.resize((tamano, tamano), Image.Resampling.LANCZOS)


def _detectar_disco_referencia(imagen):
    grises = np.asarray(
        Image.fromarray(_a_grises_normalizados(imagen)).resize(
            (256, 256),
            Image.Resampling.BILINEAR,
        ),
        dtype=np.float32,
    )
    yy, xx = np.indices(grises.shape)
    centro = (np.array(grises.shape[::-1]) - 1) / 2
    distancia = np.hypot(xx - centro[0], yy - centro[1])

    mejor = None
    for radio in range(102, 126):
        interior = grises[distancia < radio * 0.82]
        exterior = grises[
            (distancia > radio * 1.02)
            & (distancia < radio * 1.12)
        ]
        if interior.size == 0 or exterior.size == 0:
            continue
        contraste = abs(
            float(np.median(interior))
            - float(np.median(exterior))
        )
        if mejor is None or contraste > mejor[0]:
            mejor = (contraste, radio)

    radio = (mejor[1] if mejor else 120) * imagen.width / 256
    return imagen.width / 2, imagen.height / 2, radio


def _disco_referencia(referencia, tamano=192):
    with Image.open(referencia.ruta) as original:
        original.load()
        imagen = Image.fromarray(_a_grises_normalizados(original))
    cx, cy, radio = _detectar_disco_referencia(imagen)
    margen = radio * 1.02
    recorte = imagen.crop(
        (cx - margen, cy - margen, cx + margen, cy + margen)
    )
    return recorte.resize((tamano, tamano), Image.Resampling.LANCZOS)


def _rasgos(imagen):
    imagen = ImageOps.autocontrast(imagen)
    suave = imagen.filter(ImageFilter.GaussianBlur(radius=3.0))
    base = np.asarray(imagen, dtype=np.float32) / 255
    baja = np.asarray(suave, dtype=np.float32) / 255
    alto = base - baja
    gy, gx = np.gradient(baja)
    bordes = np.hypot(gx, gy)
    rasgos = np.abs(alto) + 1.8 * bordes

    alto_imagen, ancho_imagen = rasgos.shape
    yy, xx = np.indices(rasgos.shape)
    radio = min(ancho_imagen, alto_imagen) * 0.43
    mascara = (
        (xx - (ancho_imagen - 1) / 2) ** 2
        + (yy - (alto_imagen - 1) / 2) ** 2
    ) <= radio**2
    valores = rasgos[mascara]
    mediana = float(np.median(valores))
    desviacion = float(np.std(valores)) or 1.0
    normalizados = (rasgos - mediana) / desviacion
    normalizados[~mascara] = 0
    return normalizados, mascara


def _rasgos_manchas(imagen):
    """Extrae estructuras compactas para alinear discos de longitudes distintas.

    La granulación y el contraste global cambian mucho entre visible, HMI y
    H-alfa. Las manchas, en cambio, permanecen como estructuras compactas. Se
    usa el contraste local absoluto para admitir tanto imágenes normales como
    invertidas sin confundir el borde o el oscurecimiento del limbo.
    """
    imagen = ImageOps.autocontrast(imagen)
    base = np.asarray(imagen, dtype=np.float32) / 255.0
    suave = np.asarray(
        imagen.filter(ImageFilter.GaussianBlur(radius=3.0)),
        dtype=np.float32,
    ) / 255.0
    respuesta = np.abs(base - suave)

    alto, ancho = respuesta.shape
    yy, xx = np.indices(respuesta.shape)
    centro_x = (ancho - 1) / 2
    centro_y = (alto - 1) / 2
    radio = min(ancho, alto) * 0.45
    mascara = (
        (xx - centro_x) ** 2 + (yy - centro_y) ** 2
    ) <= radio**2
    valores = respuesta[mascara]
    if valores.size == 0:
        return np.zeros_like(respuesta), mascara

    # Elimina la textura débil y conserva los núcleos que distinguen una AR.
    umbral = float(np.percentile(valores, 95.0))
    techo = float(np.percentile(valores, 99.5))
    respuesta = np.clip(
        (respuesta - umbral) / max(techo - umbral, 1e-6),
        0.0,
        1.0,
    )
    respuesta[~mascara] = 0.0
    respuesta = np.asarray(
        Image.fromarray(
            np.asarray(respuesta * 255, dtype=np.uint8)
        ).filter(ImageFilter.GaussianBlur(radius=1.0)),
        dtype=np.float32,
    ) / 255.0
    return respuesta, mascara


def _transformar(imagen, rotacion, espejo_horizontal, espejo_vertical):
    resultado = imagen
    if espejo_horizontal:
        resultado = ImageOps.mirror(resultado)
    if espejo_vertical:
        resultado = ImageOps.flip(resultado)
    return resultado.rotate(
        -float(rotacion),
        resample=Image.Resampling.BILINEAR,
        expand=False,
        fillcolor=0,
    )


def _correlacion(rasgos_a, rasgos_b, mascara):
    a = rasgos_a[mascara]
    b = rasgos_b[mascara]
    a = a - float(a.mean())
    b = b - float(b.mean())
    denominador = math.sqrt(
        float(np.dot(a, a)) * float(np.dot(b, b))
    )
    if denominador <= 1e-12:
        return -1.0
    return float(np.dot(a, b) / denominador)


def registrar_orientacion(
    ruta_usuario,
    centro_x,
    centro_y,
    radio,
    referencias,
):
    usuario = _disco_usuario(
        ruta_usuario,
        centro_x,
        centro_y,
        radio,
    )
    # Para el registro automático usamos solo manchas/estructuras compactas.
    # Comparar toda la textura hacía que una diferencia de longitud de onda
    # pareciera una orientación distinta.
    rasgos_usuario, mascara = _rasgos_manchas(usuario)
    candidatos = []

    for referencia in referencias:
        disco = _disco_referencia(referencia)
        for espejo_horizontal, espejo_vertical in (
            (False, False),
            (True, False),
            (False, True),
            (True, True),
        ):
            for rotacion in range(-180, 180, 10):
                transformada = _transformar(
                    disco,
                    rotacion,
                    espejo_horizontal,
                    espejo_vertical,
                )
                rasgos, _ = _rasgos_manchas(transformada)
                puntuacion = _correlacion(
                    rasgos_usuario,
                    rasgos,
                    mascara,
                )
                candidatos.append(
                    (
                        puntuacion,
                        referencia,
                        float(rotacion),
                        espejo_horizontal,
                        espejo_vertical,
                        disco,
                    )
                )

    candidatos.sort(key=lambda valor: valor[0], reverse=True)
    refinados = []
    for candidato in candidatos[:6]:
        _, referencia, rotacion, espejo_h, espejo_v, disco = candidato
        for angulo in np.arange(rotacion - 6, rotacion + 6.1, 1.0):
            angulo = ((float(angulo) + 180) % 360) - 180
            transformada = _transformar(
                disco,
                angulo,
                espejo_h,
                espejo_v,
            )
            rasgos, _ = _rasgos_manchas(transformada)
            puntuacion = _correlacion(
                rasgos_usuario,
                rasgos,
                mascara,
            )
            refinados.append(
                (
                    puntuacion,
                    referencia,
                    angulo,
                    espejo_h,
                    espejo_v,
                )
            )

    refinados.sort(key=lambda valor: valor[0], reverse=True)
    puntuacion, referencia, rotacion, espejo_h, espejo_v = refinados[0]
    if puntuacion >= 0.50:
        confianza = "alta"
    elif puntuacion >= 0.30:
        confianza = "media"
    else:
        confianza = "baja"

    return ResultadoRegistro(
        rotacion=rotacion,
        espejo_horizontal=espejo_h,
        espejo_vertical=espejo_v,
        puntuacion=puntuacion,
        confianza=confianza,
        referencia=referencia,
    )


def registrar_orientacion_catalogo(
    ruta_usuario,
    centro_x,
    centro_y,
    radio,
    regiones,
    instante,
    referencia,
):
    """Resuelve la orientación usando las posiciones NOAA/HEK.

    En H-alfa las estructuras filamentosas y las plages pueden parecer muy
    distintas entre dos observatorios. Por eso esta segunda ruta no compara
    la textura con una referencia: transforma las coordenadas catalogadas de
    cada AR y busca, dentro de una vecindad limitada, el contraste compacto de
    la propia fotografía. Es una solución de placa guiada por catálogo y
    funciona también con imágenes invertidas.
    """
    tamano = 512
    disco = _disco_usuario(
        ruta_usuario,
        centro_x,
        centro_y,
        radio,
        tamano=tamano,
    )
    imagen = ImageOps.autocontrast(disco)
    base = np.asarray(imagen, dtype=np.float32) / 255.0
    suave = np.asarray(
        imagen.filter(ImageFilter.GaussianBlur(radius=5.0)),
        dtype=np.float32,
    ) / 255.0
    respuesta = np.abs(base - suave)
    yy, xx = np.indices(respuesta.shape)
    centro = (tamano - 1) / 2
    radio_mapa = tamano / 2.04
    mascara = (xx - centro) ** 2 + (yy - centro) ** 2 <= (
        radio_mapa * 0.96
    ) ** 2
    valores = respuesta[mascara]
    if valores.size < 50:
        return ResultadoRegistro(
            rotacion=0.0,
            espejo_horizontal=False,
            espejo_vertical=False,
            puntuacion=-1.0,
            confianza="baja",
            referencia=referencia,
        )
    umbral = float(np.percentile(valores, 95.0))
    techo = float(np.percentile(valores, 99.5))
    respuesta = np.clip(
        (respuesta - umbral) / max(techo - umbral, 1e-6),
        0.0,
        1.0,
    )
    respuesta[~mascara] = 0.0
    respuesta = np.asarray(
        Image.fromarray(
            np.asarray(respuesta * 255, dtype=np.uint8)
        ).filter(ImageFilter.GaussianBlur(radius=1.0)),
        dtype=np.float32,
    ) / 255.0

    controles = []
    for region in regiones:
        posicion = coordenadas_catalogo_normalizadas(
            region,
            instante,
        )
        if posicion is None:
            continue
        peso = math.sqrt(max(float(region.area or 1), 1.0))
        controles.append((posicion[0], posicion[1], peso))
    if len(controles) < 2:
        return ResultadoRegistro(
            rotacion=0.0,
            espejo_horizontal=False,
            espejo_vertical=False,
            puntuacion=-1.0,
            confianza="baja",
            referencia=referencia,
        )

    # El ajuste manual del limbo puede tener unos píxeles de diferencia,
    # especialmente cuando el disco está recortado por el borde superior.
    # Probamos pequeños desplazamientos y escalas en el mapa normalizado;
    # así la orientación no depende de que Hough haya elegido exactamente el
    # mismo radio que el catálogo. No se altera el círculo del usuario: solo
    # se usa esta tolerancia para resolver la placa.
    ajustes_geometricos = (
        (0.0, 0.0, 1.000),
        (0.0, 0.0, 0.975),
        (0.0, 0.0, 1.025),
    )

    def evaluar(
        angulo,
        espejo_horizontal,
        espejo_vertical,
        ajuste_x=0.0,
        ajuste_y=0.0,
        ajuste_radio=1.0,
    ):
        valores = []
        pesos = []
        centro_ajustado_x = centro + ajuste_x * radio_mapa
        centro_ajustado_y = centro + ajuste_y * radio_mapa
        radio_ajustado = radio_mapa * ajuste_radio
        for x, y_solar, peso in controles:
            dx = x
            dy = -y_solar
            if espejo_horizontal:
                dx *= -1
            if espejo_vertical:
                dy *= -1
            angulo_rad = math.radians(angulo)
            esperado_x = (
                math.cos(angulo_rad) * dx
                - math.sin(angulo_rad) * dy
            )
            esperado_y = (
                math.sin(angulo_rad) * dx
                + math.cos(angulo_rad) * dy
            )
            px = centro_ajustado_x + esperado_x * radio_ajustado
            py = centro_ajustado_y + esperado_y * radio_ajustado
            if not (0 <= px < tamano and 0 <= py < tamano):
                continue
            # El SRS se publica a 00:00Z y la foto puede estar varias horas
            # alejada de esa referencia. La rotación solar y una pequeña
            # imprecisión del círculo justifican una ventana de ~10% del
            # radio; no se debe saltar a otra región activa.
            busqueda = max(10, min(20, radio_mapa * 0.065))
            x0 = max(0, int(px - busqueda))
            x1 = min(tamano, int(px + busqueda + 1))
            y0 = max(0, int(py - busqueda))
            y1 = min(tamano, int(py + busqueda + 1))
            ventana = respuesta[y0:y1, x0:x1]
            if ventana.size == 0:
                continue
            # Una AR puede ocupar solo una fracción pequeña de la ventana.
            # El percentil 90 solía devolver cero y descartaba precisamente
            # las manchas que sí estaban bajo la posición catalogada. Se
            # pondera el pico compacto (p99.2) con el promedio de la cola
            # superior; así una línea larga de filamento no domina por sí
            # sola.
            pico = float(np.percentile(ventana, 99.2))
            cola = np.sort(ventana.reshape(-1))
            cantidad_cola = max(3, int(cola.size * 0.01))
            promedio_cola = float(np.mean(cola[-cantidad_cola:]))
            valores.append(0.72 * pico + 0.28 * promedio_cola)
            pesos.append(peso)
        if not valores:
            return -1.0, 0
        valores = np.asarray(valores, dtype=np.float32)
        pesos = np.asarray(pesos, dtype=np.float32)
        fuertes = int(np.count_nonzero(valores >= 0.42))
        puntuacion = float(np.average(valores, weights=pesos))
        # La cantidad de coincidencias es más informativa que un promedio
        # alto provocado por una sola plage brillante.
        puntuacion += 0.12 * fuertes / max(len(controles), 1)
        return puntuacion, fuertes

    candidatos = []
    for espejo_horizontal, espejo_vertical in (
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ):
        for ajuste_x, ajuste_y, ajuste_radio in ajustes_geometricos:
            for angulo in range(-180, 180, 4):
                puntuacion, fuertes = evaluar(
                    angulo,
                    espejo_horizontal,
                    espejo_vertical,
                    ajuste_x,
                    ajuste_y,
                    ajuste_radio,
                )
                candidatos.append(
                    (
                        puntuacion,
                        fuertes,
                        float(angulo),
                        espejo_horizontal,
                        espejo_vertical,
                        ajuste_x,
                        ajuste_y,
                        ajuste_radio,
                    )
                )

    candidatos.sort(
        key=lambda valor: (valor[0], valor[1]),
        reverse=True,
    )
    refinados = []
    for candidato in candidatos[:8]:
        (
            _,
            _,
            angulo,
            espejo_horizontal,
            espejo_vertical,
            ajuste_x,
            ajuste_y,
            ajuste_radio,
        ) = candidato
        for refinado in np.arange(angulo - 5, angulo + 5.1, 1.0):
            refinado = ((float(refinado) + 180) % 360) - 180
            puntuacion, fuertes = evaluar(
                refinado,
                espejo_horizontal,
                espejo_vertical,
                ajuste_x,
                ajuste_y,
                ajuste_radio,
            )
            refinados.append(
                (
                    puntuacion,
                    fuertes,
                    refinado,
                    espejo_horizontal,
                    espejo_vertical,
                    ajuste_x,
                    ajuste_y,
                    ajuste_radio,
                )
            )
    refinados.sort(
        key=lambda valor: (valor[0], valor[1]),
        reverse=True,
    )
    (
        puntuacion,
        fuertes,
        angulo,
        espejo_h,
        espejo_v,
        _ajuste_x,
        _ajuste_y,
        _ajuste_radio,
    ) = refinados[0]
    alternativas = [
        valor
        for valor in refinados[1:]
        if (
            valor[3] != espejo_h
            or valor[4] != espejo_v
            or abs(valor[2] - angulo) >= 12
        )
    ]
    segundo = alternativas[0][0] if alternativas else -1.0
    separacion = puntuacion - segundo
    if puntuacion >= 0.50 and fuertes >= 3:
        confianza = "alta"
    elif (
        puntuacion >= 0.24
        and fuertes >= 2
        and separacion >= 0.012
    ):
        confianza = "media"
    else:
        confianza = "baja"
    return ResultadoRegistro(
        rotacion=angulo,
        espejo_horizontal=espejo_h,
        espejo_vertical=espejo_v,
        puntuacion=puntuacion,
        confianza=confianza,
        referencia=referencia,
        evidencia=fuertes,
        separacion=separacion,
    )


def _fuente_texto(tamano):
    candidatos = (
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    )
    for ruta in candidatos:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()


def _interseccion_rectangulos(a, b):
    ancho = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    alto = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return ancho * alto


def _posicion_texto_sin_solapes(
    dibujo,
    texto,
    fuente,
    px,
    py,
    radio_marca,
    ancho_imagen,
    alto_imagen,
    ocupados,
):
    caja = dibujo.multiline_textbbox(
        (0, 0),
        texto,
        font=fuente,
        spacing=2,
        stroke_width=2,
    )
    ancho = caja[2] - caja[0]
    alto = caja[3] - caja[1]
    distancia = radio_marca + 12
    candidatos = (
        (distancia, -alto - distancia),
        (distancia, distancia),
        (-ancho - distancia, -alto - distancia),
        (-ancho - distancia, distancia),
        (-ancho / 2, -alto - distancia * 1.6),
        (-ancho / 2, distancia * 1.6),
        (distancia * 1.7, -alto / 2),
        (-ancho - distancia * 1.7, -alto / 2),
    )
    mejor = None
    margen = 8
    for indice, (dx, dy) in enumerate(candidatos):
        rectangulo = (
            px + dx,
            py + dy,
            px + dx + ancho,
            py + dy + alto,
        )
        fuera = (
            max(0, margen - rectangulo[0])
            + max(0, margen - rectangulo[1])
            + max(0, rectangulo[2] - ancho_imagen + margen)
            + max(0, rectangulo[3] - alto_imagen + margen)
        )
        solape = sum(
            _interseccion_rectangulos(rectangulo, ocupado)
            for ocupado in ocupados
        )
        puntuacion = fuera * 100_000 + solape + indice
        if mejor is None or puntuacion < mejor[0]:
            mejor = (puntuacion, dx, dy, rectangulo)
    return mejor[1], mejor[2], mejor[3]


def crear_referencia_anotada(
    referencia,
    regiones,
    instante,
    mostrar_conteo=True,
):
    with Image.open(referencia.ruta) as original:
        imagen = original.convert("RGB")
    cx, cy, radio = _detectar_disco_referencia(imagen)
    dibujo = ImageDraw.Draw(imagen)
    fuente = _fuente_texto(max(16, imagen.width // 48))
    color = (255, 191, 29)
    ocupados = []

    for region in regiones:
        posicion = coordenadas_normalizadas(region, instante)
        if posicion is None:
            continue
        x, y = posicion
        px = cx + x * radio
        py = cy - y * radio
        if not (0 <= px < imagen.width and 0 <= py < imagen.height):
            continue

        lineas = [region.nombre]
        if region.clase_magnetica:
            lineas.append(
                tr(
                    "reference_magnetic_short",
                    value=region.clase_magnetica,
                )
            )
        if mostrar_conteo and region.manchas is not None:
            lineas.append(
                tr(
                    (
                        "one_sunspot"
                        if region.manchas == 1
                        else "many_sunspots"
                    ),
                    count=region.manchas,
                )
            )
        texto = "\n".join(lineas)
        ancho_marca, alto_marca = tamano_region_en_imagen(
            region,
            radio,
        )
        ancho_marca = max(ancho_marca, imagen.width / 80)
        alto_marca = max(alto_marca, imagen.width / 100)
        radio_texto = max(ancho_marca, alto_marca) / 2
        dibujo.ellipse(
            (
                px - ancho_marca / 2,
                py - alto_marca / 2,
                px + ancho_marca / 2,
                py + alto_marca / 2,
            ),
            outline=color,
            width=max(2, imagen.width // 500),
        )
        dx, dy, caja_texto = _posicion_texto_sin_solapes(
            dibujo,
            texto,
            fuente,
            px,
            py,
            radio_texto,
            imagen.width,
            imagen.height,
            ocupados,
        )
        ocupados.append(caja_texto)
        destino_x = (
            caja_texto[0]
            if dx >= 0
            else caja_texto[2]
        )
        destino_y = min(
            max(py, caja_texto[1]),
            caja_texto[3],
        )
        dibujo.line(
            (px, py, destino_x, destino_y),
            fill=color,
            width=max(2, imagen.width // 500),
        )
        dibujo.multiline_text(
            (px + dx, py + dy),
            texto,
            fill=color,
            font=fuente,
            spacing=2,
            stroke_width=2,
            stroke_fill=(0, 0, 0),
        )

    instante_texto = instante.astimezone(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    pie = f"{referencia.fuente.nombre} · {instante_texto}"
    dibujo.text(
        (14, imagen.height - 34),
        pie,
        fill=(255, 255, 255),
        font=_fuente_texto(max(13, imagen.width // 64)),
        stroke_width=2,
        stroke_fill=(0, 0, 0),
    )

    destino = (
        _carpeta_cache()
        / f"{referencia.ruta.stem}_anotada.png"
    )
    imagen.save(destino, "PNG")
    return destino
