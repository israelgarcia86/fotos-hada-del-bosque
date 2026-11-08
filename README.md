<p align="center"><img src="hada_del_bosque/resources/hada.png" width="180" alt="Hada del bosque con cámara"></p>

# Fotos del hada del bosque

Aplicación de escritorio (Windows y Linux) para **clasificar fotos y vídeos por año, mes y categoría** y copiarlos a una carpeta ya ordenada con la estructura:

```
DESTINO/
└── 2023/
    └── 05 - Mayo/
        └── Feria de Abril/
```

## Cómo funciona

1. **Al abrir**, eliges la carpeta con las fotos que quieres ordenar (se recorren todas sus subcarpetas). La primera vez el programa te pregunta, de forma opcional, cuál es tu **carpeta destino** ya ordenada, para importar sus categorías (`Año/Mes/Categoría`).
2. **Paso 1: revisión de carpetas** (solo la primera vez). Para cada carpeta que contiene fotos dices si es ya una **agrupación** (un evento o un viaje) o no (Descargas, WhatsApp Images…). Si es que sí, se crea una categoría con año, mes y nombre propuestos, que puedes cambiar. Haz clic en una miniatura para verla en grande o reproducir el vídeo.
3. **Paso 2: foto a foto**, en orden de fecha. A la izquierda se ve la foto, o el vídeo, que se reproduce solo. A la derecha aparecen:
   - el nombre, la carpeta, la **fecha estimada** y de dónde sale (EXIF, metadatos del vídeo, nombre del fichero o fecha del fichero), y los metadatos (cámara, dimensiones, exposición, GPS…);
   - las categorías del **mes de la foto y de los meses anterior y siguiente**. Si la foto venía de una carpeta agrupada, su categoría aparece **resaltada en amarillo**: basta con pulsarla;
   - las categorías **recientes**: las que ya has asignado a fotos con fecha cercana (±2 meses), aunque sean de otro mes. Así, una categoría que eliges con «Otra categoría» sigue apareciendo en las fotos de esas fechas;
   - **Sin categoría**: la foto va directamente a la carpeta de su mes (`2023/05 - Mayo/`), sin carpeta de evento;
   - **Otra categoría…** para buscar cualquier categoría, y **Nueva categoría** para crear una (año y mes sugeridos).

   Al pulsar una categoría, se pasa **directamente a la siguiente foto**. Con «Anterior» y «Siguiente» puedes volver para corregir; la categoría elegida aparece en verde.
4. **Destino → Copiar las fotos clasificadas al destino…** las **copia**, sin mover ni borrar nada del origen. Reutiliza las carpetas de año, mes y categoría que ya existan, y no duplica un fichero que ya esté. El formato de las carpetas de mes nuevas se deduce de las que ya tienes; si no tienes ninguna, se usa `05 - Mayo`.

### Progreso guardado
Tras **cada** foto se actualiza el fichero `hada_del_bosque.json` dentro de la carpeta de fotos. Ahí están las categorías (año, mes y nombre), la categoría de cada foto, las fechas leídas y las copias hechas. Las rutas son relativas, así que funciona igual en Linux y en Windows. Si cierras el programa y vuelves a abrir la carpeta, sigues donde lo dejaste. Además se guarda una copia de seguridad, `hada_del_bosque.json.bak`.

Para **empezar de cero** (por ejemplo, después de hacer pruebas), marca *«Empezar de cero»* en la pantalla de bienvenida o usa **Archivo → Reiniciar todo el trabajo de esta carpeta…**. No se borra ninguna foto, y el progreso anterior se guarda como `hada_del_bosque.reiniciado-FECHA.json`.

### Atajos de teclado
| Tecla | Acción |
|---|---|
| `1`…`9`, `0` | asignar la categoría con ese número |
| `S` | sin categoría (solo el mes de la foto) |
| `N` | nueva categoría · `O` otra categoría |
| `D` | descartar (no se copiará) · `Supr` quitar clasificación |
| `←` `→` | anterior / siguiente · `P` siguiente pendiente |
| `Espacio` | pausa del vídeo · `M` sonido (empieza silenciado) |
| `A` | abrir con el programa del sistema |
| En el paso 1: `S` / `N` | sí / no es una agrupación |

Formatos admitidos: JPG, PNG, HEIC/HEIF (iPhone), WebP, TIFF, GIF, BMP, RAW (CR2, CR3, NEF, ARW, DNG, ORF, RW2, RAF…) y vídeos MP4, MOV, AVI, MKV, 3GP, MTS, WMV, WebM…

---

## Instalación

### Linux (para probar)
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run.py
```

### Windows, opción A: programa ya hecho (no hace falta instalar nada)
GitHub crea el `.exe` gratis (los repositorios públicos tienen GitHub Actions gratuito):

1. Sube esta carpeta a un repositorio de GitHub, incluida la carpeta oculta `.github`.
2. En el repositorio, entra en **Actions → «Crear programa para Windows» → Run workflow**.
3. Cuando termine (unos 5 minutos), abre la ejecución y descarga **FotosDelHadaDelBosque-Windows** en *Artifacts*.
   - Otra forma: publica una **Release** con una etiqueta nueva (por ejemplo `1.1.0`) y el `.zip` aparecerá en ella, descargable sin iniciar sesión.
4. Descomprime el `.zip` donde quieras y ejecuta `FotosDelHadaDelBosque.exe`.

> La primera vez, Windows SmartScreen puede avisar de que el programa no está firmado: pulsa **Más información → Ejecutar de todas formas**.

### Windows, opción B: con Python
1. Instala Python 3.12 desde <https://www.python.org/downloads/> y marca **«Add python.exe to PATH»**.
2. Haz doble clic en **`Hada_del_bosque_Windows.bat`**. La primera vez instala lo necesario en una carpeta `.venv` (tarda unos minutos); las siguientes arranca directamente.

Componentes que usa: PySide6 (interfaz y reproductor de vídeo), Pillow + pillow-heif (fotos y HEIC), rawpy (RAW), ExifRead y hachoir (fechas). Todos se instalan con `pip`; no hace falta VLC ni FFmpeg aparte.
