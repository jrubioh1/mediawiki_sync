"""
Módulo para el control y gestión de páginas vacías en MediaWiki Sync.
Permite registrar páginas sin contenido, crear plantillas Markdown locales
o eliminarlas del servidor remoto según las opciones del usuario.
"""
import os
import sys
import urllib.parse
from datetime import datetime
from mw_sync.client import MediaWikiClient
from mw_sync.state import SyncState, calcular_sha256
from mw_sync.i18n import _, parse_bool_response


def crear_plantilla_md_vacia(cliente: MediaWikiClient, estado: SyncState,
                             titulo: str, nombre_archivo: str, ruta_archivo: str,
                             revid: int) -> int:
    """
    Crea un archivo .md local con frontmatter y título, listo para ser rellenado por el usuario.
    """
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    url_articulo = f"{cliente.base_url}/index.php?title={urllib.parse.quote(titulo)}"
    doc_md = (
        f"---\n"
        f"titulo: \"{titulo}\"\n"
        f"revid: {revid}\n"
        f"url: \"{url_articulo}\"\n"
        f"fecha_sincronizacion: \"{fecha_actual}\"\n"
        f"---\n\n"
        f"# {titulo}\n\n"
    )

    os.makedirs(os.path.dirname(os.path.abspath(ruta_archivo)), exist_ok=True)
    with open(ruta_archivo, "w", encoding="utf-8") as f:
        f.write(doc_md)

    tam_bytes = len(doc_md.encode("utf-8"))
    h_sha256 = calcular_sha256(ruta_archivo)
    estado.registrar_articulo(nombre_archivo, titulo, h_sha256, revid)
    estado.registrar_pagina_vacia(titulo, nombre_archivo, revid, accion="creada_local")
    return tam_bytes


def eliminar_pagina_remota(cliente: MediaWikiClient, estado: SyncState,
                           titulo: str, nombre_archivo: str, ruta_archivo: str,
                           revid: int, motivo: str = None) -> tuple[bool, str]:
    """
    Elimina una página en el servidor remoto y actualiza el registro local.
    """
    motivo_efectivo = motivo if motivo is not None else _("empty_page_delete_reason")
    res = cliente.eliminar_pagina(titulo, motivo=motivo_efectivo)
    if res.get("exito"):
        estado.registrar_pagina_vacia(titulo, nombre_archivo, revid, accion="eliminada_remoto")
        if os.path.isfile(ruta_archivo):
            try:
                os.remove(ruta_archivo)
            except OSError:
                pass
        return True, _("empty_deleted_remote_ok")
    else:
        err = res.get("error", "Error desconocido")
        estado.registrar_pagina_vacia(titulo, nombre_archivo, revid, accion="omitida")
        return False, err


def omitir_pagina_vacia(estado: SyncState, titulo: str, nombre_archivo: str, revid: int):
    """
    Registra la página como omitida en el estado local para no repetir avisos ni errores.
    """
    estado.registrar_pagina_vacia(titulo, nombre_archivo, revid, accion="omitida")


def gestionar_paginas_vacias(cliente: MediaWikiClient, estado: SyncState,
                             output_dir: str, paginas_vacias: list,
                             accion: str = "ask",
                             articulos_actualizados_locales: list = None,
                             auto_confirmar: bool = False):
    """
    Gestiona el conjunto de páginas vacías detectadas según la acción solicitada.
    paginas_vacias: lista de tuplas (titulo, nombre_archivo, ruta_archivo, revid)
    """
    if not paginas_vacias:
        return

    sel = accion.lower().strip()
    if sel == "ask":
        if not sys.stdin.isatty():
            print(_("empty_non_interactive_notice"))
            sel = "ignore"
        else:
            print("\n" + "=" * 75)
            print(_("empty_banner"))
            print("=" * 75)
            print(_("empty_detected_count", count=len(paginas_vacias)))
            for t, f_name, _path, rev in paginas_vacias:
                print(f"   • {t} (revid: {rev})")

            print(_("empty_menu_title"))
            print(_("empty_menu_opt1"))
            print(_("empty_menu_opt2"))
            print(_("empty_menu_opt3"))

            try:
                resp = input(_("empty_prompt_option")).strip()
            except (EOFError, KeyboardInterrupt):
                resp = "3"

            if resp == "1":
                sel = "create-md"
            elif resp == "2":
                sel = "delete-remote"
            else:
                sel = "ignore"

    if sel in ("1", "create-md", "create"):
        print(_("empty_creating_templates", count=len(paginas_vacias)))
        for t, f_name, ruta_f, rev in paginas_vacias:
            tam = crear_plantilla_md_vacia(cliente, estado, t, f_name, ruta_f, rev)
            if articulos_actualizados_locales is not None:
                articulos_actualizados_locales.append((t, f_name, tam))
            print(_("empty_template_created", file=f_name, bytes=tam))

    elif sel in ("2", "delete-remote", "delete"):
        if not auto_confirmar and sys.stdin.isatty():
            try:
                conf = input(_("empty_prompt_confirm_delete", count=len(paginas_vacias))).strip()
            except (EOFError, KeyboardInterrupt):
                conf = "n"

            if parse_bool_response(conf) is not True:
                print(_("empty_delete_cancelled"))
                for t, f_name, _path, rev in paginas_vacias:
                    omitir_pagina_vacia(estado, t, f_name, rev)
                return

        print(_("empty_deleting_remote", count=len(paginas_vacias)))
        for t, f_name, ruta_f, rev in paginas_vacias:
            ok, msg = eliminar_pagina_remota(cliente, estado, t, f_name, ruta_f, rev)
            if ok:
                print(_("empty_remote_deleted_ok", title=t, msg=msg))
            else:
                print(_("empty_remote_delete_error", title=t, msg=msg))

    else:  # "3", "ignore", "omitir"
        print(_("empty_recording_skipped", count=len(paginas_vacias)))
        for t, f_name, _path, rev in paginas_vacias:
            omitir_pagina_vacia(estado, t, f_name, rev)
            print(_("empty_recorded_skipped", title=t))


def listar_y_gestionar_paginas_vacias(cliente: MediaWikiClient, output_dir: str,
                                      accion: str = "ask", auto_confirmar: bool = False):
    """
    Lista y permite gestionar las páginas vacías almacenadas en el estado local.
    """
    ruta_estado = os.path.join(output_dir, ".sync_state.json")
    estado = SyncState(ruta_estado)
    vacias = estado.obtener_paginas_vacias()

    print("\n" + "=" * 75)
    print(_("empty_registry_banner"))
    print(_("empty_directory", dir=os.path.abspath(output_dir)))
    print("=" * 75)

    if not vacias:
        print(_("empty_none_registered"))
        return

    print(_("empty_total_registered", count=len(vacias)))
    th_title = _("empty_th_title")
    th_file = _("empty_th_file")
    th_status = _("empty_th_status")
    th_revid = _("empty_th_revid")
    print(f"{th_title:<40} {th_file:<30} {th_status:<15} {th_revid:<8}")
    print("-" * 95)
    for t, info in sorted(vacias.items(), key=lambda x: x[0].lower()):
        f_name = info.get("archivo", "")
        est = info.get("accion", "pendiente")
        rev = str(info.get("revid", 0))
        print(f"{t:<40} {f_name:<30} {est:<15} {rev:<8}")

    # Filtrar las que están omitidas o pendientes de decisión
    candidatas = [
        (t, info["archivo"], os.path.join(output_dir, info["archivo"]), info.get("revid", 0))
        for t, info in vacias.items()
        if info.get("accion") == "omitida"
    ]

    if candidatas:
        print(_("empty_count_skipped", count=len(candidatas)))
        gestionar_paginas_vacias(
            cliente=cliente,
            estado=estado,
            output_dir=output_dir,
            paginas_vacias=candidatas,
            accion=accion,
            auto_confirmar=auto_confirmar
        )
        estado.guardar()
    else:
        print(_("empty_none_pending"))
