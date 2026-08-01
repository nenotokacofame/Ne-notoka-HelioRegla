# Ne-notoka HelioRegla 0.11.1

## Instalación

1. Cierra Ne-notoka HelioRegla.
2. Extrae el contenido del ZIP.
3. Copia las carpetas y archivos extraídos dentro de:

   `C:\Users\d_oli\Proyectos\HelioRegla`

4. Acepta reemplazar los archivos existentes.
5. Desde la terminal de VS Code ejecuta:

   `.\.venv\Scripts\python.exe -m py_compile app\main.py app\filamentos.py`

6. Si no aparece ningún mensaje de error, inicia:

   `.\.venv\Scripts\python.exe app\main.py`

## Medición de filamentos

- Pulsa **Medir filamento**.
- Clic izquierdo: agrega puntos siguiendo el filamento.
- Clic derecho mientras dibujas: retira el último punto.
- **Aceptar medición** o Enter: termina el trazado y oculta sus puntos.
- Esc: cancela.
- Arrastra los puntos terminados para afinar la curva.
- Clic derecho sobre un punto, curva o texto: elimina esa medición.
- Ctrl+Z: deshace creación, movimiento o eliminación.

La aplicación informa la longitud proyectada en kilómetros y la compara con
los diámetros de la Tierra y la Luna. La escala se actualiza si posteriormente
se calibra la imagen mediante los datos del equipo.

Después de aceptar una curva puedes pulsar nuevamente **Medir filamento** y
añadir tantas mediciones como necesites en la misma fotografía.
