import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QSettings, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QColor,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QFont,
)
from ajuste_parcial import ajustar_limbo_parcial
from acerca_de import DialogoAcercaDe
from calibracion import DialogoCalibracion
from comparaciones import (
    ComparacionPlaneta,
    ComparacionTierraLuna,
    PLANETAS,
)
from catalogo_regiones import (
    ErrorCatalogoRegiones,
    consultar_regiones,
    leer_fecha_hora_imagen,
    posicion_en_imagen,
    tamano_region_en_imagen,
)
from detector_limbo import detectar_limbo, ErrorDeteccionLimbo
from dialogos_regiones import (
    DialogoConsultaRegiones,
    DialogoResultadosRegiones,
)
from dialogo_referencia import DialogoReferenciaSolar
from filamentos import MedicionFilamento, PuntoFilamento
from i18n import establecer_idioma, tr
from limbo import CirculoLimbo
from manchas import EtiquetaMancha, acomodar_etiquetas
from mediciones import MedicionProtuberancia
from proyectos import (
    ErrorProyecto,
    guardar_proyecto,
    leer_proyecto,
    referencias_imagen,
    resolver_imagen,
)
from referencia_solar import (
    ErrorReferenciaSolar,
    crear_referencia_anotada,
    descargar_referencias,
    refinar_posiciones_regiones,
    registrar_orientacion,
    registrar_orientacion_catalogo,
)
from regla_solar import ReglaSolar

from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QComboBox,
    QScrollArea,
    QStatusBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QFontComboBox,
    QWidget,
)


NOMBRE_APLICACION = "Ne-notoka HelioRegla"


def ruta_base_aplicacion():
    """Devuelve la raíz de recursos en desarrollo o en PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(sys.executable).resolve().parent,
            )
        )
    return Path(__file__).resolve().parent.parent


RUTA_PROYECTO = ruta_base_aplicacion()
RUTA_LOGO = RUTA_PROYECTO / "assets" / "logo_ne_notoka.png"
RUTA_ICONO = RUTA_PROYECTO / "assets" / "icono_ne_notoka.ico"
VERSION = "1.3.0"


class VisorSolar(QGraphicsView):
    imagen_cargada = Signal(str)
    punto_protuberancia = Signal(float, float)
    punto_filamento = Signal(float, float)
    quitar_punto_filamento = Signal(float, float)
    finalizar_filamento = Signal()
    cancelar_filamento = Signal()
    region_mancha = Signal(float, float, float, float)

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
        self.modo_medicion_filamento = False
        self.modo_etiquetado_mancha = False
        self.inicio_region_mancha = None
        self.previsualizacion_region_mancha = None

        self.setAcceptDrops(True)
        self.setObjectName("visorSolar")
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
                tr("open_failed"),
                tr("incompatible_image"),
            )
            return False

        self.escena.clear()
        self.circulo_limbo = None
        self.inicio_region_mancha = None
        self.previsualizacion_region_mancha = None
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
                tr("first_open_image"),
                tr("need_image_limb"),
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
                tr("first_open_image"),
                tr("need_limb_photo"),
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
                tr("missing_points"),
                tr("three_points"),
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
        if self.modo_etiquetado_mancha:
            if event.button() == Qt.LeftButton:
                self.inicio_region_mancha = self.mapToScene(
                    event.position().toPoint()
                )
                self.previsualizacion_region_mancha = (
                    QGraphicsEllipseItem()
                )
                lapiz = QPen(QColor("#00A6C8"), 2)
                lapiz.setCosmetic(True)
                lapiz.setStyle(Qt.DashLine)
                self.previsualizacion_region_mancha.setPen(
                    lapiz
                )
                self.previsualizacion_region_mancha.setBrush(
                    QBrush(Qt.NoBrush)
                )
                self.previsualizacion_region_mancha.setZValue(70)
                self.escena.addItem(
                    self.previsualizacion_region_mancha
                )
                event.accept()
                return

            if event.button() == Qt.RightButton:
                self.cancelar_region_mancha()
                event.accept()
                return

        if self.modo_medicion_filamento:
            if event.button() == Qt.LeftButton:
                elemento = self.itemAt(
                    event.position().toPoint()
                )

                if isinstance(elemento, PuntoFilamento):
                    super().mousePressEvent(event)
                    return

                posicion = self.mapToScene(
                    event.position().toPoint()
                )
                self.punto_filamento.emit(
                    posicion.x(),
                    posicion.y(),
                )
                event.accept()
                return

            if event.button() == Qt.RightButton:
                posicion = self.mapToScene(
                    event.position().toPoint()
                )
                self.quitar_punto_filamento.emit(
                    posicion.x(),
                    posicion.y(),
                )
                event.accept()
                return

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

    def mouseMoveEvent(self, event):
        if (
            self.modo_etiquetado_mancha
            and self.inicio_region_mancha is not None
            and self.previsualizacion_region_mancha is not None
        ):
            actual = self.mapToScene(event.position().toPoint())
            rectangulo = QRectF(
                self.inicio_region_mancha,
                actual,
            ).normalized()
            self.previsualizacion_region_mancha.setRect(
                rectangulo
            )
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            self.modo_etiquetado_mancha
            and event.button() == Qt.LeftButton
            and self.inicio_region_mancha is not None
        ):
            final = self.mapToScene(event.position().toPoint())
            rectangulo = QRectF(
                self.inicio_region_mancha,
                final,
            ).normalized()

            if rectangulo.width() < 8:
                rectangulo.setLeft(
                    self.inicio_region_mancha.x() - 18
                )
                rectangulo.setRight(
                    self.inicio_region_mancha.x() + 18
                )
            if rectangulo.height() < 8:
                rectangulo.setTop(
                    self.inicio_region_mancha.y() - 18
                )
                rectangulo.setBottom(
                    self.inicio_region_mancha.y() + 18
                )

            rectangulo = rectangulo.intersected(
                self.elemento_imagen.boundingRect()
            )
            if rectangulo.isEmpty():
                self.cancelar_region_mancha()
                event.accept()
                return

            centro = rectangulo.center()
            self.limpiar_previsualizacion_region_mancha()
            self.region_mancha.emit(
                centro.x(),
                centro.y(),
                rectangulo.width(),
                rectangulo.height(),
            )
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def limpiar_previsualizacion_region_mancha(self):
        if self.previsualizacion_region_mancha is not None:
            if (
                self.previsualizacion_region_mancha.scene()
                is not None
            ):
                self.escena.removeItem(
                    self.previsualizacion_region_mancha
                )
            self.previsualizacion_region_mancha = None
        self.inicio_region_mancha = None

    def cancelar_region_mancha(self):
        self.limpiar_previsualizacion_region_mancha()
        self.modo_etiquetado_mancha = False
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.unsetCursor()

    def keyPressEvent(self, event):
        if (
            self.modo_etiquetado_mancha
            and event.key() == Qt.Key_Escape
        ):
            self.cancelar_region_mancha()
            event.accept()
            return

        if self.modo_medicion_filamento:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.finalizar_filamento.emit()
                event.accept()
                return

            if event.key() == Qt.Key_Escape:
                self.cancelar_filamento.emit()
                event.accept()
                return

        super().keyPressEvent(event)

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
                tr("unsupported_format"),
                tr("supported_formats"),
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
        self.idioma = self.ajustes.value(
            "interfaz/idioma",
            "es",
            type=str,
        )
        establecer_idioma(self.idioma)

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
        self.modo_ajuste = tr("manual_limb")
        self.error_limbo_px = None
        self.incertidumbre_radio_px = None
        self.puntos_limbo = None
        self.escala_equipo_km = None
        self.usar_escala_equipo = True
        self.descripcion_calibracion = None
        self.muestras_circulos = []
        self.regla_solar = None
        self.ruta_proyecto_actual = None
        self.comparacion_tierra_luna = None
        self.comparaciones_planetas = {}
        self.rutas_imagenes_planetas = {
            planeta: (
                self.ajustes.value(
                    f"comparaciones/imagen_{planeta}",
                    "",
                    type=str,
                )
                or None
            )
            for planeta in PLANETAS
        }
        self.ruta_imagen_tierra = self.ajustes.value(
            "comparaciones/imagen_tierra",
            "",
            type=str,
        ) or None
        self.ruta_imagen_luna = self.ajustes.value(
            "comparaciones/imagen_luna",
            "",
            type=str,
        ) or None
        self.color_distancia_tierra_luna = self.ajustes.value(
            "anotaciones/distancia/color",
            self.ajustes.value(
                "comparaciones/color_distancia",
                "#FFB81C",
                type=str,
            ),
            type=str,
        )
        self.mostrar_linea_distancia = self.ajustes.value(
            "comparaciones/mostrar_linea_distancia",
            True,
            type=bool,
        )
        self.color_informacion_planetas = self.ajustes.value(
            "anotaciones/informacion_planetaria/color",
            self.ajustes.value(
                "comparaciones/color_informacion_planetas",
                "#FFFFFF",
                type=str,
            ),
            type=str,
        )

        self.intervalo_regla = self.ajustes.value(
            "regla/intervalo_km",
            25_000,
            type=int,
        )
        self.maximo_regla = self.ajustes.value(
            "regla/maximo_km",
            200_000,
            type=int,
        )
        self.color_regla = self.ajustes.value(
            "regla/color",
            "#00A6C8",
            type=str,
        )
        self.grosor_regla = self.ajustes.value(
            "regla/grosor",
            1,
            type=int,
        )
        self.tamano_regla = self.ajustes.value(
            "regla/tamano_texto",
            18,
            type=int,
        )
        self.fuente_regla = self.ajustes.value(
            "regla/fuente",
            "Century Gothic",
            type=str,
        )

        color_anotaciones_base = self.ajustes.value(
            "anotaciones/color",
            "#ff3dbb",
            type=str,
        )
        tamano_anotaciones_base = self.ajustes.value(
            "anotaciones/tamano",
            28,
            type=int,
        )
        fuente_anotaciones_base = self.ajustes.value(
            "anotaciones/fuente",
            "Century Gothic",
            type=str,
        )

        self.color_protuberancia = self.ajustes.value(
            "anotaciones/protuberancia/color",
            color_anotaciones_base,
            type=str,
        )
        self.tamano_protuberancia = self.ajustes.value(
            "anotaciones/protuberancia/tamano",
            tamano_anotaciones_base,
            type=int,
        )
        self.fuente_protuberancia = self.ajustes.value(
            "anotaciones/protuberancia/fuente",
            fuente_anotaciones_base,
            type=str,
        )
        self.color_filamento = self.ajustes.value(
            "anotaciones/filamento/color",
            color_anotaciones_base,
            type=str,
        )
        self.tamano_filamento = self.ajustes.value(
            "anotaciones/filamento/tamano",
            tamano_anotaciones_base,
            type=int,
        )
        self.fuente_filamento = self.ajustes.value(
            "anotaciones/filamento/fuente",
            fuente_anotaciones_base,
            type=str,
        )
        self.color_ra = self.ajustes.value(
            "anotaciones/ra/color",
            color_anotaciones_base,
            type=str,
        )
        self.tamano_ra = self.ajustes.value(
            "anotaciones/ra/tamano",
            tamano_anotaciones_base,
            type=int,
        )
        self.fuente_ra = self.ajustes.value(
            "anotaciones/ra/fuente",
            fuente_anotaciones_base,
            type=str,
        )
        self.tamano_distancia_tierra_luna = self.ajustes.value(
            "anotaciones/distancia/tamano",
            20,
            type=int,
        )
        self.fuente_distancia_tierra_luna = self.ajustes.value(
            "anotaciones/distancia/fuente",
            "Century Gothic",
            type=str,
        )
        self.tamano_informacion_planetas = self.ajustes.value(
            "anotaciones/informacion_planetaria/tamano",
            20,
            type=int,
        )
        self.fuente_informacion_planetas = self.ajustes.value(
            "anotaciones/informacion_planetaria/fuente",
            "Century Gothic",
            type=str,
        )

        # Alias de compatibilidad para proyectos y actualizaciones anteriores.
        self.color_anotaciones = self.color_ra
        self.tamano_anotaciones = self.tamano_ra
        self.fuente_anotaciones = self.fuente_ra
        self.controles_estilo = {}
        self.rotacion_catalogo = self.ajustes.value(
            "catalogo/rotacion",
            0.0,
            type=float,
        )
        self.espejo_horizontal_catalogo = self.ajustes.value(
            "catalogo/espejo_horizontal",
            False,
            type=bool,
        )
        self.espejo_vertical_catalogo = self.ajustes.value(
            "catalogo/espejo_vertical",
            False,
            type=bool,
        )
        self.ajuste_catalogo_x = self.ajustes.value(
            "catalogo/desplazamiento_x",
            0.0,
            type=float,
        )
        self.ajuste_catalogo_y = self.ajustes.value(
            "catalogo/desplazamiento_y",
            0.0,
            type=float,
        )
        self.escala_mapa_catalogo = self.ajustes.value(
            "catalogo/escala_mapa",
            1.0,
            type=float,
        )
        self.mostrar_conteo_manchas = self.ajustes.value(
            "catalogo/mostrar_conteo",
            True,
            type=bool,
        )
        self.fuente_referencia_catalogo = self.ajustes.value(
            "catalogo/fuente_referencia",
            "automatica",
            type=str,
        )
        self.ultimas_regiones_catalogo = []
        self.instante_catalogo = None
        self.ruta_referencia_catalogo = None
        self.nombre_fuente_referencia_catalogo = ""
        self.detalle_alineacion_catalogo = ""

        self.visor = VisorSolar()
        self.visor.imagen_cargada.connect(
            self.actualizar_informacion
        )
        self.visor.punto_protuberancia.connect(
            self.crear_medicion_protuberancia
        )
        self.visor.punto_filamento.connect(
            self.agregar_punto_filamento
        )
        self.visor.quitar_punto_filamento.connect(
            self.quitar_ultimo_punto_filamento
        )
        self.visor.finalizar_filamento.connect(
            self.finalizar_medicion_filamento
        )
        self.visor.cancelar_filamento.connect(
            self.cancelar_medicion_filamento
        )
        self.visor.region_mancha.connect(
            self.crear_region_mancha_manual
        )
        self.mediciones_protuberancias = []
        self.mediciones_filamentos = []
        self.etiquetas_manchas = []
        self.filamento_en_curso = None
        self.historial_estados = []
        self.restaurando_historial = False
        self.suspendiendo_historial = False

        self.crear_interfaz()
        self.crear_barra_herramientas()
        self.aplicar_idioma()
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
        subtitulo.setMinimumWidth(250)

        logo_marca = QLabel()
        logo_marca.setObjectName("logoMarca")
        logo_marca.setFixedSize(70, 70)

        pixmap_logo = QPixmap(str(RUTA_LOGO))

        if not pixmap_logo.isNull():
            logo_marca.setPixmap(
                pixmap_logo.scaled(
                    67,
                    67,
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

        self.descripcion_interfaz = QLabel(
            "Medición, comparación y etiquetado de imágenes solares."
        )
        self.descripcion_interfaz.setWordWrap(True)
        self.descripcion_interfaz.setObjectName("descripcion")

        self.boton_abrir = QPushButton("Abrir imagen solar")
        self.boton_abrir.setObjectName("botonPrincipal")
        self.boton_abrir.clicked.connect(self.abrir_imagen)

        self.boton_exportar = QPushButton(
            "Exportar imagen anotada"
        )
        self.boton_exportar.setObjectName("botonSecundario")
        self.boton_exportar.clicked.connect(
            self.exportar_imagen_anotada
        )

        self.boton_procesar_lote = QPushButton(
            "Procesar lote"
        )
        self.boton_procesar_lote.setObjectName("botonSecundario")
        self.boton_procesar_lote.clicked.connect(
            self.procesar_lote
        )

        self.boton_abrir_proyecto = QPushButton(
            "Abrir proyecto"
        )
        self.boton_abrir_proyecto.setObjectName(
            "botonSecundario"
        )
        self.boton_abrir_proyecto.clicked.connect(
            self.abrir_proyecto
        )

        self.boton_guardar_proyecto = QPushButton(
            "Guardar proyecto"
        )
        self.boton_guardar_proyecto.setObjectName(
            "botonSecundario"
        )
        self.boton_guardar_proyecto.clicked.connect(
            self.guardar_proyecto
        )

        self.boton_limbo = QPushButton("Ajustar limbo solar")
        self.boton_limbo.setObjectName("botonSecundario")
        self.boton_limbo.clicked.connect(self.iniciar_ajuste_limbo)

        self.boton_autodetectar = QPushButton("Autodetectar limbo")
        self.boton_autodetectar.setObjectName("botonHerramienta")
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
        self.boton_protuberancia.setObjectName("botonHerramienta")
        self.boton_protuberancia.clicked.connect(
            self.iniciar_medicion_protuberancia
        )

        self.boton_filamento = QPushButton(
            "Medir filamento"
        )
        self.boton_filamento.setObjectName("botonHerramienta")
        self.boton_filamento.clicked.connect(
            self.iniciar_medicion_filamento
        )

        self.boton_mancha = QPushButton(
            "Marcar región activa manualmente"
        )
        self.boton_mancha.setObjectName("botonHerramienta")
        self.boton_mancha.clicked.connect(
            self.iniciar_etiquetado_mancha
        )

        self.boton_detectar_manchas = QPushButton(
            "Consultar regiones NOAA/HEK"
        )
        self.boton_detectar_manchas.setObjectName(
            "botonHerramienta"
        )
        self.boton_detectar_manchas.clicked.connect(
            self.consultar_catalogos_regiones
        )

        self.boton_referencia_solar = QPushButton(
            "Ver referencia solar anotada"
        )
        self.boton_referencia_solar.setObjectName(
            "botonContextual"
        )
        self.boton_referencia_solar.clicked.connect(
            self.mostrar_referencia_solar
        )
        self.boton_referencia_solar.setVisible(False)

        self.boton_aceptar_filamento = QPushButton(
            "Aceptar medición"
        )
        self.boton_aceptar_filamento.setObjectName(
            "botonContextual"
        )
        self.boton_aceptar_filamento.clicked.connect(
            self.finalizar_medicion_filamento
        )
        self.boton_aceptar_filamento.setVisible(False)

        self.boton_borrar_mediciones = QPushButton(
            "Borrar mediciones"
        )
        self.boton_borrar_mediciones.clicked.connect(
            self.borrar_mediciones
        )

        self.boton_regla = QPushButton("Mostrar regla solar")
        self.boton_regla.setObjectName("botonHerramienta")
        self.boton_regla.clicked.connect(
            self.alternar_regla_solar
        )

        self.selector_intervalo_regla = QComboBox()

        for valor in (10_000, 25_000, 50_000, 100_000):
            self.selector_intervalo_regla.addItem(
                f"Cada {valor // 1000} mil km",
                valor,
            )

        indice = self.selector_intervalo_regla.findData(
            self.intervalo_regla
        )
        self.selector_intervalo_regla.setCurrentIndex(
            max(0, indice)
        )
        self.selector_intervalo_regla.currentIndexChanged.connect(
            self.cambiar_configuracion_regla
        )

        self.selector_maximo_regla = QComboBox()

        for valor in (
            50_000,
            100_000,
            150_000,
            200_000,
            300_000,
            500_000,
        ):
            self.selector_maximo_regla.addItem(
                f"Hasta {valor // 1000} mil km",
                valor,
            )

        indice = self.selector_maximo_regla.findData(
            self.maximo_regla
        )
        self.selector_maximo_regla.setCurrentIndex(
            max(0, indice)
        )
        self.selector_maximo_regla.currentIndexChanged.connect(
            self.cambiar_configuracion_regla
        )

        self.boton_color_regla = QPushButton("Color de regla")
        self.boton_color_regla.clicked.connect(
            self.seleccionar_color_regla
        )
        self.boton_color_regla.setStyleSheet(
            f"border: 2px solid {self.color_regla};"
        )

        self.selector_grosor_regla = QComboBox()

        for grosor in range(1, 6):
            self.selector_grosor_regla.addItem(
                f"Línea {grosor} px",
                grosor,
            )

        self.selector_grosor_regla.setCurrentIndex(
            max(0, self.grosor_regla - 1)
        )
        self.selector_grosor_regla.currentIndexChanged.connect(
            self.cambiar_configuracion_regla
        )

        self.selector_tamano_regla = QComboBox()

        for tamano in (12, 16, 18, 20, 24, 28, 32):
            self.selector_tamano_regla.addItem(
                f"Texto {tamano} px",
                tamano,
            )

        indice = self.selector_tamano_regla.findData(
            self.tamano_regla
        )
        self.selector_tamano_regla.setCurrentIndex(
            max(0, indice)
        )
        self.selector_tamano_regla.currentIndexChanged.connect(
            self.cambiar_configuracion_regla
        )

        self.selector_fuente_regla = QFontComboBox()
        self.selector_fuente_regla.setCurrentFont(
            QFont(self.fuente_regla)
        )
        self.selector_fuente_regla.currentFontChanged.connect(
            self.cambiar_fuente_regla
        )
        self.selector_fuente_regla.setToolTip(
            "Tipo de fuente de la regla solar"
        )

        self.boton_finalizar_parcial = QPushButton(
            "Finalizar ajuste parcial"
        )
        self.boton_finalizar_parcial.setObjectName(
            "botonContextual"
        )
        self.boton_finalizar_parcial.clicked.connect(
            self.finalizar_ajuste_parcial
        )
        self.boton_finalizar_parcial.setVisible(False)

        self.boton_cancelar_parcial = QPushButton("Cancelar puntos")
        self.boton_cancelar_parcial.setObjectName(
            "botonContextual"
        )
        self.boton_cancelar_parcial.clicked.connect(
            self.cancelar_ajuste_parcial
        )
        self.boton_cancelar_parcial.setVisible(False)

        self.boton_color_limbo = QPushButton("Color del contorno")
        self.boton_color_limbo.setObjectName("botonColor")
        self.boton_color_limbo.clicked.connect(self.seleccionar_color_limbo)

        self.selector_grosor = QComboBox()

        for grosor in range(0, 11):
            self.selector_grosor.addItem(
                f"{grosor} px",
                grosor,
            )

        self.selector_grosor.setCurrentIndex(
            max(0, min(10, self.grosor_limbo))
        )
        self.selector_grosor.setToolTip(
            "Grosor del contorno del limbo"
        )
        self.selector_grosor.currentIndexChanged.connect(
            self.cambiar_grosor_limbo
        )

        self.seccion_estilos = QLabel("ESTILOS DE ANOTACIONES")
        self.seccion_estilos.setObjectName("seccionPanel")

        self.filas_estilo = {}
        for clave, clave_texto in (
            ("protuberancia", "prominence_style"),
            ("filamento", "filament_style"),
            ("ra", "active_region_style"),
            ("distancia", "distance_style"),
            ("informacion_planetaria", "planet_info_style"),
        ):
            self.filas_estilo[clave] = self.crear_fila_estilo(
                clave,
                tr(clave_texto),
            )

        self.etiqueta_medicion = QLabel("Calibración pendiente")
        self.etiqueta_medicion.setWordWrap(True)
        self.etiqueta_medicion.setObjectName("medicion")

        self.etiqueta_advertencia_calibracion = QLabel()
        self.etiqueta_advertencia_calibracion.setWordWrap(True)
        self.etiqueta_advertencia_calibracion.setObjectName(
            "calibracionAdvertencia"
        )
        self.etiqueta_advertencia_calibracion.setVisible(False)

        self.etiqueta_archivo = QLabel("Ninguna imagen cargada")
        self.etiqueta_archivo.setWordWrap(True)
        self.etiqueta_archivo.setObjectName("informacion")

        self.etiqueta_ayuda = QLabel(
            "Rueda: zoom\n"
            "Arrastrar: desplazar\n"
            "También puedes soltar una imagen."
        )
        self.etiqueta_ayuda.setObjectName("ayuda")

        self.seccion_calibracion = QLabel("CALIBRACIÓN")
        self.seccion_calibracion.setObjectName("seccionPanel")

        self.seccion_mediciones = QLabel("MEDICIONES")
        self.seccion_mediciones.setObjectName("seccionPanel")

        self.seccion_visualizacion = QLabel("VISUALIZACIÓN")
        self.seccion_visualizacion.setObjectName("seccionPanel")

        panel_layout.addLayout(cabecera_marca)
        panel_layout.addWidget(self.descripcion_interfaz)
        panel_layout.addSpacing(8)
        panel_layout.addWidget(self.boton_abrir)
        panel_layout.addWidget(self.boton_exportar)
        panel_layout.addWidget(self.boton_procesar_lote)
        panel_layout.addWidget(self.boton_abrir_proyecto)
        panel_layout.addWidget(self.boton_guardar_proyecto)
        panel_layout.addWidget(self.seccion_calibracion)
        panel_layout.addWidget(self.boton_calibracion)
        panel_layout.addWidget(self.boton_limbo)
        panel_layout.addWidget(self.boton_autodetectar)
        panel_layout.addWidget(self.boton_parcial)
        panel_layout.addWidget(
            self.boton_finalizar_parcial,
            0,
            Qt.AlignHCenter,
        )
        panel_layout.addWidget(
            self.boton_cancelar_parcial,
            0,
            Qt.AlignHCenter,
        )
        panel_layout.addWidget(self.seccion_mediciones)
        panel_layout.addWidget(self.boton_protuberancia)
        panel_layout.addWidget(self.boton_filamento)
        panel_layout.addWidget(
            self.boton_aceptar_filamento,
            0,
            Qt.AlignHCenter,
        )
        panel_layout.addWidget(self.boton_detectar_manchas)
        panel_layout.addWidget(
            self.boton_referencia_solar,
            0,
            Qt.AlignHCenter,
        )
        panel_layout.addWidget(self.boton_mancha)
        panel_layout.addWidget(self.boton_borrar_mediciones)
        panel_layout.addWidget(self.seccion_visualizacion)
        panel_layout.addWidget(self.boton_regla)

        fila_regla_1 = QHBoxLayout()
        fila_regla_1.setSpacing(8)
        fila_regla_1.addWidget(self.selector_intervalo_regla)
        fila_regla_1.addWidget(self.selector_maximo_regla)
        panel_layout.addLayout(fila_regla_1)

        fila_regla_2 = QHBoxLayout()
        fila_regla_2.setSpacing(8)
        fila_regla_2.addWidget(self.boton_color_regla)
        fila_regla_2.addWidget(self.selector_grosor_regla)
        fila_regla_2.addWidget(self.selector_fuente_regla)
        fila_regla_2.addWidget(self.selector_tamano_regla)
        panel_layout.addLayout(fila_regla_2)

        fila_estilo = QHBoxLayout()
        fila_estilo.setSpacing(8)
        fila_estilo.addWidget(self.boton_color_limbo, 1)
        fila_estilo.addWidget(self.selector_grosor)
        panel_layout.addLayout(fila_estilo)

        panel_layout.addWidget(self.seccion_estilos)
        for fila in self.filas_estilo.values():
            panel_layout.addWidget(fila)

        panel_layout.addWidget(self.etiqueta_archivo)
        panel_layout.addWidget(self.etiqueta_medicion)
        panel_layout.addWidget(
            self.etiqueta_advertencia_calibracion
        )
        panel_layout.addStretch()
        panel_layout.addWidget(self.etiqueta_ayuda)

        zona_visor = QWidget()
        zona_layout = QVBoxLayout(zona_visor)
        zona_layout.setContentsMargins(18, 18, 18, 18)

        self.encabezado_area = QLabel("Área de trabajo solar")
        self.encabezado_area.setObjectName("encabezado")

        zona_layout.addWidget(self.encabezado_area)
        zona_layout.addWidget(self.visor, 1)

        scroll_panel = QScrollArea()
        scroll_panel.setWidgetResizable(True)
        scroll_panel.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        scroll_panel.setFrameShape(QFrame.NoFrame)
        scroll_panel.setFixedWidth(400)
        scroll_panel.setWidget(panel)

        distribucion.addWidget(scroll_panel)
        distribucion.addWidget(zona_visor, 1)

        self.setCentralWidget(contenedor)

    def _valores_estilo(self, clave):
        atributos = {
            "protuberancia": (
                "color_protuberancia",
                "tamano_protuberancia",
                "fuente_protuberancia",
            ),
            "filamento": (
                "color_filamento",
                "tamano_filamento",
                "fuente_filamento",
            ),
            "ra": (
                "color_ra",
                "tamano_ra",
                "fuente_ra",
            ),
            "distancia": (
                "color_distancia_tierra_luna",
                "tamano_distancia_tierra_luna",
                "fuente_distancia_tierra_luna",
            ),
            "informacion_planetaria": (
                "color_informacion_planetas",
                "tamano_informacion_planetas",
                "fuente_informacion_planetas",
            ),
        }
        nombres = atributos[clave]
        return tuple(getattr(self, nombre) for nombre in nombres)

    def crear_fila_estilo(self, clave, titulo):
        contenedor = QWidget()
        distribucion = QVBoxLayout(contenedor)
        distribucion.setContentsMargins(0, 2, 0, 2)
        distribucion.setSpacing(4)

        etiqueta = QLabel(titulo)
        etiqueta.setObjectName("tituloEstilo")
        distribucion.addWidget(etiqueta)

        fila = QHBoxLayout()
        fila.setSpacing(6)

        color, tamano, familia = self._valores_estilo(clave)
        boton_color = QPushButton("Color")
        boton_color.setObjectName("botonColor")
        boton_color.setFixedWidth(72)
        boton_color.setToolTip("Seleccionar color de esta anotación")
        boton_color.setStyleSheet(
            f"border: 2px solid {color};"
        )
        boton_color.clicked.connect(
            lambda comprobado=False, clave=clave:
            self.seleccionar_color_estilo(clave)
        )

        selector_fuente = QFontComboBox()
        selector_fuente.setCurrentFont(QFont(familia))
        selector_fuente.setToolTip("Seleccionar tipo de fuente")
        selector_fuente.currentFontChanged.connect(
            lambda fuente, clave=clave:
            self.cambiar_fuente_estilo(clave, fuente)
        )

        selector_tamano = QComboBox()
        for valor in (
            10,
            12,
            14,
            16,
            18,
            20,
            24,
            28,
            32,
            40,
            48,
            56,
            64,
            72,
        ):
            selector_tamano.addItem(
                tr("text_px", value=valor),
                valor,
            )
        indice = selector_tamano.findData(tamano)
        selector_tamano.setCurrentIndex(max(0, indice))
        selector_tamano.setToolTip(
            "Tamaño del texto en píxeles de la imagen"
        )
        selector_tamano.currentIndexChanged.connect(
            lambda indice, clave=clave:
            self.cambiar_tamano_estilo(clave, indice)
        )

        fila.addWidget(boton_color)
        fila.addWidget(selector_fuente, 1)
        fila.addWidget(selector_tamano)
        distribucion.addLayout(fila)

        controles = {
            "etiqueta": etiqueta,
            "color": boton_color,
            "fuente": selector_fuente,
            "tamano": selector_tamano,
        }
        self.controles_estilo[clave] = controles
        return contenedor

    def createPopupMenu(self):
        return None

    def crear_barra_herramientas(self):
        barra = QToolBar("Herramientas principales")
        barra.setMovable(False)
        barra.setContextMenuPolicy(Qt.PreventContextMenu)
        self.addToolBar(barra)

        self.accion_abrir = QAction("Abrir", self)
        self.accion_abrir.setShortcut(QKeySequence.Open)
        self.accion_abrir.triggered.connect(self.abrir_imagen)

        self.accion_ajustar = QAction(
            "Ajustar a ventana",
            self,
        )
        self.accion_ajustar.setShortcut("F")
        self.accion_ajustar.triggered.connect(
            self.visor.ajustar_ventana
        )

        self.accion_real = QAction("Tamaño real", self)
        self.accion_real.setShortcut("1")
        self.accion_real.triggered.connect(
            self.visor.tamano_real
        )

        barra.addAction(self.accion_abrir)

        self.accion_exportar = QAction("Exportar", self)
        self.accion_exportar.setShortcut("Ctrl+Shift+S")
        self.accion_exportar.triggered.connect(
            self.exportar_imagen_anotada
        )
        barra.addAction(self.accion_exportar)

        self.accion_procesar_lote = QAction(
            "Procesar lote",
            self,
        )
        self.accion_procesar_lote.setShortcut("Ctrl+Shift+B")
        self.accion_procesar_lote.triggered.connect(
            self.procesar_lote
        )
        barra.addAction(self.accion_procesar_lote)

        self.accion_guardar_proyecto = QAction(
            "Guardar proyecto",
            self,
        )
        self.accion_guardar_proyecto.setShortcut(
            QKeySequence.Save
        )
        self.accion_guardar_proyecto.triggered.connect(
            self.guardar_proyecto
        )
        barra.addAction(self.accion_guardar_proyecto)

        self.accion_abrir_proyecto = QAction(
            "Abrir proyecto",
            self,
        )
        self.accion_abrir_proyecto.setShortcut("Ctrl+Alt+O")
        self.accion_abrir_proyecto.triggered.connect(
            self.abrir_proyecto
        )
        barra.addAction(self.accion_abrir_proyecto)

        barra.addSeparator()
        barra.addAction(self.accion_ajustar)
        barra.addAction(self.accion_real)
        barra.addSeparator()

        self.accion_deshacer = QAction("Deshacer", self)
        self.accion_deshacer.setShortcut(QKeySequence.Undo)
        self.accion_deshacer.triggered.connect(
            self.deshacer_ultimo_cambio
        )
        self.addAction(self.accion_deshacer)

        self.menu_comparaciones = QMenu(self)
        self.accion_anadir_tierra_luna = QAction(
            "Añadir Tierra–Luna",
            self,
        )
        self.accion_anadir_tierra_luna.triggered.connect(
            self.anadir_comparacion_tierra_luna
        )
        self.menu_comparaciones.addAction(
            self.accion_anadir_tierra_luna
        )

        self.menu_anadir_planeta = QMenu(
            "Añadir planeta",
            self,
        )
        self.acciones_anadir_planeta = {}

        for planeta in PLANETAS:
            accion = QAction(planeta.title(), self)
            accion.triggered.connect(
                lambda comprobado=False, clave=planeta:
                self.anadir_comparacion_planeta(clave)
            )
            self.menu_anadir_planeta.addAction(accion)
            self.acciones_anadir_planeta[planeta] = accion

        self.opcion_distancia_tierra_luna = QAction(
            "Mostrar distancia real (384,400 km)",
            self,
        )
        self.opcion_distancia_tierra_luna.setCheckable(True)
        self.opcion_distancia_tierra_luna.toggled.connect(
            self.cambiar_distancia_tierra_luna
        )
        self.menu_comparaciones.addAction(
            self.opcion_distancia_tierra_luna
        )

        self.opcion_linea_distancia = QAction(
            "Mostrar línea y distancia",
            self,
        )
        self.opcion_linea_distancia.setCheckable(True)
        self.opcion_linea_distancia.setChecked(
            self.mostrar_linea_distancia
        )
        self.opcion_linea_distancia.toggled.connect(
            self.cambiar_linea_distancia_tierra_luna
        )
        self.menu_comparaciones.addAction(
            self.opcion_linea_distancia
        )

        self.menu_comparaciones.addSeparator()
        self.menu_comparaciones.addMenu(
            self.menu_anadir_planeta
        )

        self.accion_imagen_tierra = QAction(
            "Usar imagen personalizada de la Tierra…",
            self,
        )
        self.accion_imagen_tierra.triggered.connect(
            self.seleccionar_imagen_tierra
        )
        self.menu_imagenes_comparacion = QMenu(
            "Imágenes personalizadas",
            self,
        )
        self.menu_imagenes_comparacion.addAction(
            self.accion_imagen_tierra
        )

        self.accion_imagen_luna = QAction(
            "Usar imagen personalizada de la Luna…",
            self,
        )
        self.accion_imagen_luna.triggered.connect(
            self.seleccionar_imagen_luna
        )
        self.menu_imagenes_comparacion.addAction(
            self.accion_imagen_luna
        )
        self.menu_imagenes_comparacion.addSeparator()

        self.acciones_imagen_planeta = {}

        for planeta in PLANETAS:
            accion = QAction(planeta.title(), self)
            accion.triggered.connect(
                lambda comprobado=False, clave=planeta:
                self.seleccionar_imagen_planeta(clave)
            )
            self.menu_imagenes_comparacion.addAction(accion)
            self.acciones_imagen_planeta[planeta] = accion

        self.menu_imagenes_comparacion.addSeparator()

        self.accion_restaurar_imagenes = QAction(
            "Restaurar Tierra–Luna",
            self,
        )
        self.accion_restaurar_imagenes.triggered.connect(
            self.restaurar_imagenes_tierra_luna
        )
        self.menu_imagenes_comparacion.addAction(
            self.accion_restaurar_imagenes
        )

        self.accion_restaurar_planetas = QAction(
            "Restaurar todos los planetas",
            self,
        )
        self.accion_restaurar_planetas.triggered.connect(
            self.restaurar_imagenes_planetas
        )
        self.menu_imagenes_comparacion.addAction(
            self.accion_restaurar_planetas
        )
        self.menu_comparaciones.addMenu(
            self.menu_imagenes_comparacion
        )
        self.menu_comparaciones.addSeparator()

        self.accion_quitar_tierra_luna = QAction(
            "Quitar comparación",
            self,
        )
        self.accion_quitar_tierra_luna.setEnabled(False)
        self.accion_quitar_tierra_luna.triggered.connect(
            self.quitar_comparacion_tierra_luna
        )
        self.menu_comparaciones.addAction(
            self.accion_quitar_tierra_luna
        )

        self.accion_quitar_planetas = QAction(
            "Quitar todos los planetas",
            self,
        )
        self.accion_quitar_planetas.setEnabled(False)
        self.accion_quitar_planetas.triggered.connect(
            self.quitar_comparaciones_planetas
        )
        self.menu_comparaciones.addAction(
            self.accion_quitar_planetas
        )

        self.boton_menu_comparaciones = QToolButton()
        self.boton_menu_comparaciones.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.boton_menu_comparaciones.setPopupMode(
            QToolButton.InstantPopup
        )
        self.boton_menu_comparaciones.setMenu(
            self.menu_comparaciones
        )
        barra.addWidget(self.boton_menu_comparaciones)

        self.menu_idioma = QMenu(self)
        grupo_idiomas = QActionGroup(self)
        grupo_idiomas.setExclusive(True)
        self.accion_espanol = QAction("Español", self)
        self.accion_espanol.setCheckable(True)
        self.accion_english = QAction("English", self)
        self.accion_english.setCheckable(True)
        grupo_idiomas.addAction(self.accion_espanol)
        grupo_idiomas.addAction(self.accion_english)
        self.menu_idioma.addActions(grupo_idiomas.actions())
        self.accion_espanol.setChecked(self.idioma == "es")
        self.accion_english.setChecked(self.idioma == "en")
        self.accion_espanol.triggered.connect(
            lambda: self.cambiar_idioma("es")
        )
        self.accion_english.triggered.connect(
            lambda: self.cambiar_idioma("en")
        )

        self.boton_menu_idioma = QToolButton()
        self.boton_menu_idioma.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.boton_menu_idioma.setPopupMode(
            QToolButton.InstantPopup
        )
        self.boton_menu_idioma.setMenu(self.menu_idioma)
        barra.addWidget(self.boton_menu_idioma)

        self.menu_ayuda = QMenu(self)
        self.accion_acerca_de = QAction(self)
        self.accion_acerca_de.triggered.connect(
            lambda comprobado=False:
            self.mostrar_acerca_de(0)
        )
        self.accion_licencia = QAction(self)
        self.accion_licencia.triggered.connect(
            lambda comprobado=False:
            self.mostrar_acerca_de(1)
        )
        self.accion_apoyar = QAction(self)
        self.accion_apoyar.triggered.connect(
            lambda comprobado=False:
            self.mostrar_acerca_de(2)
        )
        self.menu_ayuda.addAction(self.accion_acerca_de)
        self.menu_ayuda.addAction(self.accion_licencia)
        self.menu_ayuda.addSeparator()
        self.menu_ayuda.addAction(self.accion_apoyar)

        self.boton_menu_ayuda = QToolButton()
        self.boton_menu_ayuda.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.boton_menu_ayuda.setPopupMode(
            QToolButton.InstantPopup
        )
        self.boton_menu_ayuda.setMenu(self.menu_ayuda)
        barra.addWidget(self.boton_menu_ayuda)

    def cambiar_idioma(self, idioma):
        if idioma == self.idioma:
            return

        modos = {
            "Ajuste manual del limbo": "manual_limb",
            "Manual limb adjustment": "manual_limb",
            "Limbo parcial ajustado por puntos": (
                "partial_limb_mode"
            ),
            "Partial limb fitted from points": (
                "partial_limb_mode"
            ),
            "Limbo detectado automáticamente": (
                "automatic_limb"
            ),
            "Limb detected automatically": "automatic_limb",
        }
        clave_modo = modos.get(self.modo_ajuste)
        self.idioma = idioma
        self.ajustes.setValue("interfaz/idioma", idioma)
        establecer_idioma(idioma)

        if clave_modo is not None:
            self.modo_ajuste = tr(clave_modo)

        self.aplicar_idioma()

        if self.visor.circulo_limbo is not None:
            circulo = self.visor.circulo_limbo
            self.actualizar_medicion_limbo(
                circulo.pos().x(),
                circulo.pos().y(),
                circulo.radio,
            )
        else:
            for medicion in self.mediciones_filamentos:
                medicion.recalcular()

        if self.filamento_en_curso is not None:
            self.filamento_en_curso.recalcular()

        if self.comparacion_tierra_luna is not None:
            self.comparacion_tierra_luna.actualizar()

        for comparacion in self.comparaciones_planetas.values():
            comparacion.actualizar()

        for etiqueta in self.etiquetas_manchas:
            datos = etiqueta.datos_catalogo
            numero = datos.get("numero")
            if not numero:
                continue
            lineas = [f"AR {numero}"]
            clase_magnetica = datos.get("clase_magnetica")
            if clase_magnetica:
                lineas.append(
                    tr(
                        "magnetic_class_short",
                        value=clase_magnetica,
                    )
                )
            manchas = datos.get("manchas")
            if (
                self.mostrar_conteo_manchas
                and manchas is not None
            ):
                lineas.append(
                    tr(
                        (
                            "one_sunspot"
                            if int(manchas) == 1
                            else "many_sunspots"
                        ),
                        count=manchas,
                    )
                )
            etiqueta.establecer_nombre("\n".join(lineas))

        acomodar_etiquetas(self.etiquetas_manchas)
        self.statusBar().showMessage(tr("language_changed"))

    def aplicar_idioma(self):
        self.descripcion_interfaz.setText(tr("description"))
        self.boton_abrir.setText(tr("open_image"))
        self.boton_exportar.setText(tr("export_image"))
        self.boton_procesar_lote.setText(tr("batch_process"))
        self.boton_abrir_proyecto.setText(tr("open_project"))
        self.boton_guardar_proyecto.setText(
            tr("save_project")
        )
        self.boton_limbo.setText(tr("adjust_limb"))
        self.boton_autodetectar.setText(
            tr("autodetect_limb")
        )
        self.boton_parcial.setText(tr("partial_limb"))
        self.boton_calibracion.setText(
            tr("equipment_calibration")
        )
        self.boton_protuberancia.setText(
            tr("measure_prominence")
        )
        self.boton_filamento.setText(tr("measure_filament"))
        self.boton_detectar_manchas.setText(
            tr("detect_sunspots")
        )
        self.boton_referencia_solar.setText(
            tr("view_solar_reference")
        )
        self.boton_mancha.setText(tr("label_sunspot"))
        self.boton_aceptar_filamento.setText(
            tr("accept_measurement")
        )
        self.boton_borrar_mediciones.setText(
            tr("delete_measurements")
        )
        self.boton_regla.setText(
            tr(
                "hide_ruler"
                if self.regla_solar is not None
                else "show_ruler"
            )
        )
        self.boton_color_regla.setText(tr("ruler_color"))
        self.boton_color_limbo.setText(tr("outline_color"))
        self.seccion_estilos.setText(tr("annotation_styles"))
        titulos_estilo = {
            "protuberancia": "prominence_style",
            "filamento": "filament_style",
            "ra": "active_region_style",
            "distancia": "distance_style",
            "informacion_planetaria": "planet_info_style",
        }
        for clave, controles in self.controles_estilo.items():
            controles["etiqueta"].setText(
                tr(titulos_estilo[clave])
            )
            controles["color"].setText(tr("color_button"))
            controles["color"].setToolTip(
                tr("annotation_color_tooltip")
            )
            controles["fuente"].setToolTip(
                tr("font_type_tooltip")
            )
            controles["tamano"].setToolTip(
                tr("annotation_size_tooltip")
            )
        self.selector_fuente_regla.setToolTip(
            tr("ruler_font_tooltip")
        )
        self.boton_finalizar_parcial.setText(
            tr("finish_partial")
        )
        self.boton_cancelar_parcial.setText(
            tr("cancel_points")
        )
        self.seccion_calibracion.setText(tr("calibration"))
        self.seccion_mediciones.setText(tr("measurements"))
        self.seccion_visualizacion.setText(
            tr("visualization")
        )
        self.etiqueta_ayuda.setText(tr("help"))
        self.encabezado_area.setText(tr("solar_workspace"))

        if self.visor.ruta_imagen is None:
            self.etiqueta_archivo.setText(tr("no_image"))
            self.etiqueta_medicion.setText(
                tr("pending_calibration")
            )
        self.actualizar_advertencia_calibracion()

        self.accion_abrir.setText(tr("open"))
        self.accion_exportar.setText(tr("export"))
        self.accion_procesar_lote.setText(tr("batch_process_action"))
        self.accion_guardar_proyecto.setText(
            tr("save_project")
        )
        self.accion_abrir_proyecto.setText(
            tr("open_project")
        )
        self.accion_ajustar.setText(tr("fit_window"))
        self.accion_real.setText(tr("actual_size"))
        self.accion_deshacer.setText(tr("undo"))
        self.boton_menu_comparaciones.setText(
            tr("comparisons")
        )
        self.accion_anadir_tierra_luna.setText(
            tr("add_earth_moon")
        )
        self.menu_anadir_planeta.setTitle(tr("add_planet"))

        for planeta, accion in (
            self.acciones_anadir_planeta.items()
        ):
            accion.setText(tr(planeta))

        self.opcion_distancia_tierra_luna.setText(
            tr("real_earth_moon_distance")
        )
        self.opcion_linea_distancia.setText(
            tr("show_distance_line")
        )
        self.accion_imagen_tierra.setText(
            tr("custom_earth")
        )
        self.accion_imagen_luna.setText(tr("custom_moon"))
        self.menu_imagenes_comparacion.setTitle(
            tr("custom_images")
        )

        for planeta, accion in (
            self.acciones_imagen_planeta.items()
        ):
            accion.setText(
                tr(
                    "custom_planet",
                    name=tr(planeta),
                )
            )

        self.accion_restaurar_imagenes.setText(
            tr("restore_earth_moon")
        )
        self.accion_restaurar_planetas.setText(
            tr("restore_all_planets")
        )
        self.accion_quitar_tierra_luna.setText(
            tr("remove_comparison")
        )
        self.accion_quitar_planetas.setText(
            tr("remove_all_planets")
        )
        self.boton_menu_idioma.setText(tr("language"))
        self.accion_espanol.setText(tr("spanish"))
        self.accion_english.setText(tr("english"))
        self.boton_menu_ayuda.setText(tr("help_menu"))
        self.accion_acerca_de.setText(tr("about_app"))
        self.accion_licencia.setText(tr("license_action"))
        self.accion_apoyar.setText(tr("support_project"))

        for indice in range(
            self.selector_intervalo_regla.count()
        ):
            valor = self.selector_intervalo_regla.itemData(
                indice
            )
            self.selector_intervalo_regla.setItemText(
                indice,
                tr("every_km", value=valor // 1000),
            )

        for indice in range(self.selector_maximo_regla.count()):
            valor = self.selector_maximo_regla.itemData(indice)
            self.selector_maximo_regla.setItemText(
                indice,
                tr("up_to_km", value=valor // 1000),
            )

        for indice in range(
            self.selector_grosor_regla.count()
        ):
            valor = self.selector_grosor_regla.itemData(indice)
            self.selector_grosor_regla.setItemText(
                indice,
                tr("line_px", value=valor),
            )

        for indice in range(self.selector_grosor.count()):
            valor = self.selector_grosor.itemData(indice)
            self.selector_grosor.setItemText(
                indice,
                tr("line_px", value=valor),
            )

        selectores_tamano = [self.selector_tamano_regla]
        selectores_tamano.extend(
            controles["tamano"]
            for controles in self.controles_estilo.values()
        )
        for selector in selectores_tamano:
            for indice in range(selector.count()):
                selector.setItemText(
                    indice,
                    tr(
                        "text_px",
                        value=selector.itemData(indice),
                    ),
                )

    def crear_estado(self):
        estado = QStatusBar()
        estado.showMessage(tr("ready"))
        self.setStatusBar(estado)

    def mostrar_acerca_de(self, pestana=0):
        DialogoAcercaDe(
            VERSION,
            RUTA_LOGO,
            RUTA_PROYECTO / "LICENSE",
            pestana=pestana,
            parent=self,
        ).exec()

    def abrir_imagen(self):
        ultima_carpeta = self.ajustes.value(
            "archivos/ultima_carpeta",
            "",
            type=str,
        )

        ruta, _ = QFileDialog.getOpenFileName(
            self,
            tr("open_image_title"),
            ultima_carpeta,
            tr("image_filter"),
        )

        if ruta:
            self.visor.cargar_imagen(ruta)

    def _renderizar_escena_anotada(self, pixmap=None):
        """Renderiza la fotografía y las anotaciones sin controles.

        ``pixmap`` permite reutilizar las mismas posiciones vectoriales con
        otra fotografía del mismo tamaño. La imagen del visor se restaura
        antes de devolver el resultado, por lo que el procesamiento por lotes
        no altera el proyecto ni la fotografía plantilla.
        """
        if self.visor.elemento_imagen is None:
            return None

        elemento_imagen = self.visor.elemento_imagen
        pixmap_original = elemento_imagen.pixmap()
        if pixmap is not None:
            elemento_imagen.setPixmap(pixmap)

        elementos_temporales = []

        def ocultar(elemento):
            if elemento is None:
                return
            elementos_temporales.append(
                (elemento, elemento.isVisible())
            )
            elemento.setVisible(False)

        circulo = self.visor.circulo_limbo

        if circulo is not None:
            for manejador in circulo.manejadores:
                ocultar(manejador)

        for medicion in self.mediciones_protuberancias:
            ocultar(medicion.manejador)

        for medicion in self.mediciones_filamentos:
            for manejador in medicion.manejadores:
                ocultar(manejador)

        if self.filamento_en_curso is not None:
            for manejador in self.filamento_en_curso.manejadores:
                ocultar(manejador)

        for marca in self.visor.marcas_limbo_parcial:
            ocultar(marca)

        ocultar(self.visor.previsualizacion_parcial)

        pixmap_render = elemento_imagen.pixmap()
        imagen = QImage(
            pixmap_render.width(),
            pixmap_render.height(),
            QImage.Format_ARGB32,
        )
        imagen.fill(Qt.transparent)
        pintor = QPainter(imagen)
        pintor.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )

        try:
            self.visor.escena.render(
                pintor,
                QRectF(0, 0, imagen.width(), imagen.height()),
                elemento_imagen.boundingRect(),
                Qt.IgnoreAspectRatio,
            )
        finally:
            pintor.end()
            for elemento, era_visible in elementos_temporales:
                elemento.setVisible(era_visible)
            if pixmap is not None:
                elemento_imagen.setPixmap(pixmap_original)

        return imagen

    def _guardar_render(self, imagen, destino):
        sufijo = destino.suffix.lower()
        calidad = 95 if sufijo in {".jpg", ".jpeg"} else -1
        return imagen.save(str(destino), quality=calidad)

    def exportar_imagen_anotada(self):
        if self.visor.elemento_imagen is None:
            QMessageBox.information(
                self,
                tr("first_open_image"),
                tr("need_image_export"),
            )
            return

        archivo_original = Path(self.visor.ruta_imagen)
        ultima_carpeta = self.ajustes.value(
            "exportacion/ultima_carpeta",
            str(archivo_original.parent),
            type=str,
        )
        ruta_sugerida = str(
            Path(ultima_carpeta)
            / f"{archivo_original.stem}_anotada.png"
        )

        ruta, filtro = QFileDialog.getSaveFileName(
            self,
            tr("export_title"),
            ruta_sugerida,
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;"
            "TIFF (*.tif *.tiff)",
        )

        if not ruta:
            return

        destino = Path(ruta)
        if not destino.suffix:
            if "JPEG" in filtro:
                destino = destino.with_suffix(".jpg")
            elif "TIFF" in filtro:
                destino = destino.with_suffix(".tif")
            else:
                destino = destino.with_suffix(".png")

        imagen = self._renderizar_escena_anotada()
        if imagen is None or not self._guardar_render(imagen, destino):
            QMessageBox.warning(
                self,
                tr("export_failed"),
                tr("export_failed_text"),
            )
            return

        self.ajustes.setValue(
            "exportacion/ultima_carpeta",
            str(destino.parent),
        )
        self.statusBar().showMessage(
            tr("image_exported", name=destino.name)
        )
        QMessageBox.information(
            self,
            tr("export_done"),
            tr(
                "export_success",
                width=imagen.width(),
                height=imagen.height(),
                path=destino,
            ),
        )

    def procesar_lote(self):
        """Aplica las anotaciones del fotograma actual a varias imágenes."""
        if self.visor.elemento_imagen is None:
            QMessageBox.information(
                self,
                tr("first_open_image"),
                tr("need_image_batch"),
            )
            return

        if (
            self.filamento_en_curso is not None
            or self.visor.modo_limbo_parcial
        ):
            QMessageBox.information(
                self,
                tr("finish_editing"),
                tr("finish_batch_editing"),
            )
            return

        archivo_original = Path(self.visor.ruta_imagen)
        ultima_carpeta = self.ajustes.value(
            "lotes/ultima_carpeta",
            str(archivo_original.parent),
            type=str,
        )
        rutas, _ = QFileDialog.getOpenFileNames(
            self,
            tr("batch_select_title"),
            ultima_carpeta,
            tr("image_filter"),
        )
        if not rutas:
            return

        carpeta_salida = QFileDialog.getExistingDirectory(
            self,
            tr("batch_output_title"),
            self.ajustes.value(
                "lotes/ultima_salida",
                str(archivo_original.parent),
                type=str,
            ),
        )
        if not carpeta_salida:
            return

        pixmap_plantilla = self.visor.elemento_imagen.pixmap()
        tamano_plantilla = pixmap_plantilla.size()
        validas = []
        incompatibles = []
        for ruta in rutas:
            pixmap = QPixmap(ruta)
            if pixmap.isNull():
                incompatibles.append(Path(ruta).name)
            elif pixmap.size() != tamano_plantilla:
                incompatibles.append(Path(ruta).name)
            else:
                validas.append((Path(ruta), pixmap))

        if not validas:
            QMessageBox.warning(
                self,
                tr("batch_no_compatible"),
                tr(
                    "batch_no_compatible_text",
                    width=tamano_plantilla.width(),
                    height=tamano_plantilla.height(),
                ),
            )
            return

        respuesta = QMessageBox.question(
            self,
            tr("batch_confirm_title"),
            tr(
                "batch_confirm_text",
                count=len(validas),
                width=tamano_plantilla.width(),
                height=tamano_plantilla.height(),
                path=carpeta_salida,
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if respuesta != QMessageBox.Yes:
            return

        progreso = QProgressDialog(
            tr("batch_progress"),
            tr("cancel"),
            0,
            len(validas),
            self,
        )
        progreso.setWindowTitle(tr("batch_title"))
        progreso.setWindowModality(Qt.WindowModal)
        progreso.setMinimumDuration(0)
        progreso.show()

        guardadas = []
        fallidas = []
        cancelado = False
        carpeta = Path(carpeta_salida)
        for indice, (ruta, pixmap) in enumerate(validas, start=1):
            if progreso.wasCanceled():
                cancelado = True
                break

            progreso.setValue(indice - 1)
            progreso.setLabelText(
                tr("batch_processing", name=ruta.name)
            )
            QApplication.processEvents()

            destino = carpeta / f"{ruta.stem}_anotada.png"
            contador = 2
            while destino.exists():
                destino = carpeta / (
                    f"{ruta.stem}_anotada_{contador}.png"
                )
                contador += 1

            imagen = self._renderizar_escena_anotada(pixmap)
            if imagen is not None and self._guardar_render(
                imagen,
                destino,
            ):
                guardadas.append(destino)
            else:
                fallidas.append(ruta.name)

        progreso.setValue(len(validas) if not cancelado else len(guardadas))
        progreso.close()

        self.ajustes.setValue("lotes/ultima_carpeta", str(Path(rutas[0]).parent))
        self.ajustes.setValue("lotes/ultima_salida", str(carpeta))
        self.statusBar().showMessage(
            tr("batch_done_status", count=len(guardadas))
        )

        QMessageBox.information(
            self,
            tr("batch_done_title"),
            tr(
                "batch_done_text",
                count=len(guardadas),
                skipped=len(incompatibles) + len(fallidas),
                cancelled=(
                    tr("batch_yes")
                    if cancelado
                    else tr("batch_no")
                ),
                path=carpeta,
            ),
        )

    def datos_del_proyecto(self, ruta_proyecto):
        circulo = self.visor.circulo_limbo
        datos_circulo = None

        if circulo is not None:
            datos_circulo = {
                "centro_x": circulo.pos().x(),
                "centro_y": circulo.pos().y(),
                "radio": circulo.radio,
                "modo": self.modo_ajuste,
                "error_limbo_px": self.error_limbo_px,
                "incertidumbre_radio_px": (
                    self.incertidumbre_radio_px
                ),
                "puntos_limbo": self.puntos_limbo,
                "muestras_circulos": self.muestras_circulos,
            }

        return {
            "aplicacion": NOMBRE_APLICACION,
            "version_aplicacion": VERSION,
            "imagen": referencias_imagen(
                ruta_proyecto,
                self.visor.ruta_imagen,
            ),
            "calibracion": {
                "km_por_pixel": self.escala_equipo_km,
                "descripcion": self.descripcion_calibracion,
                "usar_escala_equipo": self.usar_escala_equipo,
            },
            "limbo": datos_circulo,
            "protuberancias": [
                medicion.estado()
                for medicion in self.mediciones_protuberancias
                if not medicion.eliminada
            ],
            "filamentos": [
                medicion.estado_completo()
                for medicion in self.mediciones_filamentos
                if not medicion.eliminada
            ],
            "manchas": [
                etiqueta.estado()
                for etiqueta in self.etiquetas_manchas
                if not etiqueta.eliminada
            ],
            "catalogo_regiones": {
                "rotacion": self.rotacion_catalogo,
                "espejo_horizontal": (
                    self.espejo_horizontal_catalogo
                ),
                "espejo_vertical": (
                    self.espejo_vertical_catalogo
                ),
                "desplazamiento_x": self.ajuste_catalogo_x,
                "desplazamiento_y": self.ajuste_catalogo_y,
                "escala_mapa": self.escala_mapa_catalogo,
                "mostrar_conteo": self.mostrar_conteo_manchas,
                "fuente_alineacion": (
                    self.fuente_referencia_catalogo
                ),
                "instante_utc": (
                    self.instante_catalogo.isoformat()
                    if self.instante_catalogo is not None
                    else None
                ),
            },
            "comparacion_tierra_luna": (
                self.comparacion_tierra_luna.estado()
                if self.comparacion_tierra_luna is not None
                else None
            ),
            "comparaciones_planetas": [
                comparacion.estado()
                for comparacion in (
                    self.comparaciones_planetas.values()
                )
                if not comparacion.eliminada
            ],
            "estilo": {
                "color_limbo": self.color_limbo,
                "grosor_limbo": self.grosor_limbo,
                "color_protuberancia": self.color_protuberancia,
                "tamano_protuberancia": self.tamano_protuberancia,
                "fuente_protuberancia": self.fuente_protuberancia,
                "color_filamento": self.color_filamento,
                "tamano_filamento": self.tamano_filamento,
                "fuente_filamento": self.fuente_filamento,
                "color_ra": self.color_ra,
                "tamano_ra": self.tamano_ra,
                "fuente_ra": self.fuente_ra,
                "color_distancia_tierra_luna": (
                    self.color_distancia_tierra_luna
                ),
                "tamano_distancia_tierra_luna": (
                    self.tamano_distancia_tierra_luna
                ),
                "fuente_distancia_tierra_luna": (
                    self.fuente_distancia_tierra_luna
                ),
                "color_informacion_planetas": (
                    self.color_informacion_planetas
                ),
                "tamano_informacion_planetas": (
                    self.tamano_informacion_planetas
                ),
                "fuente_informacion_planetas": (
                    self.fuente_informacion_planetas
                ),
                # Claves conservadas para proyectos anteriores.
                "color_anotaciones": self.color_anotaciones,
                "tamano_anotaciones": self.tamano_anotaciones,
                "fuente_anotaciones": self.fuente_anotaciones,
            },
            "regla": {
                "visible": self.regla_solar is not None,
                "intervalo_km": self.intervalo_regla,
                "maximo_km": self.maximo_regla,
                "color": self.color_regla,
                "grosor": self.grosor_regla,
                "tamano_texto": self.tamano_regla,
                "fuente": self.fuente_regla,
            },
        }

    def guardar_proyecto(self):
        if self.visor.ruta_imagen is None:
            QMessageBox.information(
                self,
                tr("first_open_image"),
                tr("need_image_project"),
            )
            return

        if (
            self.filamento_en_curso is not None
            or self.visor.modo_limbo_parcial
        ):
            QMessageBox.information(
                self,
                tr("finish_editing"),
                tr("finish_editing_text"),
            )
            return

        ruta = self.ruta_proyecto_actual

        if ruta is None:
            ultima_carpeta = self.ajustes.value(
                "proyectos/ultima_carpeta",
                str(Path(self.visor.ruta_imagen).parent),
                type=str,
            )
            sugerida = str(
                Path(ultima_carpeta)
                / f"{Path(self.visor.ruta_imagen).stem}.helio"
            )
            seleccionada, _ = QFileDialog.getSaveFileName(
                self,
                tr("save_project_title"),
                sugerida,
                tr("project_filter"),
            )

            if not seleccionada:
                return

            ruta = Path(seleccionada)

            if ruta.suffix.lower() != ".helio":
                ruta = ruta.with_suffix(".helio")

        try:
            guardar_proyecto(
                ruta,
                self.datos_del_proyecto(ruta),
            )
        except OSError as error:
            QMessageBox.warning(
                self,
                tr("save_failed"),
                str(error),
            )
            return

        self.ruta_proyecto_actual = Path(ruta)
        self.ajustes.setValue(
            "proyectos/ultima_carpeta",
            str(self.ruta_proyecto_actual.parent),
        )
        self.statusBar().showMessage(
            tr(
                "project_saved",
                name=self.ruta_proyecto_actual.name,
            )
        )

    def abrir_proyecto(self):
        ultima_carpeta = self.ajustes.value(
            "proyectos/ultima_carpeta",
            "",
            type=str,
        )
        seleccionada, _ = QFileDialog.getOpenFileName(
            self,
            tr("open_project_title"),
            ultima_carpeta,
            tr("project_filter"),
        )

        if not seleccionada:
            return

        ruta_proyecto = Path(seleccionada)

        try:
            datos = leer_proyecto(ruta_proyecto)
        except ErrorProyecto as error:
            QMessageBox.warning(
                self,
                tr("invalid_project"),
                str(error),
            )
            return

        ruta_imagen = resolver_imagen(
            ruta_proyecto,
            datos["imagen"],
        )

        if ruta_imagen is None:
            encontrada, _ = QFileDialog.getOpenFileName(
                self,
                tr("locate_project_image"),
                str(ruta_proyecto.parent),
                tr("image_filter"),
            )

            if not encontrada:
                return

            ruta_imagen = Path(encontrada)

        self.suspendiendo_historial = True

        try:
            if not self.visor.cargar_imagen(str(ruta_imagen)):
                return

            estilo = datos.get("estilo", {})
            self.color_limbo = estilo.get(
                "color_limbo",
                self.color_limbo,
            )
            self.grosor_limbo = int(
                estilo.get(
                    "grosor_limbo",
                    self.grosor_limbo,
                )
            )
            color_anotaciones = estilo.get(
                "color_anotaciones",
                self.color_ra,
            )
            tamano_anotaciones = int(
                estilo.get(
                    "tamano_anotaciones",
                    self.tamano_ra,
                )
            )
            fuente_anotaciones = estilo.get(
                "fuente_anotaciones",
                self.fuente_ra,
            )
            self.color_protuberancia = estilo.get(
                "color_protuberancia",
                color_anotaciones,
            )
            self.tamano_protuberancia = int(
                estilo.get(
                    "tamano_protuberancia",
                    tamano_anotaciones,
                )
            )
            self.fuente_protuberancia = estilo.get(
                "fuente_protuberancia",
                fuente_anotaciones,
            )
            self.color_filamento = estilo.get(
                "color_filamento",
                color_anotaciones,
            )
            self.tamano_filamento = int(
                estilo.get(
                    "tamano_filamento",
                    tamano_anotaciones,
                )
            )
            self.fuente_filamento = estilo.get(
                "fuente_filamento",
                fuente_anotaciones,
            )
            self.color_ra = estilo.get(
                "color_ra",
                color_anotaciones,
            )
            self.tamano_ra = int(
                estilo.get("tamano_ra", tamano_anotaciones)
            )
            self.fuente_ra = estilo.get(
                "fuente_ra",
                fuente_anotaciones,
            )
            self.color_distancia_tierra_luna = estilo.get(
                "color_distancia_tierra_luna",
                self.color_distancia_tierra_luna,
            )
            self.tamano_distancia_tierra_luna = int(
                estilo.get(
                    "tamano_distancia_tierra_luna",
                    self.tamano_distancia_tierra_luna,
                )
            )
            self.fuente_distancia_tierra_luna = estilo.get(
                "fuente_distancia_tierra_luna",
                self.fuente_distancia_tierra_luna,
            )
            self.color_informacion_planetas = estilo.get(
                "color_informacion_planetas",
                self.color_informacion_planetas,
            )
            self.tamano_informacion_planetas = int(
                estilo.get(
                    "tamano_informacion_planetas",
                    self.tamano_informacion_planetas,
                )
            )
            self.fuente_informacion_planetas = estilo.get(
                "fuente_informacion_planetas",
                self.fuente_informacion_planetas,
            )
            self.color_anotaciones = self.color_ra
            self.tamano_anotaciones = self.tamano_ra
            self.fuente_anotaciones = self.fuente_ra

            calibracion = datos.get("calibracion", {})
            self.escala_equipo_km = calibracion.get(
                "km_por_pixel"
            )
            self.descripcion_calibracion = calibracion.get(
                "descripcion"
            )
            self.usar_escala_equipo = bool(
                calibracion.get("usar_escala_equipo", True)
            )

            catalogo = datos.get("catalogo_regiones", {})
            self.rotacion_catalogo = float(
                catalogo.get(
                    "rotacion",
                    self.rotacion_catalogo,
                )
            )
            self.espejo_horizontal_catalogo = bool(
                catalogo.get(
                    "espejo_horizontal",
                    self.espejo_horizontal_catalogo,
                )
            )
            self.espejo_vertical_catalogo = bool(
                catalogo.get(
                    "espejo_vertical",
                    self.espejo_vertical_catalogo,
                )
            )
            self.ajuste_catalogo_x = float(
                catalogo.get(
                    "desplazamiento_x",
                    self.ajuste_catalogo_x,
                )
            )
            self.ajuste_catalogo_y = float(
                catalogo.get(
                    "desplazamiento_y",
                    self.ajuste_catalogo_y,
                )
            )
            self.escala_mapa_catalogo = float(
                catalogo.get(
                    "escala_mapa",
                    self.escala_mapa_catalogo,
                )
            )
            self.mostrar_conteo_manchas = bool(
                catalogo.get(
                    "mostrar_conteo",
                    self.mostrar_conteo_manchas,
                )
            )
            self.fuente_referencia_catalogo = catalogo.get(
                "fuente_alineacion",
                self.fuente_referencia_catalogo,
            )

            datos_limbo = datos.get("limbo")

            if datos_limbo:
                modo_guardado = datos_limbo.get(
                    "modo",
                    tr("manual_limb"),
                )
                modos_guardados = {
                    "Ajuste manual del limbo": "manual_limb",
                    "Manual limb adjustment": "manual_limb",
                    "Limbo parcial ajustado por puntos": (
                        "partial_limb_mode"
                    ),
                    "Partial limb fitted from points": (
                        "partial_limb_mode"
                    ),
                    "Limbo detectado automáticamente": (
                        "automatic_limb"
                    ),
                    "Limb detected automatically": (
                        "automatic_limb"
                    ),
                }
                self.modo_ajuste = tr(
                    modos_guardados.get(
                        modo_guardado,
                        "manual_limb",
                    )
                )
                self.error_limbo_px = datos_limbo.get(
                    "error_limbo_px"
                )
                self.incertidumbre_radio_px = (
                    datos_limbo.get(
                        "incertidumbre_radio_px"
                    )
                )
                self.puntos_limbo = datos_limbo.get(
                    "puntos_limbo"
                )
                self.muestras_circulos = [
                    tuple(muestra)
                    for muestra in datos_limbo.get(
                        "muestras_circulos",
                        [],
                    )
                ]
                self.visor.circulo_limbo = CirculoLimbo(
                    datos_limbo["centro_x"],
                    datos_limbo["centro_y"],
                    datos_limbo["radio"],
                    self.actualizar_medicion_limbo,
                )
                self.visor.escena.addItem(
                    self.visor.circulo_limbo
                )
                self.aplicar_estilo_limbo()

            for punto in datos.get("protuberancias", []):
                if self.visor.circulo_limbo is not None:
                    medicion = self.crear_medicion_protuberancia(
                        punto["x"],
                        punto["y"],
                    )
                    if (
                        medicion is not None
                        and "texto_x" in punto
                        and "texto_y" in punto
                    ):
                        medicion.establecer_desplazamiento_etiqueta(
                            punto["texto_x"],
                            punto["texto_y"],
                        )

            escala = self._escala_activa()

            if escala is not None:
                for datos_filamento in datos.get(
                    "filamentos",
                    [],
                ):
                    if isinstance(datos_filamento, dict):
                        puntos = datos_filamento.get(
                            "puntos",
                            [],
                        )
                    else:
                        puntos = datos_filamento
                    medicion = MedicionFilamento(
                        self.visor.escena,
                        [
                            QPointF(p["x"], p["y"])
                            for p in puntos
                        ],
                        escala,
                        self.visor.elemento_imagen.boundingRect(),
                        al_eliminar=(
                            self.eliminar_filamento_individual
                        ),
                        color=self.color_filamento,
                        tamano_texto=self.tamano_filamento,
                        familia_fuente=self.fuente_filamento,
                        antes_cambiar=self.registrar_estado,
                    )
                    if (
                        isinstance(datos_filamento, dict)
                        and "texto_x" in datos_filamento
                        and "texto_y" in datos_filamento
                    ):
                        medicion.establecer_desplazamiento_etiqueta(
                            datos_filamento["texto_x"],
                            datos_filamento["texto_y"],
                        )
                    self.mediciones_filamentos.append(
                        medicion
                    )

            for datos_mancha in datos.get("manchas", []):
                self.crear_etiqueta_mancha(
                    datos_mancha["x"],
                    datos_mancha["y"],
                    nombre=datos_mancha.get(
                        "nombre",
                        tr(
                            "sunspot_default",
                            number=(
                                len(self.etiquetas_manchas) + 1
                            ),
                        ),
                    ),
                    preguntar=False,
                    registrar=False,
                    radio=datos_mancha.get("radio", 18),
                    ancho=datos_mancha.get("ancho"),
                    alto=datos_mancha.get("alto"),
                    datos_catalogo=datos_mancha.get(
                        "catalogo"
                    ),
                )

            datos_comparacion = datos.get(
                "comparacion_tierra_luna"
            )

            if escala is not None and datos_comparacion:
                separacion_real = bool(
                    datos_comparacion.get(
                        "separacion_real",
                        False,
                    )
                )
                color_distancia = datos_comparacion.get(
                    "color_distancia",
                    self.color_distancia_tierra_luna,
                )
                mostrar_linea_distancia = bool(
                    datos_comparacion.get(
                        "mostrar_linea_distancia",
                        self.mostrar_linea_distancia,
                    )
                )
                color_informacion = datos_comparacion.get(
                    "color_informacion",
                    self.color_informacion_planetas,
                )
                self.color_distancia_tierra_luna = (
                    color_distancia
                )
                self.mostrar_linea_distancia = (
                    mostrar_linea_distancia
                )
                self.color_informacion_planetas = (
                    color_informacion
                )
                self.opcion_distancia_tierra_luna.blockSignals(
                    True
                )
                self.opcion_distancia_tierra_luna.setChecked(
                    separacion_real
                )
                self.opcion_distancia_tierra_luna.blockSignals(
                    False
                )
                self.opcion_linea_distancia.blockSignals(True)
                self.opcion_linea_distancia.setChecked(
                    mostrar_linea_distancia
                )
                self.opcion_linea_distancia.blockSignals(False)
                self.comparacion_tierra_luna = (
                    ComparacionTierraLuna(
                        self.visor.escena,
                        escala,
                        QPointF(
                            datos_comparacion["x"],
                            datos_comparacion["y"],
                        ),
                        separacion_real,
                        self.tamano_informacion_planetas,
                        familia_fuente=(
                            self.fuente_informacion_planetas
                        ),
                        imagen_tierra=(
                            datos_comparacion.get(
                                "imagen_tierra",
                                self.ruta_imagen_tierra,
                            )
                        ),
                        imagen_luna=(
                            datos_comparacion.get(
                                "imagen_luna",
                                self.ruta_imagen_luna,
                            )
                        ),
                        color_distancia=color_distancia,
                        mostrar_linea_distancia=(
                            mostrar_linea_distancia
                        ),
                        color_informacion=color_informacion,
                        tamano_distancia=(
                            datos_comparacion.get(
                                "tamano_distancia",
                                self.tamano_distancia_tierra_luna,
                            )
                        ),
                        familia_fuente_distancia=(
                            datos_comparacion.get(
                                "familia_fuente_distancia",
                                self.fuente_distancia_tierra_luna,
                            )
                        ),
                        tamano_informacion=(
                            datos_comparacion.get(
                                "tamano_informacion",
                                self.tamano_informacion_planetas,
                            )
                        ),
                        familia_fuente_informacion=(
                            datos_comparacion.get(
                                "familia_fuente_informacion",
                                self.fuente_informacion_planetas,
                            )
                        ),
                        al_eliminar=(
                            self.eliminar_comparacion_tierra_luna
                        ),
                        antes_cambiar=self.registrar_estado,
                    )
                )
                self.accion_quitar_tierra_luna.setEnabled(True)

            if escala is not None:
                for datos_planeta in datos.get(
                    "comparaciones_planetas",
                    [],
                ):
                    self._crear_planeta_desde_estado(
                        datos_planeta,
                        escala,
                    )

            self.accion_quitar_planetas.setEnabled(
                bool(self.comparaciones_planetas)
            )

            datos_regla = datos.get("regla", {})
            self.intervalo_regla = int(
                datos_regla.get(
                    "intervalo_km",
                    self.intervalo_regla,
                )
            )
            self.maximo_regla = int(
                datos_regla.get(
                    "maximo_km",
                    self.maximo_regla,
                )
            )
            self.color_regla = datos_regla.get(
                "color",
                self.color_regla,
            )
            self.grosor_regla = int(
                datos_regla.get(
                    "grosor",
                    self.grosor_regla,
                )
            )
            self.tamano_regla = int(
                datos_regla.get(
                    "tamano_texto",
                    self.tamano_regla,
                )
            )
            self.fuente_regla = datos_regla.get(
                "fuente",
                self.fuente_regla,
            )
            self._sincronizar_controles_proyecto()

            if (
                datos_regla.get("visible")
                and self.visor.circulo_limbo is not None
            ):
                self.alternar_regla_solar()

            if self.visor.circulo_limbo is not None:
                circulo = self.visor.circulo_limbo
                self.actualizar_medicion_limbo(
                    circulo.pos().x(),
                    circulo.pos().y(),
                    circulo.radio,
                )
            elif self.escala_equipo_km is not None:
                fuente = (
                    tr("active_scale_equipment")
                    if self.usar_escala_equipo
                    else tr("active_scale_limb")
                )
                self.etiqueta_medicion.setText(
                    f"{tr('recovered_calibration')}\n"
                    f"{self.descripcion_calibracion or ''}\n"
                    f"{tr('active_physical_scale')}: "
                    f"{(self._escala_activa() or self.escala_equipo_km):,.2f} km/px\n"
                    f"{tr('calibration_source')}: {fuente}"
                )

            self.actualizar_advertencia_calibracion()

            self.historial_estados.clear()
            self.ruta_proyecto_actual = ruta_proyecto
            self.ajustes.setValue(
                "proyectos/ultima_carpeta",
                str(ruta_proyecto.parent),
            )
            self.statusBar().showMessage(
                tr("project_opened", name=ruta_proyecto.name)
            )
        finally:
            self.suspendiendo_historial = False

    def _sincronizar_controles_proyecto(self):
        controles = (
            (self.selector_intervalo_regla, self.intervalo_regla),
            (self.selector_maximo_regla, self.maximo_regla),
            (self.selector_grosor_regla, self.grosor_regla),
            (self.selector_tamano_regla, self.tamano_regla),
            (self.selector_grosor, self.grosor_limbo),
        )

        for selector, valor in controles:
            indice = selector.findData(valor)

            if indice >= 0:
                selector.blockSignals(True)
                selector.setCurrentIndex(indice)
                selector.blockSignals(False)

        self.boton_color_limbo.setStyleSheet(
            f"border: 2px solid {self.color_limbo};"
        )
        self.boton_color_regla.setStyleSheet(
            f"border: 2px solid {self.color_regla};"
        )
        self.selector_fuente_regla.blockSignals(True)
        self.selector_fuente_regla.setCurrentFont(
            QFont(self.fuente_regla)
        )
        self.selector_fuente_regla.blockSignals(False)
        for clave, controles in self.controles_estilo.items():
            color, tamano, familia = self._valores_estilo(clave)
            controles["color"].setStyleSheet(
                f"border: 2px solid {color};"
            )
            controles["fuente"].blockSignals(True)
            controles["fuente"].setCurrentFont(QFont(familia))
            controles["fuente"].blockSignals(False)
            selector = controles["tamano"]
            indice = selector.findData(tamano)
            if indice >= 0:
                selector.blockSignals(True)
                selector.setCurrentIndex(indice)
                selector.blockSignals(False)

    def anadir_comparacion_tierra_luna(
        self,
        separacion_real=False,
    ):
        escala = self._escala_activa()

        if escala is None or self.visor.elemento_imagen is None:
            QMessageBox.information(
                self,
                tr("first_calibrate"),
                tr("comparison_needs_scale"),
            )
            return

        if self.comparacion_tierra_luna is not None:
            if (
                not separacion_real
                and self.comparacion_tierra_luna.separacion_real
            ):
                self.registrar_estado()
                self.opcion_distancia_tierra_luna.blockSignals(
                    True
                )
                self.opcion_distancia_tierra_luna.setChecked(
                    False
                )
                self.opcion_distancia_tierra_luna.blockSignals(
                    False
                )
                self.comparacion_tierra_luna\
                    .establecer_separacion_real(False)
                return

            self.statusBar().showMessage(
                tr("comparison_exists")
            )
            return

        self.registrar_estado()
        self.opcion_distancia_tierra_luna.blockSignals(True)
        self.opcion_distancia_tierra_luna.setChecked(
            bool(separacion_real)
        )
        self.opcion_distancia_tierra_luna.blockSignals(False)
        rectangulo = (
            self.visor.elemento_imagen.boundingRect()
        )
        posicion = rectangulo.center()
        self.comparacion_tierra_luna = (
            ComparacionTierraLuna(
                self.visor.escena,
                escala,
                posicion,
                bool(separacion_real),
                self.tamano_informacion_planetas,
                familia_fuente=self.fuente_informacion_planetas,
                imagen_tierra=self.ruta_imagen_tierra,
                imagen_luna=self.ruta_imagen_luna,
                color_distancia=(
                    self.color_distancia_tierra_luna
                ),
                tamano_distancia=self.tamano_distancia_tierra_luna,
                familia_fuente_distancia=(
                    self.fuente_distancia_tierra_luna
                ),
                mostrar_linea_distancia=(
                    self.mostrar_linea_distancia
                ),
                color_informacion=(
                    self.color_informacion_planetas
                ),
                tamano_informacion=self.tamano_informacion_planetas,
                familia_fuente_informacion=(
                    self.fuente_informacion_planetas
                ),
                al_eliminar=(
                    self.eliminar_comparacion_tierra_luna
                ),
                antes_cambiar=self.registrar_estado,
            )
        )
        self.accion_quitar_tierra_luna.setEnabled(True)
        self.statusBar().showMessage(
            tr("comparison_added")
        )

    def cambiar_distancia_tierra_luna(self, activa):
        if self.comparacion_tierra_luna is None:
            if activa:
                self.anadir_comparacion_tierra_luna(True)
            return

        self.registrar_estado()
        self.comparacion_tierra_luna.establecer_separacion_real(
            activa
        )

    def cambiar_linea_distancia_tierra_luna(self, visible):
        self.mostrar_linea_distancia = bool(visible)
        self.ajustes.setValue(
            "comparaciones/mostrar_linea_distancia",
            self.mostrar_linea_distancia,
        )

        if self.comparacion_tierra_luna is None:
            return

        self.registrar_estado()
        self.comparacion_tierra_luna\
            .establecer_linea_distancia_visible(visible)

    def seleccionar_color_distancia_tierra_luna(self):
        self.seleccionar_color_estilo("distancia")

    def quitar_comparacion_tierra_luna(self):
        if self.comparacion_tierra_luna is not None:
            self.comparacion_tierra_luna.eliminar()

    def eliminar_comparacion_tierra_luna(self, comparacion):
        if comparacion is self.comparacion_tierra_luna:
            self.comparacion_tierra_luna = None

        self.accion_quitar_tierra_luna.setEnabled(False)
        self.opcion_distancia_tierra_luna.blockSignals(True)
        self.opcion_distancia_tierra_luna.setChecked(False)
        self.opcion_distancia_tierra_luna.blockSignals(False)
        self.statusBar().showMessage(
            tr("comparison_removed")
        )

    def seleccionar_color_informacion_planetas(self):
        self.seleccionar_color_estilo("informacion_planetaria")

    def anadir_comparacion_planeta(self, planeta):
        escala = self._escala_activa()

        if escala is None or self.visor.elemento_imagen is None:
            QMessageBox.information(
                self,
                tr("first_calibrate"),
                tr("comparison_needs_scale"),
            )
            return

        if planeta in self.comparaciones_planetas:
            self.statusBar().showMessage(
                tr("planet_exists", name=tr(planeta))
            )
            return

        self.registrar_estado()
        rectangulo = self.visor.elemento_imagen.boundingRect()
        separacion = 35 * len(self.comparaciones_planetas)
        posicion = rectangulo.center() + QPointF(
            separacion,
            separacion,
        )
        comparacion = ComparacionPlaneta(
            self.visor.escena,
            planeta,
            escala,
            posicion,
            self.tamano_informacion_planetas,
            familia_fuente=self.fuente_informacion_planetas,
            imagen=self.rutas_imagenes_planetas.get(planeta),
            color_informacion=(
                self.color_informacion_planetas
            ),
            al_eliminar=self.eliminar_comparacion_planeta,
            antes_cambiar=self.registrar_estado,
        )
        self.comparaciones_planetas[planeta] = comparacion
        self.accion_quitar_planetas.setEnabled(True)
        self.statusBar().showMessage(
            tr("planet_added", name=tr(planeta))
        )

    def eliminar_comparacion_planeta(self, comparacion):
        planeta = comparacion.planeta

        if self.comparaciones_planetas.get(planeta) is comparacion:
            del self.comparaciones_planetas[planeta]

        self.accion_quitar_planetas.setEnabled(
            bool(self.comparaciones_planetas)
        )
        self.statusBar().showMessage(
            tr("planet_removed", name=tr(planeta))
        )

    def quitar_comparaciones_planetas(self):
        if not self.comparaciones_planetas:
            return

        self.registrar_estado()

        for comparacion in list(
            self.comparaciones_planetas.values()
        ):
            comparacion.antes_cambiar = None
            comparacion.eliminar()

        self.comparaciones_planetas.clear()
        self.accion_quitar_planetas.setEnabled(False)

    def seleccionar_imagen_planeta(self, planeta):
        ruta_actual = self.rutas_imagenes_planetas.get(planeta)
        carpeta = (
            str(Path(ruta_actual).parent)
            if ruta_actual
            else self.ajustes.value(
                "comparaciones/ultima_carpeta",
                "",
                type=str,
            )
        )
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            tr(
                "select_planet_image",
                name=tr(planeta),
            ),
            carpeta,
            tr("image_filter"),
        )

        if not ruta:
            return

        if planeta in self.comparaciones_planetas:
            self.registrar_estado()

        self.rutas_imagenes_planetas[planeta] = ruta
        self.ajustes.setValue(
            f"comparaciones/imagen_{planeta}",
            ruta,
        )
        self.ajustes.setValue(
            "comparaciones/ultima_carpeta",
            str(Path(ruta).parent),
        )

        if planeta in self.comparaciones_planetas:
            self.comparaciones_planetas[
                planeta
            ].establecer_imagen(ruta)

        self.statusBar().showMessage(
            tr(
                "planet_custom_applied",
                name=tr(planeta),
            )
        )

    def restaurar_imagenes_planetas(self):
        if not any(self.rutas_imagenes_planetas.values()):
            return

        if self.comparaciones_planetas:
            self.registrar_estado()

        for planeta in PLANETAS:
            self.rutas_imagenes_planetas[planeta] = None
            self.ajustes.remove(
                f"comparaciones/imagen_{planeta}"
            )

            if planeta in self.comparaciones_planetas:
                self.comparaciones_planetas[
                    planeta
                ].establecer_imagen()

        self.statusBar().showMessage(
            tr("planet_defaults_restored")
        )

    def _crear_planeta_desde_estado(self, datos, escala):
        planeta = datos.get("planeta")

        if planeta not in PLANETAS:
            return

        imagen = datos.get(
            "imagen",
            self.rutas_imagenes_planetas.get(planeta),
        )
        color_informacion = datos.get(
            "color_informacion",
            self.color_informacion_planetas,
        )
        self.color_informacion_planetas = color_informacion
        self.rutas_imagenes_planetas[planeta] = imagen
        comparacion = ComparacionPlaneta(
            self.visor.escena,
            planeta,
            escala,
            QPointF(datos["x"], datos["y"]),
            self.tamano_informacion_planetas,
            imagen=imagen,
            color_informacion=color_informacion,
            familia_fuente=self.fuente_informacion_planetas,
            al_eliminar=self.eliminar_comparacion_planeta,
            antes_cambiar=self.registrar_estado,
        )
        self.comparaciones_planetas[planeta] = comparacion

    def _seleccionar_imagen_comparacion(self, cuerpo):
        clave = (
            "imagen_tierra"
            if cuerpo == "Tierra"
            else "imagen_luna"
        )
        ruta_actual = (
            self.ruta_imagen_tierra
            if cuerpo == "Tierra"
            else self.ruta_imagen_luna
        )
        carpeta = (
            str(Path(ruta_actual).parent)
            if ruta_actual
            else self.ajustes.value(
                "comparaciones/ultima_carpeta",
                "",
                type=str,
            )
        )
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            tr(
                "select_body_image",
                body=tr(
                    "earth" if cuerpo == "Tierra" else "moon"
                ),
            ),
            carpeta,
            tr("image_filter"),
        )

        if not ruta:
            return

        self.registrar_estado()

        if cuerpo == "Tierra":
            self.ruta_imagen_tierra = ruta
        else:
            self.ruta_imagen_luna = ruta

        self.ajustes.setValue(
            f"comparaciones/{clave}",
            ruta,
        )
        self.ajustes.setValue(
            "comparaciones/ultima_carpeta",
            str(Path(ruta).parent),
        )

        if self.comparacion_tierra_luna is not None:
            self.comparacion_tierra_luna.establecer_imagenes(
                self.ruta_imagen_tierra,
                self.ruta_imagen_luna,
            )

        self.statusBar().showMessage(
            tr(
                "custom_applied",
                body=tr(
                    "earth" if cuerpo == "Tierra" else "moon"
                ),
            )
        )

    def seleccionar_imagen_tierra(self):
        self._seleccionar_imagen_comparacion("Tierra")

    def seleccionar_imagen_luna(self):
        self._seleccionar_imagen_comparacion("Luna")

    def restaurar_imagenes_tierra_luna(self):
        if (
            self.ruta_imagen_tierra is None
            and self.ruta_imagen_luna is None
        ):
            return

        self.registrar_estado()
        self.ruta_imagen_tierra = None
        self.ruta_imagen_luna = None
        self.ajustes.remove("comparaciones/imagen_tierra")
        self.ajustes.remove("comparaciones/imagen_luna")

        if self.comparacion_tierra_luna is not None:
            self.comparacion_tierra_luna.establecer_imagenes()

        self.statusBar().showMessage(
            tr("defaults_restored")
        )

    def actualizar_comparacion_tierra_luna(self):
        escala = self._escala_activa()

        if (
            escala is not None
            and self.comparacion_tierra_luna is not None
        ):
            self.comparacion_tierra_luna.establecer_escala(
                escala
            )

        if escala is not None:
            for comparacion in (
                self.comparaciones_planetas.values()
            ):
                comparacion.establecer_escala(escala)

    def alternar_regla_solar(self):
        if self.regla_solar is not None:
            self.regla_solar.eliminar()
            self.regla_solar = None
            self.boton_regla.setText(tr("show_ruler"))
            self.statusBar().showMessage(tr("ruler_hidden"))
            return

        circulo = self.visor.circulo_limbo

        if circulo is None:
            QMessageBox.information(
                self,
                tr("first_adjust_limb"),
                tr("ruler_needs_limb"),
            )
            return

        self.regla_solar = ReglaSolar(
            self.visor.escena,
            self.intervalo_regla,
            self.maximo_regla,
            self.color_regla,
            self.grosor_regla,
            self.tamano_regla,
            self.fuente_regla,
        )
        self.boton_regla.setText(tr("hide_ruler"))
        self.actualizar_regla_solar()
        self.statusBar().showMessage(tr("ruler_visible"))

    def seleccionar_color_regla(self):
        color = QColorDialog.getColor(
            self.color_regla,
            self,
            tr("select_ruler_color"),
        )

        if not color.isValid():
            return

        self.color_regla = color.name()
        self.ajustes.setValue(
            "regla/color",
            self.color_regla,
        )
        self.boton_color_regla.setStyleSheet(
            f"border: 2px solid {self.color_regla};"
        )
        self.cambiar_configuracion_regla()

    def cambiar_configuracion_regla(self, indice=None):
        intervalo = self.selector_intervalo_regla.currentData()
        maximo = self.selector_maximo_regla.currentData()
        grosor = self.selector_grosor_regla.currentData()
        tamano = self.selector_tamano_regla.currentData()

        if None in (intervalo, maximo, grosor, tamano):
            return

        self.intervalo_regla = int(intervalo)
        self.maximo_regla = int(maximo)
        self.grosor_regla = int(grosor)
        self.tamano_regla = int(tamano)

        self.ajustes.setValue(
            "regla/intervalo_km",
            self.intervalo_regla,
        )
        self.ajustes.setValue(
            "regla/maximo_km",
            self.maximo_regla,
        )
        self.ajustes.setValue(
            "regla/grosor",
            self.grosor_regla,
        )
        self.ajustes.setValue(
            "regla/tamano_texto",
            self.tamano_regla,
        )

        if self.regla_solar is not None:
            self.regla_solar.establecer_configuracion(
                self.intervalo_regla,
                self.maximo_regla,
                self.color_regla,
                self.grosor_regla,
                self.tamano_regla,
                self.fuente_regla,
            )
            self.actualizar_regla_solar()

    def cambiar_fuente_regla(self, fuente):
        self.fuente_regla = fuente.family()
        self.ajustes.setValue(
            "regla/fuente",
            self.fuente_regla,
        )
        self.cambiar_configuracion_regla()

    def actualizar_regla_solar(self):
        if (
            self.regla_solar is None
            or self.visor.circulo_limbo is None
            or self.visor.elemento_imagen is None
        ):
            return

        circulo = self.visor.circulo_limbo
        escala_limbo = 1_391_400 / (circulo.radio * 2)
        escala = (
            self.escala_equipo_km
            if (
                self.escala_equipo_km is not None
                and self.usar_escala_equipo
            )
            else escala_limbo
        )

        self.regla_solar.actualizar(
            circulo.pos().x(),
            circulo.pos().y(),
            circulo.radio,
            escala,
            self.visor.elemento_imagen.boundingRect(),
        )

    def _atributos_estilo(self, clave):
        nombres = {
            "protuberancia": (
                "color_protuberancia",
                "tamano_protuberancia",
                "fuente_protuberancia",
            ),
            "filamento": (
                "color_filamento",
                "tamano_filamento",
                "fuente_filamento",
            ),
            "ra": (
                "color_ra",
                "tamano_ra",
                "fuente_ra",
            ),
            "distancia": (
                "color_distancia_tierra_luna",
                "tamano_distancia_tierra_luna",
                "fuente_distancia_tierra_luna",
            ),
            "informacion_planetaria": (
                "color_informacion_planetas",
                "tamano_informacion_planetas",
                "fuente_informacion_planetas",
            ),
        }
        return nombres[clave]

    def _guardar_estilo(self, clave):
        color, tamano, fuente = self._valores_estilo(clave)
        prefijo = {
            "protuberancia": "anotaciones/protuberancia",
            "filamento": "anotaciones/filamento",
            "ra": "anotaciones/ra",
            "distancia": "anotaciones/distancia",
            "informacion_planetaria": (
                "anotaciones/informacion_planetaria"
            ),
        }[clave]
        self.ajustes.setValue(f"{prefijo}/color", color)
        self.ajustes.setValue(f"{prefijo}/tamano", tamano)
        self.ajustes.setValue(f"{prefijo}/fuente", fuente)

        if clave == "ra":
            self.color_anotaciones = self.color_ra
            self.tamano_anotaciones = self.tamano_ra
            self.fuente_anotaciones = self.fuente_ra
            self.ajustes.setValue("anotaciones/color", color)
            self.ajustes.setValue("anotaciones/tamano", tamano)
            self.ajustes.setValue("anotaciones/fuente", fuente)
        elif clave == "distancia":
            self.ajustes.setValue(
                "comparaciones/color_distancia",
                color,
            )
        elif clave == "informacion_planetaria":
            self.ajustes.setValue(
                "comparaciones/color_informacion_planetas",
                color,
            )

    def seleccionar_color_estilo(self, clave):
        color_actual, _, _ = self._valores_estilo(clave)
        claves_dialogo = {
            "protuberancia": "select_prominence_color",
            "filamento": "select_filament_color",
            "ra": "select_active_region_color",
            "distancia": "select_distance_color",
            "informacion_planetaria": "select_planet_info_color",
        }
        color = QColorDialog.getColor(
            QColor(color_actual),
            self,
            tr(claves_dialogo[clave]),
        )

        if not color.isValid():
            return

        nombre_color, _, _ = self._atributos_estilo(clave)
        setattr(self, nombre_color, color.name())
        self._guardar_estilo(clave)
        controles = self.controles_estilo.get(clave)
        if controles is not None:
            controles["color"].setStyleSheet(
                f"border: 2px solid {color.name()};"
            )
        self.aplicar_estilo_estilo(clave)

    def cambiar_tamano_estilo(self, clave, indice):
        selector = self.controles_estilo[clave]["tamano"]
        tamano = selector.itemData(indice)
        if tamano is None:
            return
        _, nombre_tamano, _ = self._atributos_estilo(clave)
        setattr(self, nombre_tamano, int(tamano))
        self._guardar_estilo(clave)
        self.aplicar_estilo_estilo(clave)

    def cambiar_fuente_estilo(self, clave, fuente):
        _, _, nombre_fuente = self._atributos_estilo(clave)
        setattr(self, nombre_fuente, fuente.family())
        self._guardar_estilo(clave)
        self.aplicar_estilo_estilo(clave)

    def aplicar_estilo_estilo(self, clave):
        color, tamano, familia = self._valores_estilo(clave)

        if clave == "protuberancia":
            for medicion in self.mediciones_protuberancias:
                medicion.establecer_estilo(color, tamano, familia)
        elif clave == "filamento":
            mediciones = list(self.mediciones_filamentos)
            if self.filamento_en_curso is not None:
                mediciones.append(self.filamento_en_curso)
            for medicion in mediciones:
                medicion.establecer_estilo(color, tamano, familia)
        elif clave == "ra":
            for etiqueta in self.etiquetas_manchas:
                etiqueta.establecer_estilo(color, tamano, familia)
            acomodar_etiquetas(self.etiquetas_manchas)
        elif clave == "distancia":
            if self.comparacion_tierra_luna is not None:
                self.comparacion_tierra_luna.establecer_estilo_distancia(
                    color,
                    tamano,
                    familia,
                )
        elif clave == "informacion_planetaria":
            if self.comparacion_tierra_luna is not None:
                self.comparacion_tierra_luna.establecer_estilo_informacion(
                    color,
                    tamano,
                    familia,
                )
            for comparacion in self.comparaciones_planetas.values():
                comparacion.establecer_estilo_informacion(
                    color,
                    tamano,
                    familia,
                )

    def aplicar_estilo_anotaciones(self):
        for clave in self._atributos_estilo_claves():
            self.aplicar_estilo_estilo(clave)

    @staticmethod
    def _atributos_estilo_claves():
        return (
            "protuberancia",
            "filamento",
            "ra",
            "distancia",
            "informacion_planetaria",
        )

    # Métodos antiguos conservados para compatibilidad con extensiones.
    def seleccionar_color_anotaciones(self):
        self.seleccionar_color_estilo("ra")

    def cambiar_tamano_anotaciones(self, indice):
        self.cambiar_tamano_estilo("ra", indice)

    def _nombre_region_catalogo(self, region):
        lineas = [region.nombre]
        if region.clase_magnetica:
            lineas.append(
                tr(
                    "magnetic_class_short",
                    value=region.clase_magnetica,
                )
            )
        if (
            self.mostrar_conteo_manchas
            and region.manchas is not None
        ):
            clave = (
                "one_sunspot"
                if region.manchas == 1
                else "many_sunspots"
            )
            lineas.append(
                tr(clave, count=region.manchas)
            )
        return "\n".join(lineas)

    @staticmethod
    def _datos_region_catalogo(region):
        return {
            "numero": region.numero,
            "ubicacion": region.ubicacion,
            "manchas": region.manchas,
            "area": region.area,
            "clasificacion": region.clasificacion,
            "clase_magnetica": region.clase_magnetica,
            "fuentes": region.fuentes,
        }

    def consultar_catalogos_regiones(self):
        if self.visor.elemento_imagen is None:
            QMessageBox.information(
                self,
                tr("first_open_image"),
                tr("sunspot_needs_image"),
            )
            return

        if self.visor.modo_medicion_filamento:
            self.cancelar_medicion_filamento()

        self._terminar_modo_mancha()
        self.visor.modo_medicion_protuberancia = False

        instante, fuente_fecha = leer_fecha_hora_imagen(
            self.visor.ruta_imagen
        )
        dialogo = DialogoConsultaRegiones(
            instante,
            fuente_fecha,
            rotacion=self.rotacion_catalogo,
            espejo_horizontal=(
                self.espejo_horizontal_catalogo
            ),
            espejo_vertical=self.espejo_vertical_catalogo,
            mostrar_manchas=self.mostrar_conteo_manchas,
            fuente_referencia=self.fuente_referencia_catalogo,
            puede_alinear=(
                self.visor.circulo_limbo is not None
            ),
            parent=self,
        )

        if dialogo.exec() != QDialog.Accepted:
            return

        instante = dialogo.instante_utc()
        self.instante_catalogo = instante
        self.rotacion_catalogo = dialogo.rotacion.value()
        self.espejo_horizontal_catalogo = (
            dialogo.espejo_horizontal.isChecked()
        )
        self.espejo_vertical_catalogo = (
            dialogo.espejo_vertical.isChecked()
        )
        # Una consulta nueva parte de la placa nominal. Si la alineación
        # automática encuentra una corrección global, se sustituye abajo.
        self.ajuste_catalogo_x = 0.0
        self.ajuste_catalogo_y = 0.0
        self.escala_mapa_catalogo = 1.0
        self.mostrar_conteo_manchas = (
            dialogo.mostrar_manchas.isChecked()
        )
        alinear_automaticamente = (
            dialogo.alinear_automaticamente.isChecked()
        )
        self.fuente_referencia_catalogo = (
            dialogo.fuente_referencia.currentData()
        )
        self.ajustes.setValue(
            "catalogo/rotacion",
            self.rotacion_catalogo,
        )
        self.ajustes.setValue(
            "catalogo/espejo_horizontal",
            self.espejo_horizontal_catalogo,
        )
        self.ajustes.setValue(
            "catalogo/espejo_vertical",
            self.espejo_vertical_catalogo,
        )
        self.ajustes.setValue(
            "catalogo/mostrar_conteo",
            self.mostrar_conteo_manchas,
        )
        self.ajustes.setValue(
            "catalogo/fuente_referencia",
            self.fuente_referencia_catalogo,
        )

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage(
            tr("querying_catalogs")
        )

        try:
            regiones, errores = consultar_regiones(instante)
        except ErrorCatalogoRegiones as error:
            QMessageBox.warning(
                self,
                tr("catalog_error_title"),
                tr(
                    "catalog_error_text",
                    details=str(error),
                ),
            )
            self.statusBar().showMessage(
                tr("catalog_query_failed")
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

        if not regiones:
            QMessageBox.information(
                self,
                tr("catalog_results_title"),
                tr("catalog_no_regions"),
            )
            self.statusBar().showMessage(
                tr("catalog_no_regions")
            )
            return

        self.ultimas_regiones_catalogo = regiones
        errores_referencia = []
        detalle_alineacion = ""

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage(
            tr("downloading_solar_references")
        )
        try:
            referencias, errores_referencia = (
                descargar_referencias(
                    instante,
                    self.fuente_referencia_catalogo,
                )
            )
            circulo = self.visor.circulo_limbo
            resultado_registro = None
            referencia_elegida = referencias[0]

            if (
                alinear_automaticamente
                and circulo is not None
                and self.visor.ruta_imagen is not None
            ):
                resultado_registro = registrar_orientacion(
                    self.visor.ruta_imagen,
                    circulo.pos().x(),
                    circulo.pos().y(),
                    circulo.radio,
                    referencias,
                )
                referencia_elegida = resultado_registro.referencia

                # En H-alfa la textura puede no correlacionar con la
                # referencia aunque las posiciones NOAA sí sean visibles.
                # El catálogo resuelve la orientación directamente sobre la
                # fotografía y se prefiere cuando alcanza confianza alta.
                resultado_catalogo = registrar_orientacion_catalogo(
                    self.visor.ruta_imagen,
                    circulo.pos().x(),
                    circulo.pos().y(),
                    circulo.radio,
                    regiones,
                    instante,
                    referencia_elegida,
                )
                # La ruta guiada por NOAA/HEK debe tener prioridad sobre la
                # correlación de textura. Esta última puede devolver una
                # puntuación alta para una imagen H-alfa que se parece poco a
                # HMI/GONG y, en ese caso, dejaba la orientación inicial como
                # si la fotografía ya estuviera norte-arriba. Dos AR
                # compactas catalogadas son una señal más útil: el resultado
                # se aplica y la confianza se comunica aparte.
                if (
                    resultado_catalogo.confianza in ("alta", "media")
                    or (
                        resultado_catalogo.evidencia >= 2
                        and resultado_catalogo.puntuacion >= 0.10
                    )
                ):
                    resultado_registro = resultado_catalogo

                confianza = tr(
                    "alignment_confidence_"
                    f"{resultado_registro.confianza}"
                )
                # Una solución guiada por el catálogo no siempre puede
                # alcanzar la etiqueta «alta» en H-alfa: la textura es muy
                # distinta de HMI/GONG y a veces solo se ven dos o tres
                # núcleos compactos.  Antes solo aplicábamos la orientación
                # cuando era «alta», de modo que una solución con evidencia
                # útil se calculaba pero la fotografía conservaba la
                # orientación anterior (aparentemente no hacía nada).
                # Aplicamos también una solución «media» o una solución con
                # al menos dos coincidencias compactas y una puntuación
                # positiva; la etiqueta de confianza sigue informando al
                # usuario del grado de seguridad.
                orientacion_utilizable = (
                    resultado_registro.confianza in ("alta", "media")
                    or (
                        resultado_registro.evidencia >= 2
                        and resultado_registro.puntuacion >= 0.20
                    )
                )
                if orientacion_utilizable:
                    self.rotacion_catalogo = (
                        resultado_registro.rotacion
                    )
                    self.espejo_horizontal_catalogo = (
                        resultado_registro.espejo_horizontal
                    )
                    self.espejo_vertical_catalogo = (
                        resultado_registro.espejo_vertical
                    )
                    self.ajuste_catalogo_x = (
                        resultado_registro.desplazamiento_x
                    )
                    self.ajuste_catalogo_y = (
                        resultado_registro.desplazamiento_y
                    )
                    self.escala_mapa_catalogo = (
                        resultado_registro.escala_mapa
                    )
                    detalle_alineacion = tr(
                        "automatic_alignment_applied",
                        source=(
                            resultado_registro.referencia.fuente.nombre
                        ),
                        rotation=self.rotacion_catalogo,
                        confidence=confianza,
                        mirrors=(
                            tr("mirror_summary_both")
                            if (
                                resultado_registro.espejo_horizontal
                                and resultado_registro.espejo_vertical
                            )
                            else tr("mirror_summary_horizontal")
                            if resultado_registro.espejo_horizontal
                            else tr("mirror_summary_vertical")
                            if resultado_registro.espejo_vertical
                            else tr("mirror_summary_none")
                        ),
                        evidence=resultado_registro.evidencia,
                    )
                else:
                    detalle_alineacion = tr(
                        "automatic_alignment_low",
                        source=(
                            resultado_registro.referencia.fuente.nombre
                        ),
                        confidence=confianza,
                    )
            # Las posiciones NOAA/HEK ya están en coordenadas heliográficas.
            # No se refinan automáticamente contra la textura de la
            # referencia: en H-alfa eso desplaza una AR hacia un filamento o
            # una plage cercana y hace que la imagen anotada parezca errónea.
            for region in regiones:
                region.refinado_x = None
                region.refinado_y = None
                region.confianza_refinado = None
            refinadas = 0
            self.ruta_referencia_catalogo = (
                crear_referencia_anotada(
                    referencia_elegida,
                    regiones,
                    instante,
                    mostrar_conteo=self.mostrar_conteo_manchas,
                )
            )
            self.nombre_fuente_referencia_catalogo = (
                referencia_elegida.fuente.nombre
            )
            if detalle_alineacion:
                detalle_alineacion += " "
            detalle_alineacion += tr(
                "catalog_local_refinement",
                refined=refinadas,
                total=len(regiones),
            )
            self.detalle_alineacion_catalogo = (
                detalle_alineacion
            )
            self.boton_referencia_solar.setVisible(True)
        except ErrorReferenciaSolar as error:
            errores_referencia.append(str(error))
            detalle_alineacion = tr(
                "automatic_alignment_unavailable"
            )
        except (OSError, ValueError) as error:
            errores_referencia.append(str(error))
            detalle_alineacion = tr(
                "automatic_alignment_unavailable"
            )
        finally:
            QApplication.restoreOverrideCursor()

        self.ajustes.setValue(
            "catalogo/rotacion",
            self.rotacion_catalogo,
        )
        self.ajustes.setValue(
            "catalogo/espejo_horizontal",
            self.espejo_horizontal_catalogo,
        )
        self.ajustes.setValue(
            "catalogo/espejo_vertical",
            self.espejo_vertical_catalogo,
        )
        self.ajustes.setValue(
            "catalogo/desplazamiento_x",
            self.ajuste_catalogo_x,
        )
        self.ajustes.setValue(
            "catalogo/desplazamiento_y",
            self.ajuste_catalogo_y,
        )
        self.ajustes.setValue(
            "catalogo/escala_mapa",
            self.escala_mapa_catalogo,
        )

        resultados = DialogoResultadosRegiones(
            regiones,
            errores=errores + errores_referencia,
            detalle_alineacion=detalle_alineacion,
            parent=self,
        )

        if resultados.exec() != QDialog.Accepted:
            return

        seleccionadas = resultados.seleccionadas()
        if not seleccionadas:
            return

        circulo = self.visor.circulo_limbo
        if circulo is None:
            QMessageBox.information(
                self,
                tr("catalog_loaded_title"),
                tr("catalog_loaded_manual_text"),
            )
            self.statusBar().showMessage(
                tr(
                    "catalog_loaded",
                    count=len(regiones),
                )
            )
            return

        self.registrar_estado()
        self.suspendiendo_historial = True
        agregadas = 0
        fuera = 0
        rectangulo_imagen = (
            self.visor.elemento_imagen.boundingRect()
        )

        try:
            for region in seleccionadas:
                posicion = posicion_en_imagen(
                    region,
                    instante,
                    circulo.pos().x(),
                    circulo.pos().y(),
                    circulo.radio,
                    rotacion=self.rotacion_catalogo,
                    espejo_horizontal=(
                        self.espejo_horizontal_catalogo
                    ),
                    espejo_vertical=(
                        self.espejo_vertical_catalogo
                    ),
                    desplazamiento_x=self.ajuste_catalogo_x,
                    desplazamiento_y=self.ajuste_catalogo_y,
                    escala_mapa=self.escala_mapa_catalogo,
                )
                if posicion is None:
                    fuera += 1
                    continue

                x, y = posicion
                if not rectangulo_imagen.contains(QPointF(x, y)):
                    fuera += 1
                    continue

                ancho, alto = tamano_region_en_imagen(
                    region,
                    circulo.radio,
                )
                existente = next(
                    (
                        etiqueta
                        for etiqueta in self.etiquetas_manchas
                        if str(
                            etiqueta.datos_catalogo.get(
                                "numero",
                                "",
                            )
                        )
                        == str(region.numero)
                    ),
                    None,
                )
                if existente is not None:
                    existente.ancho = ancho
                    existente.alto = alto
                    existente.datos_catalogo = (
                        self._datos_region_catalogo(region)
                    )
                    existente.establecer_nombre(
                        self._nombre_region_catalogo(region)
                    )
                    existente.grupo.setPos(QPointF(x, y))
                    existente.actualizar()
                    agregadas += 1
                    continue

                self.crear_etiqueta_mancha(
                    x,
                    y,
                    nombre=self._nombre_region_catalogo(region),
                    preguntar=False,
                    registrar=False,
                    ancho=ancho,
                    alto=alto,
                    datos_catalogo=(
                        self._datos_region_catalogo(region)
                    ),
                )
                agregadas += 1
        finally:
            self.suspendiendo_historial = False

        acomodar_etiquetas(self.etiquetas_manchas)

        self.statusBar().showMessage(
            tr(
                "catalog_regions_added",
                count=agregadas,
                skipped=fuera,
            )
        )

    def mostrar_referencia_solar(self):
        if (
            self.ruta_referencia_catalogo is None
            or not Path(self.ruta_referencia_catalogo).exists()
        ):
            QMessageBox.information(
                self,
                tr("solar_reference_title"),
                tr("solar_reference_unavailable"),
            )
            return

        DialogoReferenciaSolar(
            self.ruta_referencia_catalogo,
            self.nombre_fuente_referencia_catalogo,
            self.detalle_alineacion_catalogo,
            parent=self,
        ).exec()

    def iniciar_etiquetado_mancha(self):
        if self.visor.elemento_imagen is None:
            QMessageBox.information(
                self,
                tr("first_open_image"),
                tr("sunspot_needs_image"),
            )
            return

        if self.visor.modo_medicion_filamento:
            self.cancelar_medicion_filamento()

        self.visor.modo_medicion_protuberancia = False
        self.visor.modo_etiquetado_mancha = True
        self.visor.setDragMode(QGraphicsView.NoDrag)
        self.visor.setCursor(Qt.CrossCursor)
        self.visor.setFocus()
        self.statusBar().showMessage(tr("sunspot_instructions"))

    def _terminar_modo_mancha(self):
        self.visor.limpiar_previsualizacion_region_mancha()
        self.visor.modo_etiquetado_mancha = False
        self.visor.setDragMode(QGraphicsView.ScrollHandDrag)
        self.visor.unsetCursor()

    def crear_region_mancha_manual(
        self,
        x,
        y,
        ancho,
        alto,
    ):
        nombre = None
        datos_catalogo = None
        preguntar = True

        if self.ultimas_regiones_catalogo:
            opcion_manual = tr("manual_region_name")
            opciones = [opcion_manual]
            por_opcion = {}

            for region in self.ultimas_regiones_catalogo:
                conteo = (
                    tr(
                        "catalog_spot_suffix",
                        count=region.manchas,
                    )
                    if region.manchas is not None
                    else ""
                )
                opcion = (
                    f"{region.nombre} · "
                    f"{region.ubicacion or '—'}{conteo}"
                )
                opciones.append(opcion)
                por_opcion[opcion] = region

            elegida, aceptado = QInputDialog.getItem(
                self,
                tr("select_active_region"),
                tr("select_active_region_prompt"),
                opciones,
                0,
                False,
            )
            if not aceptado:
                self._terminar_modo_mancha()
                return

            region = por_opcion.get(elegida)
            if region is not None:
                nombre = self._nombre_region_catalogo(region)
                datos_catalogo = (
                    self._datos_region_catalogo(region)
                )
                preguntar = False

        self.crear_etiqueta_mancha(
            x,
            y,
            nombre=nombre,
            preguntar=preguntar,
            ancho=ancho,
            alto=alto,
            datos_catalogo=datos_catalogo,
        )

    def crear_etiqueta_mancha(
        self,
        x,
        y,
        nombre=None,
        preguntar=True,
        registrar=True,
        radio=18,
        ancho=None,
        alto=None,
        datos_catalogo=None,
    ):
        self._terminar_modo_mancha()

        if self.visor.elemento_imagen is None:
            return None

        if nombre is None:
            nombre = tr(
                "sunspot_default",
                number=len(self.etiquetas_manchas) + 1,
            )

        if preguntar:
            nombre, aceptado = QInputDialog.getText(
                self,
                tr("sunspot_name_title"),
                tr("sunspot_name_prompt"),
                text=nombre,
            )

            if not aceptado:
                self.statusBar().showMessage(
                    tr("sunspot_cancelled")
                )
                return None

            nombre = nombre.strip() or tr(
                "sunspot_default",
                number=len(self.etiquetas_manchas) + 1,
            )

        if registrar:
            self.registrar_estado()

        etiqueta = EtiquetaMancha(
            self.visor.escena,
            QPointF(float(x), float(y)),
            nombre,
            self.visor.elemento_imagen.boundingRect(),
            color=self.color_ra,
            tamano_texto=self.tamano_ra,
            familia_fuente=self.fuente_ra,
            radio=radio,
            ancho=ancho,
            alto=alto,
            datos_catalogo=datos_catalogo,
            al_eliminar=self.eliminar_etiqueta_mancha,
            al_editar=self.editar_etiqueta_mancha,
            antes_cambiar=self.registrar_estado,
        )
        self.etiquetas_manchas.append(etiqueta)
        self.statusBar().showMessage(
            tr("sunspot_created", name=nombre)
        )
        return etiqueta

    def editar_etiqueta_mancha(self, etiqueta):
        nombre, aceptado = QInputDialog.getText(
            self,
            tr("sunspot_name_title"),
            tr("sunspot_name_prompt"),
            text=etiqueta.nombre,
        )

        if not aceptado or not nombre.strip():
            return

        self.registrar_estado()
        etiqueta.establecer_nombre(nombre.strip())
        self.statusBar().showMessage(
            tr("sunspot_renamed", name=nombre.strip())
        )

    def eliminar_etiqueta_mancha(self, etiqueta):
        if etiqueta in self.etiquetas_manchas:
            self.etiquetas_manchas.remove(etiqueta)

        self.statusBar().showMessage(tr("sunspot_deleted"))

    def iniciar_medicion_protuberancia(self):
        self._terminar_modo_mancha()

        if self.visor.modo_medicion_filamento:
            self.cancelar_medicion_filamento()

        if self.visor.circulo_limbo is None:
            QMessageBox.information(
                self,
                tr("first_adjust_limb"),
                tr("prominence_needs_limb"),
            )
            return

        self.visor.modo_medicion_protuberancia = True
        self.visor.setDragMode(QGraphicsView.NoDrag)
        self.visor.setCursor(Qt.CrossCursor)
        self.statusBar().showMessage(
            tr("click_prominence_tip")
        )

    def crear_medicion_protuberancia(self, x, y):
        self.registrar_estado()
        circulo = self.visor.circulo_limbo
        escala_limbo = 1_391_400 / (circulo.radio * 2)
        escala = (
            self.escala_equipo_km
            if (
                self.escala_equipo_km is not None
                and self.usar_escala_equipo
            )
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
            color_anotacion=self.color_protuberancia,
            tamano_texto=self.tamano_protuberancia,
            familia_fuente=self.fuente_protuberancia,
            antes_cambiar=self.registrar_estado,
        )
        self.mediciones_protuberancias.append(medicion)
        self.statusBar().showMessage(
            tr("prominence_created")
        )
        return medicion

    def iniciar_medicion_filamento(self):
        self._terminar_modo_mancha()

        if self.visor.elemento_imagen is None:
            QMessageBox.information(
                self,
                tr("first_open_image"),
                tr("need_solar_image_filament"),
            )
            return

        if self.filamento_en_curso is not None:
            self.cancelar_medicion_filamento()

        self.visor.modo_medicion_filamento = True
        self.visor.modo_medicion_protuberancia = False
        self.visor.setDragMode(QGraphicsView.NoDrag)
        self.visor.setCursor(Qt.CrossCursor)
        self.visor.setFocus()
        self.boton_aceptar_filamento.setVisible(True)
        self.statusBar().showMessage(
            tr("filament_instructions")
        )

    def obtener_diferencia_calibracion(self):
        circulo = self.visor.circulo_limbo
        if circulo is None or self.escala_equipo_km is None:
            return None

        escala_limbo = 1_391_400 / (circulo.radio * 2)
        diferencia = (
            (self.escala_equipo_km - escala_limbo)
            / escala_limbo
            * 100
        )
        return escala_limbo, diferencia

    def actualizar_advertencia_calibracion(self):
        datos = self.obtener_diferencia_calibracion()
        etiqueta = self.etiqueta_advertencia_calibracion

        if datos is None:
            etiqueta.clear()
            etiqueta.setVisible(False)
            return

        escala_limbo, diferencia = datos
        if abs(diferencia) <= 5.0:
            etiqueta.clear()
            etiqueta.setVisible(False)
            return

        valores = {
            "difference": f"{diferencia:+.1f}%",
            "limb": f"{escala_limbo:,.1f}",
            "equipment": f"{self.escala_equipo_km:,.1f}",
        }
        critica = abs(diferencia) > 15.0
        etiqueta.setText(
            tr(
                "calibration_panel_critical"
                if critica
                else "calibration_panel_warning",
                **valores,
            )
        )
        if critica:
            color = "#B42318"
            fondo = "#FDECEC"
        else:
            color = "#A15C00"
            fondo = "#FFF4CF"
        etiqueta.setStyleSheet(
            "padding: 8px; border: 1px solid "
            f"{color}; border-left: 4px solid {color}; "
            f"border-radius: 6px; background-color: {fondo};"
        )
        etiqueta.setVisible(True)

    def _escala_activa(self):
        circulo = self.visor.circulo_limbo

        if (
            self.escala_equipo_km is not None
            and self.usar_escala_equipo
        ):
            return self.escala_equipo_km

        if circulo is not None:
            return 1_391_400 / (circulo.radio * 2)

        return None

    def agregar_punto_filamento(self, x, y):
        escala = self._escala_activa()

        if escala is None:
            QMessageBox.information(
                self,
                tr("first_calibrate"),
                tr("filament_needs_scale"),
            )
            self.cancelar_medicion_filamento()
            return

        punto = QPointF(x, y)

        if self.filamento_en_curso is None:
            self.registrar_estado()
            self.filamento_en_curso = MedicionFilamento(
                self.visor.escena,
                [punto],
                escala,
                self.visor.elemento_imagen.boundingRect(),
                al_eliminar=self.eliminar_filamento_individual,
                color=self.color_filamento,
                tamano_texto=self.tamano_filamento,
                familia_fuente=self.fuente_filamento,
                antes_cambiar=self.registrar_estado,
                finalizada=False,
            )
        else:
            self.filamento_en_curso.agregar_punto(punto)

        self.statusBar().showMessage(
            tr(
                "filament_progress",
                count=len(self.filamento_en_curso.puntos),
            )
        )

    def quitar_ultimo_punto_filamento(self, x, y):
        if self.filamento_en_curso is None:
            return

        puntos = self.filamento_en_curso.puntos

        if not puntos:
            return

        escala = max(abs(self.visor.transform().m11()), 0.001)
        tolerancia = 18 / escala
        posicion = QPointF(x, y)
        distancias = [
            (
                (punto.x() - posicion.x()) ** 2
                + (punto.y() - posicion.y()) ** 2
            ) ** 0.5
            for punto in puntos
        ]
        indice = min(
            range(len(distancias)),
            key=distancias.__getitem__,
        )

        if distancias[indice] > tolerancia:
            self.statusBar().showMessage(
                tr("right_click_point")
            )
            return

        quedan_puntos = self.filamento_en_curso.quitar_punto(
            indice
        )

        if not quedan_puntos:
            self.filamento_en_curso.eliminar()
            self.filamento_en_curso = None

        cantidad = (
            len(self.filamento_en_curso.puntos)
            if self.filamento_en_curso is not None
            else 0
        )
        self.statusBar().showMessage(
            tr("filament_points", count=cantidad)
        )

    def finalizar_medicion_filamento(self):
        if (
            self.filamento_en_curso is None
            or len(self.filamento_en_curso.puntos) < 2
        ):
            QMessageBox.information(
                self,
                tr("missing_points"),
                tr("filament_two_points"),
            )
            return

        medicion = self.filamento_en_curso
        medicion.finalizar()
        self.mediciones_filamentos.append(medicion)
        self.filamento_en_curso = None
        self._terminar_modo_filamento()
        self.statusBar().showMessage(
            tr("filament_measured")
        )

    def cancelar_medicion_filamento(self):
        if self.filamento_en_curso is not None:
            medicion = self.filamento_en_curso
            self.filamento_en_curso = None
            medicion.antes_cambiar = None
            medicion.eliminar()

        self._terminar_modo_filamento()
        self.statusBar().showMessage(
            tr("filament_cancelled")
        )

    def _terminar_modo_filamento(self):
        self.visor.modo_medicion_filamento = False
        self.visor.setDragMode(QGraphicsView.ScrollHandDrag)
        self.visor.unsetCursor()
        self.boton_aceptar_filamento.setVisible(False)

    def eliminar_filamento_individual(self, medicion):
        if medicion is self.filamento_en_curso:
            self.filamento_en_curso = None
            self._terminar_modo_filamento()

        if medicion in self.mediciones_filamentos:
            self.mediciones_filamentos.remove(medicion)

        self.statusBar().showMessage(
            tr("filament_deleted")
        )

    def eliminar_medicion_individual(self, medicion):
        if medicion in self.mediciones_protuberancias:
            self.mediciones_protuberancias.remove(medicion)

        self.statusBar().showMessage(
            tr("measurement_deleted")
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
            medicion.estado()
            for medicion in self.mediciones_protuberancias
            if not medicion.eliminada
        ]

        filamentos = [
            medicion.estado_completo()
            for medicion in self.mediciones_filamentos
            if not medicion.eliminada
        ]

        manchas = [
            etiqueta.estado()
            for etiqueta in self.etiquetas_manchas
            if not etiqueta.eliminada
        ]

        return {
            "circulo": estado_circulo,
            "mediciones": mediciones,
            "filamentos": filamentos,
            "manchas": manchas,
            "comparacion_tierra_luna": (
                self.comparacion_tierra_luna.estado()
                if self.comparacion_tierra_luna is not None
                else None
            ),
            "comparaciones_planetas": [
                comparacion.estado()
                for comparacion in (
                    self.comparaciones_planetas.values()
                )
                if not comparacion.eliminada
            ],
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
                tr("nothing_to_undo")
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

            for medicion in self.mediciones_filamentos[:]:
                medicion.antes_cambiar = None
                medicion.eliminar()

            self.mediciones_filamentos.clear()

            for etiqueta in self.etiquetas_manchas[:]:
                etiqueta.antes_cambiar = None
                etiqueta.eliminar()

            self.etiquetas_manchas.clear()

            if self.comparacion_tierra_luna is not None:
                comparacion = self.comparacion_tierra_luna
                self.comparacion_tierra_luna = None
                comparacion.antes_cambiar = None
                comparacion.eliminar()

            self.accion_quitar_tierra_luna.setEnabled(False)

            for comparacion in list(
                self.comparaciones_planetas.values()
            ):
                comparacion.antes_cambiar = None
                comparacion.eliminar()

            self.comparaciones_planetas.clear()
            self.accion_quitar_planetas.setEnabled(False)

            for datos in estado["mediciones"]:
                medicion = self.crear_medicion_protuberancia(
                    datos["x"],
                    datos["y"],
                )
                if (
                    medicion is not None
                    and "texto_x" in datos
                    and "texto_y" in datos
                ):
                    medicion.establecer_desplazamiento_etiqueta(
                        datos["texto_x"],
                        datos["texto_y"],
                    )

            escala = self._escala_activa()

            if escala is not None:
                for datos_filamento in estado.get(
                    "filamentos",
                    [],
                ):
                    if isinstance(datos_filamento, dict):
                        puntos = datos_filamento.get(
                            "puntos",
                            [],
                        )
                    else:
                        puntos = datos_filamento
                    medicion = MedicionFilamento(
                        self.visor.escena,
                        [
                            QPointF(p["x"], p["y"])
                            for p in puntos
                        ],
                        escala,
                        self.visor.elemento_imagen.boundingRect(),
                        al_eliminar=(
                            self.eliminar_filamento_individual
                        ),
                        color=self.color_filamento,
                        tamano_texto=self.tamano_filamento,
                        familia_fuente=self.fuente_filamento,
                        antes_cambiar=self.registrar_estado,
                    )
                    if (
                        isinstance(datos_filamento, dict)
                        and "texto_x" in datos_filamento
                        and "texto_y" in datos_filamento
                    ):
                        medicion.establecer_desplazamiento_etiqueta(
                            datos_filamento["texto_x"],
                            datos_filamento["texto_y"],
                        )
                    self.mediciones_filamentos.append(
                        medicion
                    )

            for datos_mancha in estado.get("manchas", []):
                self.crear_etiqueta_mancha(
                    datos_mancha["x"],
                    datos_mancha["y"],
                    nombre=datos_mancha.get(
                        "nombre",
                        tr(
                            "sunspot_default",
                            number=(
                                len(self.etiquetas_manchas) + 1
                            ),
                        ),
                    ),
                    preguntar=False,
                    registrar=False,
                    radio=datos_mancha.get("radio", 18),
                    ancho=datos_mancha.get("ancho"),
                    alto=datos_mancha.get("alto"),
                    datos_catalogo=datos_mancha.get(
                        "catalogo"
                    ),
                )

            datos_comparacion = estado.get(
                "comparacion_tierra_luna"
            )

            if escala is not None and datos_comparacion:
                separacion_real = bool(
                    datos_comparacion.get(
                        "separacion_real",
                        False,
                    )
                )
                color_distancia = datos_comparacion.get(
                    "color_distancia",
                    self.color_distancia_tierra_luna,
                )
                mostrar_linea_distancia = bool(
                    datos_comparacion.get(
                        "mostrar_linea_distancia",
                        self.mostrar_linea_distancia,
                    )
                )
                color_informacion = datos_comparacion.get(
                    "color_informacion",
                    self.color_informacion_planetas,
                )
                self.color_distancia_tierra_luna = (
                    color_distancia
                )
                self.mostrar_linea_distancia = (
                    mostrar_linea_distancia
                )
                self.color_informacion_planetas = (
                    color_informacion
                )
                self.opcion_distancia_tierra_luna.blockSignals(
                    True
                )
                self.opcion_distancia_tierra_luna.setChecked(
                    separacion_real
                )
                self.opcion_distancia_tierra_luna.blockSignals(
                    False
                )
                self.opcion_linea_distancia.blockSignals(True)
                self.opcion_linea_distancia.setChecked(
                    mostrar_linea_distancia
                )
                self.opcion_linea_distancia.blockSignals(False)
                self.comparacion_tierra_luna = (
                    ComparacionTierraLuna(
                        self.visor.escena,
                        escala,
                        QPointF(
                            datos_comparacion["x"],
                            datos_comparacion["y"],
                        ),
                        separacion_real,
                        self.tamano_informacion_planetas,
                        familia_fuente=self.fuente_informacion_planetas,
                        imagen_tierra=(
                            datos_comparacion.get(
                                "imagen_tierra",
                                self.ruta_imagen_tierra,
                            )
                        ),
                        imagen_luna=(
                            datos_comparacion.get(
                                "imagen_luna",
                                self.ruta_imagen_luna,
                            )
                        ),
                        color_distancia=color_distancia,
                        mostrar_linea_distancia=(
                            mostrar_linea_distancia
                        ),
                        color_informacion=color_informacion,
                        tamano_distancia=(
                            datos_comparacion.get(
                                "tamano_distancia",
                                self.tamano_distancia_tierra_luna,
                            )
                        ),
                        familia_fuente_distancia=(
                            datos_comparacion.get(
                                "familia_fuente_distancia",
                                self.fuente_distancia_tierra_luna,
                            )
                        ),
                        tamano_informacion=(
                            datos_comparacion.get(
                                "tamano_informacion",
                                self.tamano_informacion_planetas,
                            )
                        ),
                        familia_fuente_informacion=(
                            datos_comparacion.get(
                                "familia_fuente_informacion",
                                self.fuente_informacion_planetas,
                            )
                        ),
                        al_eliminar=(
                            self.eliminar_comparacion_tierra_luna
                        ),
                        antes_cambiar=self.registrar_estado,
                    )
                )
                self.accion_quitar_tierra_luna.setEnabled(True)

            if escala is not None:
                for datos_planeta in estado.get(
                    "comparaciones_planetas",
                    [],
                ):
                    self._crear_planeta_desde_estado(
                        datos_planeta,
                        escala,
                    )

            self.accion_quitar_planetas.setEnabled(
                bool(self.comparaciones_planetas)
            )

            self.statusBar().showMessage(
                tr("change_undone")
            )
        finally:
            self.suspendiendo_historial = False
            self.restaurando_historial = False

    def borrar_mediciones(self):
        if (
            not self.mediciones_protuberancias
            and not self.mediciones_filamentos
            and not self.etiquetas_manchas
            and self.filamento_en_curso is None
        ):
            return

        self.registrar_estado()
        self.suspendiendo_historial = True

        try:
            for medicion in self.mediciones_protuberancias[:]:
                medicion.eliminar()

            for medicion in self.mediciones_filamentos[:]:
                medicion.eliminar()

            for etiqueta in self.etiquetas_manchas[:]:
                etiqueta.eliminar()

            if self.filamento_en_curso is not None:
                medicion = self.filamento_en_curso
                self.filamento_en_curso = None
                medicion.antes_cambiar = None
                medicion.eliminar()
        finally:
            self.suspendiendo_historial = False

        self.mediciones_protuberancias.clear()
        self.mediciones_filamentos.clear()
        self.etiquetas_manchas.clear()
        self._terminar_modo_filamento()
        self._terminar_modo_mancha()
        self.statusBar().showMessage(tr("measurements_deleted"))

    def abrir_calibracion_equipo(self):
        if self.visor.ruta_imagen is None:
            QMessageBox.information(
                self,
                tr("first_open_image"),
                tr("need_image_calibration"),
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
        self.usar_escala_equipo = resultado.usar_escala_equipo
        self.descripcion_calibracion = resultado.descripcion

        self.etiqueta_medicion.setText(
            f"{tr('equipment_dialog')}\n"
            f"{resultado.descripcion}\n"
            f"{tr('angular_scale')}: "
            f"{resultado.arcsec_por_pixel:.5f} ″/px\n"
            f"{tr('active_physical_scale')}: "
            f"{self._escala_activa() or resultado.km_por_pixel:,.2f} km/px\n"
            f"{tr('calibration_source')}: "
            f"{tr('active_scale_equipment' if self.usar_escala_equipo else 'active_scale_limb')}"
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

        if circulo is None:
            escala_activa = self._escala_activa()
            if escala_activa is not None:
                for medicion in self.mediciones_filamentos:
                    medicion.km_por_pixel = escala_activa
                    medicion.recalcular()

                if self.filamento_en_curso is not None:
                    self.filamento_en_curso.km_por_pixel = (
                        escala_activa
                    )
                    self.filamento_en_curso.recalcular()

        self.actualizar_comparacion_tierra_luna()

        self.statusBar().showMessage(
            tr("calibration_updated")
        )
        self.actualizar_advertencia_calibracion()

    def iniciar_ajuste_parcial(self):
        if self.visor.modo_medicion_filamento:
            self.cancelar_medicion_filamento()

        if not self.visor.iniciar_limbo_parcial(
            self.actualizar_info_parcial
        ):
            return

        self.boton_finalizar_parcial.setVisible(True)
        self.boton_cancelar_parcial.setVisible(True)
        self.etiqueta_medicion.setText(
            tr("partial_instructions")
        )
        self.statusBar().showMessage(
            tr("partial_status")
        )

    def actualizar_info_parcial(self, resultado):
        if resultado is None:
            cantidad = len(
                self.visor.puntos_limbo_parcial
            )
            self.etiqueta_medicion.setText(
                tr("partial_need_points", count=cantidad)
            )
            return

        cobertura = resultado.cobertura_grados
        incertidumbre = resultado.incertidumbre_radio_px

        if cobertura < 45:
            calidad = tr("quality_very_low")
        elif cobertura < 90:
            calidad = tr("quality_limited")
        elif cobertura < 180:
            calidad = tr("quality_good")
        else:
            calidad = tr("quality_excellent")

        self.etiqueta_medicion.setText(
            tr(
                "partial_preview",
                points=resultado.puntos_usados,
                coverage=cobertura,
                radius=resultado.radio,
                residual=resultado.residuo_px,
                uncertainty=incertidumbre,
                quality=calidad,
            )
        )

    def finalizar_ajuste_parcial(self):
        resultado = self.visor.finalizar_limbo_parcial(
            self.actualizar_medicion_limbo
        )

        if resultado is None:
            return

        self.modo_ajuste = tr("partial_limb_mode")
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
        self.etiqueta_medicion.setText(
            tr("pending_calibration")
        )
        self.statusBar().showMessage(tr("partial_cancelled"))

    def iniciar_ajuste_limbo(self):
        if self.visor.modo_medicion_filamento:
            self.cancelar_medicion_filamento()

        self.modo_ajuste = tr("manual_limb")
        self.error_limbo_px = None
        self.incertidumbre_radio_px = None
        self.muestras_circulos = []
        self.puntos_limbo = None
        self.visor.crear_ajuste_limbo(self.actualizar_medicion_limbo)
        self.aplicar_estilo_limbo()

    def iniciar_autodeteccion_limbo(self):
        if self.visor.modo_medicion_filamento:
            self.cancelar_medicion_filamento()

        if self.visor.ruta_imagen is None:
            QMessageBox.information(
                self,
                tr("first_open_image"),
                tr("need_solar_image"),
            )
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage(tr("analyzing_limb"))

        try:
            resultado = detectar_limbo(self.visor.ruta_imagen)
        except ErrorDeteccionLimbo as error:
            QMessageBox.warning(
                self,
                tr("limb_detection_failed"),
                str(error),
            )
            self.statusBar().showMessage(
                tr("limb_not_conclusive")
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

        if self.visor.circulo_limbo is not None:
            self.visor.escena.removeItem(
                self.visor.circulo_limbo
            )

        self.modo_ajuste = tr("automatic_limb")
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
            tr("select_outline_color"),
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
            if (
                self.escala_equipo_km is not None
                and self.usar_escala_equipo
            )
            else escala_limbo
        )

        for medicion in self.mediciones_protuberancias:
            medicion.km_por_pixel = km_por_pixel
            medicion.recalcular_desde_limbo()

        for medicion in self.mediciones_filamentos:
            medicion.km_por_pixel = km_por_pixel
            medicion.recalcular()

        if self.filamento_en_curso is not None:
            self.filamento_en_curso.km_por_pixel = km_por_pixel
            self.filamento_en_curso.recalcular()

        self.actualizar_regla_solar()
        self.actualizar_comparacion_tierra_luna()

        detalle_error = ""

        if self.error_limbo_px is not None:
            error_km = self.error_limbo_px * km_por_pixel
            detalle_error = (
                f"\n{tr('residual')}: "
                f"±{self.error_limbo_px:.2f} px"
                f" (±{error_km:,.0f} km)"
            )

            if self.incertidumbre_radio_px is not None:
                incertidumbre_km = (
                    self.incertidumbre_radio_px
                    * km_por_pixel
                )
                detalle_error += (
                    f"\n{tr('radius_uncertainty')}: "
                    f"±{self.incertidumbre_radio_px:.2f} px"
                    f" (±{incertidumbre_km:,.0f} km)"
                )

            detalle_error += (
                f"\n{tr('points_used')}: {self.puntos_limbo}"
            )

        self.etiqueta_medicion.setText(
            f"{self.modo_ajuste}\n"
            f"{tr('center')}: "
            f"{centro_x:.1f}, {centro_y:.1f} px\n"
            f"{tr('radius')}: {radio:.1f} px\n"
            f"{tr('diameter')}: {diametro:.1f} px\n"
            f"{tr('limb_scale')}: "
            f"{escala_limbo:,.1f} km/px\n"
            f"{tr('active_scale')}: "
            f"{km_por_pixel:,.1f} km/px\n"
            f"{tr('calibration_source')}: "
            f"{tr('active_scale_equipment' if self.usar_escala_equipo and self.escala_equipo_km is not None else 'active_scale_limb')}"
            f"{detalle_error}"
        )
        self.statusBar().showMessage(
            f"{tr('solar_diameter')}: {diametro:.1f} px · "
            f"{tr('provisional_scale')}: "
            f"{km_por_pixel:,.1f} km/px"
        )
        self.actualizar_advertencia_calibracion()

    def actualizar_informacion(self, ruta):
        archivo = Path(ruta)
        self.mediciones_protuberancias.clear()
        self.mediciones_filamentos.clear()
        self.etiquetas_manchas.clear()
        self.ultimas_regiones_catalogo.clear()
        self.instante_catalogo = None
        self.ajuste_catalogo_x = 0.0
        self.ajuste_catalogo_y = 0.0
        self.escala_mapa_catalogo = 1.0
        self.ruta_referencia_catalogo = None
        self.nombre_fuente_referencia_catalogo = ""
        self.detalle_alineacion_catalogo = ""
        self.boton_referencia_solar.setVisible(False)
        self.filamento_en_curso = None
        self.ruta_proyecto_actual = None
        self.comparacion_tierra_luna = None
        self.comparaciones_planetas.clear()
        self.accion_quitar_tierra_luna.setEnabled(False)
        self.accion_quitar_planetas.setEnabled(False)
        self.opcion_distancia_tierra_luna.blockSignals(True)
        self.opcion_distancia_tierra_luna.setChecked(False)
        self.opcion_distancia_tierra_luna.blockSignals(False)
        self._terminar_modo_filamento()
        self._terminar_modo_mancha()
        self.historial_estados.clear()
        self.regla_solar = None
        self.boton_regla.setText(tr("show_ruler"))
        self.escala_equipo_km = None
        self.usar_escala_equipo = True
        self.descripcion_calibracion = None
        self.etiqueta_medicion.setText(
            tr("pending_calibration")
        )
        self.actualizar_advertencia_calibracion()
        self.ajustes.setValue(
            "archivos/ultima_carpeta",
            str(archivo.parent),
        )
        pixmap = self.visor.elemento_imagen.pixmap()

        self.etiqueta_archivo.setText(
            f"{archivo.name}\n"
            f"{pixmap.width()} × {pixmap.height()} "
            f"{tr('pixels')}"
        )
        self.statusBar().showMessage(
            tr("image_loaded", name=archivo.name)
        )

    def closeEvent(self, event):
        if (
            not self.mediciones_protuberancias
            and not self.mediciones_filamentos
            and not self.etiquetas_manchas
            and self.filamento_en_curso is None
            and self.comparacion_tierra_luna is None
        ):
            event.accept()
            return

        respuesta = QMessageBox.question(
            self,
            tr("close_title"),
            tr("close_question"),
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
                padding: 7px;
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

            QMenuBar {
                background-color: #FFFFFF;
                color: #004976;
                border-bottom: 1px solid #D6E0E5;
                padding: 3px;
            }

            QMenuBar::item {
                background-color: transparent;
                padding: 7px 11px;
                border-radius: 5px;
                font-weight: 600;
            }

            QMenuBar::item:selected {
                background-color: #E4F0F6;
            }

            QMenu {
                background-color: #FFFFFF;
                color: #183241;
                border: 1px solid #9CB7C5;
                padding: 5px;
            }

            QMenu::item {
                padding: 8px 28px 8px 10px;
                border-radius: 4px;
            }

            QMenu::item:selected {
                background-color: #E4F0F6;
                color: #004976;
            }

            QMenu::indicator:checked {
                background-color: #FFB81C;
                border: 1px solid #004976;
                width: 12px;
                height: 12px;
            }

            #botonPrincipal {
                background-color: #FFB81C;
                color: #173543;
                border: 1px solid #D89500;
                padding: 9px;
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

            #botonHerramienta {
                background-color: #E7F2F7;
                color: #004976;
                border: 1px solid #6E9DB5;
                border-left: 5px solid #004976;
                padding: 8px;
                border-radius: 6px;
                font-weight: 700;
            }

            #botonHerramienta:hover {
                background-color: #D2E8F1;
                border-color: #004976;
            }

            #botonContextual {
                background-color: #FFF4CF;
                color: #745000;
                border: 2px solid #FFB81C;
                padding: 5px 12px;
                border-radius: 5px;
                min-width: 250px;
                max-width: 285px;
                font-weight: 700;
            }

            #botonContextual:hover {
                background-color: #FFE49A;
                border-color: #D28B00;
            }

            #seccionPanel {
                background-color: transparent;
                color: #6A8390;
                border-bottom: 1px solid #C9D9E1;
                padding: 8px 2px 3px 2px;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 1px;
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

            #calibracionAdvertencia {
                color: #7A4300;
                font-weight: 600;
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

            #visorSolar QScrollBar:vertical {
                width: 15px;
            }

            #visorSolar QScrollBar::handle:vertical {
                min-height: 37px;
            }

            #visorSolar QScrollBar:horizontal {
                height: 15px;
            }

            #visorSolar QScrollBar::handle:horizontal {
                min-width: 37px;
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

