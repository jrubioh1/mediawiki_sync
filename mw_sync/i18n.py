"""
Módulo nativo de internacionalización (i18n) para MediaWiki Sync.
Sin dependencias externas (100% biblioteca estándar de Python).
Soporta español ('es') e inglés ('en').
"""
import os
import sys
import locale

IDIOMAS_SOPORTADOS = ("es", "en")
IDIOMA_POR_DEFECTO = "es"

_IDIOMA_ACTUAL = IDIOMA_POR_DEFECTO

TRANSLATIONS = {
    "es": {
        # CLI general
        "cli_desc": "Sincronizador integral MediaWiki <-> Markdown nativo en Python, multihilo e incremental.",
        "cli_epilog": """Ejemplos de uso:
  # 1. Sincronización incremental (descarga solo lo nuevo/modificado con 8 hilos):
  mw-sync

  # 2. Sanear y limpiar los archivos Markdown existentes (quita [editar], TOC y ****):
  mw-sync --sanitize

  # 3. Previsualizar qué se subiría a la wiki con diff:
  mw-sync --upload --diff --dry-run

  # 4. Subir cambios locales a la MediaWiki:
  mw-sync --upload

  # 5. Subir un artículo o imagen específico:
  mw-sync --upload --file ./wiki_docs/Manual_Usuario.md

  # 6. Cambiar idioma de salida a inglés:
  mw-sync --lang en
""",
        # CLI flags
        "help_download": "Modo descarga incremental (por defecto): Sincroniza desde MediaWiki a Markdown.",
        "help_upload": "Modo subida: Publica en MediaWiki los cambios o nuevos artículos locales.",
        "help_sanitize": "Sanea todos los archivos .md locales eliminando [editar], TOC y artefactos rotos.",
        "help_diff": "Muestra previsualización de diferencias de Wikitext antes de subir.",
        "help_dry_run": "Simula la operación sin escribir en disco ni modificar el servidor.",
        "help_force": "Fuerza la descarga o subida completa de todos los elementos.",
        "help_yes": "Responde 'sí' automáticamente a confirmaciones interactivas (ej. forzar resolución de conflicto o borrado).",
        "help_empty_pages": "Lista y gestiona las páginas vacías registradas en el estado local (.sync_state.json).",
        "help_empty_action": "Acción ante páginas vacías detectadas: ask (preguntar), create-md (crear .md), delete-remote (borrar de wiki), ignore (omitir).",
        "help_threads": "Número de hilos concurrentes para descarga (por defecto: {threads})",
        "help_url": "Endpoint api.php de la MediaWiki (por defecto: valor de MW_URL o https://wiki.example.com/api.php).",
        "help_user": "Usuario para HTTP Basic Auth / MediaWiki (legado).",
        "help_password": "Contraseña para HTTP Basic Auth / MediaWiki (legado).",
        "help_http_user": "Usuario para autenticación Apache / HTTP Basic Auth.",
        "help_http_password": "Contraseña para autenticación Apache / HTTP Basic Auth.",
        "help_wiki_user": "Usuario de la MediaWiki (Action API).",
        "help_wiki_password": "Contraseña de la MediaWiki.",
        "help_verify_ssl": "Activa verificación estricta de certificados SSL.",
        "help_ca_bundle": "Ruta al archivo CA Bundle (.crt/.pem) para validar SSL de forma segura.",
        "help_dir": "Directorio local de documentación (por defecto: {output_dir})",
        "help_file": "Especifica un único archivo .md o multimedia para subir.",
        "help_no_images": "Ignora la sincronización de archivos multimedia.",
        "help_include_redirects": "Incluye páginas de redirección de MediaWiki en la sincronización (por defecto se omiten).",
        "help_summary": "Mensaje de resumen para el historial de revisiones de MediaWiki.",
        "help_lang": "Idioma de la interfaz y mensajes en consola: es (español), en (inglés).",
        "help_version": "Muestra la versión del programa y sale.",

        # CLI runtime
        "cli_header": "MEDIAWIKI SYNC 3.0 (Markdown <-> Wikitext)",
        "cli_server": "Servidor:     {url}",
        "cli_web_user": "Usuario Web:  {user}",
        "cli_wiki_user": "Usuario Wiki: {user}",
        "none": "(ninguno)",
        "anonymous": "(anónimo)",
        "dry_run_notice": "Modo simulación (--dry-run) activo: Ejecución segura offline sin llamadas de red.",
        "conn_error": "Error de conexión al servidor: {sitename}\nComprueba la URL del endpoint, credenciales en .env o el acceso por red.",
        "conn_success": "Conexión establecida con éxito a '{sitename}'",
        "auth_error": "Error de autenticación en MediaWiki: {msg}",
        "upload_cancelled_no_auth": "Operación cancelada: No se puede publicar contenido sin iniciar sesión en MediaWiki.",
        "anon_upload_warning": "Aviso: No se han configurado credenciales de MediaWiki (MW_WIKI_USER / MW_WIKI_PASS).\nLa publicación se intentará como usuario anónimo y podría ser rechazada.",
        "updating_hashes": "Actualizando registro de hashes en .sync_state.json...",
        "hashes_updated": "Hashes actualizados.",

        # Config
        "env_read_warning": "[AVISO] Al leer {path}: {err}",
        "prompt_http_user": "Introduce usuario Apache/HTTP (opcional): ",
        "prompt_http_pass": "Introduce contraseña Apache/HTTP (opcional): ",
        "prompt_wiki_user": "Introduce usuario de MediaWiki (opcional): ",
        "prompt_wiki_pass": "Introduce contraseña de MediaWiki (opcional): ",

        # Downloader
        "dl_banner": "INICIANDO SINCRONIZACIÓN DESDE MEDIAWIKI (MODO INCREMENTAL CONCURRENTE)",
        "dl_dest_dir": "Directorio de destino: {dir}",
        "dl_threads": "Hilos de descarga:     {threads}",
        "dl_step1": "\n1/4. Obteniendo catálogo de artículos remotos...",
        "dl_no_articles": "[AVISO] No se han encontrado artículos en la MediaWiki.",
        "dl_articles_found": "Localizados {count} artículos en la wiki.",
        "dl_step2": "2/4. Verificando revisiones en el servidor para detectar cambios...",
        "dl_catalog_status": "Estado del catálogo:",
        "dl_up_to_date": "   - Artículos al día en local: {count}",
        "dl_pending": "   - Artículos nuevos o con cambios: {count}",
        "dl_disambiguated": "   - Artículos desambiguados por colisión de títulos: {count}",
        "dl_step3": "\n3/4. Descargando {count} artículos con {threads} hilos...",
        "dl_article_downloaded": "  [{idx}/{total}] Descargado: {title} ({size} KB)",
        "dl_empty_detected": "  [AVISO] Página vacía detectada: '{title}'",
        "dl_article_error": "  [ERROR] Fallo en '{title}': {error}",
        "dl_step4": "\n--- 4/4. Verificando catálogo de imágenes...",
        "dl_total_images": "Total imágenes en wiki: {total} | Pendientes de descarga: {pending}",
        "dl_downloading_images": "Descargando {count} imágenes concurrentemente...",
        "dl_images_progress": "  Progreso de imágenes: {idx}/{total} ({saved} guardadas)",
        "dl_images_failed": "\n  [AVISO] {count} imágenes no pudieron descargarse.",
        "dl_images_sample_errors": "  Detalle de fallos detectados (muestra representativa):",
        "dl_image_error_item": "    • Archivo '{name}': {reason}",
        "dl_index_title": "# INDICE GENERAL DE LA MEDIAWIKI\n\n",
        "dl_index_last_update": "Última actualización: {date}\n",
        "dl_index_total": "Total de artículos indexados: {total}\n\n",
        "dl_index_th_title": "Título del Artículo",
        "dl_index_th_file": "Archivo Local",
        "dl_index_th_size": "Tamaño",
        "dl_success_banner": "SINCRONIZACIÓN FINALIZADA CON ÉXITO",
        "dl_summary_time": "Tiempo total:                      {time:.1f} segundos",
        "dl_summary_new": "Artículos nuevos / actualizados:   {count}",
        "dl_summary_kept": "Artículos conservados sin cambios: {count}",
        "dl_summary_empty": "Páginas vacías gestionadas:        {count}",
        "dl_summary_errors": "Errores en artículos:              {count}",
        "dl_summary_index": "Índice actualizado:                {path}",

        # Uploader
        "up_banner": "INICIANDO SUBIDA DE CAMBIOS A MEDIAWIKI",
        "up_target_server": "Servidor destino:   {url}",
        "up_source_dir": "Directorio origen:  {dir}",
        "up_dry_run_banner": "[MODO DRY-RUN] Simulación activa. No se aplicarán cambios reales.",
        "up_file_not_found": "[ERROR] El archivo especificado no existe: {path}",
        "up_dir_not_found": "[ERROR] El directorio {dir} no existe.",
        "up_everything_up_to_date": "\n[OK] Todo está al día. No se detectaron modificaciones locales pendientes de subida.",
        "up_pending_items": "\nElementos pendientes de publicación:",
        "up_pending_md": "   - Artículos Markdown (.md): {count}",
        "up_pending_media": "   - Archivos multimedia:       {count}",
        "up_step1_images": "\n[1/2] Subiendo imágenes / multimedia...",
        "up_uploading_image": "  Subiendo imagen '{name}'...",
        "up_dry_run_simulated": " [DRY-RUN Simulado]",
        "up_step2_articles": "\n[2/2] Procesando y publicando artículos...",
        "up_publishing_article": "  Publicando '{title}' (desde {file})...",
        "up_no_change": " [SIN CAMBIOS] El contenido ya es idéntico en el servidor",
        "up_published_ok": " [OK] Publicado (Revisión #{rev})",
        "up_diff_preview": "\n[PREVISUALIZACION] Wikitext generado para {file}:",
        "up_diff_more_lines": "   | ... ({count} líneas más)",
        "up_conflict_detected": "\n  [CONFLICTO] La página '{title}' fue modificada en el servidor remoto.",
        "up_backup_saved": "  [COPIA SEGURIDAD] Versión remota guardada en: {path}",
        "up_prompt_force_conflict": "  ¿Deseas sobreescribir la versión remota y forzar la subida de '{file}'? [s/N]: ",
        "up_autoconfirm": "  [AUTO-CONFIRM] Forzando subida por parámetro explícito.",
        "up_non_interactive_warning": "  [AVISO] Sesión no interactiva detectada. No es posible solicitar confirmación por consola.",
        "up_user_cancelled": "\n  Operación cancelada por el usuario.",
        "up_forcing_upload": "  [FORZANDO] Sobreescribiendo '{title}' en el servidor...",
        "up_force_published_ok": " [OK] Publicado de forma forzada (Revisión #{rev})",
        "up_force_failed": " [ERROR] No se pudo forzar la publicación: {err}",
        "up_skipped_conflict": "  [OMITIDO] Se conserva la versión del servidor. Revisa el archivo de respaldo: {file}.servidor.conflict",
        "up_summary_banner": "RESUMEN DE LA SUBIDA (--upload)",
        "up_summary_success": "Artículos actualizados con éxito: {count}",
        "up_summary_nochange": "Artículos sin diferencias:        {count}",
        "up_summary_conflicts": "Conflictos detectados:            {count}",
        "up_summary_errors": "Errores en la publicación:        {count}",

        # Empty pages
        "empty_page_delete_reason": "Página vacía eliminada por mediawiki_sync",
        "empty_deleted_remote_ok": "Eliminada con éxito del servidor remoto.",
        "empty_non_interactive_notice": "\n[AVISO] Ejecución no interactiva detectada. Las páginas vacías se registrarán como omitidas.",
        "empty_banner": "CONTROL DE PÁGINAS VACÍAS DETECTADAS",
        "empty_detected_count": "Se han detectado {count} página(s) sin contenido en la MediaWiki:",
        "empty_menu_title": "\n¿Qué acción deseas realizar?",
        "empty_menu_opt1": "   [1] Crear archivos .md locales (plantilla vacía con metadatos para rellenar)",
        "empty_menu_opt2": "   [2] Eliminar las páginas del servidor remoto MediaWiki (action=delete)",
        "empty_menu_opt3": "   [3] Omitir / Ignorar por ahora (no descargar ni volver a reportar error)",
        "empty_prompt_option": "\nSelecciona una opción [1/2/3] (por defecto 3): ",
        "empty_creating_templates": "\nCreando plantillas Markdown locales para {count} páginas...",
        "empty_template_created": "   [CREADO] '{file}' listo para rellenar ({bytes} bytes).",
        "empty_prompt_confirm_delete": "\n¿Confirmas que deseas ELIMINAR {count} página(s) en la MediaWiki? (s/N): ",
        "empty_delete_cancelled": "   Operación de borrado cancelada. Las páginas quedan registradas como omitidas.",
        "empty_deleting_remote": "\nEliminando {count} página(s) del servidor MediaWiki...",
        "empty_remote_deleted_ok": "   [BORRADO REMOTO] '{title}': {msg}",
        "empty_remote_delete_error": "   [ERROR AL BORRAR] '{title}': {msg}",
        "empty_recording_skipped": "\nRegistrando {count} página(s) como omitidas...",
        "empty_recorded_skipped": "   [OMITIDA] '{title}' registrada como omitida (se ignorará en futuras descargas).",
        "empty_registry_banner": "REGISTRO DE PÁGINAS VACÍAS LOCAL (.sync_state.json)",
        "empty_directory": "Directorio: {dir}",
        "empty_none_registered": "\nNo hay ninguna página vacía registrada en el estado local.",
        "empty_total_registered": "\nTotal de páginas vacías registradas: {count}\n",
        "empty_th_title": "Título",
        "empty_th_file": "Archivo",
        "empty_th_status": "Estado",
        "empty_th_revid": "Revid",
        "empty_count_skipped": "\nHay {count} página(s) con estado 'omitida'.",
        "empty_none_pending": "\nNo hay páginas omitidas pendientes de acción.",

        # Sanitizer
        "san_dir_not_found": "[ERROR] El directorio {dir} no existe.",
        "san_starting": "[INFO] Iniciando saneamiento de {total} archivos Markdown en {dir}...",
        "san_error_file": "[AVISO] Error procesando {file}: {err}",
        "san_finished": "[OK] Saneamiento finalizado: {mod} de {total} archivos fueron limpiados y corregidos.",

        # Client
        "client_error_get_articles": "[AVISO] Error al obtener artículos: {err}",
        "client_error_batch_revs": "[AVISO] Error consultando lote de revisiones: {err}",
        "client_error_image_catalog": "[AVISO] Error consultando catálogo de imágenes: {err}",

        # State
        "state_read_error": "[AVISO] Al leer estado ({path}): {err}",
        "state_save_error": "[AVISO] No se pudo guardar el archivo de estado: {err}",
    },
    "en": {
        # CLI general
        "cli_desc": "Comprehensive native Python synchronizer for MediaWiki <-> Markdown, multithreaded and incremental.",
        "cli_epilog": """Usage examples:
  # 1. Incremental sync (downloads only new/modified pages with 8 threads):
  mw-sync

  # 2. Sanitize and clean existing Markdown files (removes [edit], TOC, and ****):
  mw-sync --sanitize

  # 3. Preview pending wiki uploads using diff:
  mw-sync --upload --diff --dry-run

  # 4. Upload local changes to MediaWiki:
  mw-sync --upload

  # 5. Upload a specific article or multimedia file:
  mw-sync --upload --file ./wiki_docs/User_Manual.md

  # 6. Change output language to Spanish:
  mw-sync --lang es
""",
        # CLI flags
        "help_download": "Incremental download mode (default): Synchronizes from MediaWiki to Markdown.",
        "help_upload": "Upload mode: Publishes local changes or new articles to MediaWiki.",
        "help_sanitize": "Sanitizes all local .md files removing [edit], TOC, and broken artifacts.",
        "help_diff": "Shows Wikitext difference preview before uploading.",
        "help_dry_run": "Simulates operation without writing to disk or modifying the server.",
        "help_force": "Forces full download or upload of all items.",
        "help_yes": "Automatically answers 'yes' to interactive confirmations (e.g. force conflict resolution or deletion).",
        "help_empty_pages": "Lists and manages empty pages recorded in local state (.sync_state.json).",
        "help_empty_action": "Action for detected empty pages: ask (prompt), create-md (create .md), delete-remote (delete from wiki), ignore (skip).",
        "help_threads": "Number of concurrent threads for download (default: {threads})",
        "help_url": "MediaWiki api.php endpoint (default: value of MW_URL or https://wiki.example.com/api.php).",
        "help_user": "Username for HTTP Basic Auth / MediaWiki (legacy).",
        "help_password": "Password for HTTP Basic Auth / MediaWiki (legacy).",
        "help_http_user": "Username for Apache / HTTP Basic Auth authentication.",
        "help_http_password": "Password for Apache / HTTP Basic Auth authentication.",
        "help_wiki_user": "MediaWiki username (Action API).",
        "help_wiki_password": "MediaWiki password.",
        "help_verify_ssl": "Enables strict SSL certificate verification.",
        "help_ca_bundle": "Path to CA Bundle file (.crt/.pem) to securely validate SSL.",
        "help_dir": "Local documentation directory (default: {output_dir})",
        "help_file": "Specifies a single .md or multimedia file to upload.",
        "help_no_images": "Ignores synchronization of multimedia files.",
        "help_include_redirects": "Includes MediaWiki redirect pages in synchronization (omitted by default).",
        "help_summary": "Summary message for MediaWiki revision history.",
        "help_lang": "Console interface and message language: es (Spanish), en (English).",
        "help_version": "Show program's version number and exit.",

        # CLI runtime
        "cli_header": "MEDIAWIKI SYNC 3.0 (Markdown <-> Wikitext)",
        "cli_server": "Server:       {url}",
        "cli_web_user": "Web User:     {user}",
        "cli_wiki_user": "Wiki User:    {user}",
        "none": "(none)",
        "anonymous": "(anonymous)",
        "dry_run_notice": "Simulation mode (--dry-run) active: Safe offline execution without network calls.",
        "conn_error": "Connection error to server: {sitename}\nCheck the endpoint URL, .env credentials, or network access.",
        "conn_success": "Connection successfully established with '{sitename}'",
        "auth_error": "MediaWiki authentication error: {msg}",
        "upload_cancelled_no_auth": "Operation cancelled: Cannot publish content without logging in to MediaWiki.",
        "anon_upload_warning": "Notice: No MediaWiki credentials configured (MW_WIKI_USER / MW_WIKI_PASS).\nPublishing will be attempted as an anonymous user and may be rejected.",
        "updating_hashes": "Updating hash registry in .sync_state.json...",
        "hashes_updated": "Hashes updated.",

        # Config
        "env_read_warning": "[WARNING] Reading {path}: {err}",
        "prompt_http_user": "Enter Apache/HTTP username (optional): ",
        "prompt_http_pass": "Enter Apache/HTTP password (optional): ",
        "prompt_wiki_user": "Enter MediaWiki username (optional): ",
        "prompt_wiki_pass": "Enter MediaWiki password (optional): ",

        # Downloader
        "dl_banner": "STARTING SYNCHRONIZATION FROM MEDIAWIKI (INCREMENTAL CONCURRENT MODE)",
        "dl_dest_dir": "Destination directory: {dir}",
        "dl_threads": "Download threads:      {threads}",
        "dl_step1": "\n1/4. Fetching remote article catalog...",
        "dl_no_articles": "[WARNING] No articles found in MediaWiki.",
        "dl_articles_found": "Found {count} articles in the wiki.",
        "dl_step2": "2/4. Checking server revisions to detect changes...",
        "dl_catalog_status": "Catalog status:",
        "dl_up_to_date": "   - Articles up to date locally: {count}",
        "dl_pending": "   - New or modified articles: {count}",
        "dl_disambiguated": "   - Articles disambiguated due to title collision: {count}",
        "dl_step3": "\n3/4. Downloading {count} articles with {threads} threads...",
        "dl_article_downloaded": "  [{idx}/{total}] Downloaded: {title} ({size} KB)",
        "dl_empty_detected": "  [WARNING] Empty page detected: '{title}'",
        "dl_article_error": "  [ERROR] Failed on '{title}': {error}",
        "dl_step4": "\n--- 4/4. Checking image catalog...",
        "dl_total_images": "Total images in wiki: {total} | Pending download: {pending}",
        "dl_downloading_images": "Downloading {count} images concurrently...",
        "dl_images_progress": "  Image progress: {idx}/{total} ({saved} saved)",
        "dl_images_failed": "\n  [WARNING] {count} images could not be downloaded.",
        "dl_images_sample_errors": "  Failure details (sample):",
        "dl_image_error_item": "    • File '{name}': {reason}",
        "dl_index_title": "# GENERAL MEDIAWIKI INDEX\n\n",
        "dl_index_last_update": "Last update: {date}\n",
        "dl_index_total": "Total indexed articles: {total}\n\n",
        "dl_index_th_title": "Article Title",
        "dl_index_th_file": "Local File",
        "dl_index_th_size": "Size",
        "dl_success_banner": "SYNCHRONIZATION COMPLETED SUCCESSFULLY",
        "dl_summary_time": "Total time:                        {time:.1f} seconds",
        "dl_summary_new": "New / updated articles:            {count}",
        "dl_summary_kept": "Articles kept without changes:     {count}",
        "dl_summary_empty": "Empty pages managed:               {count}",
        "dl_summary_errors": "Article errors:                    {count}",
        "dl_summary_index": "Index updated:                     {path}",

        # Uploader
        "up_banner": "STARTING UPLOAD OF CHANGES TO MEDIAWIKI",
        "up_target_server": "Target server:     {url}",
        "up_source_dir": "Source directory:  {dir}",
        "up_dry_run_banner": "[DRY-RUN MODE] Simulation active. No real changes will be applied.",
        "up_file_not_found": "[ERROR] Specified file does not exist: {path}",
        "up_dir_not_found": "[ERROR] Directory {dir} does not exist.",
        "up_everything_up_to_date": "\n[OK] Everything is up to date. No pending local modifications detected for upload.",
        "up_pending_items": "\nPending items for publication:",
        "up_pending_md": "   - Markdown articles (.md): {count}",
        "up_pending_media": "   - Multimedia files:        {count}",
        "up_step1_images": "\n[1/2] Uploading images / multimedia...",
        "up_uploading_image": "  Uploading image '{name}'...",
        "up_dry_run_simulated": " [DRY-RUN Simulated]",
        "up_step2_articles": "\n[2/2] Processing and publishing articles...",
        "up_publishing_article": "  Publishing '{title}' (from {file})...",
        "up_no_change": " [NO CHANGE] Content is already identical on the server",
        "up_published_ok": " [OK] Published (Revision #{rev})",
        "up_diff_preview": "\n[PREVIEW] Wikitext generated for {file}:",
        "up_diff_more_lines": "   | ... ({count} more lines)",
        "up_conflict_detected": "\n  [CONFLICT] Page '{title}' was modified on the remote server.",
        "up_backup_saved": "  [BACKUP] Remote version saved at: {path}",
        "up_prompt_force_conflict": "  Do you want to overwrite the remote version and force upload of '{file}'? [y/N]: ",
        "up_autoconfirm": "  [AUTO-CONFIRM] Forcing upload due to explicit parameter.",
        "up_non_interactive_warning": "  [WARNING] Non-interactive session detected. Cannot request console confirmation.",
        "up_user_cancelled": "\n  Operation cancelled by user.",
        "up_forcing_upload": "  [FORCING] Overwriting '{title}' on server...",
        "up_force_published_ok": " [OK] Force published (Revision #{rev})",
        "up_force_failed": " [ERROR] Could not force publication: {err}",
        "up_skipped_conflict": "  [SKIPPED] Keeping server version. Check backup file: {file}.servidor.conflict",
        "up_summary_banner": "UPLOAD SUMMARY (--upload)",
        "up_summary_success": "Articles successfully updated: {count}",
        "up_summary_nochange": "Articles without differences:     {count}",
        "up_summary_conflicts": "Conflicts detected:               {count}",
        "up_summary_errors": "Publication errors:               {count}",

        # Empty pages
        "empty_page_delete_reason": "Empty page deleted by mediawiki_sync",
        "empty_deleted_remote_ok": "Successfully deleted from remote server.",
        "empty_non_interactive_notice": "\n[WARNING] Non-interactive session detected. Empty pages will be recorded as skipped.",
        "empty_banner": "CONTROL OF DETECTED EMPTY PAGES",
        "empty_detected_count": "Detected {count} page(s) without content on MediaWiki:",
        "empty_menu_title": "\nWhat action do you want to perform?",
        "empty_menu_opt1": "   [1] Create local .md files (empty template with metadata to fill in)",
        "empty_menu_opt2": "   [2] Delete pages from remote MediaWiki server (action=delete)",
        "empty_menu_opt3": "   [3] Skip / Ignore for now (do not download or report error again)",
        "empty_prompt_option": "\nSelect an option [1/2/3] (default 3): ",
        "empty_creating_templates": "\nCreating local Markdown templates for {count} pages...",
        "empty_template_created": "   [CREATED] '{file}' ready to fill in ({bytes} bytes).",
        "empty_prompt_confirm_delete": "\nConfirm that you want to DELETE {count} page(s) on MediaWiki? (y/N): ",
        "empty_delete_cancelled": "   Deletion cancelled. Pages recorded as skipped.",
        "empty_deleting_remote": "\nDeleting {count} page(s) from MediaWiki server...",
        "empty_remote_deleted_ok": "   [REMOTE DELETED] '{title}': {msg}",
        "empty_remote_delete_error": "   [DELETE ERROR] '{title}': {msg}",
        "empty_recording_skipped": "\nRecording {count} page(s) as skipped...",
        "empty_recorded_skipped": "   [SKIPPED] '{title}' recorded as skipped (will be ignored in future downloads).",
        "empty_registry_banner": "LOCAL EMPTY PAGES REGISTRY (.sync_state.json)",
        "empty_directory": "Directory: {dir}",
        "empty_none_registered": "\nNo empty pages recorded in local state.",
        "empty_total_registered": "\nTotal empty pages recorded: {count}\n",
        "empty_th_title": "Title",
        "empty_th_file": "File",
        "empty_th_status": "Status",
        "empty_th_revid": "Revid",
        "empty_count_skipped": "\nThere are {count} page(s) with status 'skipped'.",
        "empty_none_pending": "\nNo skipped pages pending action.",

        # Sanitizer
        "san_dir_not_found": "[ERROR] Directory {dir} does not exist.",
        "san_starting": "[INFO] Starting sanitization of {total} Markdown files in {dir}...",
        "san_error_file": "[WARNING] Error processing {file}: {err}",
        "san_finished": "[OK] Sanitization completed: {mod} of {total} files were cleaned and fixed.",

        # Client
        "client_error_get_articles": "[WARNING] Error fetching articles: {err}",
        "client_error_batch_revs": "[WARNING] Error querying revision batch: {err}",
        "client_error_image_catalog": "[WARNING] Error querying image catalog: {err}",

        # State
        "state_read_error": "[WARNING] Reading state ({path}): {err}",
        "state_save_error": "[WARNING] Could not save state file: {err}",
    }
}


def detectar_idioma_sistema() -> str:
    """Detecta el idioma preferido del entorno del sistema operativo."""
    env_lang = os.getenv("MW_LANG")
    if env_lang:
        code = env_lang.strip().lower()[:2]
        if code in IDIOMAS_SOPORTADOS:
            return code

    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.getenv(var)
        if val:
            code = val.strip().lower()[:2]
            if code in IDIOMAS_SOPORTADOS:
                return code

    try:
        loc = locale.getlocale()[0]
        if loc:
            code = loc.strip().lower()[:2]
            if code in IDIOMAS_SOPORTADOS:
                return code
    except Exception:
        pass

    return IDIOMA_POR_DEFECTO


def set_language(lang: str) -> str:
    """Establece el idioma activo para las traducciones ('es' o 'en')."""
    global _IDIOMA_ACTUAL
    if not lang:
        _IDIOMA_ACTUAL = IDIOMA_POR_DEFECTO
        return _IDIOMA_ACTUAL

    code = lang.strip().lower()[:2]
    if code in IDIOMAS_SOPORTADOS:
        _IDIOMA_ACTUAL = code
    else:
        _IDIOMA_ACTUAL = IDIOMA_POR_DEFECTO
    return _IDIOMA_ACTUAL


def get_language() -> str:
    """Devuelve el código del idioma activo ('es' o 'en')."""
    return _IDIOMA_ACTUAL


def is_spanish() -> bool:
    return _IDIOMA_ACTUAL == "es"


def is_english() -> bool:
    return _IDIOMA_ACTUAL == "en"


def init_language(cli_lang: str = None) -> str:
    """Inicializa el idioma resolviendo CLI -> MW_LANG -> entorno de sistema -> por defecto."""
    if cli_lang and cli_lang.strip().lower()[:2] in IDIOMAS_SOPORTADOS:
        return set_language(cli_lang)
    return set_language(detectar_idioma_sistema())


def t(clave: str, **kwargs) -> str:
    """
    Obtiene la cadena traducida para la clave en el idioma actual.
    Si falta en el idioma actual, busca en español como respaldo.
    Acepta parámetros de interpolación estilo format (**kwargs).
    """
    catalogo_actual = TRANSLATIONS.get(_IDIOMA_ACTUAL, TRANSLATIONS[IDIOMA_POR_DEFECTO])
    texto = catalogo_actual.get(clave)

    if texto is None:
        texto = TRANSLATIONS[IDIOMA_POR_DEFECTO].get(clave, clave)

    if kwargs:
        try:
            return texto.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            return texto

    return texto


# Alias canónico
_ = t


def parse_bool_response(respuesta: str) -> bool | None:
    """Interpreta respuestas afirmativas o negativas en español o inglés."""
    if not respuesta:
        return None
    r = respuesta.strip().lower()
    if r in ("s", "si", "sí", "y", "yes", "true", "1"):
        return True
    if r in ("n", "no", "false", "0"):
        return False
    return None
