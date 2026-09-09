"""
Módulo de Configuración para MediaWiki Sync.
Carga variables de entorno desde archivo .env (sin dependencias externas)
y define valores por defecto.
"""
import os
import sys
import getpass
from pathlib import Path


def cargar_env(ruta_env: str = ".env", sobrescribir: bool = False) -> dict:
    """Lee un archivo .env si existe y carga sus valores en os.environ."""
    env_vars = {}
    path = Path(ruta_env)
    if not path.is_file():
        return env_vars

    try:
        with open(path, "r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#"):
                    continue
                if "=" in linea:
                    clave, valor = linea.split("=", 1)
                    clave = clave.strip()
                    valor = valor.strip()
                    # Quitar comillas simples o dobles envolventes
                    if (valor.startswith('"') and valor.endswith('"')) or (valor.startswith("'") and valor.endswith("'")):
                        valor = valor[1:-1]
                    env_vars[clave] = valor
                    if sobrescribir or clave not in os.environ:
                        os.environ[clave] = valor
    except Exception as e:
        print(f"[AVISO] Al leer {ruta_env}: {e}", file=sys.stderr)

    return env_vars


def actualizar_config_desde_directorio(dir_path: str = None) -> str:
    """
    Si dir_path o su directorio padre (o cwd) contiene un archivo .env, lo carga y actualiza DEFAULT_CONFIG.

    Resuelve adecuadamente el directorio de documentación (docs_dir):
    - Si se especifica la raíz de un proyecto (donde reside .env), redirige automáticamente
      a la subcarpeta 'wiki_docs' (o al valor relativo indicado en MW_OUTPUT_DIR).
    - Si se especifica directamente la subcarpeta 'wiki_docs' o un directorio con ficheros .md, lo respeta.
    - Resuelve rutas relativas de MW_OUTPUT_DIR respecto a la ubicación del archivo .env.

    Devuelve la ruta absoluta normalizada al directorio de documentación.
    """
    if dir_path:
        p = Path(dir_path).resolve()
    else:
        p = Path.cwd().resolve()

    env_file = None
    project_dir = None

    candidatos = [
        p / ".env",
        p.parent / ".env",
        Path.cwd().resolve() / ".env",
        Path.cwd().resolve().parent / ".env"
    ]
    for candidato in candidatos:
        if candidato.is_file():
            env_file = candidato
            project_dir = candidato.parent
            break

    env_vars = {}
    if env_file:
        env_vars = cargar_env(str(env_file), sobrescribir=True)
        DEFAULT_CONFIG["MEDIAWIKI_URL"] = os.getenv("MW_URL", "https://wiki.example.com/api.php")
        DEFAULT_CONFIG["HTTP_USER"] = os.getenv("MW_HTTP_USER", os.getenv("MW_USER", ""))
        DEFAULT_CONFIG["HTTP_PASS"] = os.getenv("MW_HTTP_PASS", os.getenv("MW_PASS", ""))
        DEFAULT_CONFIG["WIKI_USER"] = os.getenv("MW_WIKI_USER", "")
        DEFAULT_CONFIG["WIKI_PASS"] = os.getenv("MW_WIKI_PASS", "")
        DEFAULT_CONFIG["AUTH_USER"] = os.getenv("MW_USER", "")
        DEFAULT_CONFIG["AUTH_PASS"] = os.getenv("MW_PASS", "")
        DEFAULT_CONFIG["VERIFY_SSL"] = os.getenv("MW_VERIFY_SSL", "false").lower() in ("true", "1", "yes")
        DEFAULT_CONFIG["CA_BUNDLE"] = os.getenv("MW_CA_BUNDLE", None)
        DEFAULT_CONFIG["THREADS"] = int(os.getenv("MW_THREADS", "8"))
        DEFAULT_CONFIG["USER_AGENT"] = os.getenv("MW_USER_AGENT", "MediaWikiSync/3.0 (Python; BiDirectional)")
        DEFAULT_CONFIG["EDIT_SUMMARY"] = os.getenv("MW_EDIT_SUMMARY", "Actualizado desde local Markdown vía mediawiki_sync")

    # Determinar el directorio de documentación efectivo
    if env_file:
        env_output_dir = env_vars.get("MW_OUTPUT_DIR")
    else:
        env_output_dir = os.getenv("MW_OUTPUT_DIR")

    if project_dir and p == project_dir:
        # El usuario especificó la raíz del proyecto (donde reside el .env)
        if env_output_dir:
            out_p = Path(env_output_dir.strip())
            docs_dir = out_p if out_p.is_absolute() else (project_dir / out_p).resolve()
        elif (project_dir / "wiki_docs").is_dir():
            docs_dir = project_dir / "wiki_docs"
        elif any(f for f in project_dir.glob("*.md") if not f.name.startswith("00_INDICE")):
            docs_dir = project_dir
        else:
            # Caso de descarga inicial o convención estándar
            docs_dir = project_dir / "wiki_docs"
    elif project_dir and p == project_dir / "wiki_docs":
        # Se apuntó directamente a wiki_docs
        docs_dir = p
    elif env_output_dir and not dir_path:
        # No se pasó flag explícito por CLI pero hay MW_OUTPUT_DIR en el entorno
        out_p = Path(env_output_dir.strip())
        if out_p.is_absolute():
            docs_dir = out_p
        elif project_dir:
            docs_dir = (project_dir / out_p).resolve()
        else:
            docs_dir = (Path.cwd() / out_p).resolve()
    elif (p / "wiki_docs").is_dir() and not any(f for f in p.glob("*.md") if not f.name.startswith("00_INDICE")):
        docs_dir = p / "wiki_docs"
    else:
        docs_dir = p

    DEFAULT_CONFIG["OUTPUT_DIR"] = str(docs_dir)
    os.environ["MW_OUTPUT_DIR"] = str(docs_dir)
    return str(docs_dir)


# Cargar variables de entorno desde .env si existe
cargar_env()

# Extensiones de archivos multimedia y documentos soportados en MediaWiki
EXTENSIONES_MULTIMEDIA = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", ".webp", ".ico",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".7z",
    ".odt", ".ods", ".odp", ".rtf", ".txt", ".csv"
}

# Configuración por defecto (usando os.getenv sin contraseñas en duro)
DEFAULT_CONFIG = {
    "MEDIAWIKI_URL": os.getenv("MW_URL", "https://wiki.example.com/api.php"),
    # Capa 1: Apache / Proxy (HTTP Basic Auth)
    "HTTP_USER": os.getenv("MW_HTTP_USER", os.getenv("MW_USER", "")),
    "HTTP_PASS": os.getenv("MW_HTTP_PASS", os.getenv("MW_PASS", "")),
    # Capa 2: Usuario de MediaWiki (Action API Login)
    "WIKI_USER": os.getenv("MW_WIKI_USER", ""),
    "WIKI_PASS": os.getenv("MW_WIKI_PASS", ""),
    # Compatibilidad hacia atrás
    "AUTH_USER": os.getenv("MW_USER", ""),
    "AUTH_PASS": os.getenv("MW_PASS", ""),
    "VERIFY_SSL": os.getenv("MW_VERIFY_SSL", "false").lower() in ("true", "1", "yes"),
    "CA_BUNDLE": os.getenv("MW_CA_BUNDLE", None),
    "OUTPUT_DIR": os.getenv("MW_OUTPUT_DIR", "./wiki_docs"),
    "THREADS": int(os.getenv("MW_THREADS", "8")),
    "USER_AGENT": os.getenv("MW_USER_AGENT", "MediaWikiSync/3.0 (Python; BiDirectional)"),
    "EDIT_SUMMARY": os.getenv("MW_EDIT_SUMMARY", "Actualizado desde local Markdown vía mediawiki_sync")
}


def solicitar_credenciales_si_faltan(user: str = None, password: str = None,
                                     wiki_user: str = None, wiki_password: str = None) -> tuple[str, str, str, str]:
    """Solicita interactivamente credenciales si no fueron provistas."""
    hu = user or DEFAULT_CONFIG["HTTP_USER"]
    hp = password or DEFAULT_CONFIG["HTTP_PASS"]
    wu = wiki_user or DEFAULT_CONFIG["WIKI_USER"]
    wp = wiki_password or DEFAULT_CONFIG["WIKI_PASS"]

    # Si se especificó solo AUTH_USER / AUTH_PASS y no WIKI_USER, mantener compatibilidad
    if not wu and DEFAULT_CONFIG["AUTH_USER"] and not os.getenv("MW_HTTP_USER"):
        wu = DEFAULT_CONFIG["AUTH_USER"]
        wp = DEFAULT_CONFIG["AUTH_PASS"]

    return hu, hp, wu, wp
