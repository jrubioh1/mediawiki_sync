# Manual de Uso: Sincronizador MediaWiki <-> Markdown (v3.0)

Herramienta nativa en Python para la sincronización bidireccional entre servidores **MediaWiki** y archivos locales en formato **Markdown (.md)** con soporte multihilo, descarga incremental inteligente, imágenes, control de conflictos y autenticación **HTTP Basic Auth** (sin dependencias externas).

---

## Indice
1. [Características Principales (v3.0)](#características-principales-v30)
2. [Estructura del Proyecto y Módulos](#estructura-del-proyecto-y-módulos)
3. [Configuración Segura (.env)](#configuración-segura-env)
4. [Modo 1: Descarga Incremental Concurrente](#modo-1-descarga-incremental-concurrente)
5. [Modo 2: Subida y Control de Conflictos (--upload)](#modo-2-subida-y-control-de-conflictos---upload)
6. [Modo 3: Saneamiento Offline de Archivos (--sanitize)](#modo-3-saneamiento-offline-de-archivos---sanitize)
7. [Referencia de Parámetros CLI](#referencia-de-parámetros-cli)
8. [Pruebas Unitarias](#pruebas-unitarias)

---

## Características Principales (v3.0)

* **Descarga Incremental Inteligente por `revid`:** Compara las revisiones del servidor en lotes de 50. Solo descarga los artículos que hayan cambiado realmente, reduciendo el tiempo de sincronización de minutos a pocos segundos.
* **Descarga Concurrente Multihilo (`ThreadPoolExecutor`):** Paraleliza la descarga de páginas e imágenes con `--threads` (por defecto 8 hilos), multiplicando por 10 la velocidad.
* **Conversión Robusta sin Artefactos:**
  * Elimina por completo sumarios (TOC), enlaces `[editar]` y asteriscos huérfanos.
  * Mapea enlaces internos de MediaWiki a archivos locales relativos `./Articulo.md` para lectura offline fluida (Obsidian, VS Code, Typora).
  * Convierte listas anidadas preservando niveles de indentación (`*`, `**`, `***`, `#`, `##`).
* **Prevención de Conflictos de Edición (`baserevid`):** Durante la subida, comprueba si alguien modificó la página en el servidor para evitar sobreescrituras accidentales. Si hay conflicto, descarga automáticamente una copia de seguridad `<archivo>.servidor.conflict`.
* **Cero Dependencias Externas:** Funciona exclusivamente con las librerías nativas de Python (`urllib`, `re`, `concurrent.futures`, `json`, `argparse`). No requiere instalar librerías pesadas ni frameworks de terceros.
* **Seguridad Reforzada:** Credenciales cargadas automáticamente desde `.env` (ignorado por Git) con solicitud interactiva por consola (`getpass`) si no están configuradas.

---

## Estructura del Proyecto y Módulos

```text
/home/ay/Escritorio/mediawiki2.0/
├── mediawiki_sync.py           # Script principal ejecutable (wrapper CLI)
├── .env.example                # Plantilla de variables de entorno
├── .env                        # Credenciales locales (IGNORADO POR GIT)
├── .gitignore                  # Protección de credenciales y temporales
├── mw_sync/                    # Paquete modular nativo
│   ├── __init__.py             # Exportación pública y versión
│   ├── config.py               # Cargador de .env y opciones por defecto
│   ├── client.py               # Cliente MediaWiki Action API (reintentos, tokens)
│   ├── state.py                # Gestión de .sync_state.json y hashes SHA-256
│   ├── downloader.py           # Motor de descarga incremental multihilo
│   ├── uploader.py             # Motor de subida y detección de conflictos
│   ├── cli.py                  # Interfaz unificada de comandos
│   └── converters/
│       ├── html_to_md.py       # Conversor HTML -> Markdown limpio
│       ├── md_to_wikitext.py   # Conversor Markdown -> Wikitext estándar
│       └── sanitizer.py        # Limpiador y saneador masivo de archivos locales
├── tests/
│   ├── test_converters.py      # Pruebas unitarias de conversión
│   └── test_uploader.py        # Pruebas unitarias de subida y conflictos
└── wiki_docs/                  # Directorio de documentación sincronizada (ignorado en Git)
    ├── .sync_state.json        # Registro de hashes y revision IDs
    ├── 00_INDICE_MEDIAWIKI.md  # Índice general navegable
    ├── *.md                    # Artículos individuales en Markdown
    └── images/                 # Imágenes y archivos multimedia
```


---

## Configuración Segura (.env)

Copia el archivo `.env.example` a `.env` y ajusta tus valores:

```ini
MW_URL=https://wiki.example.com/api.php

# Capa 1: Apache / Proxy (HTTP Basic Auth)
MW_HTTP_USER=tu_usuario_apache
MW_HTTP_PASS=tu_contraseña_apache

# Capa 2: MediaWiki (Action API)
MW_WIKI_USER=tu_usuario_de_wiki
MW_WIKI_PASS=tu_contraseña_de_wiki

MW_VERIFY_SSL=false
MW_OUTPUT_DIR=./wiki_docs
MW_THREADS=8
MW_EDIT_SUMMARY=Actualizado desde local Markdown vía mediawiki_sync
```

> [!IMPORTANT]
> El archivo `.env` está en el `.gitignore`. Nunca subas contraseñas al repositorio Git.


---

## Modo 1: Descarga Incremental Concurrente

Sincroniza el contenido desde la MediaWiki hacia tu carpeta local. Solo descarga páginas nuevas o modificadas en el servidor.

```bash
# 1. Descarga incremental rápida (8 hilos en paralelo):
python3 mediawiki_sync.py

# 2. Especificar más hilos (ej. 12 hilos):
python3 mediawiki_sync.py --threads 12

# 3. Forzar re-descarga completa de todo el wiki:
python3 mediawiki_sync.py --force

# 4. Descargar solo texto sin imágenes:
python3 mediawiki_sync.py --no-images
```

---

## Modo 2: Subida y Control de Conflictos (--upload)

Detecta archivos `.md` o imágenes modificados localmente y los publica en la MediaWiki.

```bash
# 1. Simulación (DRY-RUN): Comprueba qué se subiría sin tocar el servidor:
python3 mediawiki_sync.py --upload --dry-run

# 2. Previsualizar diferencias de Wikitext antes de subir:
python3 mediawiki_sync.py --upload --diff --dry-run

# 3. Subir todos los cambios locales detectados:
python3 mediawiki_sync.py --upload

# 4. Subir únicamente un archivo específico:
python3 mediawiki_sync.py --upload --file ./wiki_docs/Manual_de_Usuario.md

# 5. Subir una imagen específica:
python3 mediawiki_sync.py --upload --file ./wiki_docs/images/diagrama.png
```

---

## Modo 3: Saneamiento Offline de Archivos (--sanitize)

Permite limpiar en bloque archivos Markdown locales (útil para reparar archivos antiguos con `[editar]`, enlaces residuales o `****` huérfanos):

```bash
# Sanear todos los archivos .md en ./wiki_docs:
python3 mediawiki_sync.py --sanitize

# Simular saneamiento sin modificar archivos:
python3 mediawiki_sync.py --sanitize --dry-run
```

---

## Referencia de Parámetros CLI (mediawiki_sync.py)


| Parámetro | Abreviatura | Descripción | Valor por defecto |
| :--- | :--- | :--- | :--- |
| `--download` | `-dl` | Modo descarga incremental (servidor -> local) | Activo por defecto |
| `--upload` | `-up` | Modo subida de cambios (local -> servidor) | Falso |
| `--sanitize` | | Limpia y sanea archivos Markdown locales | Falso |
| `--diff` | | Muestra previsualización unificada de Wikitext | Falso |
| `--dry-run` | | Simula operaciones sin alterar servidor ni disco | Falso |
| `--force` | `-f` | Fuerza descarga/subida omitiendo comprobación de hash/revid | Falso |
| `--yes` | `-y` | Responde afirmativamente de forma no interactiva (ej. forzar conflictos) | Falso |
| `--threads` | `-t` | Número de hilos concurrentes para descarga | `8` |
| `--dir` | `-o` | Directorio local de documentación | `./wiki_docs` |
| `--file` | | Archivo `.md` o imagen específico a subir | `None` |
| `--no-images` | | Omite la descarga o subida de archivos multimedia | Falso |
| `--summary` | | Resumen de edición para el historial de MediaWiki | Configurado en `.env` |
| `--url` | | URL del endpoint `api.php` | Configurado en `.env` |
| `--http-user` | | Usuario de autenticación Apache / HTTP Basic Auth | Configurado en `.env` |
| `--http-password` | | Contraseña de Apache / HTTP Basic Auth | Configurado en `.env` |
| `--wiki-user` | | Usuario de la MediaWiki (Action API) | Configurado en `.env` |
| `--wiki-password` | | Contraseña de la MediaWiki | Configurado en `.env` |
| `--verify-ssl` | | Activa verificación estricta de certificados SSL | Configurado en `.env` |
| `--ca-bundle` | | Ruta al certificado CA corporativo para validar SSL | `None` |

---

## Pruebas Unitarias

Para validar los conversores y la integridad del sistema:

```bash
python3 -m unittest discover tests
```

