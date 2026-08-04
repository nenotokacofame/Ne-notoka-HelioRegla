from dataclasses import dataclass
from datetime import date, datetime
from math import cos, pi, radians, tan
from pathlib import Path

from PIL import ExifTags, Image
from PySide6.QtCore import QDate, QSettings
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from i18n import tr


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
    escala_limbo: float | None = None
    diferencia_pct: float | None = None
    usar_escala_equipo: bool = True


UMBRAL_REVISION_PORCENTAJE = 5.0
UMBRAL_CRITICO_PORCENTAJE = 15.0


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
            valor_binning = _numero(
                _buscar(
                    encabezado,
                    ("XBINNING", "BINNING"),
                )
            )
            datos.binning = (
                int(valor_binning)
                if valor_binning is not None
                else None
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
            valor_binning = _numero(
                _buscar(
                    combinados,
                    ("XBINNING", "BINNING"),
                )
            )
            datos.binning = (
                int(valor_binning)
                if valor_binning is not None
                else None
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
        self.usar_escala_equipo = True
        self.metadatos = leer_metadatos(ruta_imagen)
        self.ajustes = QSettings(
            "Ne-notoka Cofame",
            "Ne-notoka HelioRegla",
        )

        self.setWindowTitle(tr("equipment_dialog"))
        self.setMinimumWidth(520)

        self.crear_interfaz()
        self.cargar_ultimos_datos()
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

        grupo = QGroupBox(tr("calibration_data"))
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

        formulario.addRow(tr("pixel_size"), self.pixel)
        formulario.addRow(tr("effective_focal"), self.focal)
        formulario.addRow(tr("binning"), self.binning)
        formulario.addRow(
            tr("final_image_size"),
            self.redimension,
        )
        formulario.addRow(tr("capture_date"), self.fecha)

        principal.addWidget(grupo)

        self.resultados = QLabel()
        self.resultados.setWordWrap(True)
        self.resultados.setStyleSheet(
            "padding: 12px; border: 1px solid #44596c;"
            "border-radius: 5px;"
        )
        principal.addWidget(self.resultados)

        detectar = QPushButton(tr("reread_metadata"))
        detectar.clicked.connect(self.cargar_metadatos)
        principal.addWidget(detectar)

        botones = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        botones.button(QDialogButtonBox.Ok).setText(tr("ok"))
        botones.button(QDialogButtonBox.Cancel).setText(
            tr("cancel")
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
            f"\n{tr('equipment')}: {datos.equipo}"
            if datos.equipo
            else ""
        )
        fuentes = {
            "Encabezado FITS": tr("metadata_fits"),
            "EXIF/metadatos de imagen": tr("metadata_exif"),
            "Sin metadatos técnicos reconocidos": (
                tr("no_metadata")
            ),
            "Sin metadatos reconocidos": tr("no_metadata"),
        }
        fuente = fuentes.get(datos.fuente, datos.fuente)
        self.info_metadatos.setText(
            f"{tr('source')}: {fuente}{equipo}\n"
            f"{tr('verify_values')}"
        )
        self.calcular()

    def cargar_ultimos_datos(self):
        self.pixel.setValue(
            self.ajustes.value(
                "calibracion/pixel_um",
                2.9,
                type=float,
            )
        )
        self.focal.setValue(
            self.ajustes.value(
                "calibracion/focal_mm",
                250.0,
                type=float,
            )
        )
        self.binning.setValue(
            self.ajustes.value(
                "calibracion/binning",
                1,
                type=int,
            )
        )
        self.redimension.setValue(
            self.ajustes.value(
                "calibracion/redimension",
                100.0,
                type=float,
            )
        )

    def guardar_datos_equipo(self):
        self.ajustes.setValue(
            "calibracion/pixel_um",
            self.pixel.value(),
        )
        self.ajustes.setValue(
            "calibracion/focal_mm",
            self.focal.value(),
        )
        self.ajustes.setValue(
            "calibracion/binning",
            self.binning.value(),
        )
        self.ajustes.setValue(
            "calibracion/redimension",
            self.redimension.value(),
        )
        self.ajustes.sync()

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
                tr("enter_pixel_focal")
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
            f"{tr('image_word')} "
            f"{self.redimension.value():.1f}%"
        )

        comparacion = ""
        diferencia_pct = None

        if self.escala_limbo:
            diferencia_pct = (
                (km_px - self.escala_limbo)
                / self.escala_limbo
                * 100
            )
            comparacion = (
                f"\n{tr('limb_scale')}: "
                f"{self.escala_limbo:,.2f} km/px"
                f"\n{tr('difference')}: {diferencia_pct:+.2f}%"
            )
            if abs(diferencia_pct) > UMBRAL_REVISION_PORCENTAJE:
                comparacion += f"\n{tr('calibration_review')}"

        self.resultado = ResultadoCalibracion(
            km_por_pixel=km_px,
            arcsec_por_pixel=arcsec_px,
            distancia_sol_km=distancia,
            metodo=tr("optical_data"),
            descripcion=descripcion,
            escala_limbo=self.escala_limbo,
            diferencia_pct=diferencia_pct,
            usar_escala_equipo=self.usar_escala_equipo,
        )

        self.resultados.setText(
            f"{tr('angular_scale')}: "
            f"{arcsec_px:.5f} ″/px\n"
            f"{tr('sun_distance')}: {distancia:,.0f} km\n"
            f"{tr('physical_scale')}: {km_px:,.2f} km/px"
            f"{comparacion}"
        )
        self.actualizar_estilo_resultados()

    def actualizar_estilo_resultados(self):
        diferencia = (
            self.resultado.diferencia_pct
            if self.resultado is not None
            else None
        )
        if diferencia is None:
            color = "#AFC7D3"
            fondo = "#F0F7FA"
        elif abs(diferencia) > UMBRAL_CRITICO_PORCENTAJE:
            color = "#B42318"
            fondo = "#FDECEC"
        elif abs(diferencia) > UMBRAL_REVISION_PORCENTAJE:
            color = "#A15C00"
            fondo = "#FFF4CF"
        else:
            color = "#2E7D32"
            fondo = "#EEF8EF"

        self.resultados.setStyleSheet(
            "padding: 12px; border: 1px solid "
            f"{color}; border-left: 4px solid {color}; "
            f"border-radius: 5px; background-color: {fondo};"
        )

    def aceptar(self):
        self.calcular()

        if self.resultado is not None:
            diferencia = self.resultado.diferencia_pct
            if (
                diferencia is not None
                and abs(diferencia) > UMBRAL_CRITICO_PORCENTAJE
            ):
                mensaje = QMessageBox(self)
                mensaje.setIcon(QMessageBox.Warning)
                mensaje.setWindowTitle(
                    tr("calibration_mismatch_title")
                )
                mensaje.setText(
                    tr(
                        "calibration_mismatch_text",
                        difference=f"{diferencia:+.1f}",
                        limb=f"{self.escala_limbo:,.1f}",
                        equipment=(
                            f"{self.resultado.km_por_pixel:,.1f}"
                        ),
                    )
                )
                boton_equipo = mensaje.addButton(
                    tr("calibration_use_equipment"),
                    QMessageBox.AcceptRole,
                )
                boton_limbo = mensaje.addButton(
                    tr("calibration_use_limb"),
                    QMessageBox.DestructiveRole,
                )
                boton_cancelar = mensaje.addButton(
                    tr("calibration_keep_editing"),
                    QMessageBox.RejectRole,
                )
                mensaje.exec()

                if mensaje.clickedButton() is boton_cancelar:
                    return
                self.usar_escala_equipo = (
                    mensaje.clickedButton() is boton_equipo
                )
                self.resultado.usar_escala_equipo = (
                    self.usar_escala_equipo
                )

            self.guardar_datos_equipo()
            self.accept()
