from math import hypot

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem


class ManejadorRadio(QGraphicsEllipseItem):
    def __init__(self, circulo):
        super().__init__(-7, -7, 14, 14, circulo)

        self.circulo = circulo
        self.setBrush(QBrush(QColor("#f5b041")))
        self.setPen(QPen(QColor("#ffffff"), 1))
        self.setCursor(Qt.SizeHorCursor)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setZValue(2)

    def mousePressEvent(self, event):
        event.accept()

    def mouseMoveEvent(self, event):
        punto = self.circulo.mapFromScene(event.scenePos())
        radio = hypot(punto.x(), punto.y())
        self.circulo.establecer_radio(radio)
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()


class CirculoLimbo(QGraphicsEllipseItem):
    def __init__(self, centro_x, centro_y, radio, al_cambiar=None):
        super().__init__()

        self.radio = float(radio)
        self.al_cambiar = al_cambiar

        self.color_linea = "#39ff88"
        self.grosor_linea = 3

        lapiz = QPen(QColor(self.color_linea), self.grosor_linea)
        lapiz.setCosmetic(True)
        self.setPen(lapiz)
        self.setBrush(QBrush(Qt.NoBrush))

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.SizeAllCursor)
        self.setZValue(10)

        self.manejador = ManejadorRadio(self)

        self.establecer_radio(radio, notificar=False)
        self.setPos(centro_x, centro_y)
        self.notificar_cambio()

    def establecer_estilo(self, color, grosor):
        self.color_linea = color
        self.grosor_linea = grosor

        lapiz = QPen(QColor(color), grosor)
        lapiz.setCosmetic(True)
        self.setPen(lapiz)

    def establecer_radio(self, radio, notificar=True):
        radio = max(10.0, float(radio))
        self.prepareGeometryChange()

        self.radio = radio
        self.setRect(-radio, -radio, radio * 2, radio * 2)
        self.manejador.setPos(radio, 0)

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
