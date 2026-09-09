"""
Interfaz de Línea de Comandos (CLI) para MediaWiki Sync.
"""
import sys
import argparse
from mw_sync.config import DEFAULT_CONFIG, solicitar_credenciales_si_faltan, actualizar_config_desde_directorio
from mw_sync.client import MediaWikiClient
from mw_sync.downloader import ejecutar_descarga
from mw_sync.uploader import ejecutar_subida
from mw_sync.converters.sanitizer import sanear_directorio
from mw_sync.empty_pages import listar_y_gestionar_paginas_vacias
from mw_sync.state import SyncState


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Sincronizador integral MediaWiki <-> Markdown nativo en Python, multihilo e incremental.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
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
        """
    )

    # Modos principales
    parser.add_argument("--download", "-dl", action="store_true",
                        help="Modo descarga incremental (por defecto): Sincroniza desde MediaWiki a Markdown.")
    parser.add_argument("--upload", "-up", action="store_true",
                        help="Modo subida: Publica en MediaWiki los cambios o nuevos artículos locales.")
    parser.add_argument("--sanitize", action="store_true",
                        help="Sanea todos los archivos .md locales eliminando [editar], TOC y artefactos rotos.")
    parser.add_argument("--diff", action="store_true",
                        help="Muestra previsualización de diferencias de Wikitext antes de subir.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula la operación sin escribir en disco ni modificar el servidor.")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Fuerza la descarga o subida completa de todos los elementos.")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Responde 'sí' automáticamente a confirmaciones interactivas (ej. forzar resolución de conflicto o borrado).")
    parser.add_argument("--empty-pages", action="store_true",
                        help="Lista y gestiona las páginas vacías registradas en el estado local (.sync_state.json).")
    parser.add_argument("--empty-action", choices=["ask", "create-md", "delete-remote", "ignore"], default="ask",
                        help="Acción ante páginas vacías detectadas: ask (preguntar), create-md (crear .md), delete-remote (borrar de wiki), ignore (omitir).")

    # Rendimiento
    parser.add_argument("--threads", "-t", type=int, default=DEFAULT_CONFIG["THREADS"],
                        help=f"Número de hilos concurrentes para descarga (por defecto: {DEFAULT_CONFIG['THREADS']})")

    # Parámetros de red y autenticación
    parser.add_argument("--url", default=DEFAULT_CONFIG["MEDIAWIKI_URL"],
                        help="Endpoint api.php de la MediaWiki (por defecto: valor de MW_URL o https://wiki.example.com/api.php).")
    parser.add_argument("--user", "-u", default=DEFAULT_CONFIG["AUTH_USER"],
                        help="Usuario para HTTP Basic Auth / MediaWiki (legado).")
    parser.add_argument("--password", "-p", default=DEFAULT_CONFIG["AUTH_PASS"],
                        help="Contraseña para HTTP Basic Auth / MediaWiki (legado).")
    parser.add_argument("--http-user", default=DEFAULT_CONFIG["HTTP_USER"],
                        help="Usuario para autenticación Apache / HTTP Basic Auth.")
    parser.add_argument("--http-password", default=DEFAULT_CONFIG["HTTP_PASS"],
                        help="Contraseña para autenticación Apache / HTTP Basic Auth.")
    parser.add_argument("--wiki-user", default=DEFAULT_CONFIG["WIKI_USER"],
                        help="Usuario de la MediaWiki (Action API).")
    parser.add_argument("--wiki-password", default=DEFAULT_CONFIG["WIKI_PASS"],
                        help="Contraseña de la MediaWiki.")
    parser.add_argument("--verify-ssl", action="store_true", default=DEFAULT_CONFIG["VERIFY_SSL"],
                        help="Activa verificación estricta de certificados SSL.")
    parser.add_argument("--ca-bundle", default=DEFAULT_CONFIG["CA_BUNDLE"],
                        help="Ruta al archivo CA Bundle (.crt/.pem) para validar SSL de forma segura.")

    # Carpetas y ficheros
    parser.add_argument("--dir", "-o", default=DEFAULT_CONFIG["OUTPUT_DIR"],
                        help=f"Directorio local de documentación (por defecto: {DEFAULT_CONFIG['OUTPUT_DIR']})")
    parser.add_argument("--file", help="Especifica un único archivo .md o multimedia para subir.")
    parser.add_argument("--no-images", action="store_true",
                        help="Ignora la sincronización de archivos multimedia.")
    parser.add_argument("--summary", default=DEFAULT_CONFIG["EDIT_SUMMARY"],
                        help="Mensaje de resumen para el historial de revisiones de MediaWiki.")

    args = parser.parse_args(argv)

    # Resolver directorio de documentación y autodescubrir .env
    raw_args = argv if argv is not None else sys.argv[1:]
    dir_explicit = any(
        a.startswith("--dir") or a == "-o" or a.startswith("-o=") or a.startswith("--dir=")
        for a in raw_args
    )

    if dir_explicit and args.dir:
        dir_resuelto = actualizar_config_desde_directorio(args.dir)
        if dir_resuelto:
            args.dir = dir_resuelto
    else:
        dir_resuelto = actualizar_config_desde_directorio(None)
        if dir_resuelto:
            args.dir = dir_resuelto

    # Actualizar argumentos si no se proporcionaron explícitamente por CLI
    if not any(a.startswith("--url") for a in raw_args):
        args.url = DEFAULT_CONFIG["MEDIAWIKI_URL"]
    if not any(a.startswith("--http-user") for a in raw_args):
        args.http_user = DEFAULT_CONFIG["HTTP_USER"]
    if not any(a.startswith("--http-password") for a in raw_args):
        args.http_password = DEFAULT_CONFIG["HTTP_PASS"]
    if not any(a.startswith("--wiki-user") for a in raw_args):
        args.wiki_user = DEFAULT_CONFIG["WIKI_USER"]
    if not any(a.startswith("--wiki-password") for a in raw_args):
        args.wiki_password = DEFAULT_CONFIG["WIKI_PASS"]
    if not any(a.startswith("--user") or a.startswith("-u") for a in raw_args):
        args.user = DEFAULT_CONFIG["AUTH_USER"]
    if not any(a.startswith("--password") or a.startswith("-p") for a in raw_args):
        args.password = DEFAULT_CONFIG["AUTH_PASS"]
    if not any(a.startswith("--verify-ssl") for a in raw_args):
        args.verify_ssl = DEFAULT_CONFIG["VERIFY_SSL"]
    if not any(a.startswith("--ca-bundle") for a in raw_args):
        args.ca_bundle = DEFAULT_CONFIG["CA_BUNDLE"]
    if not any(a.startswith("--threads") or a == "-t" or a.startswith("-t=") or a.startswith("--threads=") for a in raw_args):
        args.threads = DEFAULT_CONFIG["THREADS"]
    if not any(a.startswith("--summary") for a in raw_args):
        args.summary = DEFAULT_CONFIG["EDIT_SUMMARY"]


    # Si se solicita modo saneamiento
    if args.sanitize:
        tot, mod = sanear_directorio(args.dir, dry_run=args.dry_run)
        if mod > 0 and not args.dry_run:
            print("Actualizando registro de hashes en .sync_state.json...")
            st = SyncState(f"{args.dir}/.sync_state.json")
            st.sincronizar_hashes_locales(args.dir)
            print("Hashes actualizados.")
        return

    # Solicitar credenciales interactivamente si no están configuradas ni en .env (solo en operaciones reales online)
    if not args.dry_run:
        http_user, http_pass, wiki_user, wiki_pass = solicitar_credenciales_si_faltan(
            user=args.http_user or args.user,
            password=args.http_password or args.password,
            wiki_user=args.wiki_user,
            wiki_password=args.wiki_password
        )
    else:
        http_user = args.http_user or args.user or DEFAULT_CONFIG["HTTP_USER"]
        http_pass = args.http_password or args.password or DEFAULT_CONFIG["HTTP_PASS"]
        wiki_user = args.wiki_user or DEFAULT_CONFIG["WIKI_USER"]
        wiki_pass = args.wiki_password or DEFAULT_CONFIG["WIKI_PASS"]

    cliente = MediaWikiClient(
        url=args.url,
        http_user=http_user,
        http_password=http_pass,
        wiki_user=wiki_user,
        wiki_password=wiki_pass,
        verify_ssl=args.verify_ssl,
        ca_bundle=args.ca_bundle
    )

    print("=" * 75)
    print("MEDIAWIKI SYNC 3.0 (Markdown <-> Wikitext)")
    print(f"Servidor:     {args.url}")
    print(f"Usuario Web:  {http_user if http_user else '(ninguno)'}")
    print(f"Usuario Wiki: {wiki_user if wiki_user else '(anónimo)'}")
    print("=" * 75)

    if args.dry_run:
        print("Modo simulación (--dry-run) activo: Ejecución segura offline sin llamadas de red.")
    else:
        ok, sitename = cliente.test_conexion()
        if not ok:
            print(f"Error de conexión al servidor: {sitename}")
            print("Comprueba la URL del endpoint, credenciales en .env o el acceso por red.")
            sys.exit(1)
        print(f"Conexión establecida con éxito a '{sitename}'")

        # Intentar inicio de sesión en MediaWiki si se proporcionan credenciales
        if wiki_user and wiki_pass:
            ok_login, msg_login = cliente.login()
            if not ok_login:
                print(f"Error de autenticación en MediaWiki: {msg_login}")
                if args.upload:
                    print("Operación cancelada: No se puede publicar contenido sin iniciar sesión en MediaWiki.")
                    sys.exit(1)
            else:
                print(f"{msg_login}")
        elif args.upload:
            print("Aviso: No se han configurado credenciales de MediaWiki (MW_WIKI_USER / MW_WIKI_PASS).")
            print("La publicación se intentará como usuario anónimo y podría ser rechazada.")

    if args.empty_pages:
        listar_y_gestionar_paginas_vacias(
            cliente=cliente,
            output_dir=args.dir,
            accion=args.empty_action,
            auto_confirmar=args.yes
        )
    elif args.upload:
        ejecutar_subida(
            cliente=cliente,
            output_dir=args.dir,
            archivo_especifico=args.file,
            forzar=args.force,
            dry_run=args.dry_run,
            mostrar_diff=args.diff,
            resumen_edicion=args.summary,
            auto_confirmar_conflicto=args.yes
        )
    else:
        ejecutar_descarga(
            cliente=cliente,
            output_dir=args.dir,
            forzar=args.force,
            no_imagenes=args.no_images,
            max_hilos=args.threads,
            empty_action=args.empty_action,
            auto_confirmar=args.yes
        )


if __name__ == "__main__":
    main()
