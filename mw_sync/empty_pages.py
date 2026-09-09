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
                           revid: int) -> tuple[bool, str]:
    """
    Elimina una página en el servidor remoto y actualiza el registro local.
    """
    res = cliente.eliminar_pagina(titulo, motivo="Página vacía eliminada por mediawiki_sync")
    if res.get("exito"):
        estado.registrar_pagina_vacia(titulo, nombre_archivo, revid, accion="eliminada_remoto")
        if os.path.isfile(ruta_archivo):
            try:
                os.remove(ruta_archivo)
            except OSError:
                pass
        return True, "Eliminada con éxito del servidor remoto."
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
            print("\n[AVISO] Ejecución no interactiva detectada. Las páginas vacías se registrarán como omitidas.")
            sel = "ignore"
        else:
            print("\n" + "=" * 75)
            print("CONTROL DE PÁGINAS VACÍAS DETECTADAS")
            print("=" * 75)
            print(f"Se han detectado {len(paginas_vacias)} página(s) sin contenido en la MediaWiki:")
            for t, f_name, _, rev in paginas_vacias:
                print(f"   • {t} (revid: {rev})")

            print("\n¿Qué acción deseas realizar?")
            print("   [1] Crear archivos .md locales (plantilla vacía con metadatos para rellenar)")
            print("   [2] Eliminar las páginas del servidor remoto MediaWiki (action=delete)")
            print("   [3] Omitir / Ignorar por ahora (no descargar ni volver a reportar error)")

            try:
                resp = input("\nSelecciona una opción [1/2/3] (por defecto 3): ").strip()
            except (EOFError, KeyboardInterrupt):
                resp = "3"

            if resp == "1":
                sel = "create-md"
            elif resp == "2":
                sel = "delete-remote"
            else:
                sel = "ignore"

    if sel in ("1", "create-md", "create"):
        print(f"\nCreando plantillas Markdown locales para {len(paginas_vacias)} páginas...")
        for t, f_name, ruta_f, rev in paginas_vacias:
            tam = crear_plantilla_md_vacia(cliente, estado, t, f_name, ruta_f, rev)
            if articulos_actualizados_locales is not None:
                articulos_actualizados_locales.append((t, f_name, tam))
            print(f"   [CREADO] '{f_name}' listo para rellenar ({tam} bytes).")

    elif sel in ("2", "delete-remote", "delete"):
        if not auto_confirmar and sys.stdin.isatty():
            try:
                conf = input(f"\n¿Confirmas que deseas ELIMINAR {len(paginas_vacias)} página(s) en la MediaWiki? (s/N): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                conf = "n"

            if conf not in ("s", "si", "sí", "y", "yes"):
                print("   Operación de borrado cancelada. Las páginas quedan registradas como omitidas.")
                for t, f_name, _, rev in paginas_vacias:
                    omitir_pagina_vacia(estado, t, f_name, rev)
                return

        print(f"\nEliminando {len(paginas_vacias)} página(s) del servidor MediaWiki...")
        for t, f_name, ruta_f, rev in paginas_vacias:
            ok, msg = eliminar_pagina_remota(cliente, estado, t, f_name, ruta_f, rev)
            if ok:
                print(f"   [BORRADO REMOTO] '{t}': {msg}")
            else:
                print(f"   [ERROR AL BORRAR] '{t}': {msg}")

    else:  # "3", "ignore", "omitir"
        print(f"\nRegistrando {len(paginas_vacias)} página(s) como omitidas...")
        for t, f_name, _, rev in paginas_vacias:
            omitir_pagina_vacia(estado, t, f_name, rev)
            print(f"   [OMITIDA] '{t}' registrada como omitida (se ignorará en futuras descargas).")


def listar_y_gestionar_paginas_vacias(cliente: MediaWikiClient, output_dir: str,
                                      accion: str = "ask", auto_confirmar: bool = False):
    """
    Lista y permite gestionar las páginas vacías almacenadas en el estado local.
    """
    ruta_estado = os.path.join(output_dir, ".sync_state.json")
    estado = SyncState(ruta_estado)
    vacias = estado.obtener_paginas_vacias()

    print("\n" + "=" * 75)
    print("REGISTRO DE PÁGINAS VACÍAS LOCAL (.sync_state.json)")
    print(f"Directorio: {os.path.abspath(output_dir)}")
    print("=" * 75)

    if not vacias:
        print("\nNo hay ninguna página vacía registrada en el estado local.")
        return

    print(f"\nTotal de páginas vacías registradas: {len(vacias)}\n")
    print(f"{'Título':<40} {'Archivo':<30} {'Estado':<15} {'Revid':<8}")
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
        print(f"\nHay {len(candidatas)} página(s) con estado 'omitida'.")
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
        print("\nNo hay páginas omitidas pendientes de acción.")
