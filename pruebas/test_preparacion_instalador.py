import unittest
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


class PreparacionInstaladorTests(unittest.TestCase):
    def leer(self, ruta):
        return (BASE / ruta).read_text(encoding="utf-8")

    def test_identidad_licencia_y_donativo(self):
        main = self.leer("app/main.py")
        acerca = self.leer("app/acerca_de.py")
        licencia = self.leer("LICENSE")

        self.assertIn('VERSION = "1.2.0"', main)
        self.assertIn('AUTOR = "David Olivos S."', acerca)
        self.assertIn(
            'URL_DONATIVOS = "https://paypal.me/nenotokacofame"',
            acerca,
        )
        self.assertIn(
            "LICENCIA DE USO GRATUITO NE-NOTOKA HELIOREGLA 1.0",
            licencia,
        )
        self.assertNotIn("GNU GENERAL PUBLIC LICENSE", licencia)

    def test_recursos_funcionan_con_pyinstaller(self):
        main = self.leer("app/main.py")
        spec = self.leer("Ne-notoka_HelioRegla.spec")

        self.assertIn('getattr(sys, "frozen", False)', main)
        self.assertIn('"_MEIPASS"', main)
        for recurso in (
            '"assets"',
            '"docs"',
            '"licencias_terceros"',
            '"LICENSE"',
            '"THIRD_PARTY_NOTICES.txt"',
        ):
            self.assertIn(recurso, spec)

    def test_configuracion_del_instalador(self):
        inno = self.leer("instalador/Ne-notoka_HelioRegla.iss")

        esperados = (
            '#define MyAppVersion "1.2.0"',
            "PrivilegesRequired=lowest",
            "MinVersion=10.0",
            "LicenseFile=..\\LICENSE",
            "SetupIconFile=..\\assets\\icono_ne_notoka.ico",
            'Name: "spanish"',
            'Name: "english"',
            "{userdesktop}",
            "Ne-notoka_HelioRegla_1.2.0_Setup",
        )
        for fragmento in esperados:
            self.assertIn(fragmento, inno)

    def test_constructor_ejecuta_pruebas_y_compiladores(self):
        constructor = self.leer("crear_instalador_windows.bat")

        self.assertIn("unittest discover -s pruebas -v", constructor)
        self.assertIn("PyInstaller --noconfirm --clean", constructor)
        self.assertIn("JRSoftware.InnoSetup", constructor)
        self.assertIn('"%ISCC%"', constructor)
        self.assertIn(
            "dist_instalador\\Ne-notoka_HelioRegla_1.2.0_Setup.exe",
            constructor,
        )


if __name__ == "__main__":
    unittest.main()
