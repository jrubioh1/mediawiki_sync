# MediaWiki Sync (mw_sync)

Suite nativa en Python para la sincronización bidireccional de alto rendimiento entre servidores **MediaWiki** y repositorios de documentación local en formato **Markdown (.md)**.

Diseñada con una arquitectura de **cero dependencias externas** (utiliza exclusivamente la biblioteca estándar de Python 3.13+) y optimizada para entornos corporativos con doble capa de autenticación, inspección SSL personalizada y concurrencia multihilo.

---

## Contenido

1. [Caracteristicas Principales](#caracteristicas-principales)
2. [Arquitectura y Componentes](#arquitectura-y-componentes)
3. [Requisitos e Instalacion](#requisitos-e-instalacion)
4. [Configuracion de Entorno (.env)](#configuracion-de-entorno-env)
5. [Guia de Uso CLI](#guia-de-uso-cli)
   - [Descarga Incremental Concurrente](#descarga-incremental-concurrente)
   - [Subida de Cambios y Control de Conflictos](#subida-de-cambios-y-control-de-conflictos)
   - [Previsualizacion de Diferencias (Diff)](#previsualizacion-de-diferencias-diff)
   - [Saneamiento y Normalizacion Offline](#saneamiento-y-normalizacion-offline)
6. [Uso como Biblioteca Python](#uso-como-biblioteca-python)
7. [Referencia Completa de Parametros CLI](#referencia-completa-de-parametros-cli)
8. [Seguridad y Buenas Practicas](#seguridad-y-buenas-practicas)
9. [Bateria de Pruebas](#bateria-de-pruebas)

---

## Caracteristicas Principales

- **Cero Dependencias Externas:** Funciona al 100% con los modulos estandar de Python (`urllib`, `re`, `concurrent.futures`, `json`, `hashlib`, `argparse`, `ssl`). No requiere `pip install`, facilitando su despliegue en entornos aislados o de alta seguridad.
- **Doble Capa de Autenticacion:** Soporte nativo y simultaneo para:
  - Capa perimetral web (HTTP Basic Auth en servidores Apache/Nginx o Proxies inversos).
  - Capa de aplicacion MediaWiki (Action API con tokens `login` y `csrf` mediante cookie jar en memoria).
- **Descarga Incremental Inteligente por Revision (`revid`):** Consulta por lotes de 50 articulos la revision remota actual contra el archivo local `.sync_state.json`. Solo transfiere el contenido de articulos nuevos o modificados en el servidor, reduciendo una sincronizacion de cientos de articulos a pocos segundos.
- **Concurrencia Multihilo:** Descarga paralela configurable de paginas y archivos multimedia mediante `ThreadPoolExecutor`.
- **Prevencion Estricta de Conflictos (`baserevid`):** Al publicar en la wiki, valida que la version local parta de la ultima revision existente en el servidor. Si se detecta una modificacion concurrente ajena:
  - Descarga inmediatamente el contenido actual del servidor a un archivo de respaldo con sufijo `.servidor.conflict`.
  - Aborta la publicacion por defecto para evitar sobreescrituras accidentales.
  - Permite forzar la publicacion con confirmacion manual por consola o de forma no interactiva con `--yes`.
- **Motor de Conversion Bidireccional de Calidad:**
  - *HTML -> Markdown:* Limpia tablas de contenidos residuales (`__TOC__`), enlaces `[editar]`, formatea tablas con sintaxis de tuberia (`|`), ajusta listas anidadas con sangria exacta y reescribe hipervinculos internos para navegacion local relativa (`./Articulo.md`).
  - *Markdown -> Wikitext:* Transforma encabezados (`#` a `=`), negritas (`**` a `'''`), cursivas (`*` a `''`), listas (`-`/`*` a `*`, `1.` a `#`), bloques de codigo y sintaxis de imagenes sin contaminar la semantica wiki.
- **Modo Diff Contextual Unificado:** Permite comparar antes de la subida el Wikitext generado frente al contenido remoto actual en formato `diff -u`.
- **Saneador Offline Masivo:** Repara colecciones de archivos Markdown eliminando artefactos sintacticos, entidades HTML rotas y sangrias defectuosas.

---

## Arquitectura y Componentes

El proyecto se estructura en un paquete desacoplado `mw_sync` junto con su ejecutable `mediawiki_sync.py`:

```text
mediawiki-sync/
├── mediawiki_sync.py           # Script principal ejecutable (punto de entrada CLI)
├── MANUAL_USO_MEDIAWIKI_SYNC.md# Manual detallado en espanol
├── README.md                   # Documentacion tecnica del repositorio
├── .env.example                # Plantilla de configuracion de entorno
├── .env                        # Variables y credenciales (excluido de git)
├── .gitignore                  # Exclusion de credenciales y cache local
├── mw_sync/                    # Paquete de la aplicacion
│   ├── __init__.py             # Exportaciones de la API publica y version
│   ├── cli.py                  # Parseo de argumentos y logica de terminal
│   ├── client.py               # Cliente HTTP/HTTPS para MediaWiki Action API
│   ├── config.py               # Gestion de configuracion y resolucion de credenciales
│   ├── downloader.py           # Motor de descarga incremental y multihilo
│   ├── state.py                # Persistencia de estado local (.sync_state.json)
│   ├── uploader.py             # Motor de subida, diff y control de conflictos
│   └── converters/
│       ├── html_to_md.py       # Conversor HTML a Markdown con sanitizado
│       ├── md_to_wikitext.py   # Conversor Markdown a Wikitext estandar
│       └── sanitizer.py        # Limpieza masiva de colecciones Markdown locales
└── tests/
    ├── test_converters.py      # Bateria de pruebas unitarias para conversores
    └── test_uploader.py        # Pruebas de resolucion de titulos y conflictos
```

---

## Requisitos e Instalacion

### Requisitos

- Python 3.13 o superior.
- Sin dependencias de terceros. No se requiere `pip` ni entornos virtuales `venv` para la ejecucion basica.

### Instalacion

1. Clonar el repositorio:
   ```bash
   git clone <URL_DEL_REPOSITORIO>
   cd mediawiki2.0
   ```

2. Preparar el archivo de configuracion:
   ```bash
   cp .env.example .env
   chmod 600 .env
   ```

---

## Configuracion de Entorno (.env)

Edite el archivo `.env` con los datos de su entorno. Este archivo nunca debe versionarse en Git.

```ini
# URL del endpoint Action API de MediaWiki
MW_URL=https://wiki.example.com/api.php

# Capa 1: Autenticacion HTTP Basic (Apache / Nginx / Proxy)
# Dejar en blanco si el servidor no requiere autenticacion HTTP perimetral
MW_HTTP_USER=usuario_proxy
MW_HTTP_PASS=password_proxy

# Capa 2: Cuenta de MediaWiki
MW_WIKI_USER=usuario_wiki
MW_WIKI_PASS=password_wiki

# Opciones de Red y Seguridad SSL
MW_VERIFY_SSL=true
# Ruta opcional a certificados de autoridad corporativa (.crt o .pem)
MW_CA_BUNDLE=

# Rendimiento y Rutas
MW_OUTPUT_DIR=./wiki_docs
MW_THREADS=8
MW_EDIT_SUMMARY=Actualizado desde local Markdown via mw_sync
```

---

## Guia de Uso CLI

El comando unificado `mediawiki_sync.py` permite alternar entre modos de operacion.

### Descarga Incremental Concurrente

Por defecto, ejecutar el script sin argumentos inicia la descarga incremental hacia la carpeta configurada (por defecto `./wiki_docs`):

```bash
# Descarga incremental estandar (8 hilos en paralelo):
python3 mediawiki_sync.py

# Ajustar el numero de hilos de concurrencia:
python3 mediawiki_sync.py --threads 16

# Forzar la re-descarga de todos los articulos ignorando el estado local:
python3 mediawiki_sync.py --force

# Descargar solo el texto de los articulos, omitiendo imagenes multimedia:
python3 mediawiki_sync.py --no-images
```

### Subida de Cambios y Control de Conflictos

El modo `--upload` escanea la carpeta local de documentacion, calcula hashes SHA-256 frente a `.sync_state.json` y detecta que articulos o imagenes fueron modificados o creados.

```bash
# Simular subida (Dry-Run) para ver que cambios se aplicarian sin alterar el servidor:
python3 mediawiki_sync.py --upload --dry-run

# Subir todos los archivos locales modificados:
python3 mediawiki_sync.py --upload

# Subir unicamente un archivo especifico:
python3 mediawiki_sync.py --upload --file ./wiki_docs/Manual_de_Usuario.md

# Subir una imagen al repositorio multimedia de la wiki:
python3 mediawiki_sync.py --upload --file ./wiki_docs/images/esquema_red.png

# Omitir confirmaciones interactivas al resolver un conflicto (sobrescritura forzada):
python3 mediawiki_sync.py --upload --force --yes
```

#### Protocolo de Resolucion de Conflictos

Si durante la subida el servidor responde con un conflicto de edicion (o si la revision remota no coincide con la esperada):
1. El motor no sobrescribe el servidor.
2. Descarga la version remota actual a `<archivo>.servidor.conflict`.
3. Notifica al operador con el comando exacto para inspeccionar las diferencias:
   ```bash
   diff -u "wiki_docs/Articulo.md" "wiki_docs/Articulo.md.servidor.conflict"
   ```
4. Pregunta en consola si desea cancelar o forzar la subida de la version local.

### Previsualizacion de Diferencias (Diff)

Permite examinar la salida Wikitext generada a partir de los archivos Markdown locales frente a lo que reside en MediaWiki:

```bash
python3 mediawiki_sync.py --upload --diff --dry-run
```

### Saneamiento y Normalizacion Offline

Permite procesar archivos Markdown en local para eliminar restos de ediciones previas, limpiar artefactos de etiquetas y corregir espaciados:

```bash
# Ejecutar saneamiento real sobre el directorio local:
python3 mediawiki_sync.py --sanitize

# Comprobar que archivos serian alterados sin modificarlos en disco:
python3 mediawiki_sync.py --sanitize --dry-run
```

---

## Uso como Biblioteca Python

`mw_sync` puede ser importado directamente en otros programas de Python:

```python
from mw_sync import MediaWikiClient, ejecutar_descarga, markdown_a_wikitext

# 1. Crear el cliente
cliente = MediaWikiClient(
    url="https://wiki.example.com/api.php",
    http_user="usuario_proxy",
    http_password="password_proxy",
    wiki_user="usuario_wiki",
    wiki_password="password_wiki",
    verify_ssl=True
)

# 2. Comprobar conexion y loguear
conectado, sitio = cliente.test_conexion()
if conectado:
    print(f"Conectado a {sitio}")
    ok_login, msg = cliente.login()
    print(msg)

# 3. Descargar articulos
ejecutar_descarga(cliente, output_dir="./wiki_docs", max_hilos=4)

# 4. Conversion manual de Markdown a Wikitext
md_texto = "# Seccion Principal\n\nEste es un parrafo con **negrita**."
wikitext = markdown_a_wikitext(md_texto)
print(wikitext)
# Salida:
# = Seccion Principal =
#
# Este es un parrafo con '''negrita'''.
```

---

## Referencia Completa de Parametros CLI

| Argumento | Abreviatura | Descripcion | Valor por Defecto |
| :--- | :--- | :--- | :--- |
| `--download` | `-dl` | Modo descarga incremental de MediaWiki a local | Activo si no se indica otro modo |
| `--upload` | `-up` | Modo subida de cambios locales a MediaWiki | Desactivado |
| `--sanitize` | | Ejecuta el saneador de sintaxis Markdown offline | Desactivado |
| `--diff` | | Muestra diferencias en formato unificado antes de publicar | Desactivado |
| `--dry-run` | | Simula operaciones sin tocar disco ni hacer cambios remotos | Desactivado |
| `--force` | `-f` | Fuerza la descarga o publicacion omitiendo verificacion de hashes | Desactivado |
| `--yes` | `-y` | Responde afirmativamente de forma no interactiva a preguntas | Desactivado |
| `--empty-pages` | | Lista y gestiona las paginas vacias registradas en el estado local | Desactivado |
| `--empty-action` | | Accion ante paginas vacias (`ask`, `create-md`, `delete-remote`, `ignore`) | `ask` |
| `--threads` | `-t` | Numero de hilos para descarga paralela | `8` |
| `--dir` | `-o` | Directorio local de documentacion | `./wiki_docs` |
| `--file` | | Ruta de un archivo individual (`.md` o imagen) para subir | `None` |
| `--no-images` | | Omite la gestion de archivos multimedia | Desactivado |
| `--summary` | | Texto para el resumen de edicion en el historial de revisiones | Configurado en `.env` |
| `--url` | | URL del endpoint `api.php` | Configurado en `.env` |
| `--http-user` | | Usuario para HTTP Basic Auth | Configurado en `.env` |
| `--http-password`| | Contrasena para HTTP Basic Auth | Configurado en `.env` |
| `--wiki-user` | | Usuario de MediaWiki (Action API) | Configurado en `.env` |
| `--wiki-password`| | Contrasena de MediaWiki | Configurado en `.env` |
| `--verify-ssl` | | Activa la validacion estricta de certificados TLS/SSL | Configurado en `.env` |
| `--ca-bundle` | | Ruta a archivo CA Bundle para certificados autofirmados/privados | `None` |

---

## Seguridad y Buenas Practicas

1. **Aislamiento de Secretos:**
   El archivo `.gitignore` excluye explicitamente:
   - `.env` (credenciales de conexion y contrasenas).
   - `wiki_docs/` (archivos descargados, imagenes y cache de hashes).
   - Archivos de resolucion de conflictos (`*.servidor.conflict`).
   - Archivos de entorno virtual y temporales (`*.pyc`, `__pycache__`).

2. **Verificacion de Certificados TLS/SSL:**
   En entornos con inspeccion de tráfico HTTPS o certificados autofirmados, evite desactivar la verificacion SSL (`MW_VERIFY_SSL=false`). En su lugar, apunte `--ca-bundle /ruta/al/certificado.pem` para garantizar una conexion segura autenticada.

3. **Prevencion de Inyeccion y Sobrescritura:**
   El uploader valida sistematicamente los tokens CSRF y comprueba la marca temporal de revision (`baserevid`) para certificar que ninguna modificacion remota se pierda inadvertidamente.

---

## Bateria de Pruebas

El repositorio incluye un conjunto de pruebas unitarias automatizadas que validan la suite sin necesidad de conexion a internet ni a un servidor MediaWiki activo:

```bash
python3 -m unittest discover tests
```

### Cobertura de Pruebas

- `tests/test_converters.py`: Valida la conversion bidireccional HTML -> Markdown y Markdown -> Wikitext, verificando listas ordenadas y no ordenadas, tablas complejas, enlaces relativos locales, bloques de codigo y remocion de artefactos (`__TOC__`, `[editar]`).
- `tests/test_uploader.py`: Valida la extraccion de titulos de articulos desde metadatos frontmatter y encabezados `#`, asi como el manejo del flujo de deteccion y alerta ante conflictos de revision remota.
