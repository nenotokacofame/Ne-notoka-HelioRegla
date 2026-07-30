import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


NOMBRE_APLICACION = "Ne-notoka HelioRegla"
VERSION = "0.1.0"


class VisorSolar(QGraphicsView):
    imagen_cargada = Signal(str)

    def __init__(self):
        super().__init__()

        self.escena = QGraphicsScene(self)
        self.setScene(self.escena)

        self.elemento_imagen = None
        self.ruta_imagen = None
        self.factor_zoom = 1.0

        self.setAcceptDrops(True)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setBackgroundBrush(Qt.black)
        self.setFrameShape(QFrame.NoFrame)

    def cargar_imagen(self, ruta):
        pixmap = QPixmap(ruta)

        if pixmap.isNull():
            QMessageBox.warning(
                self,
                "No se pudo abrir",
                "El archivo seleccionado no contiene una imagen compatible.",
            )
            return False

        self.escena.clear()
        self.elemento_imagen = QGraphicsPixmapItem(pixmap)
        self.escena.addItem(self.elemento_imagen)
        self.escena.setSceneRect(self.elemento_imagen.boundingRect())

        self.ruta_imagen = ruta
        self.factor_zoom = 1.0
        self.ajustar_ventana()
        self.imagen_cargada.emit(ruta)
        return True

    def ajustar_ventana(self):
        if self.elemento_imagen is None:
            return

        self.resetTransform()
        self.fitInView(
            self.elemento_imagen.boundingRect(),
            Qt.KeepAspectRatio,
        )
        self.factor_zoom = 1.0

    def tamano_real(self):
        if self.elemento_imagen is None:
            return

        self.resetTransform()
        self.factor_zoom = 1.0

    def wheelEvent(self, event):
        if self.elemento_imagen is None:
            return

        if event.angleDelta().y() > 0:
            factor = 1.20
        else:
            factor = 1 / 1.20

        nuevo_zoom = self.factor_zoom * factor

        if 0.05 <= nuevo_zoom <= 40:
            self.scale(factor, factor)
            self.factor_zoom = nuevo_zoom

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()

        if not urls:
            return

        ruta = urls[0].toLocalFile()
        extensiones = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

        if Path(ruta).suffix.lower() not in extensiones:
            QMessageBox.information(
                self,
                "Formato no compatible",
                "Por ahora puedes abrir PNG, JPEG, BMP y TIFF.",
            )
            return

        self.cargar_imagen(ruta)
        event.acceptProposedAction()


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"{NOMBRE_APLICACION} — {VERSION}")
        self.resize(1400, 850)
        self.setMinimumSize(1000, 650)

        self.visor = VisorSolar()
        self.visor.imagen_cargada.connect(self.actualizar_informacion)

        self.crear_interfaz()
        self.crear_barra_herramientas()
        self.crear_estado()
        self.aplicar_estilo()

    def crear_interfaz(self):
        contenedor = QWidget()
        distribucion = QHBoxLayout(contenedor)
        distribucion.setContentsMargins(0, 0, 0, 0)
        distribucion.setSpacing(0)

        panel = QFrame()
        panel.setObjectName("panelLateral")
        panel.setFixedWidth(285)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 24, 22, 24)
        panel_layout.setSpacing(14)

        titulo = QLabel("Ne-notoka")
        titulo.setObjectName("marca")

        subtitulo = QLabel("HELIOREGLA")
        subtitulo.setObjectName("nombreAplicacion")

        descripcion = QLabel(
            "Medición, comparación y etiquetado de imágenes solares."
        )
        descripcion.setWordWrap(True)
        descripcion.setObjectName("descripcion")

        self.boton_abrir = QPushButton("Abrir imagen solar")
        self.boton_abrir.setObjectName("botonPrincipal")
        self.boton_abrir.clicked.connect(self.abrir_imagen)

        self.etiqueta_archivo = QLabel("Ninguna imagen cargada")
        self.etiqueta_archivo.setWordWrap(True)
        self.etiqueta_archivo.setObjectName("informacion")

        separador = QFrame()
        separador.setFrameShape(QFrame.HLine)
        separador.setObjectName("separador")

        proximamente = QLabel(
            "Próximas herramientas\n\n"
            "○ Ajuste del limbo\n"
            "↔ Regla solar\n"
            "⌖ Medición de estructuras\n"
            "● Comparación planetaria\n"
            "🏷 Etiquetado de regiones"
        )
        proximamente.setObjectName("proximamente")
        proximamente.setWordWrap(True)

        ayuda = QLabel(
            "Rueda: zoom\n"
            "Arrastrar: desplazar\n"
            "También puedes soltar una imagen."
        )
        ayuda.setObjectName("ayuda")

        panel_layout.addWidget(titulo)
        panel_layout.addWidget(subtitulo)
        panel_layout.addWidget(descripcion)
        panel_layout.addSpacing(8)
        panel_layout.addWidget(self.boton_abrir)
        panel_layout.addWidget(self.etiqueta_archivo)
        panel_layout.addWidget(separador)
        panel_layout.addWidget(proximamente)
        panel_layout.addStretch()
        panel_layout.addWidget(ayuda)

        zona_visor = QWidget()
        zona_layout = QVBoxLayout(zona_visor)
        zona_layout.setContentsMargins(18, 18, 18, 18)

        encabezado = QLabel("Área de trabajo solar")
        encabezado.setObjectName("encabezado")

        zona_layout.addWidget(encabezado)
        zona_layout.addWidget(self.visor, 1)

        distribucion.addWidget(panel)
        distribucion.addWidget(zona_visor, 1)

        self.setCentralWidget(contenedor)

    def crear_barra_herramientas(self):
        barra = QToolBar("Herramientas principales")
        barra.setMovable(False)
        self.addToolBar(barra)

        accion_abrir = QAction("Abrir", self)
        accion_abrir.setShortcut(QKeySequence.Open)
        accion_abrir.triggered.connect(self.abrir_imagen)

        accion_ajustar = QAction("Ajustar a ventana", self)
        accion_ajustar.setShortcut("F")
        accion_ajustar.triggered.connect(self.visor.ajustar_ventana)

        accion_real = QAction("Tamaño real", self)
        accion_real.setShortcut("1")
        accion_real.triggered.connect(self.visor.tamano_real)

        barra.addAction(accion_abrir)
        barra.addSeparator()
        barra.addAction(accion_ajustar)
        barra.addAction(accion_real)

    def crear_estado(self):
        estado = QStatusBar()
        estado.showMessage("Listo para abrir una imagen solar")
        self.setStatusBar(estado)

    def abrir_imagen(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir imagen solar",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;"
            "Todos los archivos (*)",
        )

        if ruta:
            self.visor.cargar_imagen(ruta)

    def actualizar_informacion(self, ruta):
        archivo = Path(ruta)
        pixmap = self.visor.elemento_imagen.pixmap()

        self.etiqueta_archivo.setText(
            f"{archivo.name}\n"
            f"{pixmap.width()} × {pixmap.height()} píxeles"
        )
        self.statusBar().showMessage(f"Imagen cargada: {archivo.name}")

    def aplicar_estilo(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background-color: #10151c;
                color: #eaf2f8;
                font-family: "Segoe UI";
                font-size: 14px;
            }

            QToolBar {
                background-color: #18212b;
                border: none;
                border-bottom: 1px solid #2c3947;
                spacing: 8px;
                padding: 6px;
            }

            QToolButton {
                background-color: transparent;
                padding: 7px 12px;
                border-radius: 5px;
            }

            QToolButton:hover {
                background-color: #283746;
            }

            #panelLateral {
                background-color: #17202a;
                border-right: 1px solid #2c3947;
            }

            #marca {
                color: #f5b041;
                font-size: 27px;
                font-weight: 700;
            }

            #nombreAplicacion {
                color: #ffffff;
                font-size: 18px;
                font-weight: 600;
                letter-spacing: 2px;
            }

            #descripcion, #informacion, #ayuda {
                color: #9fb2c4;
            }

            #encabezado {
                font-size: 18px;
                font-weight: 600;
                padding: 4px 2px 10px 2px;
            }

            #botonPrincipal {
                background-color: #d68910;
                color: #ffffff;
                border: none;
                padding: 11px;
                border-radius: 6px;
                font-weight: 600;
            }

            #botonPrincipal:hover {
                background-color: #f5b041;
            }

            #proximamente {
                color: #c7d5e0;
                line-height: 1.5;
            }

            #separador {
                color: #34495e;
                margin-top: 8px;
                margin-bottom: 8px;
            }

            QGraphicsView {
                background-color: #050709;
                border: 1px solid #2c3947;
                border-radius: 7px;
            }

            QStatusBar {
                background-color: #18212b;
                color: #aebdca;
            }
            """
        )


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(NOMBRE_APLICACION)
    app.setOrganizationName("Ne-notoka Cofame")

    ventana = VentanaPrincipal()
    ventana.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
