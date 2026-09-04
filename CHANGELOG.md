# Historial de cambios

## 1.3.0

- Añadidos estilos independientes para mediciones de protuberancias,
  filamentos, regiones activas, distancia Tierra–Luna e información
  planetaria.
- Cada estilo permite elegir color, tamaño y familia tipográfica; la regla
  solar también tiene su propia fuente.
- Los colores de distancia e información planetaria pasan del menú
  **Comparaciones** al panel izquierdo de estilos.
- Las etiquetas de protuberancias y filamentos terminados se pueden mover con
  arrastre para despejarlas de la estructura medida.
- La posición manual de esas etiquetas se conserva en proyectos `.helio`,
  Ctrl+Z y exportaciones por lotes.

## 1.2.0

- Añadida comprobación visible de coherencia entre la escala calculada por el
  limbo y la escala introducida mediante los datos del equipo.
- La calibración muestra advertencias amarillas o rojas cuando la diferencia
  supera el 5% o el 15%, respectivamente, indicando qué parámetros revisar.
- Si la discrepancia supera el 15%, el usuario puede conservar la escala del
  equipo, usar la escala del limbo o volver a editar los datos.
- La elección de escala activa se conserva en los proyectos y recalcula las
  mediciones, la regla solar y las comparaciones.

## 1.1.0

- Añadido procesamiento por lotes para aplicar las anotaciones de una imagen
  plantilla a varios fotogramas ya alineados de un timelapse.
- El lote conserva las posiciones vectoriales y el tamaño en píxeles de todas
  las anotaciones, genera PNG sin sobrescribir archivos y omite resoluciones
  incompatibles con un informe final.
- Corregido el arrastre del control de tamaño de las regiones activas: ahora
  el grupo distingue el control de esquina del movimiento de la anotación y
  modifica el ancho y el alto del óvalo correctamente.
- Añadido `0 px` al contorno del limbo para ocultarlo sin perder los
  manejadores de edición.
- La alineación automática guiada por NOAA/HEK prueba y conserva pequeños
  desplazamientos y escalas globales además de la rotación y los espejos;
  la misma corrección se guarda en los proyectos y se aplica a las etiquetas.

## 1.0.0

- Primera versión estable de distribución pública para Windows.
- Autoría oficial actualizada a **David Olivos S. / Ne-notoka Cofame**.
- Nueva Licencia de uso gratuito Ne-notoka HelioRegla 1.0: permite el uso
  gratuito y compartir el instalador oficial intacto, pero no modificar,
  descompilar, vender ni redistribuir versiones alteradas.
- Se declara expresamente que las fotografías, proyectos, mediciones y
  exportaciones pertenecen a sus usuarios.
- Enlace oficial de apoyo integrado: `https://paypal.me/nenotokacofame`.
- Rutas de recursos compatibles con ejecución empaquetada mediante PyInstaller.
- Construcción automatizada con PyInstaller e Inno Setup: instalador bilingüe,
  icono Ne-notoka, accesos directos, licencia visible y desinstalador.
- Avisos y licencias de componentes de terceros incluidos en la distribución.
- El alineamiento automático de regiones activas compara ahora estructuras
  compactas de manchas, no la textura completa del disco. Esto mejora la
  correspondencia entre fotografías Seestar/luz visible y referencias HMI,
  GONG o AIA, admite imágenes invertidas y prueba las cuatro combinaciones de
  espejo antes de aceptar la orientación.
- Para H-alfa y otras longitudes con textura muy diferente se añadió una
  segunda solución guiada por las coordenadas NOAA/HEK: busca las AR en la
  propia fotografía y usa la referencia anotada únicamente como comprobación.
- Corregido el caso en que una mancha ocupa pocos píxeles: la alineación guiada
  usa picos compactos y coincidencias de varias AR, en lugar del percentil de
  toda la ventana que podía quedar en cero. La orientación con confianza media
  también se aplica cuando la evidencia catalogada supera a la correlación
  global.
- Las etiquetas de la referencia y de la fotografía conservan ahora la
  posición heliográfica NOAA/HEK; ya no se desplazan automáticamente hacia
  filamentos o plages cercanas.
- Al editar rotación o espejos en el diálogo de regiones activas se desactiva
  la alineación automática, para que la orientación manual no sea reemplazada
  silenciosamente al consultar NOAA/HEK.
- La solución guiada por catálogo tolera pequeños errores del radio detectado
  del limbo y aplica también resultados con confianza media o evidencia
  suficiente; antes podía calcularlos y dejar intacta la orientación anterior.
- Las regiones pequeñas reciben un óvalo mínimo más legible sin alterar su
  posición ni el valor publicado por NOAA.
- Cada óvalo de región activa incorpora un control de esquina para ajustar
  manualmente su ancho y alto sin mover el centro; el cambio se guarda en
  proyectos, exportaciones y Ctrl+Z.

## 0.21.0

- Corregida la conversión involuntaria de UTC a la zona horaria local en el
  selector de fecha y hora de regiones activas.
- Las 22:18 obtenidas del nombre permanecen como 22:18 UTC en Windows.
- Las fuentes de fecha se traducen correctamente al cambiar entre español e
  inglés, incluido `nombre del archivo` / `file name`.
- Pruebas de regresión para la orientación este/oeste de las coordenadas SRS.
- La referencia anotada dimensiona cada óvalo mediante el área y extensión
  publicadas por NOAA, en lugar de dibujar círculos idénticos.
- Nueva sección **Ayuda** con Acerca de, licencia y apoyo al proyecto.
- Añadidos `README.md` y `LICENSE` para preparar la distribución pública.
- La sección de apoyo explica que los donativos son voluntarios y no
  desbloquean funciones; el enlace directo de PayPal queda preparado para el
  distribución 1.0.

## 0.20.1

- Lectura robusta de fecha y hora desde nombres con fecha separada o compacta,
  hora con o sin separadores, segundos opcionales y orden día-mes-año.
- Los nombres de fotografías procesadas tienen prioridad sobre metadatos EXIF
  de exportación; `DATE-OBS` de FITS continúa siendo la fuente principal.
- El diálogo de regiones muestra el fragmento exacto del nombre interpretado
  para facilitar su verificación antes de consultar NOAA/HEK.
- Pruebas de regresión añadidas para formatos reales de Solex, ImPPG, video y
  nombres compactos.

## 0.20.0

- Selector de referencia para alineación: H-alfa GONG, continuo HMI,
  AIA 1700 Å como aproximación visual a CaK o selección automática.
- La posición diaria del SRS ya no es sustituida por una coordenada HEK
  potencialmente perteneciente a otro instante del intervalo consultado.
- Refinamiento local de cada AR alrededor de su posición catalogada; no se
  recupera el detector global por umbral que producía falsos positivos.
- La orientación automática informa su confianza y aplica coincidencias medias
  cuando hay evidencia suficiente; una coincidencia baja sin evidencia
  conserva los valores manuales.
- La referencia anotada utiliza las posiciones refinadas y distribuye sus
  textos para evitar superposiciones.
- Zoom con rueda, desplazamiento por arrastre, Ajustar a ventana y Tamaño
  real dentro del visor de referencia.
- Las etiquetas NOAA/HEK de la fotografía se acomodan automáticamente sin
  mover las regiones que señalan.
- Eliminada la tarjeta lateral Próximas herramientas.
- Preferencia de longitud de onda conservada entre sesiones y en proyectos.

## 0.19.0

- Registro automático de orientación contra referencias de disco completo de
  Helioviewer: SDO/HMI continuum, GONG H-alpha y SDO/AIA 1700 Å.
- La comparación de estructuras funciona con imágenes normales o invertidas y
  estima rotación e inversión horizontal.
- La orientación automática solo se aplica con confianza media o alta; una
  coincidencia débil conserva el ajuste manual.
- Nueva referencia solar oficial anotada, accesible tras consultar NOAA/HEK,
  para comprobar visualmente la correspondencia de regiones activas.
- Las etiquetas muestran el número AR y únicamente la clasificación magnética
  publicada por NOAA; el conteo de manchas continúa siendo opcional.
- Se evita inferir polaridad desde intensidad: HelioRegla no presenta como
  magnetograma una fotografía de luz visible, H-alpha o CaK.
- Referencias descargadas almacenadas en caché local para consultas repetidas.
- Interfaz, guía, atajos y mensajes actualizados en español e inglés.

## 0.7.1

- Movimiento fino del limbo mediante teclado.
- Color y tamaño configurables para anotaciones.
- Panel lateral desplazable.
- Confirmación al cerrar con mediciones.
- Reajuste automático de protuberancias al modificar el limbo.
- Arrastre nativo del punto de medición.
- Documentación inicial de controles y atajos.

## 0.6

- Medición de altura de protuberancias.
- Incertidumbre local mediante simulación.
- Comparaciones con diámetros terrestres y lunares.

## 0.5

- Calibración por datos ópticos del equipo.
- Lectura inicial de metadatos.

## 0.4

- Ajuste de limbo parcial mediante puntos.

## 0.3

- Autodetección del disco solar completo.

## 0.7.2

- Recalibración inmediata de todas las mediciones al aceptar datos del equipo.
- Las mediciones permanecen vinculadas al centro y radio del limbo.

## 0.9.0

- Nueva interfaz clara con identidad visual Ne-notoka.
- Azul institucional #004976.
- Amarillo institucional #FFB81C.
- Tipografía Century Gothic.
- Paneles y tarjetas claras.
- Barras de desplazamiento personalizadas.
- El área de la fotografía conserva fondo negro para análisis.
## 0.11.0

- Nuevo módulo para medir la longitud proyectada de filamentos.
- Trazado por puntos con edición posterior mediante arrastre.
- Comparación con diámetros terrestres y lunares.
- Incertidumbre estimada por colocación manual.
- Recalibración automática al cambiar la escala activa.
- Eliminación individual y compatibilidad con Ctrl+Z.
- Barras de desplazamiento del área de trabajo 15% mayores.

## 0.11.1

- Botón Aceptar medición para finalizar filamentos.
- Los nodos se ocultan al aceptar y permanece la curva medida.
- Se pueden medir varios filamentos sucesivamente en la misma imagen.

## 0.11.2

- Clic derecho elimina el punto concreto señalado durante el trazado.
- Clic izquierdo permite arrastrar y reajustar los puntos.
- La calibración recuerda los últimos datos del equipo.
- Los metadatos reconocidos conservan prioridad sobre los datos recordados.
- Cabecera lateral ampliada para mostrar CIENCIA SOLAR completa.

## 0.11.3

- Las mediciones de filamentos se recalculan al corregir los datos del equipo,
  incluso cuando la imagen no tiene un ajuste de limbo.

## 0.11.4

- Finalizar ajuste parcial y Cancelar puntos aparecen inmediatamente debajo
  de Limbo parcial por puntos mientras ese modo está activo.

## 0.12.0

- Exportación de la imagen anotada en PNG, JPEG o TIFF.
- Conserva exactamente la resolución y límites de la fotografía original.
- Excluye el fondo del visor y los controles auxiliares de edición.
- Recuerda la última carpeta de exportación.
- Atajo Ctrl + Shift + S.
- Tipografía unificada para protuberancias y filamentos mediante Century
  Gothic, negrita y tamaño real en píxeles.

## 0.12.1

- Corregida la persistencia del binning cuando la imagen no trae ese metadato.
- Los datos del equipo se sincronizan al pulsar OK.
- Toda medición de filamento se recalcula siempre después de calibrar.
- Panel lateral organizado en Calibración, Mediciones y Visualización.
- Acciones contextuales más pequeñas, centradas y resaltadas.

## 0.13.0

- Guardado y apertura de proyectos editables `.helio`.
- Conserva imagen, calibración, limbo, incertidumbres, protuberancias,
  filamentos, estilos y regla solar.
- Localización asistida cuando la fotografía original fue trasladada.
- Atajos Ctrl+S y Ctrl+Alt+O.
- Logo Ne-notoka aproximadamente 20% mayor.

## 0.14.0

- Primer módulo de comparación planetaria: Tierra y Luna a escala.
- Modo compacto y opción de distancia media real de 384,400 km entre centros.
- Comparación movible sobre la fotografía y eliminación con clic derecho.
- Recalibración automática al modificar los datos del equipo o el limbo.
- Compatibilidad con Ctrl+Z, proyectos `.helio` y exportación anotada.
- Indicadores en kilómetros, diámetros terrestres y diámetros lunares.

## 0.14.1

- Las herramientas planetarias pasan al menú superior Comparaciones.
- Carga de imágenes personalizadas para la Tierra y la Luna.
- Recorte circular automático y conservación del diámetro físico correcto.
- Restauración inmediata de los dibujos vectoriales predeterminados.
- Las imágenes elegidas se recuerdan para futuras sesiones.
- Los proyectos `.helio` conservan las referencias personalizadas.

## 0.15.0

- Interfaz bilingüe en español e inglés.
- Nuevo menú desplegable Idioma en la barra principal.
- Cambio inmediato y persistente entre ambos idiomas.
- Traducción de controles, diálogos principales, calibración y estados.
- Anotaciones científicas de protuberancias, filamentos y Tierra–Luna
  traducidas dinámicamente.
- Comparaciones pasa a la barra principal en el lugar del botón Deshacer.
- Ctrl+Z continúa disponible aunque Deshacer ya no ocupe espacio visible.

## 0.15.1

- La barra de herramientas principal ya no puede ocultarse accidentalmente
  mediante el menú contextual.
- Calibración por equipo aparece como primera opción de Calibración.
- La comparación Tierra–Luna conserva su posición al cambiar imágenes,
  recalibrar y guardar o abrir proyectos.
- Nuevo selector de color para la distancia Tierra–Luna.
- Opción para ocultar la línea y el texto de distancia sin retirar los
  cuerpos de la comparación.
- Las líneas de protuberancias y filamentos utilizan un trazo discontinuo
  que deja visible la estructura medida.
- Nuevo creador de acceso directo de escritorio para iniciar HelioRegla en
  Windows sin abrir Visual Studio Code ni una terminal.

## 0.16.0

- Comparaciones a escala para Mercurio, Venus, Marte, Júpiter, Saturno,
  Urano y Neptuno.
- Saturno incluye su disco y el diámetro aproximado del sistema principal
  de anillos.
- Nuevo submenú Añadir planeta dentro de Comparaciones.
- Cada planeta puede moverse independientemente y eliminarse con clic
  derecho.
- Se admiten imágenes personalizadas independientes para todos los planetas.
- Nuevo submenú Imágenes personalizadas para mantener ordenada la barra
  principal.
- Posición e imagen de cada planeta conservadas en proyectos `.helio`.
- Las comparaciones planetarias responden a Ctrl+Z y se recalculan al cambiar
  el limbo o los datos del equipo.
- Los nombres y resultados planetarios se actualizan al cambiar entre español
  e inglés.

## 0.16.1

- Corregida la superposición de las etiquetas de Tierra y Luna en el modo
  compacto mediante una leyenda conjunta en dos renglones.
- Añadir Tierra–Luna activa directamente el modo compacto.
- Mostrar distancia real crea automáticamente Tierra–Luna cuando todavía no
  está visible.
- Es posible alternar en cualquier orden entre el modo compacto y la distancia
  real sin quitar y volver a añadir la comparación.
- Añadir planeta pasa junto a Imágenes personalizadas para mejorar el orden
  del menú Comparaciones.
- Nuevo selector de color para la información de todos los planetas, incluida
  la leyenda de Tierra–Luna.
- El color planetario se conserva en preferencias, proyectos `.helio` y
  estados de Ctrl+Z.

## 0.17.0

- El tamaño elegido para las anotaciones se interpreta ahora en píxeles de la
  fotografía, no en píxeles de pantalla.
- Los textos conservan la misma proporción respecto de la imagen al acercar o
  alejar y coinciden con el tamaño obtenido al exportar.
- El cambio se aplica a protuberancias, filamentos, Tierra–Luna y todos los
  planetas; los puntos de edición siguen siendo cómodos de seleccionar.
- Primera etapa del módulo de manchas solares con detección asistida de
  regiones oscuras y alternativa de etiquetado manual.
- Cada mancha puede nombrarse, moverse con clic izquierdo, renombrarse con
  doble clic y eliminarse con clic derecho.
- Las etiquetas de manchas admiten color y tamaño configurables.
- Las manchas se incluyen en Ctrl+Z, proyectos `.helio`, exportación,
  confirmación de cierre e interfaz bilingüe.
- La detección propone candidatas para revisión; no asigna automáticamente
  números NOAA ni sustituye la validación del usuario.

## 0.18.0

- Eliminada la detección de manchas basada en umbral de brillo y contraste,
  que producía falsos positivos y omitía regiones reales en imágenes
  procesadas, H-alpha y CaK.
- Nueva consulta de regiones activas mediante NOAA Solar Region Summary y
  Heliophysics Events Knowledgebase a través de Helioviewer.
- Lectura inicial de fecha y hora desde FITS, EXIF o nombre de archivo, con
  verificación manual en UTC antes de consultar.
- Consulta histórica del SRS correspondiente a la fecha de captura.
- La tabla de resultados incluye número AR, ubicación, cantidad de manchas,
  área, clasificación y fuentes disponibles.
- El número de manchas es opcional y procede del campo `NN` publicado por
  NOAA; HelioRegla no inventa ni estima el conteo.
- Proyección automática de posiciones sobre discos completos y limbos
  parciales ajustados, con controles de rotación e inversión horizontal o
  vertical.
- Repetir la consulta actualiza las AR ya colocadas en lugar de duplicarlas.
- Sin un limbo ajustado, el catálogo queda disponible para asignar la AR
  durante el marcado manual.
- El modo manual permite encerrar una región activa mediante clic izquierdo
  y arrastre; un clic breve conserva la creación de una marca pequeña.
- Las regiones guardan tamaño elíptico y datos de catálogo en proyectos
  `.helio`, Ctrl+Z y exportación.
- Interfaz, mensajes y documentación actualizados en español e inglés.
