<p align="center"><img src="hada_del_bosque/resources/hada.png" width="180" alt="Hada del bosque con cámara"></p>

<p align="center">
  <a href="https://github.com/israelgarcia86/fotos-hada-del-bosque/releases/latest/download/FotosDelHadaDelBosque-Windows.zip"><b>⬇️ Descargar para Windows</b></a>
  ·
  <a href="#instalación-en-linux"><b>🐧 Instalar en Linux</b></a>
  ·
  <a href="https://github.com/israelgarcia86/fotos-hada-del-bosque/releases/latest">Todas las versiones</a>
</p>

# Fotos del hada del bosque

Programa para **ordenar tus fotos y vídeos por año, mes y categoría** y copiarlos a una carpeta ya ordenada, con esta estructura:

```
Fotos ordenadas/
└── 2023/
    └── 05 - Mayo/
        ├── Feria de Abril/
        └── (fotos del mes sin categoría)
```

Nunca mueve ni borra tus fotos: solo las **copia**.

## Instalación en Windows

1. Pulsa **[⬇️ Descargar para Windows](https://github.com/israelgarcia86/fotos-hada-del-bosque/releases/latest/download/FotosDelHadaDelBosque-Windows.zip)**.
2. Busca el fichero descargado (`FotosDelHadaDelBosque-Windows.zip`), haz clic derecho sobre él y elige **Extraer todo…**. Puedes guardarlo, por ejemplo, en Documentos.
3. Dentro de la carpeta extraída, haz doble clic en **`FotosDelHadaDelBosque.exe`**. No hace falta instalar nada más.
4. La primera vez, Windows puede mostrar un aviso azul («Windows protegió su PC»), porque el programa no está firmado por una empresa. Pulsa **Más información → Ejecutar de todas formas**.

Para tener un acceso directo, haz clic derecho sobre `FotosDelHadaDelBosque.exe` → **Enviar a → Escritorio (crear acceso directo)**.

**Para actualizar** a una versión nueva, descárgala igual y sustituye la carpeta antigua. Tu trabajo no se pierde, porque se guarda junto a tus fotos.

## Instalación en Linux

En Linux el programa funciona con Python, que casi todas las distribuciones traen ya instalado.

1. **Instala lo básico** (solo la primera vez). Abre una terminal y escribe:
   - Ubuntu, Debian, Linux Mint:
     ```bash
     sudo apt install python3-venv libxcb-cursor0
     ```
   - Fedora:
     ```bash
     sudo dnf install python3 xcb-util-cursor
     ```
2. **Descarga el programa**: en [la última versión](https://github.com/israelgarcia86/fotos-hada-del-bosque/releases/latest), dentro de *Assets*, pulsa **Source code (zip)** y descomprímelo donde quieras.
3. **Arráncalo** desde una terminal, dentro de la carpeta descomprimida:
   ```bash
   bash Hada_del_bosque_Linux.sh
   ```
   La primera vez instala sus componentes, lo que tarda unos minutos. Las siguientes veces arranca enseguida.

**Para actualizar**, descarga la nueva versión y ejecuta `bash Hada_del_bosque_Linux.sh` en la carpeta nueva. La primera vez volverá a instalar los componentes.

<details>
<summary>Opcional: añadirlo al menú de aplicaciones</summary>

Ejecuta esto **dentro de la carpeta del programa**:

```bash
cat > ~/.local/share/applications/hada-del-bosque.desktop <<EOF
[Desktop Entry]
Type=Application
Name=Fotos del hada del bosque
Exec=bash "$PWD/Hada_del_bosque_Linux.sh"
Icon=$PWD/hada_del_bosque/resources/hada.png
Terminal=false
Categories=Graphics;Photography;
EOF
```

Aparecerá en el menú como «Fotos del hada del bosque». La primera vez ábrelo desde la terminal, para que termine de instalarse.
</details>

## Cómo se usa

1. **Elige la carpeta** con las fotos que quieres ordenar. Se revisan también todas sus subcarpetas.
   La primera vez, el programa te pregunta (es opcional) dónde tienes tus fotos **ya ordenadas**. Así aprovecha las categorías que ya tienes.
2. **Paso 1: revisión de carpetas.** Solo se hace la primera vez. Para cada carpeta dices si es ya un grupo de fotos (un viaje, una celebración…) pulsando **Sí**, o si no lo es (Descargas, WhatsApp Images…) pulsando **No**. Haz clic en una miniatura para verla en grande o reproducir el vídeo.
3. **Paso 2: foto a foto**, ordenadas por fecha. A la izquierda ves la foto o el vídeo; a la derecha, su fecha y los botones de categoría:
   - las categorías del **mes de la foto y de los meses de alrededor**. Si la foto venía de una carpeta agrupada, su categoría aparece **en amarillo**: basta con pulsarla;
   - las categorías **recientes**: las que ya has usado en fotos de fechas cercanas (±2 meses), aunque sean de otro mes;
   - **Sin categoría**: la foto va directamente a la carpeta de su mes;
   - **Nueva categoría** para crear una, y **Otra categoría…** para buscar cualquier otra.

   Al pulsar una categoría, se pasa **directamente a la siguiente foto**. Si te equivocas, vuelve con **Anterior**: la categoría elegida aparece en verde.
4. Cuando quieras, en el menú **Destino → Copiar las fotos clasificadas al destino…** se copian las fotos a tu carpeta ordenada. Se aprovechan las carpetas de año, mes y categoría que ya existan, y no se duplica una foto que ya esté allí. Las carpetas de mes nuevas se nombran igual que las que ya tienes (por ejemplo `05 - Mayo`).

### Tu trabajo se guarda solo
Después de cada foto, el progreso se guarda en el fichero `hada_del_bosque.json`, dentro de tu carpeta de fotos. Si cierras el programa y vuelves a abrir la misma carpeta, sigues donde lo dejaste. Funciona igual en Windows y en Linux, así que puedes empezar en un ordenador y seguir en otro.

Para **empezar de cero** (por ejemplo, después de hacer pruebas), marca **«Empezar de cero»** en la pantalla de inicio, o usa **Archivo → Reiniciar todo el trabajo de esta carpeta…**. No se borra ninguna foto, y el progreso anterior se guarda como copia (`hada_del_bosque.reiniciado-FECHA.json`).

### Atajos de teclado
Con el teclado se va mucho más rápido:

| Tecla | Acción |
|---|---|
| `1` … `9`, `0` | elegir la categoría con ese número |
| `S` | sin categoría (solo el mes de la foto) |
| `N` | nueva categoría |
| `O` | buscar otra categoría |
| `D` | descartar la foto (no se copiará) |
| `Supr` | quitar la clasificación |
| `←` `→` | foto anterior / siguiente |
| `P` | siguiente foto pendiente |
| `Espacio` | pausar el vídeo · `M` activar el sonido |
| `A` | abrir la foto con el programa del sistema |
| `S` / `N` en el paso 1 | sí / no es un grupo de fotos |

### Formatos
Fotos JPG, PNG, HEIC (iPhone), WebP, TIFF, GIF, BMP y RAW de cámara (CR2, CR3, NEF, ARW, DNG, ORF, RW2, RAF…). Vídeos MP4, MOV, AVI, MKV, 3GP, MTS, WMV, WebM…

---

## Para desarrolladores

Aplicación de escritorio en Python 3.10+ con PySide6 (Qt). Componentes: PySide6 (interfaz y reproductor de vídeo), Pillow + pillow-heif (fotos y HEIC), rawpy (RAW), ExifRead y hachoir (fechas). No hace falta VLC ni FFmpeg aparte.

### Ejecutar desde el código

**Linux**
```bash
git clone https://github.com/israelgarcia86/fotos-hada-del-bosque.git
cd fotos-hada-del-bosque
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run.py
```

**Windows con Python**
1. Instala Python 3.12 desde <https://www.python.org/downloads/> y marca **«Add python.exe to PATH»**.
2. Haz doble clic en **`Hada_del_bosque_Windows.bat`**. La primera vez instala lo necesario en una carpeta `.venv` (tarda unos minutos); las siguientes veces arranca directamente.

La opción `python run.py --selftest` comprueba que todos los componentes funcionan: HEIC, RAW, decodificación de vídeo e icono.

### Publicar una versión nueva (crea el .exe de Windows)

El flujo `.github/workflows/windows.yml` crea el ejecutable con PyInstaller en una máquina Windows de GitHub, gratis en repositorios públicos. Antes de publicarlo, ejecuta la comprobación `--selftest`.

1. Sube los cambios a la rama `main`.
2. Crea una **Release** con una etiqueta nueva (por ejemplo `1.2.0`): **Releases → Draft a new release → Choose a tag**.
3. Unos 5 minutos después, el fichero `FotosDelHadaDelBosque-Windows.zip` aparece en la Release. El enlace de descarga de este README apunta siempre a la última versión.

También se puede lanzar a mano desde **Actions → «Crear programa para Windows» → Run workflow**. En ese caso el zip queda en *Artifacts* (hay que iniciar sesión para descargarlo y caduca a los 90 días). Si se elige una etiqueta en «Use workflow from», el zip se añade a esa Release.

### Estructura del código

| Fichero | Contenido |
|---|---|
| `run.py` | punto de entrada |
| `hada_del_bosque/app.py` | arranque, bienvenida, `--selftest` |
| `hada_del_bosque/main_window.py` | ventana: paso 1 (carpetas) y paso 2 (fotos) |
| `hada_del_bosque/dialogs.py` | escaneo, otra categoría, gestor de categorías, copia |
| `hada_del_bosque/widgets.py` | visor de imagen y de vídeo, miniaturas, vista previa |
| `hada_del_bosque/store.py` | estado en `hada_del_bosque.json` (rutas relativas, guardado atómico) |
| `hada_del_bosque/dates.py` | fecha estimada (EXIF, vídeo, nombre del fichero) |
| `hada_del_bosque/folders.py` | interpretar nombres de carpeta (año, mes, nombre) |
| `hada_del_bosque/copier.py` | copia a `DESTINO/AAAA/<mes>/<categoría>/` |
| `hada_del_bosque/media.py` | carga de imágenes (HEIC, RAW) y metadatos |
| `hada_del_bosque/resources/` | icono del hada (SVG, PNG, ICO) |
