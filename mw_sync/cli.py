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
from mw_sync.i18n import _, init_language, set_language, get_language
from mw_sync import __version__


def main(argv=None):
    raw_args = argv if argv is not None else sys.argv[1:]

    # Detección temprana de idioma para --help y mensajes CLI
    cli_lang = None
    for i, a in enumerate(raw_args):
        if a.startswith("--lang="):
            cli_lang = a.split("=", 1)[1]
            break
        elif a in ("--lang", "-l") and i + 1 < len(raw_args):
            cli_lang = raw_args[i + 1]
            break
        elif a.startswith("-l="):
            cli_lang = a.split("=", 1)[1]
            break

    init_language(cli_lang or DEFAULT_CONFIG.get("LANG"))

    parser = argparse.ArgumentParser(
        description=_("cli_desc"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_("cli_epilog")
    )

    # Versión e Idioma
    parser.add_argument("--version", "-V", action="version",
                        version=f"%(prog)s {__version__}",
                        help=_("help_version"))
    parser.add_argument("--lang", "-l", choices=["es", "en"], default=get_language(),
                        help=_("help_lang"))

    # Modos principales
    parser.add_argument("--download", "-dl", action="store_true",
                        help=_("help_download"))
    parser.add_argument("--upload", "-up", action="store_true",
                        help=_("help_upload"))
    parser.add_argument("--sanitize", action="store_true",
                        help=_("help_sanitize"))
    parser.add_argument("--diff", action="store_true",
                        help=_("help_diff"))
    parser.add_argument("--dry-run", action="store_true",
                        help=_("help_dry_run"))
    parser.add_argument("--force", "-f", action="store_true",
                        help=_("help_force"))
    parser.add_argument("--yes", "-y", action="store_true",
                        help=_("help_yes"))
    parser.add_argument("--empty-pages", action="store_true",
                        help=_("help_empty_pages"))
    parser.add_argument("--empty-action", choices=["ask", "create-md", "delete-remote", "ignore"], default="ask",
                        help=_("help_empty_action"))

    # Rendimiento
    parser.add_argument("--threads", "-t", type=int, default=DEFAULT_CONFIG["THREADS"],
                        help=_("help_threads", threads=DEFAULT_CONFIG['THREADS']))

    # Parámetros de red y autenticación
    parser.add_argument("--url", default=DEFAULT_CONFIG["MEDIAWIKI_URL"],
                        help=_("help_url"))
    parser.add_argument("--user", "-u", default=DEFAULT_CONFIG["AUTH_USER"],
                        help=_("help_user"))
    parser.add_argument("--password", "-p", default=DEFAULT_CONFIG["AUTH_PASS"],
                        help=_("help_password"))
    parser.add_argument("--http-user", default=DEFAULT_CONFIG["HTTP_USER"],
                        help=_("help_http_user"))
    parser.add_argument("--http-password", default=DEFAULT_CONFIG["HTTP_PASS"],
                        help=_("help_http_password"))
    parser.add_argument("--wiki-user", default=DEFAULT_CONFIG["WIKI_USER"],
                        help=_("help_wiki_user"))
    parser.add_argument("--wiki-password", default=DEFAULT_CONFIG["WIKI_PASS"],
                        help=_("help_wiki_password"))
    parser.add_argument("--verify-ssl", action="store_true", default=DEFAULT_CONFIG["VERIFY_SSL"],
                        help=_("help_verify_ssl"))
    parser.add_argument("--ca-bundle", default=DEFAULT_CONFIG["CA_BUNDLE"],
                        help=_("help_ca_bundle"))

    # Carpetas y ficheros
    parser.add_argument("--dir", "-o", default=DEFAULT_CONFIG["OUTPUT_DIR"],
                        help=_("help_dir", output_dir=DEFAULT_CONFIG['OUTPUT_DIR']))
    parser.add_argument("--file", help=_("help_file"))
    parser.add_argument("--no-images", action="store_true",
                        help=_("help_no_images"))
    parser.add_argument("--include-redirects", action="store_true",
                        help=_("help_include_redirects"))
    parser.add_argument("--summary", default=DEFAULT_CONFIG["EDIT_SUMMARY"],
                        help=_("help_summary"))

    args = parser.parse_args(argv)

    if args.lang:
        set_language(args.lang)

    # Resolver directorio de documentación y autodescubrir .env
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

    # Si se detectó MW_LANG en el .env y no se pasó explícito en raw_args, sincronizar
    if not any(a.startswith("--lang") or a == "-l" or a.startswith("-l=") or a.startswith("--lang=") for a in raw_args):
        if DEFAULT_CONFIG.get("LANG"):
            set_language(DEFAULT_CONFIG["LANG"])

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
            print(_("updating_hashes"))
            st = SyncState(f"{args.dir}/.sync_state.json")
            st.sincronizar_hashes_locales(args.dir)
            print(_("hashes_updated"))
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
    print(_("cli_header"))
    print(_("cli_server", url=args.url))
    print(_("cli_web_user", user=http_user if http_user else _("none")))
    print(_("cli_wiki_user", user=wiki_user if wiki_user else _("anonymous")))
    print("=" * 75)

    if args.dry_run:
        print(_("dry_run_notice"))
    else:
        ok, sitename = cliente.test_conexion()
        if not ok:
            print(_("conn_error", sitename=sitename))
            sys.exit(1)
        print(_("conn_success", sitename=sitename))

        # Intentar inicio de sesión en MediaWiki si se proporcionan credenciales
        if wiki_user and wiki_pass:
            ok_login, msg_login = cliente.login()
            if not ok_login:
                print(_("auth_error", msg=msg_login))
                if args.upload:
                    print(_("upload_cancelled_no_auth"))
                    sys.exit(1)
            else:
                print(f"{msg_login}")
        elif args.upload:
            print(_("anon_upload_warning"))

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
            auto_confirmar=args.yes,
            incluir_redirecciones=args.include_redirects
        )


if __name__ == "__main__":
    main()
