import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, PngImagePlugin


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

from catalogo_regiones import (  # noqa: E402
    _instante_desde_nombre,
    leer_fecha_hora_imagen,
)


class LecturaFechaNombreTest(unittest.TestCase):
    CASOS = {
        "2026-07-04-1915_3-U-G-Sun_Halpha.tif": (
            2026,
            7,
            4,
            19,
            15,
            0,
        ),
        "2026-07-09-2218_Sun_Halpha.tif": (
            2026,
            7,
            9,
            22,
            18,
            0,
        ),
        "2026-07-25-202030_Sun_CaK.png": (
            2026,
            7,
            25,
            20,
            20,
            30,
        ),
        "Sun_2026-07-30_23-08-45_ap413.tif": (
            2026,
            7,
            30,
            23,
            8,
            45,
        ),
        "VID_20260730_230845_HDR10PLUS.mp4": (
            2026,
            7,
            30,
            23,
            8,
            45,
        ),
        "Sun_20260730-2308.tif": (
            2026,
            7,
            30,
            23,
            8,
            0,
        ),
        "captura_20260730230845_final.png": (
            2026,
            7,
            30,
            23,
            8,
            45,
        ),
        "04-07-2026_1915_Halpha.tif": (
            2026,
            7,
            4,
            19,
            15,
            0,
        ),
        "4_7_2026_9-05-Sol.tif": (
            2026,
            7,
            4,
            9,
            5,
            0,
        ),
    }

    def test_formatos_admitidos(self):
        for nombre, componentes in self.CASOS.items():
            with self.subTest(nombre=nombre):
                instante, fragmento = _instante_desde_nombre(
                    nombre
                )
                self.assertIsNotNone(instante)
                self.assertIsNotNone(fragmento)
                self.assertEqual(
                    instante,
                    datetime(
                        *componentes,
                        tzinfo=timezone.utc,
                    ),
                )

    def test_fechas_invalidas_no_se_aceptan(self):
        for nombre in (
            "Sol_2026-02-30-1915.tif",
            "Sol_2026-07-04.tif",
            "Sol_20260704_256199.tif",
            "imagen(148).png",
        ):
            with self.subTest(nombre=nombre):
                instante, fragmento = _instante_desde_nombre(
                    nombre
                )
                self.assertIsNone(instante)
                self.assertIsNone(fragmento)

    def test_nombre_tiene_prioridad_sobre_exif_de_exportacion(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = (
                Path(temporal)
                / "2026-07-04-1915_Sun_Halpha.png"
            )
            metadatos = PngImagePlugin.PngInfo()
            metadatos.add_text(
                "DateTime",
                "2026:07:31 03:20:00",
            )
            Image.new("RGB", (8, 8)).save(
                ruta,
                pnginfo=metadatos,
            )

            instante, fuente = leer_fecha_hora_imagen(ruta)
            self.assertEqual(
                instante,
                datetime(
                    2026,
                    7,
                    4,
                    19,
                    15,
                    tzinfo=timezone.utc,
                ),
            )
            self.assertEqual(fuente.clave, "filename")
            self.assertEqual(
                fuente.detalle,
                "2026-07-04-1915",
            )


if __name__ == "__main__":
    unittest.main()
