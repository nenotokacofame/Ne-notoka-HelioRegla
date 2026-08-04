from math import hypot

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem


class ManejadorRadio(QGraphicsEllipseItem):
    def __init__(self, circulo, direccion_x, direccion_y):
        super().__init__(-7, -7, 14, 14, circulo)

        self.circulo = circulo
        self.direccion_x = direccion_x
        self.direccion_y = direccion_y

        self.setBrush(QBrush(QColor("#f5b041")))
        self.setPen(QPen(QColor("#ffffff"), 1))

        if direccion_y == 0:
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.SizeVerCursor)

        self.setFlag(
            QGraphicsItem.ItemIgnoresTransformations,
            True,
        )
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setZValue(2)

    def mousePressEvent(self, event):
        self.circulo.notificar_inicio_cambio()
        event.accept()

    def mouseMoveEvent(self, event):
        punto = self.circulo.mapFromScene(event.scenePos())
        radio = hypot(punto.x(), punto.y())
        self.circulo.establecer_radio(radio)
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()


class CirculoLimbo(QGraphicsEllipseItem):
    def __init__(
        self,
        centro_x,
        centro_y,
        radio,
        al_cambiar=None,
        antes_cambiar=None,
    ):
        super().__init__()

        self.radio = float(radio)
        self.al_cambiar = al_cambiar
        self.antes_cambiar = antes_cambiar

        self.color_linea = "#39ff88"
        self.grosor_linea = 3

        lapiz = QPen(
            QColor(self.color_linea),
            self.grosor_linea,
        )
        lapiz.setCosmetic(True)
        self.setPen(lapiz)
        self.setBrush(QBrush(Qt.NoBrush))

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setFlag(
            QGraphicsItem.ItemSendsGeometryChanges,
            True,
        )
        self.setCursor(Qt.SizeAllCursor)
        self.setZValue(10)

        self.manejadores = [
            ManejadorRadio(self, 1, 0),
            ManejadorRadio(self, -1, 0),
            ManejadorRadio(self, 0, -1),
            ManejadorRadio(self, 0, 1),
        ]

        # Compatibilidad con código anterior.
        self.manejador = self.manejadores[0]

        self.establecer_radio(radio, notificar=False)
        self.setPos(centro_x, centro_y)
        self.notificar_cambio()

    def notificar_inicio_cambio(self):
        if self.antes_cambiar:
            self.antes_cambiar()

    def mousePressEvent(self, event):
        self.setFocus()
        self.notificar_inicio_cambio()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        paso = 1.0

        if event.modifiers() & Qt.ShiftModifier:
            paso = 0.1
        elif event.modifiers() & Qt.ControlModifier:
            paso = 10.0

        desplazamientos = {
            Qt.Key_Left: (-paso, 0),
            Qt.Key_Right: (paso, 0),
            Qt.Key_Up: (0, -paso),
            Qt.Key_Down: (0, paso),
        }

        if event.key() in desplazamientos:
            self.notificar_inicio_cambio()
            dx, dy = desplazamientos[event.key()]
            self.moveBy(dx, dy)
            event.accept()
            return

        super().keyPressEvent(event)

    def establecer_estilo(self, color, grosor):
        self.color_linea = color
        self.grosor_linea = max(0, int(grosor))

        # En Qt un QPen de ancho 0 sigue dibujando una línea cosmética de
        # un píxel. Para que "0 px" signifique realmente ocultar el limbo
        # usamos NoPen y dejamos los manejadores disponibles mientras se
        # está editando el círculo.
        if self.grosor_linea <= 0:
            self.setPen(QPen(Qt.NoPen))
            return

        lapiz = QPen(QColor(color), self.grosor_linea)
        lapiz.setCosmetic(True)
        self.setPen(lapiz)

    def establecer_radio(self, radio, notificar=True):
        radio = max(10.0, float(radio))
        self.prepareGeometryChange()

        self.radio = radio
        self.setRect(
            -radio,
            -radio,
            radio * 2,
            radio * 2,
        )

        posiciones = (
            (radio, 0),
            (-radio, 0),
            (0, -radio),
            (0, radio),
        )

        for manejador, posicion in zip(
            self.manejadores,
            posiciones,
        ):
            manejador.setPos(*posicion)

        if notificar:
            self.notificar_cambio()

    def notificar_cambio(self):
        if self.al_cambiar:
            self.al_cambiar(
                self.pos().x(),
                self.pos().y(),
                self.radio,
            )

    def itemChange(self, cambio, valor):
        resultado = super().itemChange(cambio, valor)

        if cambio == QGraphicsItem.ItemPositionHasChanged:
            self.notificar_cambio()

        return resultado
