from pathlib import Path

from PySide6.QtCore import QLineF, QPointF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsSimpleTextItem,
)
from i18n import tr


DIAMETRO_TIERRA_KM = 12_742.0
DIAMETRO_LUNA_KM = 3_474.8
DISTANCIA_TIERRA_LUNA_KM = 384_400.0

PLANETAS = {
    "mercurio": {
        "diametro_km": 4_879.0,
        "color": "#8F8A83",
        "borde": "#D4CEC5",
    },
    "venus": {
        "diametro_km": 12_104.0,
        "color": "#D9A45B",
        "borde": "#FFE0A3",
    },
    "marte": {
        "diametro_km": 6_779.0,
        "color": "#B84E2B",
        "borde": "#F29A72",
    },
    "jupiter": {
        "diametro_km": 139_820.0,
        "color": "#D7B28A",
        "borde": "#F5DFC5",
    },
    "saturno": {
        "diametro_km": 116_460.0,
        "diametro_anillos_km": 282_000.0,
        "color": "#D9C28D",
        "borde": "#FFF0C2",
    },
    "urano": {
        "diametro_km": 50_724.0,
        "color": "#8ADAE6",
        "borde": "#D5FAFF",
    },
    "neptuno": {
        "diametro_km": 49_244.0,
        "color": "#4169D8",
        "borde": "#AFC7FF",
    },
}


class ImagenCircular(QGraphicsPixmapItem):
    def paint(self, painter, option, widget=None):
        ruta = QPainterPath()
        ruta.addEllipse(self.boundingRect())
        painter.save()
        painter.setClipPath(ruta)
        super().paint(painter, option, widget)
        painter.restore()


class GrupoTierraLuna(QGraphicsItemGroup):
    def __init__(self, comparacion):
        super().__init__()
        self.comparacion = comparacion
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setCursor(Qt.SizeAllCursor)
        self.setZValue(40)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.comparacion.eliminar()
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            self.comparacion.notificar_inicio_cambio()

        super().mousePressEvent(event)


class ComparacionTierraLuna:
    def __init__(
        self,
        escena,
        km_por_pixel,
        posicion,
        separacion_real=False,
        tamano_texto=20,
        imagen_tierra=None,
        imagen_luna=None,
        color_distancia="#FFB81C",
        mostrar_linea_distancia=True,
        color_informacion="#FFFFFF",
        al_eliminar=None,
        antes_cambiar=None,
        familia_fuente="Century Gothic",
        tamano_distancia=None,
        familia_fuente_distancia=None,
        tamano_informacion=None,
        familia_fuente_informacion=None,
    ):
        self.escena = escena
        self.km_por_pixel = float(km_por_pixel)
        self.separacion_real = bool(separacion_real)
        self.tamano_texto = int(tamano_texto)
        self.familia_fuente = str(
            familia_fuente or "Century Gothic"
        )
        self.imagen_tierra = imagen_tierra
        self.imagen_luna = imagen_luna
        self.color_distancia = color_distancia
        self.mostrar_linea_distancia = bool(
            mostrar_linea_distancia
        )
        self.color_informacion = color_informacion
        self.tamano_distancia = int(
            tamano_distancia
            if tamano_distancia is not None
            else tamano_texto
        )
        self.familia_fuente_distancia = str(
            familia_fuente_distancia or self.familia_fuente
        )
        self.tamano_informacion = int(
            tamano_informacion
            if tamano_informacion is not None
            else tamano_texto
        )
        self.familia_fuente_informacion = str(
            familia_fuente_informacion or self.familia_fuente
        )
        self.al_eliminar = al_eliminar
        self.antes_cambiar = antes_cambiar
        self.eliminada = False
        self.grupo = GrupoTierraLuna(self)
        self.escena.addItem(self.grupo)
        self.grupo.setPos(QPointF(posicion))
        self.actualizar()

    def notificar_inicio_cambio(self):
        if self.antes_cambiar is not None:
            self.antes_cambiar()

    def _limpiar_grupo(self):
        for elemento in self.grupo.childItems():
            self.grupo.removeFromGroup(elemento)

            if elemento.scene() is not None:
                self.escena.removeItem(elemento)

    def _fuente(self, tamano=None, familia=None):
        fuente = QFont(familia or self.familia_fuente)
        fuente.setPixelSize(
            int(tamano if tamano is not None else self.tamano_texto)
        )
        fuente.setBold(True)
        return fuente

    def _texto(
        self,
        contenido,
        color,
        x,
        y,
        alinear_derecha=False,
        tamano=None,
        familia=None,
    ):
        texto = QGraphicsSimpleTextItem(contenido)
        texto.setBrush(QBrush(QColor(color)))
        texto.setFont(self._fuente(tamano, familia))

        if alinear_derecha:
            x -= texto.boundingRect().width()

        texto.setPos(x, y)
        self.grupo.addToGroup(texto)

    def _pixmap_valido(self, ruta):
        if not ruta or not Path(ruta).is_file():
            return None

        pixmap = QPixmap(str(ruta))
        return pixmap if not pixmap.isNull() else None

    def _imagen_circular(
        self,
        ruta,
        centro_x,
        diametro,
        color_borde,
    ):
        pixmap = self._pixmap_valido(ruta)

        if pixmap is None:
            return False

        lado = max(2, round(diametro))
        pixmap = pixmap.scaled(
            lado,
            lado,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        pixmap = pixmap.copy(
            max(0, (pixmap.width() - lado) // 2),
            max(0, (pixmap.height() - lado) // 2),
            lado,
            lado,
        )
        imagen = ImagenCircular(pixmap)
        imagen.setOffset(
            centro_x - pixmap.width() / 2,
            -pixmap.height() / 2,
        )
        self.grupo.addToGroup(imagen)
        borde = QGraphicsEllipseItem(
            centro_x - diametro / 2,
            -diametro / 2,
            diametro,
            diametro,
        )
        lapiz = QPen(QColor(color_borde), 2)
        lapiz.setCosmetic(True)
        borde.setPen(lapiz)
        borde.setBrush(QBrush(Qt.NoBrush))
        self.grupo.addToGroup(borde)
        return True

    def actualizar(self):
        if self.eliminada or self.km_por_pixel <= 0:
            return

        posicion_escena = self.grupo.scenePos()
        self.grupo.setPos(0, 0)
        self._limpiar_grupo()
        diametro_tierra = DIAMETRO_TIERRA_KM / self.km_por_pixel
        diametro_luna = DIAMETRO_LUNA_KM / self.km_por_pixel
        radio_tierra = diametro_tierra / 2
        radio_luna = diametro_luna / 2

        if self.separacion_real:
            distancia_centros = (
                DISTANCIA_TIERRA_LUNA_KM / self.km_por_pixel
            )
        else:
            distancia_centros = (
                radio_tierra
                + radio_luna
                + diametro_tierra * 0.35
            )

        x_tierra = -distancia_centros / 2
        x_luna = distancia_centros / 2

        if not self._imagen_circular(
            self.imagen_tierra,
            x_tierra,
            diametro_tierra,
            "#BDE7FF",
        ):
            tierra = QGraphicsEllipseItem(
                x_tierra - radio_tierra,
                -radio_tierra,
                diametro_tierra,
                diametro_tierra,
            )
            tierra.setBrush(QBrush(QColor("#2F80ED")))
            lapiz_tierra = QPen(QColor("#BDE7FF"), 2)
            lapiz_tierra.setCosmetic(True)
            tierra.setPen(lapiz_tierra)
            self.grupo.addToGroup(tierra)

            continente = QGraphicsEllipseItem(
                x_tierra - radio_tierra * 0.45,
                -radio_tierra * 0.25,
                radio_tierra * 0.75,
                radio_tierra * 0.45,
            )
            continente.setBrush(QBrush(QColor("#62B56B")))
            continente.setPen(QPen(Qt.NoPen))
            self.grupo.addToGroup(continente)

        if not self._imagen_circular(
            self.imagen_luna,
            x_luna,
            diametro_luna,
            "#F2F2F2",
        ):
            luna = QGraphicsEllipseItem(
                x_luna - radio_luna,
                -radio_luna,
                diametro_luna,
                diametro_luna,
            )
            luna.setBrush(QBrush(QColor("#B8BDC3")))
            lapiz_luna = QPen(QColor("#F2F2F2"), 2)
            lapiz_luna.setCosmetic(True)
            luna.setPen(lapiz_luna)
            self.grupo.addToGroup(luna)

            crater = QGraphicsEllipseItem(
                x_luna - radio_luna * 0.35,
                -radio_luna * 0.25,
                max(0.8, radio_luna * 0.35),
                max(0.8, radio_luna * 0.35),
            )
            crater.setBrush(QBrush(QColor("#8D939A")))
            crater.setPen(QPen(Qt.NoPen))
            self.grupo.addToGroup(crater)

        desplazamiento = max(radio_tierra, radio_luna) + 8
        if self.separacion_real:
            self._texto(
                tr("earth_label"),
                self.color_informacion,
                x_tierra - radio_tierra - 8,
                desplazamiento,
                alinear_derecha=True,
                tamano=self.tamano_informacion,
                familia=self.familia_fuente_informacion,
            )
            self._texto(
                tr("moon_label"),
                self.color_informacion,
                x_luna + radio_luna + 8,
                desplazamiento,
                tamano=self.tamano_informacion,
                familia=self.familia_fuente_informacion,
            )
        else:
            self._texto(
                tr("earth_moon_compact_label"),
                self.color_informacion,
                x_tierra - radio_tierra,
                desplazamiento,
                tamano=self.tamano_informacion,
                familia=self.familia_fuente_informacion,
            )

        if (
            self.separacion_real
            and self.mostrar_linea_distancia
        ):
            linea = QGraphicsLineItem(
                QLineF(x_tierra, 0, x_luna, 0)
            )
            lapiz = QPen(QColor(self.color_distancia), 2)
            lapiz.setCosmetic(True)
            lapiz.setStyle(Qt.DashLine)
            lapiz.setDashPattern([4.0, 3.0])
            linea.setPen(lapiz)
            linea.setZValue(-1)
            self.grupo.addToGroup(linea)
            self._texto(
                tr("distance_label"),
                self.color_distancia,
                -distancia_centros * 0.22,
                -desplazamiento - self.tamano_distancia * 1.8,
                tamano=self.tamano_distancia,
                familia=self.familia_fuente_distancia,
            )

        self.grupo.setPos(posicion_escena)

    def establecer_separacion_real(self, activa):
        self.separacion_real = bool(activa)
        self.actualizar()

    def establecer_escala(self, km_por_pixel):
        self.km_por_pixel = float(km_por_pixel)
        self.actualizar()

    def establecer_tamano_texto(self, tamano):
        self.tamano_texto = int(tamano)
        self.tamano_distancia = int(tamano)
        self.tamano_informacion = int(tamano)
        self.actualizar()

    def establecer_estilo_distancia(
        self,
        color,
        tamano,
        familia,
    ):
        self.color_distancia = str(color)
        self.tamano_distancia = int(tamano)
        self.familia_fuente_distancia = str(
            familia or self.familia_fuente
        )
        self.actualizar()

    def establecer_estilo_informacion(
        self,
        color,
        tamano,
        familia,
    ):
        self.color_informacion = str(color)
        self.tamano_informacion = int(tamano)
        self.familia_fuente_informacion = str(
            familia or self.familia_fuente
        )
        self.actualizar()

    def establecer_imagenes(self, tierra=None, luna=None):
        self.imagen_tierra = tierra
        self.imagen_luna = luna
        self.actualizar()

    def establecer_color_distancia(self, color):
        self.color_distancia = color
        self.actualizar()

    def establecer_linea_distancia_visible(self, visible):
        self.mostrar_linea_distancia = bool(visible)
        self.actualizar()

    def establecer_color_informacion(self, color):
        self.color_informacion = color
        self.actualizar()

    def eliminar(self):
        if self.eliminada:
            return

        self.notificar_inicio_cambio()
        self.eliminada = True

        if self.grupo.scene() is not None:
            self.escena.removeItem(self.grupo)

        if self.al_eliminar is not None:
            self.al_eliminar(self)

    def estado(self):
        posicion = self.grupo.scenePos()
        return {
            "x": posicion.x(),
            "y": posicion.y(),
            "separacion_real": self.separacion_real,
            "imagen_tierra": self.imagen_tierra,
            "imagen_luna": self.imagen_luna,
            "color_distancia": self.color_distancia,
            "mostrar_linea_distancia": (
                self.mostrar_linea_distancia
            ),
            "color_informacion": self.color_informacion,
            "tamano_distancia": self.tamano_distancia,
            "familia_fuente_distancia": (
                self.familia_fuente_distancia
            ),
            "tamano_informacion": self.tamano_informacion,
            "familia_fuente_informacion": (
                self.familia_fuente_informacion
            ),
        }


class GrupoPlaneta(QGraphicsItemGroup):
    def __init__(self, comparacion):
        super().__init__()
        self.comparacion = comparacion
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setCursor(Qt.SizeAllCursor)
        self.setZValue(40)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.comparacion.eliminar()
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            self.comparacion.notificar_inicio_cambio()

        super().mousePressEvent(event)


class ComparacionPlaneta:
    def __init__(
        self,
        escena,
        planeta,
        km_por_pixel,
        posicion,
        tamano_texto=20,
        imagen=None,
        color_informacion="#FFFFFF",
        al_eliminar=None,
        antes_cambiar=None,
        familia_fuente="Century Gothic",
    ):
        if planeta not in PLANETAS:
            raise ValueError(f"Planeta desconocido: {planeta}")

        self.escena = escena
        self.planeta = planeta
        self.km_por_pixel = float(km_por_pixel)
        self.tamano_texto = int(tamano_texto)
        self.familia_fuente = str(
            familia_fuente or "Century Gothic"
        )
        self.imagen = imagen
        self.color_informacion = color_informacion
        self.al_eliminar = al_eliminar
        self.antes_cambiar = antes_cambiar
        self.eliminada = False
        self.grupo = GrupoPlaneta(self)
        self.escena.addItem(self.grupo)
        self.grupo.setPos(QPointF(posicion))
        self.actualizar()

    def notificar_inicio_cambio(self):
        if self.antes_cambiar is not None:
            self.antes_cambiar()

    def _limpiar_grupo(self):
        for elemento in self.grupo.childItems():
            self.grupo.removeFromGroup(elemento)

            if elemento.scene() is not None:
                self.escena.removeItem(elemento)

    def _fuente(self):
        fuente = QFont(self.familia_fuente)
        fuente.setPixelSize(self.tamano_texto)
        fuente.setBold(True)
        return fuente

    def _anadir_texto(self, contenido, color, x, y):
        texto = QGraphicsSimpleTextItem(contenido)
        texto.setBrush(QBrush(QColor(color)))
        texto.setFont(self._fuente())
        texto.setPos(x, y)
        self.grupo.addToGroup(texto)

    def _anadir_anillos(self, diametro, diametro_anillos):
        alto = diametro * 0.48

        for proporcion, color, grosor in (
            (1.0, "#E9D7A1", 3),
            (0.88, "#B89A65", 2),
            (0.72, "#F5E8C2", 2),
        ):
            ancho = diametro_anillos * proporcion
            anillo = QGraphicsEllipseItem(
                -ancho / 2,
                -alto * proporcion / 2,
                ancho,
                alto * proporcion,
            )
            lapiz = QPen(QColor(color), grosor)
            lapiz.setCosmetic(True)
            anillo.setPen(lapiz)
            anillo.setBrush(QBrush(Qt.NoBrush))
            self.grupo.addToGroup(anillo)

    def _anadir_disco(self, datos, diametro):
        radio = diametro / 2
        pixmap = None

        if self.imagen and Path(self.imagen).is_file():
            candidato = QPixmap(str(self.imagen))

            if not candidato.isNull():
                pixmap = candidato

        if pixmap is not None:
            lado = max(2, round(diametro))
            pixmap = pixmap.scaled(
                lado,
                lado,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            pixmap = pixmap.copy(
                max(0, (pixmap.width() - lado) // 2),
                max(0, (pixmap.height() - lado) // 2),
                lado,
                lado,
            )
            imagen = ImagenCircular(pixmap)
            imagen.setOffset(
                -pixmap.width() / 2,
                -pixmap.height() / 2,
            )
            self.grupo.addToGroup(imagen)
        else:
            disco = QGraphicsEllipseItem(
                -radio,
                -radio,
                diametro,
                diametro,
            )
            disco.setBrush(QBrush(QColor(datos["color"])))
            lapiz = QPen(QColor(datos["borde"]), 2)
            lapiz.setCosmetic(True)
            disco.setPen(lapiz)
            self.grupo.addToGroup(disco)
            self._anadir_detalles(diametro)

        borde = QGraphicsEllipseItem(
            -radio,
            -radio,
            diametro,
            diametro,
        )
        lapiz_borde = QPen(QColor(datos["borde"]), 2)
        lapiz_borde.setCosmetic(True)
        borde.setPen(lapiz_borde)
        borde.setBrush(QBrush(Qt.NoBrush))
        self.grupo.addToGroup(borde)

    def _anadir_saturno_personalizado(
        self,
        diametro_anillos,
        diametro_planeta,
    ):
        if not self.imagen or not Path(self.imagen).is_file():
            return False

        pixmap = QPixmap(str(self.imagen))

        if pixmap.isNull():
            return False

        ancho = max(2, round(diametro_anillos))
        alto = max(2, round(diametro_planeta * 1.25))
        pixmap = pixmap.scaled(
            ancho,
            alto,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        imagen = QGraphicsPixmapItem(pixmap)
        imagen.setOffset(
            -pixmap.width() / 2,
            -pixmap.height() / 2,
        )
        self.grupo.addToGroup(imagen)
        return True

    def _anadir_detalles(self, diametro):
        radio = diametro / 2

        if self.planeta in {"jupiter", "saturno"}:
            color = (
                "#9A6548"
                if self.planeta == "jupiter"
                else "#A98D58"
            )

            for proporcion in (-0.45, -0.15, 0.18, 0.46):
                mitad = (
                    radio
                    * max(0.25, 1 - abs(proporcion) * 0.7)
                )
                linea = QGraphicsLineItem(
                    -mitad,
                    proporcion * radio,
                    mitad,
                    proporcion * radio,
                )
                lapiz = QPen(QColor(color), 2)
                lapiz.setCosmetic(True)
                linea.setPen(lapiz)
                self.grupo.addToGroup(linea)
        elif self.planeta in {"mercurio", "marte"}:
            crater = QGraphicsEllipseItem(
                -radio * 0.45,
                -radio * 0.25,
                max(1.0, radio * 0.35),
                max(1.0, radio * 0.35),
            )
            crater.setBrush(QBrush(QColor("#6E5146")))
            crater.setPen(QPen(Qt.NoPen))
            self.grupo.addToGroup(crater)

    def actualizar(self):
        if self.eliminada or self.km_por_pixel <= 0:
            return

        posicion_escena = self.grupo.scenePos()
        self.grupo.setPos(0, 0)
        self._limpiar_grupo()
        datos = PLANETAS[self.planeta]
        diametro = datos["diametro_km"] / self.km_por_pixel

        if self.planeta == "saturno":
            diametro_anillos = (
                datos["diametro_anillos_km"]
                / self.km_por_pixel
            )

            if not self._anadir_saturno_personalizado(
                diametro_anillos,
                diametro,
            ):
                self._anadir_anillos(
                    diametro,
                    diametro_anillos,
                )
                self._anadir_disco(datos, diametro)
        else:
            self._anadir_disco(datos, diametro)
        desplazamiento = (
            max(
                diametro,
                (
                    datos.get(
                        "diametro_anillos_km",
                        datos["diametro_km"],
                    )
                    / self.km_por_pixel
                ),
            )
            / 2
            + 8
        )
        etiqueta = tr(
            "planet_label",
            name=tr(self.planeta),
            diameter=f"{datos['diametro_km']:,.0f}",
        )

        if self.planeta == "saturno":
            etiqueta += "\n" + tr(
                "saturn_rings_label",
                diameter=(
                    f"{datos['diametro_anillos_km']:,.0f}"
                ),
            )

        self._anadir_texto(
            etiqueta,
            self.color_informacion,
            -diametro / 2,
            desplazamiento,
        )
        self.grupo.setPos(posicion_escena)

    def establecer_escala(self, km_por_pixel):
        self.km_por_pixel = float(km_por_pixel)
        self.actualizar()

    def establecer_tamano_texto(self, tamano):
        self.tamano_texto = int(tamano)
        self.actualizar()

    def establecer_estilo_informacion(
        self,
        color,
        tamano,
        familia,
    ):
        self.color_informacion = str(color)
        self.tamano_texto = int(tamano)
        self.familia_fuente = str(
            familia or self.familia_fuente
        )
        self.actualizar()

    def establecer_imagen(self, imagen=None):
        self.imagen = imagen
        self.actualizar()

    def establecer_color_informacion(self, color):
        self.color_informacion = color
        self.actualizar()

    def eliminar(self):
        if self.eliminada:
            return

        self.notificar_inicio_cambio()
        self.eliminada = True

        if self.grupo.scene() is not None:
            self.escena.removeItem(self.grupo)

        if self.al_eliminar is not None:
            self.al_eliminar(self)

    def estado(self):
        posicion = self.grupo.scenePos()
        return {
            "planeta": self.planeta,
            "x": posicion.x(),
            "y": posicion.y(),
            "imagen": self.imagen,
            "color_informacion": self.color_informacion,
            "tamano_informacion": self.tamano_texto,
            "familia_fuente_informacion": self.familia_fuente,
        }
