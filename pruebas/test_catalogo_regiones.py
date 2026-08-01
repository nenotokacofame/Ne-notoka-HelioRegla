import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

from catalogo_regiones import (  # noqa: E402
    analizar_srs,
    coordenadas_catalogo_normalizadas,
    tamano_region_en_imagen,
)


SRS_EJEMPLO = """\
Solar Region Summary
:Issued: 2026 Jul 10 0030 UTC
I.  Regions with Sunspots.  Locations Valid at 09/2400Z
Nmbr Location  Lo  Area  Z   LL   NN Mag Type
4482 S11E45   123  100 Dso  05   09 Beta-Gamma
4485 N08W32   080  220 Dkc  12   12 Beta-Gamma
IA. H-alpha Plages without Spots.
"""


class CatalogoRegionesTest(unittest.TestCase):
    def setUp(self):
        self.regiones = analizar_srs(
            SRS_EJEMPLO,
            date(2026, 7, 9),
        )

    def test_este_y_oeste_conservan_signos_opuestos(self):
        por_numero = {
            region.numero: region
            for region in self.regiones
        }
        self.assertEqual(por_numero["14482"].cmd, -45.0)
        self.assertEqual(por_numero["14485"].cmd, 32.0)

        instante = datetime(
            2026,
            7,
            10,
            tzinfo=timezone.utc,
        )
        este = coordenadas_catalogo_normalizadas(
            por_numero["14482"],
            instante,
        )
        oeste = coordenadas_catalogo_normalizadas(
            por_numero["14485"],
            instante,
        )
        self.assertLess(este[0], 0)
        self.assertGreater(oeste[0], 0)

    def test_extension_noaa_controla_el_tamano_de_marca(self):
        por_numero = {
            region.numero: region
            for region in self.regiones
        }
        pequena = tamano_region_en_imagen(
            por_numero["14482"],
            450,
        )
        grande = tamano_region_en_imagen(
            por_numero["14485"],
            450,
        )
        self.assertGreater(grande[0], pequena[0])
        self.assertGreater(grande[1], pequena[1])


if __name__ == "__main__":
    unittest.main()
