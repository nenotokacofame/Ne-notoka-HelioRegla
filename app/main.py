import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QKeySequence,
    QPen,
    QPixmap,
)
from ajuste_parcial import ajustar_limbo_parcial
from detector_limbo import detectar_limbo, ErrorDeteccionLimbo
from limbo import CirculoLimbo

from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFileDialog,
    QFrame,
    QGraphicsEllipseItem,
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
VERSION = "0.4.0"


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
        self.modo_limbo_parcial = False
        self.puntos_limbo_parcial = []
        self.marcas_limbo_parcial = []
        self.previsualizacion_parcial = None
        self.resultado_parcial = None
        self.callback_parcial = None

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

    def iniciar_limbo_parcial(self, callback):
        if self.elemento_imagen is None:
            QMessageBox.information(
                self,
                "Primero abre una imagen",
                "Necesitas cargar una fotografía del limbo solar.",
            )
            return False

        self.cancelar_limbo_parcial()
        self.eliminar_ajuste_limbo()

        self.modo_limbo_parcial = True
        self.callback_parcial = callback
        self.setDragMode(QGraphicsView.NoDrag)
        self.setCursor(Qt.CrossCursor)
        return True

    def agregar_punto_parcial(self, posicion):
        marca = QGraphicsEllipseItem(-5, -5, 10, 10)
        marca.setPos(posicion)
        marca.setBrush(QColor("#00e5ff"))

        lapiz = QPen(QColor("#ffffff"), 1)
        lapiz.setCosmetic(True)
        marca.setPen(lapiz)
        marca.setFlag(
            QGraphicsEllipseItem.ItemIgnoresTransformations,
            True,
        )
        marca.setZValue(30)

        self.escena.addItem(marca)
        self.marcas_limbo_parcial.append(marca)
        self.puntos_limbo_parcial.append(
            (posicion.x(), posicion.y())
        )
        self.recalcular_limbo_parcial()

    def eliminar_punto_parcial(self, posicion):
        if not self.puntos_limbo_parcial:
            return

        escala = max(abs(self.transform().m11()), 0.001)
        tolerancia = 18 / escala

        distancias = [
            (
                (x - posicion.x()) ** 2
                + (y - posicion.y()) ** 2
            ) ** 0.5
            for x, y in self.puntos_limbo_parcial
        ]
        indice = min(
            range(len(distancias)),
            key=distancias.__getitem__,
        )

        if distancias[indice] > tolerancia:
            return

        marca = self.marcas_limbo_parcial.pop(indice)
        self.escena.removeItem(marca)
        self.puntos_limbo_parcial.pop(indice)
        self.recalcular_limbo_parcial()

    def recalcular_limbo_parcial(self):
        if self.previsualizacion_parcial is not None:
            self.escena.removeItem(
                self.previsualizacion_parcial
            )
            self.previsualizacion_parcial = None

        self.resultado_parcial = None

        if len(self.puntos_limbo_parcial) < 3:
            if self.callback_parcial:
                self.callback_parcial(None)
            return

        try:
            resultado = ajustar_limbo_parcial(
                self.puntos_limbo_parcial
            )
        except ValueError:
            if self.callback_parcial:
                self.callback_parcial(None)
            return

        self.resultado_parcial = resultado

        circulo = QGraphicsEllipseItem(
            -resultado.radio,
            -resultado.radio,
            resultado.radio * 2,
            resultado.radio * 2,
        )
        circulo.setPos(
            resultado.centro_x,
            resultado.centro_y,
        )

        lapiz = QPen(QColor("#00e5ff"), 2)
        lapiz.setCosmetic(True)
        lapiz.setStyle(Qt.DashLine)
        circulo.setPen(lapiz)
        circulo.setZValue(20)

        self.escena.addItem(circulo)
        self.previsualizacion_parcial = circulo

        if self.callback_parcial:
            self.callback_parcial(resultado)

    def finalizar_limbo_parcial(self, al_cambiar):
        resultado = self.resultado_parcial

        if resultado is None:
            QMessageBox.information(
                self,
                "Faltan puntos",
                "Marca al menos tres puntos bien separados "
                "sobre el limbo.",
            )
            return None

        self.limpiar_marcas_parciales()
        self.modo_limbo_parcial = False
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.unsetCursor()

        self.circulo_limbo = CirculoLimbo(
            resultado.centro_x,
            resultado.centro_y,
            resultado.radio,
            al_cambiar,
        )
        self.escena.addItem(self.circulo_limbo)

        return resultado

    def limpiar_marcas_parciales(self):
        for marca in self.marcas_limbo_parcial:
            self.escena.removeItem(marca)

        self.marcas_limbo_parcial.clear()
        self.puntos_limbo_parcial.clear()

        if self.previsualizacion_parcial is not None:
            self.escena.removeItem(
                self.previsualizacion_parcial
            )
            self.previsualizacion_parcial = None

    def cancelar_limbo_parcial(self):
        self.limpiar_marcas_parciales()
        self.resultado_parcial = None
        self.modo_limbo_parcial = False
        self.callback_parcial = None
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.unsetCursor()

    def mousePressEvent(self, event):
        if not self.modo_limbo_parcial:
            super().mousePressEvent(event)
            return

        posicion = self.mapToScene(event.position().toPoint())

        if event.button() == Qt.LeftButton:
            self.agregar_punto_parcial(posicion)
            event.accept()
            return

        if event.button() == Qt.RightButton:
            self.eliminar_punto_parcial(posicion)
            event.accept()
            return

        super().mousePressEvent(event)

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

        self.ajustes = QSettings(
            "Ne-notoka Cofame",
            "Ne-notoka HelioRegla",
        )

        self.color_limbo = self.ajustes.value(
            "contorno/color",
            "#39ff88",
            type=str,
        )
        self.grosor_limbo = self.ajustes.value(
            "contorno/grosor",
            3,
            type=int,
        )
        self.modo_ajuste = "Ajuste manual del limbo"
        self.error_limbo_px = None
        self.incertidumbre_radio_px = None
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

        self.boton_parcial = QPushButton("Limbo parcial por puntos")
        self.boton_parcial.setObjectName("botonSecundario")
        self.boton_parcial.clicked.connect(
            self.iniciar_ajuste_parcial
        )

        self.boton_finalizar_parcial = QPushButton(
            "Finalizar ajuste parcial"
        )
        self.boton_finalizar_parcial.clicked.connect(
            self.finalizar_ajuste_parcial
        )
        self.boton_finalizar_parcial.setVisible(False)

        self.boton_cancelar_parcial = QPushButton("Cancelar puntos")
        self.boton_cancelar_parcial.clicked.connect(
            self.cancelar_ajuste_parcial
        )
        self.boton_cancelar_parcial.setVisible(False)

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
        panel_layout.addWidget(self.boton_parcial)
        panel_layout.addWidget(self.boton_finalizar_parcial)
        panel_layout.addWidget(self.boton_cancelar_parcial)

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
        ultima_carpeta = self.ajustes.value(
            "archivos/ultima_carpeta",
            "",
            type=str,
        )

        ruta, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir imagen solar",
            ultima_carpeta,
            "Imágenes (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;"
            "Todos los archivos (*)",
        )

        if ruta:
            self.visor.cargar_imagen(ruta)

    def iniciar_ajuste_parcial(self):
        if not self.visor.iniciar_limbo_parcial(
            self.actualizar_info_parcial
        ):
            return

        self.boton_finalizar_parcial.setVisible(True)
        self.boton_cancelar_parcial.setVisible(True)
        self.etiqueta_medicion.setText(
            "Ajuste de limbo parcial\n"
            "Clic izquierdo: añadir punto\n"
            "Clic derecho: eliminar punto\n"
            "Marca al menos 5 puntos sobre el arco."
        )
        self.statusBar().showMessage(
            "Marca puntos distribuidos sobre el limbo visible"
        )

    def actualizar_info_parcial(self, resultado):
        if resultado is None:
            cantidad = len(
                self.visor.puntos_limbo_parcial
            )
            self.etiqueta_medicion.setText(
                "Ajuste de limbo parcial\n"
                f"Puntos marcados: {cantidad}\n"
                "Se necesitan al menos 3 puntos."
            )
            return

        cobertura = resultado.cobertura_grados
        incertidumbre = resultado.incertidumbre_radio_px

        if cobertura < 45:
            calidad = "Muy baja: amplía el arco marcado"
        elif cobertura < 90:
            calidad = "Limitada"
        elif cobertura < 180:
            calidad = "Buena"
        else:
            calidad = "Excelente"

        self.etiqueta_medicion.setText(
            "Previsualización del limbo parcial\n"
            f"Puntos: {resultado.puntos_usados}\n"
            f"Cobertura: {cobertura:.1f}°\n"
            f"Radio: {resultado.radio:.1f} px\n"
            f"Residuo: ±{resultado.residuo_px:.2f} px\n"
            f"Incertidumbre radio: ±{incertidumbre:.1f} px\n"
            f"Calidad geométrica: {calidad}"
        )

    def finalizar_ajuste_parcial(self):
        resultado = self.visor.finalizar_limbo_parcial(
            self.actualizar_medicion_limbo
        )

        if resultado is None:
            return

        self.modo_ajuste = "Limbo parcial ajustado por puntos"
        self.error_limbo_px = resultado.residuo_px
        self.incertidumbre_radio_px = (
            resultado.incertidumbre_radio_px
        )
        self.puntos_limbo = resultado.puntos_usados
        self.aplicar_estilo_limbo()
        self.actualizar_medicion_limbo(
            resultado.centro_x,
            resultado.centro_y,
            resultado.radio,
        )

        self.boton_finalizar_parcial.setVisible(False)
        self.boton_cancelar_parcial.setVisible(False)

    def cancelar_ajuste_parcial(self):
        self.visor.cancelar_limbo_parcial()
        self.boton_finalizar_parcial.setVisible(False)
        self.boton_cancelar_parcial.setVisible(False)
        self.etiqueta_medicion.setText("Calibración pendiente")
        self.statusBar().showMessage("Ajuste parcial cancelado")

    def iniciar_ajuste_limbo(self):
        self.modo_ajuste = "Ajuste manual del limbo"
        self.error_limbo_px = None
        self.incertidumbre_radio_px = None
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
        self.incertidumbre_radio_px = None
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
        self.ajustes.setValue(
            "contorno/color",
            self.color_limbo,
        )
        self.boton_color_limbo.setStyleSheet(
            f"border: 2px solid {self.color_limbo};"
        )
        self.aplicar_estilo_limbo()

    def cambiar_grosor_limbo(self, grosor):
        self.grosor_limbo = grosor
        self.ajustes.setValue(
            "contorno/grosor",
            self.grosor_limbo,
        )
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
            )

            if self.incertidumbre_radio_px is not None:
                incertidumbre_km = (
                    self.incertidumbre_radio_px
                    * km_por_pixel
                )
                detalle_error += (
                    f"\nIncertidumbre del radio: "
                    f"±{self.incertidumbre_radio_px:.2f} px"
                    f" (±{incertidumbre_km:,.0f} km)"
                )

            detalle_error += (
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
        self.ajustes.setValue(
            "archivos/ultima_carpeta",
            str(archivo.parent),
        )
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

