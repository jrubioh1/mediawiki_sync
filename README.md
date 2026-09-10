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
   - [Control y Gestion de Paginas Vacias](#control-y-gestion-de-paginas-vacias)
6. [Uso como Biblioteca Python](#uso-como-biblioteca-python)
7. [Referencia Completa de Parametros CLI](#referencia-completa-de-parametros-cli)
8. [Seguridad y Buenas Practicas](#seguridad-y-buenas-practicas)
9. [Bateria de Pruebas](#bateria-de-pruebas)
10. [Licencia](#licencia)

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

El proyecto se estructura como paquete estándar de Python `mw_sync` gestionado con Poetry:

```text
mediawiki-sync/
├── pyproject.toml              # Definición del paquete y configuración de Poetry (PEP 621)
├── LICENSE                     # Licencia GNU General Public License v3 (GPL-3.0)
├── MANUAL_USO_MEDIAWIKI_SYNC.md# Manual detallado de usuario y casos de uso
├── README.md                   # Documentación técnica del repositorio
├── .env.example                # Plantilla de configuración de entorno
├── .env                        # Variables y credenciales locales (excluido de Git)
├── .gitignore                  # Exclusión de credenciales, dist/ y temporales
├── .github/
│   └── workflows/
│       └── e2e-mediawiki.yml   # CI/CD: Matriz de tests unitarios y pruebas E2E con MediaWiki en Docker
├── mw_sync/                    # Paquete principal de la aplicación
│   ├── __init__.py             # Exportaciones de la API pública y versión del paquete
│   ├── __main__.py             # Punto de entrada para ejecución modular (`python3 -m mw_sync`)
│   ├── cli.py                  # Parseo de argumentos y lógica de terminal
│   ├── client.py               # Cliente HTTP/HTTPS para MediaWiki Action API
│   ├── config.py               # Gestión de configuración y resolución de credenciales
│   ├── downloader.py           # Motor de descarga incremental y multihilo
│   ├── empty_pages.py          # Detección y gestión de páginas remotas vacías
│   ├── state.py                # Persistencia de estado local (.sync_state.json)
│   ├── uploader.py             # Motor de subida, diff y control de conflictos
│   └── converters/
│       ├── html_to_md.py       # Conversor HTML a Markdown con sanitizado
│       ├── md_to_wikitext.py   # Conversor Markdown a Wikitext estándar
│       └── sanitizer.py        # Limpieza masiva de colecciones Markdown locales
└── tests/
    ├── test_converters.py      # Pruebas unitarias para conversores de formato
    ├── test_uploader.py        # Pruebas de subida, detección de títulos y conflictos
    ├── test_empty_pages.py     # Pruebas de control de páginas vacías y eliminación
    └── test_live_wiki.py       # Pruebas E2E de integración real contra servidor MediaWiki
```

---

## Requisitos e Instalación

### Requisitos

- Python 3.13 o superior.
- Sin dependencias externas obligatorias (arquitectura nativa con módulos estándar de Python).

### Preparación del Entorno

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/jrubioh1/mediawiki_sync.git
   cd mediawiki_sync
   ```

2. Preparar el archivo de configuración con sus credenciales:
   ```bash
   cp .env.example .env
   chmod 600 .env
   ```

### Opciones de Instalación y Empaquetado

El proyecto puede utilizarse como paquete global/virtualenv o de forma autónoma:

#### Opción 1: Instalación directa desde PyPI (Recomendado)
```bash
pip install mediawiki-sync

# Comandos de terminal disponibles en el sistema o virtualenv:
mw-sync --help
mediawiki-sync --help
```

#### Opción 2: Entorno de desarrollo local con Poetry
Instala el proyecto en modo editable registrando los comandos ejecutables `mw-sync` y `mediawiki-sync`:
```bash
poetry install

# Ejecutar comandos directamente en el entorno:
poetry run mw-sync --help
# o activando el entorno:
source .venv/bin/activate
mw-sync --help
```

#### Opción 3: Instalación vía Wheel local (.whl)
Genera el paquete estándar y lo instala en cualquier entorno Python:
```bash
# Construir paquete distribuible (en dist/):
poetry build

# Instalar el wheel generado:
pip install dist/mediawiki_sync-1.1.2-py3-none-any.whl

# Comandos de terminal disponibles globalmente en el entorno:
mw-sync --help
mediawiki-sync --help
```

#### Opción 4: Instalación con soporte opcional de alto rendimiento HTTP
Si se desea aceleración de red mediante pool de conexiones `requests` / `urllib3`:
```bash
pip install "mediawiki-sync[fast-http]"
# o en local:
pip install ".[fast-http]"
```

#### Opción 5: Ejecución directa como módulo
Si se ejecuta directamente desde el clon del repositorio sin haber instalado el paquete en el entorno:
```bash
python3 -m mw_sync --help
```

---

## Configuracion de Entorno (.env y Variables de Sistema)

`mw_sync` permite configurar la conexión, credenciales y opciones de ejecución tanto en desarrollo local como en entornos de producción (Docker, Kubernetes, GitHub Actions, systemd, etc.).

### Orden de Precedencia (Jerarquía de Configuración)

El motor de configuración resuelve los valores aplicando la siguiente jerarquía (de mayor a menor prioridad):

1. **Parámetros CLI:** Argumentos pasados directamente en la terminal (ej. `--url`, `--threads 16`, `--wiki-user`).
2. **Variables de Entorno del Sistema / Producción:** Variables exported en el sistema operativo, contenedor Docker o pipeline de CI/CD (ej. `export MW_URL=...`).
3. **Archivo `.env` Local:** Cargas desde el archivo `.env` situado en el directorio de trabajo (sin sobrescribir variables ya existentes en el sistema).
4. **Valores por Defecto:** Valores predeterminados integrados en la aplicación.

---

### Uso Local vs Producción

- **Desarrollo Local:** Copie el archivo `.env.example` como `.env` en la raíz de su proyecto y ajuste sus valores. El archivo `.env` se encuentra excluido en `.gitignore` para prevenir filtraciones de credenciales.
- **Entornos de Producción / Contenedores / CI/CD:** No es necesario crear un archivo `.env`. Defina directamente las variables de entorno de sistema (`MW_URL`, `MW_WIKI_USER`, etc.) en su orquestador de contenedores (Docker / Kubernetes Secrets), servicios systemd o secretos de CI/CD (GitHub Actions / GitLab CI).
- **Ubicación del Directorio de Salida (`MW_OUTPUT_DIR` / `--dir`):**
  - **No es necesario ejecutar `mw-sync` dentro del directorio de documentación.** El programa detecta automáticamente la ruta desde la variable de entorno `MW_OUTPUT_DIR` o el flag CLI `--dir` (`-o`).
  - **Rutas Absolutas vs Relativas:** Si especifica una ruta relativa (ej. `MW_OUTPUT_DIR=./wiki_docs`), se resolverá respecto al directorio donde se ubica el archivo `.env` del proyecto (o al directorio actual de ejecución si no hay `.env`). Si especifica una ruta absoluta (ej. `MW_OUTPUT_DIR=/home/usuario/wiki_docs`), funcionará exactamente igual sin importar el directorio de trabajo actual desde el que ejecute la terminal.
  - El archivo de estado `.sync_state.json` se guardará automáticamente dentro del directorio configurado (`<OUTPUT_DIR>/.sync_state.json`).

---

### Gestión de Múltiples Servidores MediaWiki (Patrón Multi-Wiki)

Si administra varios servidores o entornos MediaWiki independientes (ej. Wiki Interna, Wiki Pública, Wiki de Proyectos), el patrón ideal y recomendado es estructurar carpetas independientes con su propio archivo `.env`:

```text
mis_wikis/
├── wiki_interna/
│   ├── .env               # Configuración y credenciales de la wiki interna
│   └── wiki_docs/         # Documentación local e historial .sync_state.json
├── wiki_publica/
│   ├── .env               # Configuración y credenciales de la wiki pública
│   └── wiki_docs/
└── wiki_proyectos/
    ├── .env               # Configuración y credenciales (MW_OUTPUT_DIR=./wiki_docs opcional)
    └── wiki_docs/
```

**Flujo de trabajo multi-sitio:**
Para sincronizar o publicar cambios en una wiki específica, simplemente sitúese en la carpeta correspondiente y ejecute la herramienta:

```bash
# Opción 1: Entrar en la carpeta del proyecto
cd mis_wikis/wiki_interna
mw-sync --upload

# Opción 2: Ejecutar desde cualquier lugar usando --dir (Auto-descubrimiento de .env)
mw-sync --upload --dir /home/usuario/mis_wikis/wiki_publica
```

> [!TIP]
> **Resolución de directorios en este ejemplo:**
> * En los archivos `.env` de este esquema **no se ha declarado la variable `MW_OUTPUT_DIR`**. Al omitirla, `mw-sync` aplica automáticamente la convención estándar y dirige las operaciones a la subcarpeta `./wiki_docs/` de ese proyecto.
> * Si en el `.env` declaras una ruta relativa (ej. `MW_OUTPUT_DIR=./mis_documentos` o `MW_OUTPUT_DIR=.`), `mw-sync` usará esa ruta resolviéndola siempre relativa a la ubicación del archivo `.env` del proyecto.

#### Guía de Casuísticas: Bajada (`--download`) y Subida (`--upload`)

> [!NOTE]
> El parámetro `--download` (o `-dl`) **no es obligatorio**: la descarga incremental es la operación por defecto de `mw-sync` si no se especifica `--upload`. Por tanto, `mw-sync --dir /ruta` equivale a `mw-sync --download --dir /ruta`.

| Casuística | Ejemplo Bajada (Download) | Ejemplo Subida (Upload) | Destino de los `.md` / Notas |
| :--- | :--- | :--- | :--- |
| **1. Dentro del proyecto** (`cd`) | `cd wiki_clientes && mw-sync` | `cd wiki_clientes && mw-sync --upload` | `./wiki_docs/` local |
| **2. Con `--dir` a raíz de proyecto** | `mw-sync --dir /ruta/wiki_clientes` | `mw-sync --upload --dir /ruta/wiki_clientes` | `/ruta/wiki_clientes/wiki_docs/` (crea o usa subcarpeta) |
| **3. Con `--dir` a `wiki_docs` directo** | `mw-sync --dir /ruta/wiki_clientes/wiki_docs` | `mw-sync --upload --dir /ruta/wiki_clientes/wiki_docs` | `/ruta/wiki_clientes/wiki_docs/` (sin anidar `wiki_docs/wiki_docs`) |
| **4. Carpeta personalizada en `.env`** | `mw-sync --dir /ruta/wiki_clientes` | `mw-sync --upload --dir /ruta/wiki_clientes` | `/ruta/wiki_clientes/<MW_OUTPUT_DIR>/` (relativo a `.env`) |
| **5. Carpeta directa sin `.env` (CI/CD)** | `mw-sync --dir /var/docs/manuales` | `mw-sync --upload --dir /var/docs/manuales` | `/var/docs/manuales/` directo (sin subcarpeta `wiki_docs`) |
| **6. Variable en el OS (`export MW_OUTPUT_DIR`)** | `mw-sync` (sin `--dir`) | `mw-sync --upload` (sin `--dir`) | Destino fijado por `os.environ["MW_OUTPUT_DIR"]` (absoluta o relativa a `$PWD`) |
| **7. Estructura plana en proyecto (`MW_OUTPUT_DIR=.`)** | `mw-sync --dir /ruta/wiki_plana` | `mw-sync --upload --dir /ruta/wiki_plana` | `/ruta/wiki_plana/` directamente (raíz del proyecto, sin subcarpeta) |

Al ejecutarse, `mw_sync` cargará automáticamente las credenciales y la URL del `.env` del directorio actual o de la carpeta especificada en `--dir`, manteniendo los archivos Markdown y el registro de estado `.sync_state.json` de cada servidor totalmente aislados.

> [!IMPORTANT]
> **Reglas clave para el patrón Multi-Wiki:**
> 1. **Auto-descubrimiento con `--dir` y resolución de `wiki_docs`:** Si ejecuta desde otra ubicación sin hacer `cd`, pase `--dir /ruta/al/proyecto`. La herramienta buscará y cargará automáticamente el archivo `.env` perteneciente a ese directorio y redirigirá la sincronización a la subcarpeta `wiki_docs/` (o al directorio definido en `MW_OUTPUT_DIR` relativo al proyecto). También puede pasar directamente `--dir /ruta/al/proyecto/wiki_docs`.
> 2. **Ubicación de `MW_OUTPUT_DIR` en el `.env` vs en el OS:** Si no se especifica `MW_OUTPUT_DIR` en el `.env`, `mw-sync` asume por defecto la subcarpeta `./wiki_docs` dentro del proyecto. Las rutas relativas de `MW_OUTPUT_DIR` en el `.env` se resuelven siempre respecto a la raíz del proyecto donde se ubica el archivo `.env`. En cambio, si `MW_OUTPUT_DIR` se define en el sistema operativo (`export`), se resolverá respecto al directorio de ejecución actual de la terminal.
> 3. **Evite definir variables `MW_*` globales en la consola (`export MW_...` o `~/.bashrc`):** Dado que las variables de entorno del sistema operativo tienen mayor precedencia que el archivo `.env`, cualquier variable global de sistema sobrescribirá el contenido de los archivos `.env` locales. Deje el entorno del sistema limpio de variables específicas (`MW_URL`, `MW_WIKI_USER`, `MW_WIKI_PASS`, `MW_OUTPUT_DIR`) para que cada proyecto responda a su propio `.env`.

---

### Referencia Completa de Variables de Entorno (`MW_*`)

| Variable de Entorno | Descripción | Valor por Defecto | Variable Mapeada en CLI / Módulo |
| :--- | :--- | :--- | :--- |
| `MW_URL` | URL completa del endpoint Action API (`api.php`) | `https://wiki.example.com/api.php` | `--url` |
| `MW_HTTP_USER` | Usuario para HTTP Basic Auth perimetral (Apache/Nginx/Proxy) | `""` (vacio) | `--http-user` |
| `MW_HTTP_PASS` | Contraseña para HTTP Basic Auth perimetral | `""` (vacio) | `--http-password` |
| `MW_WIKI_USER` | Usuario de la cuenta MediaWiki (Action API) | `""` (vacio) | `--wiki-user` |
| `MW_WIKI_PASS` | Contraseña de la cuenta MediaWiki | `""` (vacio) | `--wiki-password` |
| `MW_USER` | Usuario legado (compatibilidad como fallback si no se define `MW_HTTP_USER`/`MW_WIKI_USER`) | `""` (vacio) | `--user` |
| `MW_PASS` | Contraseña legada (compatibilidad como fallback si no se define `MW_HTTP_PASS`/`MW_WIKI_PASS`) | `""` (vacio) | `--password` |
| `MW_VERIFY_SSL` | Activa la verificación estricta de certificados SSL (`true`/`false`/`1`/`0`/`yes`/`no`) | `false` | `--verify-ssl` |
| `MW_CA_BUNDLE` | Ruta a archivo CA Bundle (`.crt`/`.pem`) para certificados corporativos o autofirmados | `None` | `--ca-bundle` |
| `MW_TIMEOUT` | Tiempo máximo de espera en segundos para cada petición HTTP/HTTPS | `10.0` | Utilizado en cliente HTTP |
| `MW_USER_AGENT` | Cabecera `User-Agent` personalizada enviada en las peticiones a MediaWiki | `MediaWikiSync/3.0 (Python; BiDirectional)` | Utilizado en cliente HTTP |
| `MW_OUTPUT_DIR` | Directorio local donde se guardan los archivos Markdown e imágenes (relativo a `.env` si es relativo) | `./wiki_docs` | `--dir`, `-o` |
| `MW_THREADS` | Número de hilos concurrentes para la descarga paralela de artículos e imágenes | `8` | `--threads`, `-t` |
| `MW_EDIT_SUMMARY` | Resumen predeterminado en el historial de revisiones al publicar cambios en MediaWiki | `Actualizado desde local Markdown vía mediawiki_sync` | `--summary` |
| `MW_TEST_LIVE` | *(Testing)* Habilita la suite de pruebas E2E contra un servidor MediaWiki en vivo (`1`/`0`) | `0` | Entorno de Pruebas |
| `MW_TEST_LIVE_URL` | *(Testing)* Endpoint Action API para pruebas E2E en vivo | `http://localhost:8080/api.php` | Entorno de Pruebas |
| `MW_TEST_WIKI_USER` | *(Testing)* Usuario administrador para pruebas E2E | `TestAdmin` | Entorno de Pruebas |
| `MW_TEST_WIKI_PASS` | *(Testing)* Contraseña para pruebas E2E | `TestPass123` | Entorno de Pruebas |

Ejemplo de plantilla `.env`:

```ini
# Endpoint principal
MW_URL=https://wiki.example.com/api.php

# Capa 1: Proxy / Apache (HTTP Basic Auth)
MW_HTTP_USER=usuario_proxy
MW_HTTP_PASS=password_proxy

# Capa 2: MediaWiki Action API
MW_WIKI_USER=usuario_wiki
MW_WIKI_PASS=password_wiki

# Seguridad TLS/SSL y Red
MW_VERIFY_SSL=true
MW_CA_BUNDLE=/etc/ssl/certs/corporate-ca.crt
MW_TIMEOUT=15.0
MW_USER_AGENT=MiEmpresaWikiSync/1.0

# Rendimiento y Rutas Locales
MW_OUTPUT_DIR=./wiki_docs
MW_THREADS=12
MW_EDIT_SUMMARY=Sincronizado automáticamente desde Git
```

---

## Guia de Uso CLI

Puede ejecutarse mediante los comandos de paquete registrados en la terminal (`mw-sync` en su forma corta o `mediawiki-sync` en su forma larga), o bien como módulo mediante `python3 -m mw_sync`. Todos aceptan exactamente los mismos parámetros.

### Descarga Incremental Concurrente

Por defecto, ejecutar el comando sin argumentos inicia la descarga incremental hacia la carpeta configurada (por defecto `./wiki_docs`):

```bash
# Descarga incremental estandar (8 hilos en paralelo):
mw-sync

# Ajustar el numero de hilos de concurrencia:
mw-sync --threads 16

# Forzar la re-descarga de todos los articulos ignorando el estado local:
mw-sync --force

# Descargar solo el texto de los articulos, omitiendo imagenes multimedia:
mw-sync --no-images
```

### Subida de Cambios y Control de Conflictos

El modo `--upload` escanea la carpeta local de documentacion, calcula hashes SHA-256 frente a `.sync_state.json` y detecta que articulos o imagenes fueron modificados o creados.

```bash
# Simular subida (Dry-Run) para ver que cambios se aplicarian sin alterar el servidor:
mw-sync --upload --dry-run

# Subir todos los archivos locales modificados:
mw-sync --upload

# Subir unicamente un archivo especifico:
mw-sync --upload --file ./wiki_docs/Manual_de_Usuario.md

# Subir una imagen al repositorio multimedia de la wiki:
mw-sync --upload --file ./wiki_docs/images/esquema_red.png

# Omitir confirmaciones interactivas al resolver un conflicto (sobrescritura forzada):
mw-sync --upload --force --yes
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
mw-sync --upload --diff --dry-run
```

### Saneamiento y Normalizacion Offline

Permite procesar archivos Markdown en local para eliminar restos de ediciones previas, limpiar artefactos de etiquetas y corregir espaciados:

```bash
# Ejecutar saneamiento real sobre el directorio local:
mw-sync --sanitize

# Comprobar que archivos serian alterados sin modificarlos en disco:
mw-sync --sanitize --dry-run
```

### Control y Gestion de Paginas Vacias

Cuando una pagina en MediaWiki carece de contenido, el sincronizador la registra en `.sync_state.json` evitando fallos de descarga, y ofrece opciones de resolucion:

```bash
# Consultar y gestionar interactivamente las paginas vacias registradas:
mw-sync --empty-pages

# Si cambiaste de opinion tras omitirlas: crear plantillas locales de golpe:
mw-sync --empty-pages --empty-action create-md

# Crear plantillas .md locales con encabezado y frontmatter listos para rellenar (en descarga):
mw-sync --empty-action create-md

# Eliminar las paginas vacias del servidor MediaWiki (action=delete):
mw-sync --empty-action delete-remote --yes

# Omitir paginas vacias en ejecuciones automatizadas:
mw-sync --empty-action ignore
```

> [!TIP]
> **Reactivacion de paginas omitidas:** Si anteriormente selecciono la opcion de omitir paginas vacias, estas quedan almacenadas en el estado local con status `omitida`. Para convertirlas en plantillas `.md` locales en cualquier momento posterior, ejecute `mw-sync --empty-pages` (y pulse `1`) o `mw-sync --empty-pages --empty-action create-md` (modo directo). Si cualquier usuario anade contenido a una pagina omitida en el servidor, `mw-sync` detectara la nueva revision y la descargara automaticamente.

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

| Argumento | Abreviatura | Variable de Entorno Mapeada | Descripción | Valor por Defecto |
| :--- | :--- | :--- | :--- | :--- |
| `--download` | `-dl` | N/A | Modo descarga incremental de MediaWiki a local | Activo por defecto |
| `--upload` | `-up` | N/A | Modo subida de cambios locales a MediaWiki | Desactivado |
| `--sanitize` | | N/A | Ejecuta el saneador de sintaxis Markdown offline | Desactivado |
| `--diff` | | N/A | Muestra diferencias en formato unificado antes de publicar | Desactivado |
| `--dry-run` | | N/A | Simula operaciones sin tocar disco ni hacer cambios remotos | Desactivado |
| `--force` | `-f` | N/A | Fuerza la descarga o publicacion omitiendo verificacion de hashes | Desactivado |
| `--yes` | `-y` | N/A | Responde afirmativamente de forma no interactiva a preguntas | Desactivado |
| `--empty-pages` | | N/A | Lista y gestiona las paginas vacias registradas en el estado local | Desactivado |
| `--empty-action` | | N/A | Accion ante paginas vacias (`ask`, `create-md`, `delete-remote`, `ignore`) | `ask` |
| `--threads` | `-t` | `MW_THREADS` | Numero de hilos para descarga paralela | `8` |
| `--dir` | `-o` | `MW_OUTPUT_DIR` | Directorio local de documentacion | `./wiki_docs` |
| `--file` | | N/A | Ruta de un archivo individual (`.md` o imagen) para subir | `None` |
| `--no-images` | | N/A | Omite la gestion de archivos multimedia | Desactivado |
| `--summary` | | `MW_EDIT_SUMMARY` | Texto para el resumen de edicion en el historial de revisiones | `Actualizado desde local...` |
| `--url` | | `MW_URL` | URL del endpoint `api.php` de MediaWiki | `https://wiki.example.com/api.php` |
| `--http-user` | | `MW_HTTP_USER` (o `MW_USER`) | Usuario para HTTP Basic Auth (Proxy/Apache) | `""` |
| `--http-password`| | `MW_HTTP_PASS` (o `MW_PASS`) | Contrasena para HTTP Basic Auth (Proxy/Apache) | `""` |
| `--wiki-user` | | `MW_WIKI_USER` (o `MW_USER`) | Usuario de MediaWiki (Action API) | `""` |
| `--wiki-password`| | `MW_WIKI_PASS` (o `MW_PASS`) | Contrasena de MediaWiki (Action API) | `""` |
| `--verify-ssl` | | `MW_VERIFY_SSL` | Activa la validacion estricta de certificados TLS/SSL | `false` |
| `--ca-bundle` | | `MW_CA_BUNDLE` | Ruta a archivo CA Bundle para certificados autofirmados/privados | `None` |

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

El repositorio incluye pruebas unitarias offline y pruebas de integración continua E2E contra instancias reales de MediaWiki:

```bash
# Ejecutar suite completa de pruebas unitarias:
python3 -m unittest discover tests

# O utilizando pytest en el entorno virtual:
poetry run pytest tests
```

### Cobertura de Pruebas

- `tests/test_converters.py`: Valida la conversión bidireccional HTML -> Markdown y Markdown -> Wikitext, verificando listas continuas anidadas (`#`, `#*`), tablas complejas, enlaces relativos locales, bloques de código y remoción de artefactos (`__TOC__`, `[editar]`).
- `tests/test_uploader.py`: Valida la extracción de títulos desde metadatos frontmatter y encabezados `#`, así como el flujo de detección y alerta ante conflictos de revisión remota (`baserevid`).
- `tests/test_empty_pages.py`: Valida la detección de páginas vacías, creación de plantillas Markdown locales, registro en `.sync_state.json` y eliminación remota (`action=delete`).
- `tests/test_live_wiki.py`: Batería de integración en vivo ejecutada en GitHub Actions contra un contenedor Docker de MediaWiki real (login, upload, download, detección de conflictos y ciclo de vida de páginas vacías).

---

## Licencia

Este proyecto se distribuye bajo los términos de la licencia **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. Para más información, consulte el archivo [LICENSE](LICENSE).
