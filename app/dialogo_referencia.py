from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from i18n import tr


class VisorReferencia(QGraphicsView):
    def __init__(self, ruta_imagen, parent=None):
        super().__init__(parent)
        self.escena = QGraphicsScene(self)
        self.setScene(self.escena)
        self.pixmap = QPixmap(str(Path(ruta_imagen)))
        self.elemento = QGraphicsPixmapItem(self.pixmap)
        self.escena.addItem(self.elemento)
        self.escena.setSceneRect(self.elemento.boundingRect())
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.factor_zoom = 1.0

    def ajustar(self):
        if self.pixmap.isNull():
            return
        self.resetTransform()
        self.fitInView(
            self.elemento,
            Qt.KeepAspectRatio,
        )
        self.factor_zoom = self.transform().m11()

    def tamano_real(self):
        self.resetTransform()
        self.factor_zoom = 1.0

    def wheelEvent(self, event):
        factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        nuevo = self.transform().m11() * factor
        if 0.08 <= nuevo <= 12.0:
            self.scale(factor, factor)
            self.factor_zoom = nuevo
        event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        if self.factor_zoom == 1.0:
            self.ajustar()


class DialogoReferenciaSolar(QDialog):
    def __init__(
        self,
        ruta_imagen,
        fuente,
        detalle_alineacion="",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("solar_reference_title"))
        self.resize(980, 860)

        principal = QVBoxLayout(self)
        explicacion = QLabel(
            tr(
                "solar_reference_text",
                source=fuente,
            )
        )
        explicacion.setWordWrap(True)
        principal.addWidget(explicacion)

        if detalle_alineacion:
            detalle = QLabel(detalle_alineacion)
            detalle.setWordWrap(True)
            detalle.setObjectName("informacion")
            principal.addWidget(detalle)

        controles = QHBoxLayout()
        boton_ajustar = QPushButton(tr("fit_window"))
        boton_real = QPushButton(tr("actual_size"))
        controles.addWidget(boton_ajustar)
        controles.addWidget(boton_real)
        controles.addStretch()
        controles.addWidget(QLabel(tr("solar_reference_zoom_tip")))
        principal.addLayout(controles)

        self.visor = VisorReferencia(ruta_imagen)
        boton_ajustar.clicked.connect(self.visor.ajustar)
        boton_real.clicked.connect(self.visor.tamano_real)
        principal.addWidget(self.visor, 1)

        nota = QLabel(tr("solar_reference_note"))
        nota.setWordWrap(True)
        principal.addWidget(nota)

        botones = QDialogButtonBox(QDialogButtonBox.Close)
        botones.button(QDialogButtonBox.Close).setText(
            tr("close")
        )
        botones.rejected.connect(self.reject)
        principal.addWidget(botones)
