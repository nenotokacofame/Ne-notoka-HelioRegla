import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "app"),
)

from PIL import Image, ImageDraw

from referencia_solar import (
    FUENTES_POR_CLAVE,
    ReferenciaSolar,
    registrar_orientacion,
    registrar_orientacion_catalogo,
)
from catalogo_regiones import RegionActiva


class AlineacionManchasTests(unittest.TestCase):
    def test_reconoce_rotacion_con_estructuras_compactas(self):
        with tempfile.TemporaryDirectory() as temporal:
            base = Image.new("L", (512, 512), 0)
            dibujo = ImageDraw.Draw(base)
            dibujo.ellipse((36, 36, 476, 476), fill=180)
            for x, y, radio in (
                (150, 180, 12),
                (300, 160, 8),
                (250, 270, 15),
                (370, 310, 6),
                (130, 350, 5),
            ):
                dibujo.ellipse(
                    (x - radio, y - radio, x + radio, y + radio),
                    fill=30,
                )

            ruta_referencia = Path(temporal) / "referencia.png"
            ruta_usuario = Path(temporal) / "usuario.png"
            base.save(ruta_referencia)
            base.rotate(
                94,
                resample=Image.Resampling.BICUBIC,
                expand=False,
                fillcolor=0,
            ).save(ruta_usuario)

            referencia = ReferenciaSolar(
                ruta_referencia,
                FUENTES_POR_CLAVE["hmi_continuum"],
                datetime.now(timezone.utc),
            )
            resultado = registrar_orientacion(
                ruta_usuario,
                256,
                256,
                220,
                [referencia],
            )

            self.assertEqual(resultado.confianza, "alta")
            self.assertAlmostEqual(resultado.rotacion, -94.0, delta=2.0)
            self.assertFalse(resultado.espejo_horizontal)
            self.assertFalse(resultado.espejo_vertical)

    def test_resuelve_orientacion_con_puntos_del_catalogo(self):
        with tempfile.TemporaryDirectory() as temporal:
            base = Image.new("L", (512, 512), 0)
            dibujo = ImageDraw.Draw(base)
            dibujo.ellipse((36, 36, 476, 476), fill=180)
            puntos = (
                (150, 180, 12),
                (300, 160, 8),
                (250, 270, 15),
                (370, 310, 6),
            )
            for x, y, radio in puntos:
                dibujo.ellipse(
                    (x - radio, y - radio, x + radio, y + radio),
                    fill=30,
                )

            ruta_usuario = Path(temporal) / "usuario.png"
            base.rotate(
                94,
                resample=Image.Resampling.BICUBIC,
                expand=False,
                fillcolor=0,
            ).save(ruta_usuario)
            instante = datetime(2026, 7, 31, 16, 8, tzinfo=timezone.utc)
            regiones = []
            for indice, (x, y, _) in enumerate(puntos):
                regiones.append(
                    RegionActiva(
                        numero=str(10000 + indice),
                        hpc_x=(x - 256) / 220 * 959.63,
                        hpc_y=(256 - y) / 220 * 959.63,
                        area=100,
                    )
                )
            referencia = ReferenciaSolar(
                Path(temporal) / "referencia.png",
                FUENTES_POR_CLAVE["gong_halpha"],
                instante,
            )

            resultado = registrar_orientacion_catalogo(
                ruta_usuario,
                256,
                256,
                220,
                regiones,
                instante,
                referencia,
            )

            self.assertEqual(resultado.confianza, "alta")
            self.assertAlmostEqual(resultado.rotacion, -94.0, delta=2.0)


if __name__ == "__main__":
    unittest.main()
