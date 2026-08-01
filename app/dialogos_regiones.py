from datetime import datetime, timezone

from PySide6.QtCore import QDate, QDateTime, QTime, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDateTimeEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from i18n import tr


class DialogoConsultaRegiones(QDialog):
    def __init__(
        self,
        instante,
        fuente_fecha,
        rotacion=0.0,
        espejo_horizontal=False,
        espejo_vertical=False,
        mostrar_manchas=True,
        fuente_referencia="automatica",
        puede_alinear=True,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("catalog_dialog_title"))
        self.setMinimumWidth(580)

        principal = QVBoxLayout(self)
        clave_fuente = getattr(
            fuente_fecha,
            "clave",
            str(fuente_fecha),
        )
        detalle_fuente = getattr(
            fuente_fecha,
            "detalle",
            "",
        )
        texto_fuente = tr(
            f"date_source_{clave_fuente}",
            fragment=detalle_fuente,
        )
        explicacion = QLabel(
            tr(
                "catalog_dialog_explanation",
                source=texto_fuente,
            )
        )
        explicacion.setWordWrap(True)
        principal.addWidget(explicacion)

        grupo = QGroupBox(tr("catalog_query_data"))
        formulario = QFormLayout(grupo)

        self.fecha_hora = QDateTimeEditUTC(instante)
        self.rotacion = QDoubleSpinBox()
        self.rotacion.setRange(-180.0, 180.0)
        self.rotacion.setDecimals(1)
        self.rotacion.setSingleStep(1.0)
        self.rotacion.setSuffix("°")
        self.rotacion.setValue(float(rotacion))

        self.espejo_horizontal = QCheckBox(
            tr("mirror_horizontal")
        )
        self.espejo_horizontal.setChecked(
            bool(espejo_horizontal)
        )
        self.espejo_vertical = QCheckBox(
            tr("mirror_vertical")
        )
        self.espejo_vertical.setChecked(
            bool(espejo_vertical)
        )
        self.mostrar_manchas = QCheckBox(
            tr("include_spot_count")
        )
        self.mostrar_manchas.setChecked(bool(mostrar_manchas))
        self.alinear_automaticamente = QCheckBox(
            tr("automatic_catalog_alignment")
        )
        self.alinear_automaticamente.setChecked(
            bool(puede_alinear)
        )
        self.alinear_automaticamente.setEnabled(
            bool(puede_alinear)
        )

        # La orientación manual debe tener prioridad explícita. Antes se
        # podían marcar los espejos, pero la alineación automática seguía
        # activa y reemplazaba esos valores al consultar el catálogo, dando
        # la impresión de que las casillas no hacían nada.
        self.rotacion.valueChanged.connect(
            self._orientacion_manual_editada
        )
        self.espejo_horizontal.stateChanged.connect(
            self._orientacion_manual_editada
        )
        self.espejo_vertical.stateChanged.connect(
            self._orientacion_manual_editada
        )
        self.fuente_referencia = QComboBox()
        for clave, texto in (
            ("automatica", tr("reference_source_auto")),
            ("gong_halpha", tr("reference_source_halpha")),
            ("hmi_continuum", tr("reference_source_continuum")),
            ("aia_1700", tr("reference_source_cak_proxy")),
        ):
            self.fuente_referencia.addItem(texto, clave)
        indice_fuente = self.fuente_referencia.findData(
            fuente_referencia
        )
        self.fuente_referencia.setCurrentIndex(
            max(0, indice_fuente)
        )

        formulario.addRow(
            tr("capture_datetime_utc"),
            self.fecha_hora,
        )
        formulario.addRow(
            tr("solar_north_rotation"),
            self.rotacion,
        )
        formulario.addRow("", self.espejo_horizontal)
        formulario.addRow("", self.espejo_vertical)
        formulario.addRow(
            tr("reference_wavelength"),
            self.fuente_referencia,
        )
        formulario.addRow("", self.alinear_automaticamente)
        formulario.addRow("", self.mostrar_manchas)
        principal.addWidget(grupo)

        nota = QLabel(tr("catalog_orientation_note"))
        nota.setWordWrap(True)
        nota.setObjectName("informacion")
        principal.addWidget(nota)

        botones = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        botones.button(QDialogButtonBox.Ok).setText(
            tr("query_catalogs")
        )
        botones.button(QDialogButtonBox.Cancel).setText(
            tr("cancel")
        )
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        principal.addWidget(botones)

    def _orientacion_manual_editada(self, _valor=None):
        if self.alinear_automaticamente.isChecked():
            self.alinear_automaticamente.setChecked(False)

    def instante_utc(self):
        fecha = self.fecha_hora.date()
        hora = self.fecha_hora.time()
        return datetime(
            fecha.year(),
            fecha.month(),
            fecha.day(),
            hora.hour(),
            hora.minute(),
            hora.second(),
            tzinfo=timezone.utc,
        )


class QDateTimeEditUTC(QDateTimeEdit):
    def __init__(self, instante):
        super().__init__()
        instante = instante.astimezone(timezone.utc)
        # QDateTimeEdit adopta de forma predeterminada la zona local
        # del sistema. Fijar UTC antes de asignar el valor evita que
        # Windows convierta, por ejemplo, 22:18 UTC en 16:18 CST.
        self.setTimeSpec(Qt.TimeSpec.UTC)
        self.setDateTime(
            QDateTime(
                QDate(
                    instante.year,
                    instante.month,
                    instante.day,
                ),
                QTime(
                    instante.hour,
                    instante.minute,
                    instante.second,
                ),
                Qt.TimeSpec.UTC,
            )
        )
        self.setDisplayFormat("yyyy-MM-dd HH:mm:ss 'UTC'")
        self.setCalendarPopup(True)


class DialogoResultadosRegiones(QDialog):
    def __init__(
        self,
        regiones,
        errores=None,
        detalle_alineacion="",
        parent=None,
    ):
        super().__init__(parent)
        self.regiones = list(regiones)
        self.setWindowTitle(tr("catalog_results_title"))
        self.resize(780, 460)

        principal = QVBoxLayout(self)
        descripcion = QLabel(
            tr(
                "catalog_results_text",
                count=len(self.regiones),
            )
        )
        descripcion.setWordWrap(True)
        principal.addWidget(descripcion)

        if detalle_alineacion:
            alineacion = QLabel(detalle_alineacion)
            alineacion.setWordWrap(True)
            alineacion.setObjectName("informacion")
            principal.addWidget(alineacion)

        self.tabla = QTableWidget(len(self.regiones), 7)
        self.tabla.setHorizontalHeaderLabels(
            [
                tr("add"),
                tr("active_region"),
                tr("location"),
                tr("spot_count"),
                tr("area"),
                tr("magnetic_classification"),
                tr("source"),
            ]
        )
        self.tabla.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        self.tabla.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        for fila, region in enumerate(self.regiones):
            agregar = QTableWidgetItem()
            agregar.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
            )
            agregar.setCheckState(Qt.Checked)
            self.tabla.setItem(fila, 0, agregar)

            valores = (
                region.nombre,
                region.ubicacion or "—",
                (
                    str(region.manchas)
                    if region.manchas is not None
                    else "—"
                ),
                (
                    str(region.area)
                    if region.area is not None
                    else "—"
                ),
                region.clase_magnetica or "—",
                region.fuentes or "HEK",
            )
            for columna, valor in enumerate(valores, start=1):
                self.tabla.setItem(
                    fila,
                    columna,
                    QTableWidgetItem(valor),
                )

        self.tabla.resizeColumnsToContents()
        self.tabla.horizontalHeader().setStretchLastSection(True)
        principal.addWidget(self.tabla)

        if errores:
            advertencia = QLabel(
                tr(
                    "catalog_partial_warning",
                    details="\n".join(errores),
                )
            )
            advertencia.setWordWrap(True)
            advertencia.setObjectName("informacion")
            principal.addWidget(advertencia)

        botones = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        botones.button(QDialogButtonBox.Ok).setText(
            tr("use_selected_regions")
        )
        botones.button(QDialogButtonBox.Cancel).setText(
            tr("cancel")
        )
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        principal.addWidget(botones)

    def seleccionadas(self):
        return [
            region
            for fila, region in enumerate(self.regiones)
            if self.tabla.item(fila, 0).checkState() == Qt.Checked
        ]
