# Manual de Uso: Sincronizador MediaWiki <-> Markdown (v3.1)

Herramienta nativa en Python para la sincronización bidireccional entre servidores **MediaWiki** y archivos locales en formato **Markdown (.md)** con soporte multihilo, descarga incremental inteligente, imágenes, control de conflictos y autenticación **HTTP Basic Auth** (sin dependencias externas).

---

## Indice
1. [Características Principales (v3.1)](#características-principales-v31)
2. [Estructura del Proyecto y Módulos](#estructura-del-proyecto-y-módulos)
3. [Formas de Ejecución (Comando CLI o Script)](#formas-de-ejecución-comando-cli-o-script)
4. [Configuración Segura (.env)](#configuración-segura-env)
5. [Modo 1: Descarga Incremental Concurrente](#modo-1-descarga-incremental-concurrente)
6. [Modo 2: Subida y Control de Conflictos (--upload)](#modo-2-subida-y-control-de-conflictos---upload)
7. [Modo 3: Saneamiento Offline de Archivos (--sanitize)](#modo-3-saneamiento-offline-de-archivos---sanitize)
8. [Modo 4: Control y Gestión de Páginas Vacías (--empty-pages)](#modo-4-control-y-gestión-de-páginas-vacías---empty-pages)
9. [Referencia de Parámetros CLI](#referencia-de-parámetros-cli)
10. [Batería de Pruebas](#batería-de-pruebas)

---

## Características Principales (v3.1)

* **Descarga Incremental Inteligente por `revid`:** Compara las revisiones del servidor en lotes de 50. Solo descarga los artículos que hayan cambiado realmente, reduciendo el tiempo de sincronización de minutos a pocos segundos.
* **Descarga Concurrente Multihilo (`ThreadPoolExecutor`):** Paraleliza la descarga de páginas e imágenes con `--threads` (por defecto 8 hilos), multiplicando por 10 la velocidad.
* **Control Inteligente de Páginas Vacías:** Detección de páginas sin contenido en la wiki sin generar falsos errores de descarga. Permite elegir interactivamente o por CLI si crear plantillas `.md` vacías locales para rellenar, eliminarlas del servidor remoto (`action=delete`), u omitirlas silenciando reintentos inútiles.
* **Conversión Robusta sin Artefactos:**
  * Elimina por completo sumarios (TOC), enlaces `[editar]` y asteriscos huérfanos.
  * Mapea enlaces internos de MediaWiki a archivos locales relativos `./Articulo.md` para lectura offline fluida (Obsidian, VS Code, Typora).
  * Convierte listas anidadas preservando niveles de indentación (`*`, `**`, `***`, `#`, `##`).
* **Prevención de Conflictos de Edición (`baserevid`):** Durante la subida, comprueba si alguien modificó la página en el servidor para evitar sobreescrituras accidentales. Si hay conflicto, descarga automáticamente una copia de seguridad `<archivo>.servidor.conflict`.
* **Cero Dependencias Externas:** Funciona exclusivamente con las librerías nativas de Python (`urllib`, `re`, `concurrent.futures`, `json`, `argparse`). No requiere instalar librerías pesadas ni frameworks de terceros.
* **Empaquetado Moderno con Poetry:** Distribuible como paquete estándar `.whl`, configurable en `pyproject.toml` y con comandos ejecutables en consola (`mw-sync` y `mediawiki-sync`).
* **Seguridad Reforzada:** Credenciales cargadas automáticamente desde `.env` (ignorado por Git) con solicitud interactiva por consola (`getpass`) si no están configuradas.

---

## Estructura del Proyecto y Módulos

```text
mediawiki-sync/
├── pyproject.toml              # Configuración de paquete Poetry (PEP 621)
├── LICENSE                     # Licencia GNU GPL v3
├── MANUAL_USO_MEDIAWIKI_SYNC.md# Este manual de usuario
├── README.md                   # Documentación técnica general
├── .env.example                # Plantilla de variables de entorno
├── .env                        # Credenciales locales (IGNORADO POR GIT)
├── .gitignore                  # Protección de credenciales, dist/ y temporales
├── .github/
│   └── workflows/
│       └── e2e-mediawiki.yml   # CI/CD: Batería de pruebas unitarias y E2E
├── mw_sync/                    # Paquete modular nativo
│   ├── __init__.py             # Exportación pública y versión
│   ├── __main__.py             # Punto de entrada modular (python3 -m mw_sync)
│   ├── config.py               # Cargador de .env y opciones por defecto
│   ├── client.py               # Cliente MediaWiki Action API (reintentos, tokens, borrado)
│   ├── state.py                # Gestión de .sync_state.json y hashes SHA-256
│   ├── empty_pages.py          # Módulo de control y gestión de páginas vacías
│   ├── downloader.py           # Motor de descarga incremental multihilo
│   ├── uploader.py             # Motor de subida y detección de conflictos
│   ├── cli.py                  # Interfaz unificada de comandos
│   └── converters/
│       ├── html_to_md.py       # Conversor HTML -> Markdown limpio
│       ├── md_to_wikitext.py   # Conversor Markdown -> Wikitext estándar
│       └── sanitizer.py        # Limpiador y saneador masivo de archivos locales
├── tests/
│   ├── test_converters.py      # Pruebas unitarias de conversión
│   ├── test_uploader.py        # Pruebas unitarias de subida y conflictos
│   ├── test_empty_pages.py     # Pruebas de control de páginas vacías y borrado
│   └── test_live_wiki.py       # Pruebas E2E en vivo con servidor MediaWiki Docker
└── wiki_docs/                  # Directorio local de documentación (ignorado en Git)
    ├── .sync_state.json        # Registro de hashes y revision IDs
    ├── 00_INDICE_MEDIAWIKI.md  # Índice general navegable
    ├── *.md                    # Artículos individuales en Markdown
    └── images/                 # Imágenes y archivos multimedia
```


## Formas de Ejecución (Comando CLI o Módulo)

El sincronizador se ejecuta mediante cualquiera de las siguientes modalidades:

1. **Comando corto de terminal (Recomendado para uso diario):**
   ```bash
   mw-sync --help
   ```
2. **Comando largo de terminal (Recomendado para scripts / automatizaciones):**
   ```bash
   mediawiki-sync --help
   ```
3. **Ejecución directa como módulo de Python:**
   ```bash
   python3 -m mw_sync --help
   ```

---

## Configuración Segura (.env y Variables de Entorno)

`mw_sync` admite la configuración de parámetros y credenciales mediante el archivo local `.env` o directamente mediante **variables de entorno del sistema operativo**, lo que facilita su integración tanto en puestos de desarrollo local como en servidores de producción o automatizaciones en contenedores Docker y pipelines CI/CD.

### Jerarquía y Precedencia de Configuración

El orden de prioridad para resolver cualquier parámetro (de mayor a menor relevancia) es:

1. **Parámetros pasados por CLI:** Argumentos como `--url`, `--threads 16` u `--wiki-user` sobrescriben cualquier otra fuente.
2. **Variables de Entorno de Sistema / Producción:** Variables definidas en el entorno (`export MW_URL=...`, Docker `ENV`, GitHub Secrets, Kubernetes).
3. **Archivo `.env` Local:** Valores cargados desde `.env` en el directorio de trabajo (sin sobrescribir variables ya presentes en el sistema).
4. **Valores Predeterminados:** Valores por defecto integrados en el módulo de configuración.

### Uso Local vs Producción

* **Uso Local (Desarrollo / Equipo Personal):** Copia `.env.example` como `.env` en la raíz del proyecto y completa tus credenciales. El archivo `.env` está en `.gitignore` para no ser subido jamás a Git.
* **Uso en Producción (Docker, CI/CD, Cron, Systemd):** No es necesario crear el archivo `.env`. Puedes pasar las variables directamente al entorno del contenedor o proceso:
  ```bash
  export MW_URL="https://wiki.empresa.com/api.php"
  export MW_WIKI_USER="bot_sincronizador"
  export MW_WIKI_PASS="SecretPassword123"
  mw-sync --upload
  ```
* **Ubicación y Ejecución con `MW_OUTPUT_DIR` / `--dir`:**
  - **No necesitas situarte ni hacer `cd` a la carpeta de salida:** El sincronizador detecta automáticamente el directorio desde la variable `MW_OUTPUT_DIR` o el parámetro CLI `--dir` (`-o`).
  - Si especificas una **ruta absoluta** (ej. `MW_OUTPUT_DIR=/home/usuario/documentos_wiki`), el comando funcionará de forma idéntica desde cualquier carpeta o ubicación de la terminal donde ejecutes `mw-sync`.
  - Si usas una **ruta relativa** (ej. `MW_OUTPUT_DIR=./wiki_docs`), esta se calculará con respecto al directorio desde el que lances la terminal.
  - El registro de estado local `.sync_state.json` siempre se guarda automáticamente dentro del directorio configurado (`<OUTPUT_DIR>/.sync_state.json`).

---

### Gestión de Múltiples Servidores MediaWiki (Patrón Multi-Wiki)

Para administrar varias wikis independientes (ej. Wiki Interna, Wiki Pública o Wiki de Clientes), el patrón más limpio y recomendado es crear una carpeta por proyecto con su propio archivo `.env`:

```text
mis_wikis/
├── wiki_interna/
│   ├── .env               # MW_URL=https://interna.empresa.com/api.php
│   └── wiki_docs/         # Markdown e historial .sync_state.json
├── wiki_publica/
│   ├── .env               # MW_URL=https://publica.empresa.com/api.php
│   └── wiki_docs/
└── wiki_clientes/
    ├── .env               # MW_URL=https://clientes.empresa.com/api.php
    └── wiki_docs/
```

Simplemente muévete a la carpeta correspondiente para trabajar con esa wiki en particular:

```bash
# Opción 1: Posicionarse en la carpeta del proyecto
cd mis_wikis/wiki_interna
mw-sync --upload

# Opción 2: Ejecutar desde cualquier directorio con --dir (Autodescubrimiento de .env)
mw-sync --upload --dir /home/usuario/mis_wikis/wiki_clientes
```

> [!IMPORTANT]
> **Puntos clave para trabajar con Múltiples Wikis:**
> 1. **Autodescubrimiento con `--dir`:** Si no deseas hacer `cd` continuamente, puedes pasar el parámetro `--dir /ruta/al/proyecto`. La herramienta buscará y cargará automáticamente el archivo `.env` perteneciente a ese directorio.
> 2. **Evitar variables globales del sistema operativo:** Las variables definidas directamente en la consola (`export MW_URL=...` o en tu `~/.bashrc`) tienen **mayor prioridad** que los archivos `.env` locales. Si defines una variable de entorno de sistema global, esta pisará el valor de los archivos `.env` locales de todas tus wikis. Mantén el entorno global del sistema libre de variables `MW_*` para que cada proyecto responda independientemente a su archivo `.env`.

---

### Catálogo Completo de Variables de Entorno (`MW_*`)

| Variable de Entorno | Descripción | Valor por Defecto |
| :--- | :--- | :--- |
| `MW_URL` | Endpoint Action API (`api.php`) de la MediaWiki | `https://wiki.example.com/api.php` |
| `MW_HTTP_USER` | Usuario de autenticación HTTP Basic Auth (Proxy / Apache) | `""` (vacío) |
| `MW_HTTP_PASS` | Contraseña de autenticación HTTP Basic Auth (Proxy / Apache) | `""` (vacío) |
| `MW_WIKI_USER` | Usuario de la MediaWiki (Action API) | `""` (vacío) |
| `MW_WIKI_PASS` | Contraseña de la MediaWiki (Action API) | `""` (vacío) |
| `MW_USER` | *(Compatibilidad)* Usuario de respaldo si no se indica `MW_HTTP_USER`/`MW_WIKI_USER` | `""` (vacío) |
| `MW_PASS` | *(Compatibilidad)* Contraseña de respaldo si no se indica `MW_HTTP_PASS`/`MW_WIKI_PASS` | `""` (vacío) |
| `MW_VERIFY_SSL` | Verificación estricta de SSL (`true`/`false`/`1`/`0`/`yes`/`no`) | `false` |
| `MW_CA_BUNDLE` | Ruta a certificados CA personalizados (`.crt`/`.pem`) para SSL privado/corporativo | `None` |
| `MW_TIMEOUT` | Tiempo límite de espera en segundos por petición HTTP/HTTPS | `10.0` |
| `MW_USER_AGENT` | Cabecera `User-Agent` de red enviada a la API | `MediaWikiSync/3.0 (Python; BiDirectional)` |
| `MW_OUTPUT_DIR` | Directorio local donde se guardan los archivos Markdown e imágenes | `./wiki_docs` |
| `MW_THREADS` | Hilos de ejecución concurrentes para descarga paralela | `8` |
| `MW_EDIT_SUMMARY` | Resumen predeterminado al publicar revisiones en la wiki | `Actualizado desde local Markdown vía mediawiki_sync` |
| `MW_TEST_LIVE` | *(Pruebas)* Habilita ejecución de tests E2E contra MediaWiki real (`1`/`0`) | `0` |
| `MW_TEST_LIVE_URL` | *(Pruebas)* Endpoint de MediaWiki para tests E2E | `http://localhost:8080/api.php` |
| `MW_TEST_WIKI_USER` | *(Pruebas)* Usuario admin para tests E2E | `TestAdmin` |
| `MW_TEST_WIKI_PASS` | *(Pruebas)* Contraseña para tests E2E | `TestPass123` |

```ini
# Ejemplo de archivo .env completo
MW_URL=https://wiki.example.com/api.php
MW_HTTP_USER=usuario_apache
MW_HTTP_PASS=contraseña_apache
MW_WIKI_USER=usuario_wiki
MW_WIKI_PASS=contraseña_wiki
MW_VERIFY_SSL=true
MW_CA_BUNDLE=/etc/ssl/certs/ca_corporativa.pem
MW_TIMEOUT=12.0
MW_USER_AGENT=MiDocumentacionBot/1.0
MW_OUTPUT_DIR=./documentacion_local
MW_THREADS=8
MW_EDIT_SUMMARY=Actualización automática vía CI/CD
```

> [!IMPORTANT]
> El archivo `.env` está en el `.gitignore`. Nunca subas contraseñas al repositorio Git.


---

## Modo 1: Descarga Incremental Concurrente

Sincroniza el contenido desde la MediaWiki hacia tu carpeta local. Solo descarga páginas nuevas o modificadas en el servidor.

```bash
# 1. Descarga incremental rápida (8 hilos en paralelo):
mw-sync

# 2. Especificar más hilos (ej. 12 hilos):
mw-sync --threads 12

# 3. Forzar re-descarga completa de todo el wiki:
mw-sync --force

# 4. Descargar solo texto sin imágenes:
mw-sync --no-images
```

---

## Modo 2: Subida y Control de Conflictos (--upload)

Detecta archivos `.md` o imágenes modificados localmente y los publica en la MediaWiki.

```bash
# 1. Simulación (DRY-RUN): Comprueba qué se subiría sin tocar el servidor:
mw-sync --upload --dry-run

# 2. Previsualizar diferencias de Wikitext antes de subir:
mw-sync --upload --diff --dry-run

# 3. Subir todos los cambios locales detectados:
mw-sync --upload

# 4. Subir únicamente un archivo específico:
mw-sync --upload --file ./wiki_docs/Manual_de_Usuario.md

# 5. Subir una imagen específica:
mw-sync --upload --file ./wiki_docs/images/diagrama.png
```

---

## Modo 3: Saneamiento Offline de Archivos (--sanitize)

Permite limpiar en bloque archivos Markdown locales (útil para reparar archivos antiguos con `[editar]`, enlaces residuales o `****` huérfanos):

```bash
# Sanear todos los archivos .md en ./wiki_docs:
mw-sync --sanitize

# Simular saneamiento sin modificar archivos:
mw-sync --sanitize --dry-run
```

---

## Modo 4: Control y Gestión de Páginas Vacías (--empty-pages)

Cuando una página remota en MediaWiki no tiene contenido o texto renderizable, el sistema no la trata como un error de descarga sino que la registra en el estado local (`.sync_state.json`). Al finalizar la descarga o al invocar `--empty-pages`, se ofrecen 3 opciones:

1. **Crear plantillas `.md` locales vacías:** Genera el archivo con frontmatter y título `# Título`, listo para rellenar offline y subir luego con `--upload`.
2. **Eliminar del servidor remoto (`action=delete`):** Borra las páginas de la MediaWiki (requiere permisos de borrado en la wiki).
3. **Omitir / Ignorar:** Registra la página como omitida para no volver a descargarla ni reportar fallos, hasta que alguien en la wiki le añada contenido nuevo (nuevo `revid`).

```bash
# 1. Consultar y gestionar interactivamente páginas vacías registradas:
mw-sync --empty-pages

# 2. Descargar forzando creación automática de .md vacíos para rellenar:
mw-sync --empty-action create-md

# 3. Descargar forzando eliminación de páginas vacías del servidor remoto:
mw-sync --empty-action delete-remote --yes

# 4. Descargar silenciando páginas vacías (modo no interactivo / scripts):
mw-sync --empty-action ignore
```

---

## Referencia de Parámetros CLI

| Parámetro | Abreviatura | Variable Mapeada (`MW_*`) | Descripción | Valor por defecto |
| :--- | :--- | :--- | :--- | :--- |
| `--download` | `-dl` | N/A | Modo descarga incremental (servidor -> local) | Activo por defecto |
| `--upload` | `-up` | N/A | Modo subida de cambios (local -> servidor) | Falso |
| `--sanitize` | | N/A | Limpia y sanea archivos Markdown locales | Falso |
| `--diff` | | N/A | Muestra previsualización unificada de Wikitext | Falso |
| `--dry-run` | | N/A | Simula operaciones sin alterar servidor ni disco | Falso |
| `--force` | `-f` | N/A | Fuerza descarga/subida omitiendo comprobación de hash/revid | Falso |
| `--yes` | `-y` | N/A | Responde afirmativamente de forma no interactiva (ej. forzar conflictos o borrado) | Falso |
| `--empty-pages` | | N/A | Lista y gestiona las páginas vacías registradas en el estado local | Falso |
| `--empty-action` | | N/A | Acción automática ante páginas vacías (`ask`, `create-md`, `delete-remote`, `ignore`) | `ask` |
| `--threads` | `-t` | `MW_THREADS` | Número de hilos concurrentes para descarga | `8` |
| `--dir` | `-o` | `MW_OUTPUT_DIR` | Directorio local de documentación | `./wiki_docs` |
| `--file` | | N/A | Archivo `.md` o imagen específico a subir | `None` |
| `--no-images` | | N/A | Omite la descarga o subida de archivos multimedia | Falso |
| `--summary` | | `MW_EDIT_SUMMARY` | Resumen de edición para el historial de MediaWiki | Configurado en entorno |
| `--url` | | `MW_URL` | URL del endpoint `api.php` | Configurado en entorno |
| `--http-user` | | `MW_HTTP_USER` (o `MW_USER`) | Usuario de autenticación Apache / HTTP Basic Auth | Configurado en entorno |
| `--http-password` | | `MW_HTTP_PASS` (o `MW_PASS`) | Contraseña de Apache / HTTP Basic Auth | Configurado en entorno |
| `--wiki-user` | | `MW_WIKI_USER` (o `MW_USER`) | Usuario de la MediaWiki (Action API) | Configurado en entorno |
| `--wiki-password` | | `MW_WIKI_PASS` (o `MW_PASS`) | Contraseña de la MediaWiki | Configurado en entorno |
| `--verify-ssl` | | `MW_VERIFY_SSL` | Activa verificación estricta de certificados SSL | Configurado en entorno |
| `--ca-bundle` | | `MW_CA_BUNDLE` | Ruta al certificado CA corporativo para validar SSL | `None` |

---

## Batería de Pruebas

Para validar los conversores, el sistema de empaquetado y la integridad general:

```bash
# Pruebas unitarias nativas (sin dependencias):
python3 -m unittest discover tests

# O mediante Poetry:
poetry run pytest tests
```

### Cobertura de la Suite:
- `tests/test_converters.py`: Conversiones bidireccionales HTML/Markdown/Wikitext, tablas, enlaces y anidación de listas.
- `tests/test_uploader.py`: Extracción de metadatos, detección de conflictos `baserevid` y respaldo automático.
- `tests/test_empty_pages.py`: Detección de páginas vacías, plantillas locales y acción de borrado remoto.
- `tests/test_live_wiki.py`: Pruebas de integración E2E en vivo contra contenedor Docker con MediaWiki real.

