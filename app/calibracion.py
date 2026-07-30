from dataclasses import dataclass
from datetime import date, datetime
from math import cos, pi, radians, tan
from pathlib import Path

from PIL import ExifTags, Image
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


AU_KM = 149_597_870.7


@dataclass
class MetadatosEquipo:
    pixel_um: float | None = None
    focal_mm: float | None = None
    binning: int | None = None
    escala_arcsec: float | None = None
    fecha: date | None = None
    equipo: str = ""
    fuente: str = "Sin metadatos reconocidos"


@dataclass
class ResultadoCalibracion:
    km_por_pixel: float
    arcsec_por_pixel: float
    distancia_sol_km: float
    metodo: str
    descripcion: str


def _numero(valor):
    if valor is None:
        return None

    try:
        if isinstance(valor, tuple) and len(valor) == 2:
            return float(valor[0]) / float(valor[1])
        return float(valor)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _fecha(valor):
    if not valor:
        return None

    texto = str(valor).strip().replace("Z", "")

    formatos = (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d",
    )

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue

    return None


def _buscar(diccionario, nombres):
    normalizado = {
        str(clave).upper().replace("-", "").replace("_", ""): valor
        for clave, valor in diccionario.items()
    }

    for nombre in nombres:
        clave = nombre.upper().replace("-", "").replace("_", "")
        if clave in normalizado:
            return normalizado[clave]

    return None


def leer_metadatos(ruta):
    ruta = Path(ruta)
    datos = MetadatosEquipo()
    sufijo = ruta.suffix.lower()

    if sufijo in {".fit", ".fits", ".fts"}:
        try:
            from astropy.io import fits

            encabezado = dict(fits.getheader(ruta))

            datos.pixel_um = _numero(
                _buscar(
                    encabezado,
                    ("XPIXSZ", "PIXSIZE1", "PIXELSIZE"),
                )
            )
            datos.focal_mm = _numero(
                _buscar(
                    encabezado,
                    ("FOCALLEN", "FOCALLENGTH", "FOCAL"),
                )
            )
            datos.binning = int(
                _numero(
                    _buscar(
                        encabezado,
                        ("XBINNING", "BINNING"),
                    )
                )
                or 1
            )
            datos.escala_arcsec = _numero(
                _buscar(
                    encabezado,
                    ("PIXSCALE", "SECPIX", "CDELT1"),
                )
            )

            if datos.escala_arcsec is not None:
                datos.escala_arcsec = abs(datos.escala_arcsec)

                # CDELT suele estar expresado en grados por píxel.
                if datos.escala_arcsec < 0.01:
                    datos.escala_arcsec *= 3600

            datos.fecha = _fecha(
                _buscar(encabezado, ("DATE-OBS", "DATEOBS"))
            )
            datos.equipo = str(
                _buscar(
                    encabezado,
                    ("INSTRUME", "CAMERA", "TELESCOP"),
                )
                or ""
            )
            datos.fuente = "Encabezado FITS"
            return datos
        except Exception:
            pass

    try:
        with Image.open(ruta) as imagen:
            exif_crudo = imagen.getexif()
            exif = {
                ExifTags.TAGS.get(clave, clave): valor
                for clave, valor in exif_crudo.items()
            }
            adicionales = dict(imagen.info)
            combinados = {**adicionales, **exif}

            datos.focal_mm = _numero(
                _buscar(
                    combinados,
                    ("FocalLength", "FOCALLEN", "FOCAL"),
                )
            )
            datos.pixel_um = _numero(
                _buscar(
                    combinados,
                    ("XPIXSZ", "PIXSIZE", "PIXELSIZE"),
                )
            )
            datos.binning = int(
                _numero(
                    _buscar(
                        combinados,
                        ("XBINNING", "BINNING"),
                    )
                )
                or 1
            )
            datos.escala_arcsec = _numero(
                _buscar(
                    combinados,
                    ("PIXSCALE", "SECPIX"),
                )
            )
            datos.fecha = _fecha(
                _buscar(
                    combinados,
                    (
                        "DateTimeOriginal",
                        "DateTimeDigitized",
                        "DATE-OBS",
                    ),
                )
            )

            fabricante = str(exif.get("Make", "")).strip()
            modelo = str(exif.get("Model", "")).strip()
            datos.equipo = " ".join(
                parte for parte in (fabricante, modelo) if parte
            )

            encontrados = any(
                (
                    datos.pixel_um,
                    datos.focal_mm,
                    datos.escala_arcsec,
                    datos.fecha,
                    datos.equipo,
                )
            )
            datos.fuente = (
                "EXIF/metadatos de imagen"
                if encontrados
                else "Sin metadatos técnicos reconocidos"
            )
    except Exception:
        pass

    return datos


def distancia_sol_km(fecha):
    inicio = date(fecha.year, 1, 1)
    dia_ano = (fecha - inicio).days + 1

    # Aproximación orbital con precisión suficiente para esta escala.
    anomalia = radians(357.529 + 0.98560028 * dia_ano)
    distancia_au = (
        1.00014
        - 0.01671 * cos(anomalia)
        - 0.00014 * cos(2 * anomalia)
    )

    return distancia_au * AU_KM


class DialogoCalibracion(QDialog):
    def __init__(
        self,
        ruta_imagen,
        escala_limbo=None,
        parent=None,
    ):
        super().__init__(parent)

        self.ruta_imagen = ruta_imagen
        self.escala_limbo = escala_limbo
        self.resultado = None
        self.metadatos = leer_metadatos(ruta_imagen)

        self.setWindowTitle("Calibración mediante el equipo")
        self.setMinimumWidth(520)

        self.crear_interfaz()
        self.cargar_metadatos()
        self.calcular()

    def crear_decimal(self, minimo, maximo, decimales, sufijo):
        control = QDoubleSpinBox()
        control.setRange(minimo, maximo)
        control.setDecimals(decimales)
        control.setSuffix(sufijo)
        control.setKeyboardTracking(False)
        control.valueChanged.connect(self.calcular)
        return control

    def crear_interfaz(self):
        principal = QVBoxLayout(self)

        self.info_metadatos = QLabel()
        self.info_metadatos.setWordWrap(True)
        principal.addWidget(self.info_metadatos)

        grupo = QGroupBox("Datos de calibración")
        formulario = QFormLayout(grupo)


        self.pixel = self.crear_decimal(
            0.01, 100.0, 4, " µm"
        )
        self.focal = self.crear_decimal(
            0.1, 100_000.0, 2, " mm"
        )

        self.binning = QSpinBox()
        self.binning.setRange(1, 16)
        self.binning.setValue(1)
        self.binning.valueChanged.connect(self.calcular)

        self.redimension = self.crear_decimal(
            1.0, 1000.0, 2, " %"
        )
        self.redimension.setValue(100)


        self.fecha = QDateEdit()
        self.fecha.setCalendarPopup(True)
        self.fecha.setDate(QDate.currentDate())
        self.fecha.dateChanged.connect(self.calcular)

        formulario.addRow("Tamaño de píxel:", self.pixel)
        formulario.addRow("Focal efectiva:", self.focal)
        formulario.addRow("Binning:", self.binning)
        formulario.addRow(
            "Tamaño final de imagen:",
            self.redimension,
        )
        formulario.addRow("Fecha de captura:", self.fecha)

        principal.addWidget(grupo)

        self.resultados = QLabel()
        self.resultados.setWordWrap(True)
        self.resultados.setStyleSheet(
            "padding: 12px; border: 1px solid #44596c;"
            "border-radius: 5px;"
        )
        principal.addWidget(self.resultados)

        detectar = QPushButton("Volver a leer metadatos")
        detectar.clicked.connect(self.cargar_metadatos)
        principal.addWidget(detectar)

        botones = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        botones.accepted.connect(self.aceptar)
        botones.rejected.connect(self.reject)
        principal.addWidget(botones)

    def cargar_metadatos(self):
        datos = leer_metadatos(self.ruta_imagen)
        self.metadatos = datos

        if datos.pixel_um:
            self.pixel.setValue(datos.pixel_um)
        if datos.focal_mm:
            self.focal.setValue(datos.focal_mm)
        if datos.binning:
            self.binning.setValue(datos.binning)
        if datos.fecha:
            self.fecha.setDate(
                QDate(
                    datos.fecha.year,
                    datos.fecha.month,
                    datos.fecha.day,
                )
            )

        equipo = (
            f"\nEquipo: {datos.equipo}"
            if datos.equipo
            else ""
        )
        self.info_metadatos.setText(
            f"Fuente: {datos.fuente}{equipo}\n"
            "Verifica siempre los valores: algunos programas "
            "conservan la focal original aunque la imagen haya "
            "sido redimensionada."
        )
        self.calcular()

    def calcular(self):
        fecha_qt = self.fecha.date()
        fecha_python = date(
            fecha_qt.year(),
            fecha_qt.month(),
            fecha_qt.day(),
        )
        distancia = distancia_sol_km(fecha_python)

        pixel = self.pixel.value()
        focal = self.focal.value()
        binning = self.binning.value()
        proporcion = self.redimension.value() / 100

        if pixel <= 0 or focal <= 0 or proporcion <= 0:
            self.resultado = None
            self.resultados.setText(
                "Introduce tamaño de píxel y focal efectiva."
            )
            return

        radianes_px = (
            pixel * binning
            / (focal * 1000 * proporcion)
        )
        arcsec_px = radianes_px * 206_264.806
        km_px = tan(radianes_px) * distancia

        descripcion = (
            f"{pixel:.4f} µm · {focal:.2f} mm · "
            f"binning {binning} · "
            f"imagen {self.redimension.value():.1f}%"
        )

        comparacion = ""

        if self.escala_limbo:
            diferencia = (
                (km_px - self.escala_limbo)
                / self.escala_limbo
                * 100
            )
            comparacion = (
                f"\nEscala por limbo: "
                f"{self.escala_limbo:,.2f} km/px"
                f"\nDiferencia: {diferencia:+.2f}%"
            )

        self.resultado = ResultadoCalibracion(
            km_por_pixel=km_px,
            arcsec_por_pixel=arcsec_px,
            distancia_sol_km=distancia,
            metodo="Datos ópticos del equipo",
            descripcion=descripcion,
        )

        self.resultados.setText(
            f"Escala angular: {arcsec_px:.5f} ″/px\n"
            f"Distancia al Sol: {distancia:,.0f} km\n"
            f"Escala física: {km_px:,.2f} km/px"
            f"{comparacion}"
        )

    def aceptar(self):
        self.calcular()

        if self.resultado is not None:
            self.accept()
