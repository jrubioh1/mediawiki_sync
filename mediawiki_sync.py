#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
MediaWiki Sync 3.0: Sincronizador Bidireccional MediaWiki <-> Markdown
=============================================================================

Características principales:
  1. DESCARGA INCREMENTAL CONCURRENTE:
     - Detección de cambios por revision ID (revid) en MediaWiki.
     - Descarga multihilo rápida de artículos e imágenes con ThreadPoolExecutor.
     - Parser HTML a Markdown limpio y robusto (sin fugas de [editar] ni TOC).
     - Conversión automática de enlaces internos a rutas Markdown relativas.
     - Generación automática de índice navegable 00_INDICE_MEDIAWIKI.md.

  2. SUBIDA INTELIGENTE (--upload):
     - Conversión de Markdown a Wikitext estándar (encabezados, listas anidadas,
       tablas, imágenes, citas y enlaces).
     - Detección de conflictos en el servidor mediante baserevid.
     - Previsualización de cambios (--diff) y simulación (--dry-run).

  3. MODO SANEAMIENTO (--sanitize):
     - Repara en bloque archivos locales existentes eliminando artefactos rotos.

  4. SEGURIDAD Y CONFIGURACIÓN:
     - Carga automática de credenciales desde archivo .env (ignorado por git).
     - Soporte para CA Bundle corporativo y HTTP Basic Auth.
     - Cero dependencias externas obligatorias (funciona en cualquier Python 3.8+).

Uso:
  python3 mediawiki_sync.py              # Descarga incremental concurrente
  python3 mediawiki_sync.py --upload     # Subida de cambios locales
  python3 mediawiki_sync.py --sanitize   # Saneamiento de documentos locales
  python3 mediawiki_sync.py --help       # Ayuda completa de parámetros
=============================================================================
"""
import sys

# Re-exportar funciones y clases clave para compatibilidad hacia atrás
from mw_sync.config import DEFAULT_CONFIG
from mw_sync.converters.html_to_md import html_a_markdown, sanitizar_nombre_archivo, normalizar_enlace_wiki_a_md
from mw_sync.converters.md_to_wikitext import markdown_a_wikitext, extraer_metadatos_frontmatter
from mw_sync.converters.sanitizer import limpiar_contenido_markdown, sanear_directorio
from mw_sync.client import MediaWikiClient
from mw_sync.state import SyncState, calcular_sha256
from mw_sync.downloader import ejecutar_descarga
from mw_sync.uploader import ejecutar_subida
from mw_sync.cli import main

if __name__ == "__main__":
    main()
