# Guía de uso de Ne-notoka HelioRegla

## Flujo básico

1. Abrir una imagen solar.
2. Ajustar el limbo:
   - Autodetección para disco completo.
   - Ajuste por puntos para acercamientos parciales.
   - Ajuste manual para correcciones.
3. Aplicar calibración por equipo cuando sea necesario.
4. Crear mediciones y comparaciones.
5. Revisar incertidumbres.
6. Exportar la imagen anotada.

## Escalas

La escala por limbo utiliza el diámetro físico nominal del Sol.

La calibración por equipo utiliza:

- Tamaño de píxel.
- Focal efectiva.
- Binning.
- Redimensionamiento de la imagen.
- Fecha y distancia Tierra-Sol.

## Incertidumbres

El residuo indica qué tan bien coincide el círculo con los puntos.

La incertidumbre del radio indica cuánto puede variar el círculo completo.

La incertidumbre local de una protuberancia se calcula simulando la posición del limbo justo debajo de esa estructura.

## Recalibración

Al aceptar una calibración por equipo, todas las mediciones existentes se recalculan inmediatamente con la nueva escala activa.
