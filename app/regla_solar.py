from math import cos, pi, sin

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsSimpleTextItem,
)


class ReglaSolar:
    def __init__(
        self,
        escena,
        intervalo_km=25_000,
        maximo_km=200_000,
        color="#00A6C8",
        grosor=1,
        tamano_texto=18,
        familia_fuente="Century Gothic",
    ):
        self.escena = escena
        self.intervalo_km = intervalo_km
        self.maximo_km = maximo_km
        self.color = color
        self.grosor = grosor
        self.tamano_texto = tamano_texto
        self.familia_fuente = str(
            familia_fuente or "Century Gothic"
        )
        self.elementos = []

    def limpiar(self):
        for elemento in self.elementos:
            if elemento.scene() is not None:
                self.escena.removeItem(elemento)

        self.elementos.clear()

    def eliminar(self):
        self.limpiar()

    def establecer_configuracion(
        self,
        intervalo_km,
        maximo_km,
        color,
        grosor,
        tamano_texto,
        familia_fuente="Century Gothic",
    ):
        self.intervalo_km = intervalo_km
        self.maximo_km = maximo_km
        self.color = color
        self.grosor = grosor
        self.tamano_texto = tamano_texto
        self.familia_fuente = str(
            familia_fuente or "Century Gothic"
        )

    def _punto_visible_para_etiqueta(
        self,
        centro_x,
        centro_y,
        radio,
        rectangulo,
    ):
        margen = max(12, self.tamano_texto)
        candidatos = []

        for indice in range(720):
            angulo = 2 * pi * indice / 720
            x = centro_x + radio * cos(angulo)
            y = centro_y + radio * sin(angulo)

            if (
                rectangulo.left() + margen
                <= x
                <= rectangulo.right() - margen
                and rectangulo.top() + margen
                <= y
                <= rectangulo.bottom() - margen
            ):
                # Prefiere la parte superior y después el centro.
                puntuacion = (
                    y
                    + abs(x - rectangulo.center().x()) * 0.08
                )
                candidatos.append((puntuacion, x, y))

        if not candidatos:
            return None

        _, x, y = min(candidatos)
        return x, y

    def actualizar(
        self,
        centro_x,
        centro_y,
        radio_limbo,
        km_por_pixel,
        rectangulo_imagen,
    ):
        self.limpiar()

        if km_por_pixel <= 0 or self.intervalo_km <= 0:
            return

        distancia = self.intervalo_km

        while distancia <= self.maximo_km:
            incremento_px = distancia / km_por_pixel
            radio = radio_limbo + incremento_px

            circulo = QGraphicsEllipseItem(
                -radio,
                -radio,
                radio * 2,
                radio * 2,
            )
            circulo.setPos(centro_x, centro_y)

            lapiz = QPen(QColor(self.color), self.grosor)
            lapiz.setCosmetic(True)
            lapiz.setStyle(Qt.DashLine)
            circulo.setPen(lapiz)
            circulo.setZValue(15)

            self.escena.addItem(circulo)
            self.elementos.append(circulo)

            punto = self._punto_visible_para_etiqueta(
                centro_x,
                centro_y,
                radio,
                rectangulo_imagen,
            )

            if punto is not None:
                etiqueta = QGraphicsSimpleTextItem(
                    f"{distancia:,.0f} km"
                )
                etiqueta.setBrush(QColor(self.color))
                fuente = QFont(self.familia_fuente)
                fuente.setPixelSize(int(self.tamano_texto))
                etiqueta.setFont(fuente)
                etiqueta.setZValue(16)

                caja = etiqueta.boundingRect()
                x = punto[0] - caja.width() / 2
                y = punto[1] - caja.height() - 5

                x = max(
                    rectangulo_imagen.left() + 6,
                    min(
                        x,
                        rectangulo_imagen.right()
                        - caja.width()
                        - 6,
                    ),
                )
                y = max(
                    rectangulo_imagen.top() + 6,
                    min(
                        y,
                        rectangulo_imagen.bottom()
                        - caja.height()
                        - 6,
                    ),
                )

                etiqueta.setPos(x, y)
                self.escena.addItem(etiqueta)
                self.elementos.append(etiqueta)

            distancia += self.intervalo_km
