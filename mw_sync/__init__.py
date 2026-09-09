"""
mw_sync: Suite de sincronización bidireccional entre MediaWiki y Markdown.

Proporciona herramientas nativas en Python (sin dependencias externas) para:
- Descargar incremental y concurrentemente artículos e imágenes desde MediaWiki a Markdown local.
- Subir artículos en Markdown convirtiéndolos a Wikitext fiel para MediaWiki con control de revisiones y prevención de sobreescrituras accidentales.
- Sanear y limpiar archivos Markdown locales con entidades HTML desalineadas o sintaxis rota.
- Comparar visualmente (diff contextual unificado) las diferencias antes de aplicar cambios.
"""

from mw_sync.client import MediaWikiClient
from mw_sync.state import SyncState, calcular_sha256
from mw_sync.downloader import ejecutar_descarga
from mw_sync.uploader import (
    ejecutar_subida,
    extraer_titulo_de_archivo_md,
    mostrar_diff_local,
)
from mw_sync.converters.html_to_md import html_a_markdown, sanitizar_nombre_archivo
from mw_sync.converters.md_to_wikitext import markdown_a_wikitext
from mw_sync.converters.sanitizer import sanear_directorio, limpiar_contenido_markdown

__version__ = "3.0.0"

__all__ = [
    "MediaWikiClient",
    "SyncState",
    "calcular_sha256",
    "ejecutar_descarga",
    "ejecutar_subida",
    "extraer_titulo_de_archivo_md",
    "mostrar_diff_local",
    "html_a_markdown",
    "sanitizar_nombre_archivo",
    "markdown_a_wikitext",
    "sanear_directorio",
    "limpiar_contenido_markdown",
]

