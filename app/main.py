import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QPixmap
from detector_limbo import detectar_limbo, ErrorDeteccionLimbo
from limbo import CirculoLimbo

from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
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
    QSpinBox,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


NOMBRE_APLICACION = "Ne-notoka HelioRegla"
VERSION = "0.3.0"


class VisorSolar(QGraphicsView):
    imagen_cargada = Signal(str)

    def __init__(self):
        super().__init__()

        self.escena = QGraphicsScene(self)
        self.setScene(self.escena)

        self.elemento_imagen = None
        self.ruta_imagen = None
        self.factor_zoom = 1.0
        self.circulo_limbo = None

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
        self.circulo_limbo = None
        self.elemento_imagen = QGraphicsPixmapItem(pixmap)
        self.escena.addItem(self.elemento_imagen)
        self.escena.setSceneRect(self.elemento_imagen.boundingRect())

        self.ruta_imagen = ruta
        self.factor_zoom = 1.0
        self.ajustar_ventana()
        self.imagen_cargada.emit(ruta)
        return True

    def crear_ajuste_limbo(self, al_cambiar):
        if self.elemento_imagen is None:
            QMessageBox.information(
                self,
                "Primero abre una imagen",
                "Necesitas cargar una fotografía solar antes de ajustar el limbo.",
            )
            return

        if self.circulo_limbo is not None:
            self.escena.removeItem(self.circulo_limbo)

        rectangulo = self.elemento_imagen.boundingRect()
        centro = rectangulo.center()
        radio = min(rectangulo.width(), rectangulo.height()) * 0.40

        self.circulo_limbo = CirculoLimbo(
            centro.x(),
            centro.y(),
            radio,
            al_cambiar,
        )
        self.escena.addItem(self.circulo_limbo)
        self.circulo_limbo.establecer_estilo("#39ff88", 3)

    def eliminar_ajuste_limbo(self):
        if self.circulo_limbo is not None:
            self.escena.removeItem(self.circulo_limbo)
            self.circulo_limbo = None

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

        self.color_limbo = "#39ff88"
        self.grosor_limbo = 3
        self.modo_ajuste = "Ajuste manual del limbo"
        self.error_limbo_px = None
        self.puntos_limbo = None

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

        self.boton_limbo = QPushButton("Ajustar limbo solar")
        self.boton_limbo.setObjectName("botonSecundario")
        self.boton_limbo.clicked.connect(self.iniciar_ajuste_limbo)

        self.boton_autodetectar = QPushButton("Autodetectar limbo")
        self.boton_autodetectar.setObjectName("botonPrincipal")
        self.boton_autodetectar.clicked.connect(
            self.iniciar_autodeteccion_limbo
        )

        self.boton_color_limbo = QPushButton("Color del contorno")
        self.boton_color_limbo.setObjectName("botonColor")
        self.boton_color_limbo.clicked.connect(self.seleccionar_color_limbo)

        self.selector_grosor = QSpinBox()
        self.selector_grosor.setRange(1, 10)
        self.selector_grosor.setValue(self.grosor_limbo)
        self.selector_grosor.setSuffix(" px")
        self.selector_grosor.setToolTip("Grosor del contorno del limbo")
        self.selector_grosor.valueChanged.connect(self.cambiar_grosor_limbo)

        self.etiqueta_medicion = QLabel("Calibración pendiente")
        self.etiqueta_medicion.setWordWrap(True)
        self.etiqueta_medicion.setObjectName("medicion")

        self.etiqueta_archivo = QLabel("Ninguna imagen cargada")
        self.etiqueta_archivo.setWordWrap(True)
        self.etiqueta_archivo.setObjectName("informacion")

        separador = QFrame()
        separador.setFrameShape(QFrame.HLine)
        separador.setObjectName("separador")

        proximamente = QLabel(
            "Próximas herramientas\n\n"
            "• Ajuste del limbo\n"
            "• Regla solar\n"
            "• Medición de estructuras\n"
            "• Comparación planetaria\n"
            "• Etiquetado de regiones"
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
        panel_layout.addWidget(self.boton_limbo)
        panel_layout.addWidget(self.boton_autodetectar)

        fila_estilo = QHBoxLayout()
        fila_estilo.setSpacing(8)
        fila_estilo.addWidget(self.boton_color_limbo, 1)
        fila_estilo.addWidget(self.selector_grosor)
        panel_layout.addLayout(fila_estilo)

        panel_layout.addWidget(self.etiqueta_archivo)
        panel_layout.addWidget(self.etiqueta_medicion)
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

    def iniciar_ajuste_limbo(self):
        self.modo_ajuste = "Ajuste manual del limbo"
        self.error_limbo_px = None
        self.puntos_limbo = None
        self.visor.crear_ajuste_limbo(self.actualizar_medicion_limbo)
        self.aplicar_estilo_limbo()

    def iniciar_autodeteccion_limbo(self):
        if self.visor.ruta_imagen is None:
            QMessageBox.information(
                self,
                "Primero abre una imagen",
                "Necesitas cargar una fotografía solar.",
            )
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage("Analizando el limbo solar…")

        try:
            resultado = detectar_limbo(self.visor.ruta_imagen)
        except ErrorDeteccionLimbo as error:
            QMessageBox.warning(
                self,
                "No fue posible detectar el limbo",
                str(error),
            )
            self.statusBar().showMessage(
                "Autodetección no concluyente; usa el ajuste manual"
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

        if self.visor.circulo_limbo is not None:
            self.visor.escena.removeItem(
                self.visor.circulo_limbo
            )

        self.modo_ajuste = "Limbo detectado automáticamente"
        self.error_limbo_px = resultado.error_px
        self.puntos_limbo = resultado.puntos_usados

        self.visor.circulo_limbo = CirculoLimbo(
            resultado.centro_x,
            resultado.centro_y,
            resultado.radio,
            self.actualizar_medicion_limbo,
        )
        self.visor.escena.addItem(
            self.visor.circulo_limbo
        )
        self.aplicar_estilo_limbo()

    def seleccionar_color_limbo(self):
        color = QColorDialog.getColor(
            self.color_limbo,
            self,
            "Seleccionar color del contorno",
        )

        if not color.isValid():
            return

        self.color_limbo = color.name()
        self.boton_color_limbo.setStyleSheet(
            f"border: 2px solid {self.color_limbo};"
        )
        self.aplicar_estilo_limbo()

    def cambiar_grosor_limbo(self, grosor):
        self.grosor_limbo = grosor
        self.aplicar_estilo_limbo()

    def aplicar_estilo_limbo(self):
        circulo = self.visor.circulo_limbo

        if circulo is not None:
            circulo.establecer_estilo(
                self.color_limbo,
                self.grosor_limbo,
            )

    def actualizar_medicion_limbo(self, centro_x, centro_y, radio):
        diametro = radio * 2
        km_por_pixel = 1_391_400 / diametro

        detalle_error = ""

        if self.error_limbo_px is not None:
            error_km = self.error_limbo_px * km_por_pixel
            detalle_error = (
                f"\nResiduo: ±{self.error_limbo_px:.2f} px"
                f" (±{error_km:,.0f} km)"
                f"\nPuntos usados: {self.puntos_limbo}"
            )

        self.etiqueta_medicion.setText(
            f"{self.modo_ajuste}\n"
            f"Centro: {centro_x:.1f}, {centro_y:.1f} px\n"
            f"Radio: {radio:.1f} px\n"
            f"Diámetro: {diametro:.1f} px\n"
            f"Escala: {km_por_pixel:,.1f} km/px"
            f"{detalle_error}"
        )
        self.statusBar().showMessage(
            f"Diámetro solar: {diametro:.1f} px · "
            f"Escala provisional: {km_por_pixel:,.1f} km/px"
        )

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

            #botonSecundario {
                background-color: #243342;
                color: #f5b041;
                border: 1px solid #d68910;
                padding: 10px;
                border-radius: 6px;
                font-weight: 600;
            }

            #botonSecundario:hover {
                background-color: #30465a;
            }

            #botonColor {
                background-color: #243342;
                color: #d8e6f0;
                border: 2px solid #39ff88;
                padding: 7px;
                border-radius: 5px;
            }

            QSpinBox {
                background-color: #111820;
                color: #ffffff;
                border: 1px solid #44596c;
                border-radius: 5px;
                padding: 6px;
                min-width: 62px;
            }

            #medicion {
                background-color: #111820;
                color: #d8e6f0;
                border: 1px solid #34495e;
                border-radius: 5px;
                padding: 9px;
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

