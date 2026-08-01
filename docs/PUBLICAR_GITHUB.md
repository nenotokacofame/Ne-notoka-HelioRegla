# Publicar Ne-notoka HelioRegla en GitHub

Este proyecto ya incluye la guía de uso (`docs/GUIA_DE_USO.md`), los atajos
(`docs/ATAJOS.md`), la licencia (`LICENSE`) y los avisos de terceros
(`THIRD_PARTY_NOTICES.txt`). Esta guía reúne los pasos para publicar la versión
1.0.0 de forma reproducible.

## 1. Preparar el instalador

En Windows, dentro de la carpeta principal del proyecto:

1. Ejecuta `crear_instalador_windows.bat`.
2. Comprueba que aparezca
   `dist_instalador\Ne-notoka_HelioRegla_1.0.0_Setup.exe`.
3. Genera el hash SHA-256:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\generar_sha256.ps1
   ```

El script crea `SHA256SUMS.txt` en la carpeta principal. Ese archivo debe
publicarse junto al instalador para que cualquier persona pueda comprobar que
descargó exactamente el archivo oficial.

También se puede indicar un archivo concreto:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\generar_sha256.ps1 `
  -InstallerPath .\dist_instalador\Ne-notoka_HelioRegla_1.0.0_Setup.exe
```

## 2. Crear el repositorio

En GitHub crea un repositorio nuevo llamado, por ejemplo,
`Ne-notoka-HelioRegla`. Para conservar la identidad y los avisos del proyecto,
no generes allí un README, `.gitignore` o licencia adicionales: esos archivos
ya están preparados aquí.

Desde PowerShell, en la carpeta del proyecto:

```powershell
git init
git add .
git commit -m "Ne-notoka HelioRegla 1.0.0"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/Ne-notoka-HelioRegla.git
git push -u origin main
```

Sustituye `TU_USUARIO` por el nombre de tu cuenta. Si el repositorio ya existe
en tu computadora, omite `git init` y `git remote add`.

## 3. Crear la versión descargable

En GitHub abre **Releases > Draft a new release**:

- Etiqueta: `v1.0.0`.
- Título: `Ne-notoka HelioRegla 1.0.0`.
- Adjunta `Ne-notoka_HelioRegla_1.0.0_Setup.exe`.
- Adjunta `SHA256SUMS.txt`.
- En la descripción enlaza `README.md`, `docs/GUIA_DE_USO.md` y `LICENSE`.

El instalador no está dentro del historial del código fuente: se publica como
activo de la versión. Así el repositorio permanece ligero y cada descarga
queda asociada a su hash.

## 4. Verificar una descarga

Después de descargar el instalador, una persona puede comprobarlo con:

```powershell
Get-FileHash .\Ne-notoka_HelioRegla_1.0.0_Setup.exe -Algorithm SHA256
```

El valor debe coincidir exactamente con la línea correspondiente de
`SHA256SUMS.txt`.

## Firma digital

La versión 1.0.0 se publicará sin certificado de firma porque ahora no es una
opción económica. Windows puede mostrar una advertencia de SmartScreen en las
primeras descargas; el instalador sigue siendo verificable mediante el hash y
la publicación oficial de GitHub. Una firma Authenticode puede añadirse en una
versión posterior sin cambiar el código de la aplicación.

## Licencia y alcance de GitHub

`LICENSE` es la licencia personalizada de uso gratuito de Ne-notoka
HelioRegla. Permite usar el programa y compartir el instalador oficial intacto,
pero no autoriza modificar, descompilar, vender ni redistribuir versiones
alteradas. El código visible en GitHub no cambia esas condiciones. Las
fotografías, proyectos, mediciones e imágenes exportadas siguen perteneciendo
a sus respectivos usuarios.
