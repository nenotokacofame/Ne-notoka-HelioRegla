import math

from PySide6.QtCore import QLineF, QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsSimpleTextItem,
)


class GrupoMancha(QGraphicsItemGroup):
    def __init__(self, etiqueta):
        super().__init__()
        self.etiqueta = etiqueta
        self.cambio_registrado = False
        self.redimensionando = False
        self.setCursor(Qt.SizeAllCursor)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(
            QGraphicsItem.ItemSendsGeometryChanges,
            True,
        )
        self.setAcceptedMouseButtons(
            Qt.LeftButton | Qt.RightButton
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(58)

    def _sobre_control_tamano(self, posicion):
        radio_x = self.etiqueta.ancho / 2
        radio_y = self.etiqueta.alto / 2
        return (
            abs(posicion.x() - radio_x) <= 10
            and abs(posicion.y() - radio_y) <= 10
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.etiqueta.notificar_inicio_cambio()
            self.etiqueta.eliminar()
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            if self._sobre_control_tamano(event.pos()):
                self.redimensionando = True
                self.etiqueta.notificar_inicio_cambio()
                event.accept()
                return
            self.cambio_registrado = False
            self.etiqueta.notificar_inicio_cambio()
            self.cambio_registrado = True

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.redimensionando and event.buttons() & Qt.LeftButton:
            centro = self.etiqueta.grupo.pos()
            posicion = event.scenePos()
            self.etiqueta.establecer_tamano(
                abs(posicion.x() - centro.x()) * 2,
                abs(posicion.y() - centro.y()) * 2,
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.redimensionando and event.button() == Qt.LeftButton:
            self.redimensionando = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def hoverMoveEvent(self, event):
        if self._sobre_control_tamano(event.pos()):
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.etiqueta.solicitar_edicion()
            event.accept()
            return

        super().mouseDoubleClickEvent(event)

    def itemChange(self, cambio, valor):
        if (
            cambio == QGraphicsItem.ItemPositionChange
            and self.scene() is not None
            and not self.etiqueta.eliminada
        ):
            rectangulo = self.etiqueta.imagen_rect
            mitad_ancho = self.etiqueta.ancho / 2
            mitad_alto = self.etiqueta.alto / 2
            valor = QPointF(
                min(
                    max(
                        valor.x(),
                        rectangulo.left() + mitad_ancho,
                    ),
                    rectangulo.right() - mitad_ancho,
                ),
                min(
                    max(
                        valor.y(),
                        rectangulo.top() + mitad_alto,
                    ),
                    rectangulo.bottom() - mitad_alto,
                ),
            )
            return valor

        if (
            cambio == QGraphicsItem.ItemPositionHasChanged
            and self.scene() is not None
            and not self.etiqueta.eliminada
        ):
            self.etiqueta.punto = QPointF(valor)
            self.etiqueta.actualizar()

        return super().itemChange(cambio, valor)


class ControlTamanoMancha(QGraphicsEllipseItem):
    """Control pequeño para redimensionar el óvalo de una región activa."""

    def __init__(self, etiqueta):
        super().__init__(-6, -6, 12, 12)
        self.etiqueta = etiqueta
        # El grupo padre procesa el arrastre para evitar que el marcador se
        # mueva como una anotación completa. Este elemento solo es visual.
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setAcceptHoverEvents(False)
        self.setZValue(2)


class EtiquetaMancha:
    def __init__(
        self,
        escena,
        punto,
        nombre,
        imagen_rect,
        color="#ff3dbb",
        tamano_texto=28,
        radio=18,
        ancho=None,
        alto=None,
        datos_catalogo=None,
        al_eliminar=None,
        al_editar=None,
        antes_cambiar=None,
    ):
        self.escena = escena
        self.punto = QPointF(punto)
        self.nombre = str(nombre)
        self.imagen_rect = imagen_rect
        self.color = color
        self.tamano_texto = int(tamano_texto)
        diametro = max(12.0, float(radio) * 2)
        self.ancho = max(
            12.0,
            float(ancho if ancho is not None else diametro),
        )
        self.alto = max(
            12.0,
            float(alto if alto is not None else diametro),
        )
        self.radio = max(self.ancho, self.alto) / 2
        self.datos_catalogo = dict(datos_catalogo or {})
        self.al_eliminar = al_eliminar
        self.al_editar = al_editar
        self.antes_cambiar = antes_cambiar
        self.eliminada = False
        self.desplazamiento_texto = None

        self.grupo = GrupoMancha(self)
        self.marca = QGraphicsEllipseItem()
        self.control_tamano = ControlTamanoMancha(self)
        self.linea = QGraphicsLineItem()
        self.texto = QGraphicsSimpleTextItem()

        self.grupo.addToGroup(self.marca)
        self.grupo.addToGroup(self.control_tamano)
        self.grupo.addToGroup(self.linea)
        self.grupo.addToGroup(self.texto)
        self.escena.addItem(self.grupo)
        self.grupo.setPos(self.punto)
        self.establecer_estilo(color, tamano_texto)

    def notificar_inicio_cambio(self):
        if self.antes_cambiar is not None:
            self.antes_cambiar()

    def solicitar_edicion(self):
        if self.al_editar is not None:
            self.al_editar(self)

    def establecer_nombre(self, nombre):
        self.nombre = str(nombre)
        self.actualizar()

    def establecer_estilo(self, color, tamano_texto):
        self.color = str(color)
        self.tamano_texto = int(tamano_texto)

        lapiz = QPen(QColor(self.color), 2)
        lapiz.setCapStyle(Qt.RoundCap)
        self.marca.setPen(lapiz)
        self.marca.setBrush(QBrush(Qt.NoBrush))
        self.control_tamano.setPen(QPen(QColor("#ffffff"), 1))
        self.control_tamano.setBrush(QBrush(QColor(self.color)))
        self.linea.setPen(lapiz)

        fuente = QFont("Century Gothic")
        fuente.setPixelSize(self.tamano_texto)
        fuente.setBold(True)
        self.texto.setFont(fuente)
        self.texto.setBrush(QBrush(QColor(self.color)))
        self.actualizar()

    def actualizar(self):
        if self.eliminada:
            return

        radio_x = self.ancho / 2
        radio_y = self.alto / 2
        self.radio = max(radio_x, radio_y)
        self.marca.setRect(
            -radio_x,
            -radio_y,
            self.ancho,
            self.alto,
        )
        self.control_tamano.setPos(radio_x, radio_y)
        self.texto.setText(self.nombre)

        caja = self.texto.boundingRect()
        margen = 10.0
        separacion = 12.0
        punto = self.grupo.pos()

        x_texto = radio_x + separacion
        y_texto = -radio_y - caja.height() - separacion

        if self.desplazamiento_texto is not None:
            x_texto, y_texto = self.desplazamiento_texto

        if self.desplazamiento_texto is None and (
            punto.x() + x_texto + caja.width()
            > self.imagen_rect.right() - margen
        ):
            x_texto = -radio_x - separacion - caja.width()

        if self.desplazamiento_texto is None and (
            punto.y() + y_texto
            < self.imagen_rect.top() + margen
        ):
            y_texto = radio_y + separacion

        if self.desplazamiento_texto is None and (
            punto.y() + y_texto + caja.height()
            > self.imagen_rect.bottom() - margen
        ):
            y_texto = (
                -caja.height() - radio_y - separacion
            )

        self.texto.setPos(x_texto, y_texto)

        destino_x = (
            x_texto
            if x_texto >= 0
            else x_texto + caja.width()
        )
        destino_y = y_texto + caja.height() / 2
        denominador = math.sqrt(
            (destino_x / max(radio_x, 0.001)) ** 2
            + (destino_y / max(radio_y, 0.001)) ** 2
        )
        factor = 1 / max(denominador, 0.001)
        inicio = QPointF(
            destino_x * factor,
            destino_y * factor,
        )
        self.linea.setLine(
            QLineF(
                inicio,
                QPointF(destino_x, destino_y),
            )
        )

    def establecer_tamano(self, ancho, alto):
        """Actualiza el ancho y alto del óvalo sin sacar la región de la foto."""
        rectangulo = self.imagen_rect
        centro = self.grupo.pos()
        max_ancho = 2 * min(
            centro.x() - rectangulo.left(),
            rectangulo.right() - centro.x(),
        )
        max_alto = 2 * min(
            centro.y() - rectangulo.top(),
            rectangulo.bottom() - centro.y(),
        )
        max_ancho = max(12.0, max_ancho)
        max_alto = max(12.0, max_alto)
        self.ancho = min(max(12.0, float(ancho)), max_ancho)
        self.alto = min(max(12.0, float(alto)), max_alto)
        self.actualizar()

    def establecer_desplazamiento_texto(self, x, y):
        self.desplazamiento_texto = (float(x), float(y))
        self.actualizar()

    def liberar_desplazamiento_texto(self):
        self.desplazamiento_texto = None
        self.actualizar()

    def eliminar(self):
        if self.eliminada:
            return

        self.eliminada = True

        if self.grupo.scene() is not None:
            self.escena.removeItem(self.grupo)

        if self.al_eliminar is not None:
            self.al_eliminar(self)

    def estado(self):
        return {
            "x": self.grupo.pos().x(),
            "y": self.grupo.pos().y(),
            "nombre": self.nombre,
            "radio": self.radio,
            "ancho": self.ancho,
            "alto": self.alto,
            "catalogo": dict(self.datos_catalogo),
        }


def acomodar_etiquetas(etiquetas):
    """Distribuye textos de catálogo sin mover sus regiones."""
    validas = [
        etiqueta
        for etiqueta in etiquetas
        if not etiqueta.eliminada
        and etiqueta.datos_catalogo.get("numero")
    ]
    validas.sort(
        key=lambda etiqueta: (
            etiqueta.grupo.pos().y(),
            etiqueta.grupo.pos().x(),
        )
    )
    ocupados = []

    for etiqueta in validas:
        caja = etiqueta.texto.boundingRect()
        radio_x = etiqueta.ancho / 2
        radio_y = etiqueta.alto / 2
        separacion = max(12.0, etiqueta.tamano_texto * 0.45)
        candidatos = (
            (radio_x + separacion, -radio_y - caja.height() - separacion),
            (radio_x + separacion, radio_y + separacion),
            (-radio_x - caja.width() - separacion, -radio_y - caja.height() - separacion),
            (-radio_x - caja.width() - separacion, radio_y + separacion),
            (-caja.width() / 2, -radio_y - caja.height() - separacion * 1.8),
            (-caja.width() / 2, radio_y + separacion * 1.8),
            (radio_x + separacion * 2, -caja.height() / 2),
            (-radio_x - caja.width() - separacion * 2, -caja.height() / 2),
        )
        centro = etiqueta.grupo.pos()
        mejor = None
        margen = 8.0

        for indice, (dx, dy) in enumerate(candidatos):
            izquierda = centro.x() + dx
            arriba = centro.y() + dy
            derecha = izquierda + caja.width()
            abajo = arriba + caja.height()
            rectangulo = (izquierda, arriba, derecha, abajo)

            fuera = (
                max(0.0, etiqueta.imagen_rect.left() + margen - izquierda)
                + max(0.0, etiqueta.imagen_rect.top() + margen - arriba)
                + max(0.0, derecha - etiqueta.imagen_rect.right() + margen)
                + max(0.0, abajo - etiqueta.imagen_rect.bottom() + margen)
            )
            solape = 0.0
            for ocupado in ocupados:
                ancho = max(
                    0.0,
                    min(derecha, ocupado[2])
                    - max(izquierda, ocupado[0]),
                )
                alto = max(
                    0.0,
                    min(abajo, ocupado[3])
                    - max(arriba, ocupado[1]),
                )
                solape += ancho * alto
            puntuacion = fuera * 100_000 + solape + indice
            if mejor is None or puntuacion < mejor[0]:
                mejor = (puntuacion, dx, dy, rectangulo)

        etiqueta.establecer_desplazamiento_texto(
            mejor[1],
            mejor[2],
        )
        ocupados.append(mejor[3])
