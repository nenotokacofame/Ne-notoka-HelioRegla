import sys
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, QSettings, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QIcon,
    QKeySequence,
    QPen,
    QPixmap,
)
from ajuste_parcial import ajustar_limbo_parcial
from calibracion import DialogoCalibracion
from detector_limbo import detectar_limbo, ErrorDeteccionLimbo
from limbo import CirculoLimbo
from mediciones import MedicionProtuberancia

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
    QComboBox,
    QScrollArea,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


NOMBRE_APLICACION = "Ne-notoka HelioRegla"
RUTA_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_LOGO = RUTA_PROYECTO / "assets" / "logo_ne_notoka.png"
RUTA_ICONO = RUTA_PROYECTO / "assets" / "icono_ne_notoka.ico"
VERSION = "0.9.1"


class VisorSolar(QGraphicsView):
    imagen_cargada = Signal(str)
    punto_protuberancia = Signal(float, float)

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
        self.modo_medicion_protuberancia = False

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
        if self.modo_medicion_protuberancia:
            if event.button() == Qt.LeftButton:
                posicion = self.mapToScene(
                    event.position().toPoint()
                )
                self.punto_protuberancia.emit(
                    posicion.x(),
                    posicion.y(),
                )
                self.modo_medicion_protuberancia = False
                self.setDragMode(QGraphicsView.ScrollHandDrag)
                self.unsetCursor()
                event.accept()
                return

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
        self.setWindowIcon(QIcon(str(RUTA_ICONO)))
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
        self.escala_equipo_km = None
        self.descripcion_calibracion = None
        self.muestras_circulos = []

        self.color_anotaciones = self.ajustes.value(
            "anotaciones/color",
            "#ff3dbb",
            type=str,
        )
        self.tamano_anotaciones = self.ajustes.value(
            "anotaciones/tamano",
            28,
            type=int,
        )

        self.visor = VisorSolar()
        self.visor.imagen_cargada.connect(
            self.actualizar_informacion
        )
        self.visor.punto_protuberancia.connect(
            self.crear_medicion_protuberancia
        )
        self.mediciones_protuberancias = []
        self.historial_estados = []
        self.restaurando_historial = False
        self.suspendiendo_historial = False

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
        panel.setMinimumWidth(315)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 24, 22, 24)
        panel_layout.setSpacing(14)

        titulo = QLabel("Ne-notoka")
        titulo.setObjectName("marca")

        subtitulo = QLabel("HELIOREGLA · CIENCIA SOLAR")
        subtitulo.setObjectName("nombreAplicacion")

        logo_marca = QLabel()
        logo_marca.setObjectName("logoMarca")
        logo_marca.setFixedSize(58, 58)

        pixmap_logo = QPixmap(str(RUTA_LOGO))

        if not pixmap_logo.isNull():
            logo_marca.setPixmap(
                pixmap_logo.scaled(
                    56,
                    56,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        logo_marca.setAlignment(Qt.AlignCenter)

        textos_marca = QVBoxLayout()
        textos_marca.setContentsMargins(0, 0, 0, 0)
        textos_marca.setSpacing(1)
        textos_marca.addWidget(titulo)
        textos_marca.addWidget(subtitulo)

        cabecera_marca = QHBoxLayout()
        cabecera_marca.setContentsMargins(0, 0, 0, 0)
        cabecera_marca.setSpacing(10)
        cabecera_marca.addWidget(logo_marca)
        cabecera_marca.addLayout(textos_marca, 1)

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

        self.boton_calibracion = QPushButton(
            "Calibración por equipo"
        )
        self.boton_calibracion.setObjectName("botonSecundario")
        self.boton_calibracion.clicked.connect(
            self.abrir_calibracion_equipo
        )

        self.boton_protuberancia = QPushButton(
            "Medir protuberancia"
        )
        self.boton_protuberancia.setObjectName("botonPrincipal")
        self.boton_protuberancia.clicked.connect(
            self.iniciar_medicion_protuberancia
        )

        self.boton_borrar_mediciones = QPushButton(
            "Borrar mediciones"
        )
        self.boton_borrar_mediciones.clicked.connect(
            self.borrar_mediciones
        )

        self.boton_color_anotaciones = QPushButton(
            "Color de anotaciones"
        )
        self.boton_color_anotaciones.clicked.connect(
            self.seleccionar_color_anotaciones
        )
        self.boton_color_anotaciones.setStyleSheet(
            f"border: 2px solid {self.color_anotaciones};"
        )

        self.selector_tamano_anotaciones = QComboBox()
        tamanos = (12, 16, 20, 24, 28, 32, 40, 48, 56, 64)

        for tamano in tamanos:
            self.selector_tamano_anotaciones.addItem(
                f"Texto {tamano} px",
                tamano,
            )

        indice_tamano = (
            self.selector_tamano_anotaciones.findData(
                self.tamano_anotaciones
            )
        )
        self.selector_tamano_anotaciones.setCurrentIndex(
            max(0, indice_tamano)
        )
        self.selector_tamano_anotaciones.currentIndexChanged.connect(
            self.cambiar_tamano_anotaciones
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

        self.selector_grosor = QComboBox()

        for grosor in range(1, 11):
            self.selector_grosor.addItem(
                f"{grosor} px",
                grosor,
            )

        self.selector_grosor.setCurrentIndex(
            max(0, min(9, self.grosor_limbo - 1))
        )
        self.selector_grosor.setToolTip(
            "Grosor del contorno del limbo"
        )
        self.selector_grosor.currentIndexChanged.connect(
            self.cambiar_grosor_limbo
        )

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

        panel_layout.addLayout(cabecera_marca)
        panel_layout.addWidget(descripcion)
        panel_layout.addSpacing(8)
        panel_layout.addWidget(self.boton_abrir)
        panel_layout.addWidget(self.boton_limbo)
        panel_layout.addWidget(self.boton_autodetectar)
        panel_layout.addWidget(self.boton_parcial)
        panel_layout.addWidget(self.boton_calibracion)
        panel_layout.addWidget(self.boton_protuberancia)
        panel_layout.addWidget(self.boton_borrar_mediciones)

        fila_anotaciones = QHBoxLayout()
        fila_anotaciones.setSpacing(8)
        fila_anotaciones.addWidget(
            self.boton_color_anotaciones
        )
        fila_anotaciones.addWidget(
            self.selector_tamano_anotaciones
        )
        panel_layout.addLayout(fila_anotaciones)

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

        scroll_panel = QScrollArea()
        scroll_panel.setWidgetResizable(True)
        scroll_panel.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        scroll_panel.setFrameShape(QFrame.NoFrame)
        scroll_panel.setFixedWidth(350)
        scroll_panel.setWidget(panel)

        distribucion.addWidget(scroll_panel)
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
        barra.addSeparator()

        accion_deshacer = QAction("Deshacer", self)
        accion_deshacer.setShortcut(QKeySequence.Undo)
        accion_deshacer.triggered.connect(
            self.deshacer_ultimo_cambio
        )
        barra.addAction(accion_deshacer)

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

    def seleccionar_color_anotaciones(self):
        color = QColorDialog.getColor(
            self.color_anotaciones,
            self,
            "Seleccionar color de anotaciones",
        )

        if not color.isValid():
            return

        self.color_anotaciones = color.name()
        self.ajustes.setValue(
            "anotaciones/color",
            self.color_anotaciones,
        )
        self.boton_color_anotaciones.setStyleSheet(
            f"border: 2px solid {self.color_anotaciones};"
        )
        self.aplicar_estilo_anotaciones()

    def cambiar_tamano_anotaciones(self, indice):
        tamano = self.selector_tamano_anotaciones.itemData(
            indice
        )

        if tamano is None:
            return

        self.tamano_anotaciones = int(tamano)
        self.ajustes.setValue(
            "anotaciones/tamano",
            self.tamano_anotaciones,
        )
        self.aplicar_estilo_anotaciones()

    def aplicar_estilo_anotaciones(self):
        for medicion in self.mediciones_protuberancias:
            medicion.establecer_estilo(
                self.color_anotaciones,
                self.tamano_anotaciones,
            )

    def iniciar_medicion_protuberancia(self):
        if self.visor.circulo_limbo is None:
            QMessageBox.information(
                self,
                "Primero ajusta el limbo",
                "Autodetecta el disco o realiza un ajuste "
                "parcial antes de medir una protuberancia.",
            )
            return

        self.visor.modo_medicion_protuberancia = True
        self.visor.setDragMode(QGraphicsView.NoDrag)
        self.visor.setCursor(Qt.CrossCursor)
        self.statusBar().showMessage(
            "Haz clic en la punta de la protuberancia"
        )

    def crear_medicion_protuberancia(self, x, y):
        self.registrar_estado()
        circulo = self.visor.circulo_limbo
        escala_limbo = 1_391_400 / (circulo.radio * 2)
        escala = (
            self.escala_equipo_km
            if self.escala_equipo_km is not None
            else escala_limbo
        )

        medicion = MedicionProtuberancia(
            self.visor.escena,
            circulo,
            QPointF(x, y),
            escala,
            self.visor.elemento_imagen.boundingRect(),
            muestras_circulos=self.muestras_circulos,
            incertidumbre_limbo_px=(
                self.error_limbo_px or 0.0
            ),
            al_eliminar=self.eliminar_medicion_individual,
            color_anotacion=self.color_anotaciones,
            tamano_texto=self.tamano_anotaciones,
            antes_cambiar=self.registrar_estado,
        )
        self.mediciones_protuberancias.append(medicion)
        self.statusBar().showMessage(
            "Medición creada; arrastra el punto rosa "
            "para ajustarla"
        )

    def eliminar_medicion_individual(self, medicion):
        if medicion in self.mediciones_protuberancias:
            self.mediciones_protuberancias.remove(medicion)

        self.statusBar().showMessage(
            "Medición individual eliminada"
        )

    def capturar_estado(self):
        circulo = self.visor.circulo_limbo

        estado_circulo = None

        if circulo is not None:
            estado_circulo = {
                "centro_x": circulo.pos().x(),
                "centro_y": circulo.pos().y(),
                "radio": circulo.radio,
            }

        mediciones = [
            {
                "x": medicion.punta.x(),
                "y": medicion.punta.y(),
            }
            for medicion in self.mediciones_protuberancias
            if not medicion.eliminada
        ]

        return {
            "circulo": estado_circulo,
            "mediciones": mediciones,
        }

    def registrar_estado(self):
        if (
            self.restaurando_historial
            or self.suspendiendo_historial
            or self.visor.ruta_imagen is None
        ):
            return

        estado = self.capturar_estado()

        if (
            self.historial_estados
            and self.historial_estados[-1] == estado
        ):
            return

        self.historial_estados.append(estado)

        if len(self.historial_estados) > 100:
            self.historial_estados.pop(0)

    def deshacer_ultimo_cambio(self):
        if not self.historial_estados:
            self.statusBar().showMessage(
                "No hay cambios que deshacer"
            )
            return

        estado = self.historial_estados.pop()
        self.restaurando_historial = True
        self.suspendiendo_historial = True

        try:
            circulo = self.visor.circulo_limbo
            estado_circulo = estado["circulo"]

            if circulo is not None and estado_circulo is not None:
                circulo.setPos(
                    estado_circulo["centro_x"],
                    estado_circulo["centro_y"],
                )
                circulo.establecer_radio(
                    estado_circulo["radio"]
                )

            for medicion in self.mediciones_protuberancias[:]:
                medicion.antes_cambiar = None
                medicion.eliminar()

            self.mediciones_protuberancias.clear()

            for datos in estado["mediciones"]:
                self.crear_medicion_protuberancia(
                    datos["x"],
                    datos["y"],
                )

            self.statusBar().showMessage(
                "Último cambio deshecho"
            )
        finally:
            self.suspendiendo_historial = False
            self.restaurando_historial = False

    def borrar_mediciones(self):
        if not self.mediciones_protuberancias:
            return

        self.registrar_estado()
        self.suspendiendo_historial = True

        try:
            for medicion in self.mediciones_protuberancias[:]:
                medicion.eliminar()
        finally:
            self.suspendiendo_historial = False

        self.mediciones_protuberancias.clear()
        self.statusBar().showMessage("Mediciones eliminadas")

    def abrir_calibracion_equipo(self):
        if self.visor.ruta_imagen is None:
            QMessageBox.information(
                self,
                "Primero abre una imagen",
                "Necesitas cargar una imagen para leer "
                "sus metadatos y calibrarla.",
            )
            return

        escala_limbo = None

        if self.visor.circulo_limbo is not None:
            escala_limbo = (
                1_391_400
                / (self.visor.circulo_limbo.radio * 2)
            )

        dialogo = DialogoCalibracion(
            self.visor.ruta_imagen,
            escala_limbo,
            self,
        )

        if dialogo.exec() != DialogoCalibracion.Accepted:
            return

        resultado = dialogo.resultado
        self.escala_equipo_km = resultado.km_por_pixel
        self.descripcion_calibracion = resultado.descripcion

        self.etiqueta_medicion.setText(
            "Calibración mediante el equipo\n"
            f"{resultado.descripcion}\n"
            f"Escala angular: "
            f"{resultado.arcsec_por_pixel:.5f} ″/px\n"
            f"Escala física activa: "
            f"{resultado.km_por_pixel:,.2f} km/px"
        )
        self.statusBar().showMessage(
            "Calibración óptica aplicada: "
            f"{resultado.km_por_pixel:,.2f} km/px"
        )

        circulo = self.visor.circulo_limbo

        if circulo is not None:
            self.actualizar_medicion_limbo(
                circulo.pos().x(),
                circulo.pos().y(),
                circulo.radio,
            )

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
        self.muestras_circulos = resultado.muestras_circulos
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
        self.muestras_circulos = []
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
        self.muestras_circulos = []
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

    def cambiar_grosor_limbo(self, indice):
        grosor = self.selector_grosor.itemData(indice)

        if grosor is None:
            return

        self.grosor_limbo = int(grosor)
        self.ajustes.setValue(
            "contorno/grosor",
            self.grosor_limbo,
        )
        self.aplicar_estilo_limbo()

    def aplicar_estilo_limbo(self):
        circulo = self.visor.circulo_limbo

        if circulo is not None:
            circulo.antes_cambiar = self.registrar_estado
            circulo.establecer_estilo(
                self.color_limbo,
                self.grosor_limbo,
            )

    def actualizar_medicion_limbo(self, centro_x, centro_y, radio):
        diametro = radio * 2
        escala_limbo = 1_391_400 / diametro
        km_por_pixel = (
            self.escala_equipo_km
            if self.escala_equipo_km is not None
            else escala_limbo
        )

        for medicion in self.mediciones_protuberancias:
            medicion.km_por_pixel = km_por_pixel
            medicion.recalcular_desde_limbo()

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
            f"Escala por limbo: "
            f"{escala_limbo:,.1f} km/px\n"
            f"Escala activa: {km_por_pixel:,.1f} km/px"
            f"{detalle_error}"
        )
        self.statusBar().showMessage(
            f"Diámetro solar: {diametro:.1f} px · "
            f"Escala provisional: {km_por_pixel:,.1f} km/px"
        )

    def actualizar_informacion(self, ruta):
        archivo = Path(ruta)
        self.mediciones_protuberancias.clear()
        self.historial_estados.clear()
        self.escala_equipo_km = None
        self.descripcion_calibracion = None
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

    def closeEvent(self, event):
        if not self.mediciones_protuberancias:
            event.accept()
            return

        respuesta = QMessageBox.question(
            self,
            "Cerrar Ne-notoka HelioRegla",
            "Hay mediciones en la imagen. "
            "¿Estás seguro de que deseas cerrar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if respuesta == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def aplicar_estilo(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background-color: #F4F7F9;
                color: #183241;
                font-family: "Century Gothic", "Segoe UI";
                font-size: 14px;
            }

            QToolBar {
                background-color: #FFFFFF;
                border: none;
                border-bottom: 1px solid #D6E0E5;
                spacing: 8px;
                padding: 7px;
            }

            QToolButton {
                background-color: transparent;
                color: #004976;
                padding: 8px 13px;
                border-radius: 6px;
                font-weight: 600;
            }

            QToolButton:hover {
                background-color: #E4F0F6;
            }

            QToolButton:pressed {
                background-color: #CFE3ED;
            }

            #panelLateral {
                background-color: #FFFFFF;
                border-right: 2px solid #D4E2E9;
            }

            #logoMarca {
                background-color: transparent;
                border: none;
            }

            #marca {
                background-color: transparent;
                color: #004976;
                font-size: 28px;
                font-weight: 700;
                padding: 3px 0;
            }

            #nombreAplicacion {
                background-color: transparent;
                color: #D28B00;
                font-size: 15px;
                font-weight: 700;
                letter-spacing: 1px;
            }

            #descripcion {
                background-color: transparent;
                color: #547080;
                padding-bottom: 4px;
            }

            #informacion, #ayuda {
                background-color: #EDF4F7;
                color: #3A5868;
                border-radius: 6px;
                padding: 8px;
            }

            #encabezado {
                color: #004976;
                font-size: 19px;
                font-weight: 700;
                padding: 4px 2px 10px 2px;
            }

            QPushButton {
                background-color: #FFFFFF;
                color: #004976;
                border: 1px solid #9CB7C5;
                padding: 9px;
                border-radius: 6px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #E7F1F6;
                border-color: #004976;
            }

            QPushButton:pressed {
                background-color: #D2E5EE;
            }

            #botonPrincipal {
                background-color: #FFB81C;
                color: #173543;
                border: 1px solid #D89500;
                padding: 11px;
                border-radius: 6px;
                font-weight: 700;
            }

            #botonPrincipal:hover {
                background-color: #FFC94D;
                border-color: #B87800;
            }

            #botonSecundario {
                background-color: #FFFFFF;
                color: #004976;
                border: 2px solid #004976;
                padding: 9px;
                border-radius: 6px;
                font-weight: 700;
            }

            #botonSecundario:hover {
                background-color: #E0EEF4;
            }

            #botonColor {
                background-color: #FFFFFF;
                color: #004976;
                border: 2px solid #39FF88;
                padding: 7px;
                border-radius: 5px;
            }

            #medicion {
                background-color: #F0F7FA;
                color: #183241;
                border: 1px solid #AFC7D3;
                border-left: 4px solid #FFB81C;
                border-radius: 6px;
                padding: 10px;
            }

            #proximamente {
                background-color: #F8FBFC;
                color: #315261;
                border: 1px solid #D7E4EA;
                border-radius: 6px;
                padding: 9px;
            }

            #separador {
                color: #C9D8DF;
                margin-top: 7px;
                margin-bottom: 7px;
            }

            QGraphicsView {
                background-color: #050708;
                border: 2px solid #004976;
                border-radius: 8px;
            }

            QComboBox,
            QSpinBox,
            QDoubleSpinBox,
            QDateEdit,
            QLineEdit {
                background-color: #FFFFFF;
                color: #183241;
                border: 1px solid #8EACBB;
                border-radius: 5px;
                padding: 7px;
                min-height: 20px;
            }

            QComboBox:hover,
            QSpinBox:hover,
            QDoubleSpinBox:hover,
            QDateEdit:hover,
            QLineEdit:hover {
                border-color: #004976;
            }

            QComboBox::drop-down {
                border: none;
                width: 24px;
            }

            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                color: #183241;
                selection-background-color: #FFB81C;
                selection-color: #173543;
                border: 1px solid #004976;
            }

            QGroupBox {
                background-color: #FFFFFF;
                color: #004976;
                border: 1px solid #AFC7D3;
                border-radius: 7px;
                margin-top: 12px;
                padding: 12px 8px 8px 8px;
                font-weight: 700;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                background-color: #FFFFFF;
            }

            QDialog {
                background-color: #F4F7F9;
            }

            QScrollArea {
                background-color: #FFFFFF;
                border: none;
            }

            QScrollArea > QWidget > QWidget {
                background-color: #FFFFFF;
            }

            QScrollBar:vertical {
                background-color: #E5EDF1;
                width: 13px;
                margin: 2px;
                border: none;
                border-radius: 6px;
            }

            QScrollBar::handle:vertical {
                background-color: #004976;
                min-height: 32px;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #FFB81C;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
                background: none;
                border: none;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }

            QScrollBar:horizontal {
                background-color: #E5EDF1;
                height: 13px;
                margin: 2px;
                border: none;
                border-radius: 6px;
            }

            QScrollBar::handle:horizontal {
                background-color: #004976;
                min-width: 32px;
                border-radius: 5px;
            }

            QScrollBar::handle:horizontal:hover {
                background-color: #FFB81C;
            }

            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0;
                background: none;
                border: none;
            }

            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {
                background: transparent;
            }

            QStatusBar {
                background-color: #004976;
                color: #FFFFFF;
                border-top: 2px solid #FFB81C;
            }

            QStatusBar QLabel {
                background-color: transparent;
                color: #FFFFFF;
            }

            QToolTip {
                background-color: #FFFFFF;
                color: #183241;
                border: 1px solid #004976;
                padding: 5px;
            }

            QMessageBox {
                background-color: #F4F7F9;
            }
            """
        )

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(RUTA_ICONO)))
    app.setApplicationName(NOMBRE_APLICACION)
    app.setOrganizationName("Ne-notoka Cofame")

    ventana = VentanaPrincipal()
    ventana.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

