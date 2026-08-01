import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsTextItem,
)
from i18n import tr


DIAMETRO_TIERRA_KM = 12_742
DIAMETRO_LUNA_KM = 3_475
ERROR_MARCADO_PX = 1.5


class TrazoFilamento(QGraphicsPathItem):
    def __init__(self, medicion):
        super().__init__()
        self.medicion = medicion
        self.setZValue(45)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            if self.medicion.finalizada:
                self.medicion.eliminar()
            else:
                self.medicion.quitar_punto(self.indice)
            event.accept()
            return
        super().mousePressEvent(event)


class EtiquetaFilamento(QGraphicsTextItem):
    def __init__(self, medicion):
        super().__init__()
        self.medicion = medicion
        self.setZValue(47)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.medicion.eliminar()
            event.accept()
            return
        super().mousePressEvent(event)


class PuntoFilamento(QGraphicsEllipseItem):
    def __init__(self, medicion, indice, posicion):
        super().__init__(-6, -6, 12, 12)
        self.medicion = medicion
        self.indice = indice
        self.cambio_registrado = False
        self.setPos(posicion)
        self.setZValue(48)
        self.setBrush(QColor(medicion.color))

        lapiz = QPen(QColor("#ffffff"), 1)
        lapiz.setCosmetic(True)
        self.setPen(lapiz)
        self.setCursor(Qt.SizeAllCursor)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(
            QGraphicsItem.ItemIgnoresTransformations,
            True,
        )
        self.setFlag(
            QGraphicsItem.ItemSendsGeometryChanges,
            True,
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.medicion.eliminar()
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            self.cambio_registrado = False

        super().mousePressEvent(event)

    def itemChange(self, cambio, valor):
        if (
            cambio == QGraphicsItem.ItemPositionChange
            and self.scene() is not None
            and not self.medicion.eliminada
        ):
            if not self.cambio_registrado:
                self.medicion.notificar_inicio_cambio()
                self.cambio_registrado = True

            self.medicion.puntos[self.indice] = QPointF(valor)
            self.medicion.actualizar()

        return super().itemChange(cambio, valor)


class MedicionFilamento:
    def __init__(
        self,
        escena,
        puntos,
        km_por_pixel,
        imagen_rect,
        al_eliminar=None,
        color="#ff3dbb",
        tamano_texto=28,
        antes_cambiar=None,
        finalizada=True,
    ):
        self.escena = escena
        self.puntos = [QPointF(p) for p in puntos]
        self.km_por_pixel = float(km_por_pixel)
        self.imagen_rect = imagen_rect
        self.al_eliminar = al_eliminar
        self.color = color
        self.tamano_texto = int(tamano_texto)
        self.antes_cambiar = antes_cambiar
        self.finalizada = finalizada
        self.eliminada = False

        self.trazo = TrazoFilamento(self)
        self.etiqueta = EtiquetaFilamento(self)
        self.manejadores = []
        self.escena.addItem(self.trazo)
        self.escena.addItem(self.etiqueta)
        self._recrear_manejadores()
        self.establecer_estilo(color, tamano_texto)
        self.actualizar()

    def _recrear_manejadores(self):
        for manejador in self.manejadores:
            if manejador.scene() is not None:
                self.escena.removeItem(manejador)

        self.manejadores = []

        for indice, punto in enumerate(self.puntos):
            manejador = PuntoFilamento(
                self,
                indice,
                punto,
            )
            manejador.setVisible(not self.finalizada)
            self.escena.addItem(manejador)
            self.manejadores.append(manejador)

    def agregar_punto(self, punto):
        self.puntos.append(QPointF(punto))
        self._recrear_manejadores()
        self.actualizar()

    def quitar_ultimo_punto(self):
        if not self.puntos:
            return False

        self.puntos.pop()
        self._recrear_manejadores()
        self.actualizar()
        return bool(self.puntos)

    def quitar_punto(self, indice):
        if not 0 <= indice < len(self.puntos):
            return False

        self.puntos.pop(indice)
        self._recrear_manejadores()
        self.actualizar()
        return bool(self.puntos)

    def finalizar(self):
        self.finalizada = True

        for manejador in self.manejadores:
            manejador.setVisible(False)

        self.actualizar()

    def notificar_inicio_cambio(self):
        if self.antes_cambiar is not None:
            self.antes_cambiar()

    def longitud_pixeles(self):
        camino = self._crear_camino()

        if camino.isEmpty():
            return 0.0

        longitud = 0.0
        anterior = camino.pointAtPercent(0.0)
        muestras = max(40, (len(self.puntos) - 1) * 30)

        for indice in range(1, muestras + 1):
            actual = camino.pointAtPercent(indice / muestras)
            longitud += math.hypot(
                actual.x() - anterior.x(),
                actual.y() - anterior.y(),
            )
            anterior = actual

        return longitud

    def _crear_camino(self):
        camino = QPainterPath()

        if not self.puntos:
            return camino

        camino.moveTo(self.puntos[0])

        if len(self.puntos) == 2:
            camino.lineTo(self.puntos[1])
            return camino

        for indice in range(len(self.puntos) - 1):
            p0 = self.puntos[max(0, indice - 1)]
            p1 = self.puntos[indice]
            p2 = self.puntos[indice + 1]
            p3 = self.puntos[
                min(len(self.puntos) - 1, indice + 2)
            ]

            control_1 = QPointF(
                p1.x() + (p2.x() - p0.x()) / 6,
                p1.y() + (p2.y() - p0.y()) / 6,
            )
            control_2 = QPointF(
                p2.x() - (p3.x() - p1.x()) / 6,
                p2.y() - (p3.y() - p1.y()) / 6,
            )
            camino.cubicTo(control_1, control_2, p2)

        return camino

    def actualizar(self):
        if self.eliminada:
            return

        self.trazo.setPath(self._crear_camino())

        if len(self.puntos) < 2:
            self.etiqueta.setVisible(False)
            return

        longitud_px = self.longitud_pixeles()
        longitud_km = longitud_px * self.km_por_pixel
        segmentos = len(self.puntos) - 1
        incertidumbre_px = (
            ERROR_MARCADO_PX
            * math.sqrt(2 * segmentos)
        )
        incertidumbre_km = (
            incertidumbre_px * self.km_por_pixel
        )

        self.etiqueta.setPlainText(
            f"{tr('projected_length')}: "
            f"{longitud_km:,.0f} "
            f"± {incertidumbre_km:,.0f} km\n"
            f"{longitud_km / DIAMETRO_TIERRA_KM:.2f} "
            f"{tr('earths')} · "
            f"{longitud_km / DIAMETRO_LUNA_KM:.1f} "
            f"{tr('moons')}"
        )
        self.etiqueta.setVisible(True)
        self._colocar_etiqueta()

    def _colocar_etiqueta(self):
        if not self.puntos:
            return

        referencia = self.puntos[len(self.puntos) // 2]
        rectangulo = self.etiqueta.boundingRect()
        margen = 8
        x = referencia.x() + 12
        y = referencia.y() - rectangulo.height() - 12
        x = max(
            self.imagen_rect.left() + margen,
            min(
                x,
                self.imagen_rect.right()
                - rectangulo.width()
                - margen,
            ),
        )
        y = max(
            self.imagen_rect.top() + margen,
            min(
                y,
                self.imagen_rect.bottom()
                - rectangulo.height()
                - margen,
            ),
        )
        self.etiqueta.setPos(x, y)

    def establecer_estilo(self, color, tamano_texto):
        self.color = color
        self.tamano_texto = int(tamano_texto)

        lapiz = QPen(QColor(color), 3)
        lapiz.setCosmetic(True)
        lapiz.setStyle(Qt.CustomDashLine)
        lapiz.setDashPattern([4.0, 3.0])
        lapiz.setCapStyle(Qt.RoundCap)
        lapiz.setJoinStyle(Qt.RoundJoin)
        self.trazo.setPen(lapiz)

        fuente = QFont("Century Gothic")
        fuente.setPixelSize(self.tamano_texto)
        fuente.setBold(True)
        self.etiqueta.setFont(fuente)
        self.etiqueta.setDefaultTextColor(QColor(color))

        for manejador in self.manejadores:
            manejador.setBrush(QColor(color))

        self.actualizar()

    def recalcular(self):
        self.actualizar()

    def eliminar(self):
        if self.eliminada:
            return

        self.notificar_inicio_cambio()
        self.eliminada = True

        for elemento in (
            self.trazo,
            self.etiqueta,
            *self.manejadores,
        ):
            if elemento.scene() is not None:
                self.escena.removeItem(elemento)

        if self.al_eliminar is not None:
            self.al_eliminar(self)

    def estado(self):
        return [
            {"x": punto.x(), "y": punto.y()}
            for punto in self.puntos
        ]
