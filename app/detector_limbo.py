from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


class ErrorDeteccionLimbo(RuntimeError):
    pass


@dataclass
class ResultadoLimbo:
    centro_x: float
    centro_y: float
    radio: float
    error_px: float
    puntos_usados: int


def _leer_imagen(ruta):
    datos = np.fromfile(str(Path(ruta)), dtype=np.uint8)
    imagen = cv2.imdecode(datos, cv2.IMREAD_COLOR)

    if imagen is None:
        raise ErrorDeteccionLimbo("No se pudo leer la imagen.")

    return imagen


def _valores_perimetro(imagen, cx, cy, radio, muestras=720):
    angulos = np.linspace(0, 2 * np.pi, muestras, endpoint=False)
    x = np.rint(cx + radio * np.cos(angulos)).astype(int)
    y = np.rint(cy + radio * np.sin(angulos)).astype(int)

    validos = (
        (x >= 0)
        & (x < imagen.shape[1])
        & (y >= 0)
        & (y < imagen.shape[0])
    )

    if validos.sum() < muestras * 0.75:
        return np.array([], dtype=float)

    return imagen[y[validos], x[validos]].astype(float)


def _puntuar_circulo(gradiente, cx, cy, radio):
    bandas = []

    for desplazamiento in range(-4, 5):
        valores = _valores_perimetro(
            gradiente,
            cx,
            cy,
            radio + desplazamiento,
        )
        if valores.size:
            bandas.append(valores)

    if not bandas:
        return -1.0

    longitud = min(len(banda) for banda in bandas)
    matriz = np.vstack([banda[:longitud] for banda in bandas])
    maximos = matriz.max(axis=0)

    soporte = np.mean(maximos > np.percentile(gradiente, 75))
    intensidad = np.mean(maximos)

    return float(intensidad * (0.5 + soporte))


def _ajustar_circulo(puntos_x, puntos_y, inicial):
    puntos_x = np.asarray(puntos_x, dtype=float)
    puntos_y = np.asarray(puntos_y, dtype=float)

    mascara = np.ones(len(puntos_x), dtype=bool)
    cx, cy, radio = inicial

    for _ in range(6):
        x = puntos_x[mascara]
        y = puntos_y[mascara]

        if len(x) < 30:
            break

        matriz = np.column_stack(
            (2.0 * x, 2.0 * y, np.ones_like(x))
        )
        objetivo = x**2 + y**2

        solucion, _, _, _ = np.linalg.lstsq(
            matriz,
            objetivo,
            rcond=None,
        )

        cx = float(solucion[0])
        cy = float(solucion[1])
        termino = float(solucion[2])
        radio = float(
            np.sqrt(max(0.0, termino + cx**2 + cy**2))
        )

        residuales_totales = (
            np.hypot(puntos_x - cx, puntos_y - cy) - radio
        )

        mediana = float(np.median(residuales_totales[mascara]))
        desviaciones = np.abs(
            residuales_totales[mascara] - mediana
        )
        mad = float(np.median(desviaciones))
        sigma = max(0.75, 1.4826 * mad)

        nueva_mascara = (
            np.abs(residuales_totales - mediana)
            <= 3.0 * sigma
        )

        if nueva_mascara.sum() == mascara.sum():
            mascara = nueva_mascara
            break

        mascara = nueva_mascara

    residuales_finales = (
        np.hypot(
            puntos_x[mascara] - cx,
            puntos_y[mascara] - cy,
        )
        - radio
    )

    error = float(
        np.sqrt(np.mean(residuales_finales**2))
    )

    return cx, cy, radio, error


def detectar_limbo(ruta):
    imagen_original = _leer_imagen(ruta)
    alto_original, ancho_original = imagen_original.shape[:2]

    limite = 1200
    factor = min(1.0, limite / max(ancho_original, alto_original))

    if factor < 1:
        imagen = cv2.resize(
            imagen_original,
            None,
            fx=factor,
            fy=factor,
            interpolation=cv2.INTER_AREA,
        )
    else:
        imagen = imagen_original.copy()

    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    gris = cv2.normalize(gris, None, 0, 255, cv2.NORM_MINMAX)

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )
    contraste = clahe.apply(gris)
    suavizada = cv2.GaussianBlur(contraste, (9, 9), 2)

    gradiente_x = cv2.Sobel(
        suavizada,
        cv2.CV_32F,
        1,
        0,
        ksize=3,
    )
    gradiente_y = cv2.Sobel(
        suavizada,
        cv2.CV_32F,
        0,
        1,
        ksize=3,
    )
    gradiente = cv2.magnitude(gradiente_x, gradiente_y)
    gradiente = cv2.normalize(
        gradiente,
        None,
        0,
        255,
        cv2.NORM_MINMAX,
    ).astype(np.uint8)

    alto, ancho = gris.shape
    dimension_minima = min(alto, ancho)
    radio_minimo = int(dimension_minima * 0.18)
    radio_maximo = int(dimension_minima * 0.58)

    candidatos = []

    for sensibilidad in (75, 60, 48, 38):
        circulos = cv2.HoughCircles(
            suavizada,
            cv2.HOUGH_GRADIENT,
            dp=1.4,
            minDist=dimension_minima * 0.25,
            param1=110,
            param2=sensibilidad,
            minRadius=radio_minimo,
            maxRadius=radio_maximo,
        )

        if circulos is not None:
            for cx, cy, radio in circulos[0]:
                candidatos.append(
                    (float(cx), float(cy), float(radio))
                )

        if len(candidatos) >= 3:
            break

    for tipo in (cv2.THRESH_BINARY, cv2.THRESH_BINARY_INV):
        _, mascara = cv2.threshold(
            suavizada,
            0,
            255,
            tipo | cv2.THRESH_OTSU,
        )

        contornos, _ = cv2.findContours(
            mascara,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        for contorno in sorted(
            contornos,
            key=cv2.contourArea,
            reverse=True,
        )[:5]:
            area = cv2.contourArea(contorno)

            if area < alto * ancho * 0.08:
                continue

            (cx, cy), radio = cv2.minEnclosingCircle(contorno)

            if radio_minimo <= radio <= radio_maximo:
                candidatos.append((cx, cy, radio))

    if not candidatos:
        raise ErrorDeteccionLimbo(
            "No se encontró un disco solar completo. "
            "Puedes continuar con el ajuste manual."
        )

    mejor = max(
        candidatos,
        key=lambda candidato: _puntuar_circulo(
            gradiente,
            *candidato,
        ),
    )
    cx_inicial, cy_inicial, radio_inicial = mejor

    angulos = np.linspace(0, 2 * np.pi, 720, endpoint=False)
    umbral_gradiente = max(
        12,
        float(np.percentile(gradiente, 70)),
    )

    puntos_x = []
    puntos_y = []

    amplitud = max(8, int(radio_inicial * 0.035))
    radios_busqueda = np.arange(
        radio_inicial - amplitud,
        radio_inicial + amplitud + 1,
    )

    for angulo in angulos:
        coseno = np.cos(angulo)
        seno = np.sin(angulo)

        xs = np.rint(
            cx_inicial + radios_busqueda * coseno
        ).astype(int)
        ys = np.rint(
            cy_inicial + radios_busqueda * seno
        ).astype(int)

        validos = (
            (xs >= 0)
            & (xs < ancho)
            & (ys >= 0)
            & (ys < alto)
        )

        if validos.sum() < 5:
            continue

        xs = xs[validos]
        ys = ys[validos]
        valores = gradiente[ys, xs]
        indice = int(np.argmax(valores))

        if valores[indice] >= umbral_gradiente:
            puntos_x.append(xs[indice])
            puntos_y.append(ys[indice])

    if len(puntos_x) < 180:
        raise ErrorDeteccionLimbo(
            "Se encontró un círculo posible, pero el limbo "
            "no tiene suficientes bordes confiables."
        )

    puntos_x = np.asarray(puntos_x, dtype=float)
    puntos_y = np.asarray(puntos_y, dtype=float)

    cx, cy, radio, error = _ajustar_circulo(
        puntos_x,
        puntos_y,
        (cx_inicial, cy_inicial, radio_inicial),
    )

    if radio <= 0 or error > radio * 0.04:
        raise ErrorDeteccionLimbo(
            "El ajuste encontrado tiene demasiada dispersión."
        )

    inverso = 1.0 / factor

    return ResultadoLimbo(
        centro_x=cx * inverso,
        centro_y=cy * inverso,
        radio=radio * inverso,
        error_px=error * inverso,
        puntos_usados=len(puntos_x),
    )
