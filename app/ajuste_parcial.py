from dataclasses import dataclass

import numpy as np


@dataclass
class ResultadoParcial:
    centro_x: float
    centro_y: float
    radio: float
    residuo_px: float
    incertidumbre_radio_px: float
    cobertura_grados: float
    puntos_usados: int


def _circulo_algebraico(puntos):
    puntos = np.asarray(puntos, dtype=float)
    x = puntos[:, 0]
    y = puntos[:, 1]

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

    if radio <= 0 or not np.isfinite(radio):
        raise ValueError("Los puntos no producen un círculo válido.")

    return cx, cy, radio


def _cobertura_angular(puntos, cx, cy):
    puntos = np.asarray(puntos, dtype=float)
    angulos = np.mod(
        np.arctan2(
            puntos[:, 1] - cy,
            puntos[:, 0] - cx,
        ),
        2 * np.pi,
    )
    angulos = np.sort(angulos)

    huecos = np.diff(
        np.concatenate((angulos, [angulos[0] + 2 * np.pi]))
    )
    mayor_hueco = float(np.max(huecos))

    return float(np.degrees(2 * np.pi - mayor_hueco))


def _incertidumbre_montecarlo(
    puntos,
    cobertura,
    muestras=250,
):
    puntos = np.asarray(puntos, dtype=float)
    rng = np.random.default_rng(20260730)

    # Incertidumbre estimada de un clic manual.
    sigma_clic = 1.5
    radios = []

    for _ in range(muestras):
        simulados = puntos + rng.normal(
            0,
            sigma_clic,
            size=puntos.shape,
        )

        try:
            _, _, radio = _circulo_algebraico(simulados)
        except (ValueError, np.linalg.LinAlgError):
            continue

        if np.isfinite(radio):
            radios.append(radio)

    if len(radios) < 30:
        return float("inf")

    incertidumbre = float(np.std(radios, ddof=1))

    # Penaliza arcos muy cortos, cuya extrapolación es inestable.
    if cobertura < 90:
        incertidumbre *= 90 / max(cobertura, 5)

    return incertidumbre


def ajustar_limbo_parcial(puntos):
    if len(puntos) < 3:
        raise ValueError("Se necesitan al menos tres puntos.")

    cx, cy, radio = _circulo_algebraico(puntos)
    puntos_np = np.asarray(puntos, dtype=float)

    distancias = np.hypot(
        puntos_np[:, 0] - cx,
        puntos_np[:, 1] - cy,
    )
    residuales = distancias - radio
    residuo = float(np.sqrt(np.mean(residuales**2)))

    cobertura = _cobertura_angular(puntos, cx, cy)
    incertidumbre = _incertidumbre_montecarlo(
        puntos,
        cobertura,
    )

    return ResultadoParcial(
        centro_x=cx,
        centro_y=cy,
        radio=radio,
        residuo_px=residuo,
        incertidumbre_radio_px=incertidumbre,
        cobertura_grados=cobertura,
        puntos_usados=len(puntos),
    )
