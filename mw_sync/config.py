"""
Módulo de Configuración para MediaWiki Sync.
Carga variables de entorno desde archivo .env (sin dependencias externas)
y define valores por defecto.
"""
import os
import sys
import getpass
from pathlib import Path


def cargar_env(ruta_env: str = ".env") -> dict:
    """Lee un archivo .env si existe y carga sus valores en os.environ sin pisar los ya definidos."""
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
                    if clave not in os.environ:
                        os.environ[clave] = valor
    except Exception as e:
        print(f"[AVISO] Al leer {ruta_env}: {e}", file=sys.stderr)

    return env_vars


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
