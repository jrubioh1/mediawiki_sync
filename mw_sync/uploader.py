"""
Módulo de subida de cambios (--upload) a MediaWiki.
Detecta modificaciones por hash SHA-256, genera Wikitext limpio,
emplea baserevid para prevenir conflictos y soporta resolución interactiva
de conflictos con confirmación por consola.
"""
import os
import sys
import re
import difflib
from mw_sync.client import MediaWikiClient
from mw_sync.state import SyncState, calcular_sha256
from mw_sync.config import DEFAULT_CONFIG
from mw_sync.converters.md_to_wikitext import markdown_a_wikitext, extraer_metadatos_frontmatter
from mw_sync.i18n import _, parse_bool_response


def extraer_titulo_de_archivo_md(ruta_archivo: str) -> str:
    """Extrae el título de la página desde frontmatter, primer h1 o nombre de archivo."""
    try:
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            contenido = f.read()

        meta, cuerpo = extraer_metadatos_frontmatter(contenido)
        if "titulo" in meta and meta["titulo"].strip():
            return meta["titulo"].strip()

        m_h1 = re.search(r'^#\s+(.+)$', cuerpo, flags=re.MULTILINE)
        if m_h1 and m_h1.group(1).strip():
            # Limpiar posible [editar]
            t = re.sub(r'\[editar.*?\]', '', m_h1.group(1)).strip()
            return t
    except Exception:
        pass

    base = os.path.basename(ruta_archivo)
    if base.endswith(".md"):
        base = base[:-3]
    return base.replace("_", " ")


def mostrar_diff_local(ruta_md: str, wikitext_generado: str):
    """Muestra una previsualización de cambios si existe información previa."""
    print(_("up_diff_preview", file=os.path.basename(ruta_md)))
    lineas = wikitext_generado.splitlines()
    for l in lineas[:25]:
        print(f"   | {l}")
    if len(lineas) > 25:
        print(_("up_diff_more_lines", count=len(lineas) - 25))


def ejecutar_subida(cliente: MediaWikiClient, output_dir: str, archivo_especifico: str = None,
                    forzar: bool = False, dry_run: bool = False, mostrar_diff: bool = False,
                    resumen_edicion: str = None, auto_confirmar_conflicto: bool = False):
    """
    Detecta cambios locales y los publica de forma segura en la MediaWiki.
    Permite resolución interactiva de conflictos con confirmación por consola.
    """
    print("\n" + "=" * 75)
    print(_("up_banner"))
    print(_("up_target_server", url=cliente.api_url))
    print(_("up_source_dir", dir=os.path.abspath(output_dir)))
    if dry_run:
        print(_("up_dry_run_banner"))
    print("=" * 75)

    ruta_estado = os.path.join(output_dir, ".sync_state.json")
    estado = SyncState(ruta_estado)
    resumen = resumen_edicion or DEFAULT_CONFIG["EDIT_SUMMARY"]

    archivos_a_subir = []
    imagenes_a_subir = []

    if archivo_especifico:
        ruta_abs = os.path.abspath(archivo_especifico)
        if not os.path.exists(ruta_abs):
            ruta_en_dir = os.path.join(output_dir, archivo_especifico)
            if os.path.exists(ruta_en_dir):
                ruta_abs = os.path.abspath(ruta_en_dir)
            else:
                print(_("up_file_not_found", path=ruta_abs))
                return

        if ruta_abs.endswith(".md"):
            archivos_a_subir.append(ruta_abs)
        else:
            imagenes_a_subir.append(ruta_abs)
    else:
        if not os.path.exists(output_dir):
            print(_("up_dir_not_found", dir=output_dir))
            return

        for f in os.listdir(output_dir):
            if f.endswith(".md") and not re.match(r'^\d{2}_INDICE', f):
                ruta_f = os.path.join(output_dir, f)
                hash_actual = calcular_sha256(ruta_f)
                hash_registrado = estado.obtener_hash(f)

                if forzar or not hash_registrado or hash_registrado != hash_actual:
                    archivos_a_subir.append(ruta_f)

        images_dir = os.path.join(output_dir, "images")
        if os.path.exists(images_dir):
            for img in os.listdir(images_dir):
                ruta_img = os.path.join(images_dir, img)
                if os.path.isfile(ruta_img):
                    hash_img = calcular_sha256(ruta_img)
                    hash_reg_img = estado.obtener_hash(img)
                    if forzar or not hash_reg_img or hash_reg_img != hash_img:
                        imagenes_a_subir.append(ruta_img)

    total_cambios = len(archivos_a_subir) + len(imagenes_a_subir)
    if total_cambios == 0:
        print(_("up_everything_up_to_date"))
        return

    print(_("up_pending_items"))
    print(_("up_pending_md", count=len(archivos_a_subir)))
    print(_("up_pending_media", count=len(imagenes_a_subir)))

    # 1. Subida de imágenes
    if imagenes_a_subir:
        print(_("up_step1_images"))
        for ruta_img in imagenes_a_subir:
            nom_img = os.path.basename(ruta_img)
            print(_("up_uploading_image", name=nom_img), end="", flush=True)

            if dry_run:
                print(_("up_dry_run_simulated"))
                continue

            res = cliente.subir_archivo(nom_img, ruta_img, comentario=resumen)
            if res.get("exito"):
                estado.registrar_imagen(nom_img, calcular_sha256(ruta_img))
                print(" [OK]")
            else:
                print(f" [ERROR] {res.get('error')}")

    # 2. Subida de artículos
    print(_("up_step2_articles"))
    exitos = 0
    fallos = 0
    conflictos = 0
    sin_cambios = 0

    for ruta_md in archivos_a_subir:
        nom_archivo = os.path.basename(ruta_md)
        titulo = extraer_titulo_de_archivo_md(ruta_md)

        with open(ruta_md, "r", encoding="utf-8") as f:
            contenido_md = f.read()

        wikitext = markdown_a_wikitext(contenido_md, dir_docs=output_dir)

        if mostrar_diff:
            mostrar_diff_local(ruta_md, wikitext)

        print(_("up_publishing_article", title=titulo, file=nom_archivo), end="", flush=True)

        if dry_run:
            print(_("up_dry_run_simulated"))
            exitos += 1
            continue

        base_rev = estado.obtener_revid(nom_archivo)
        if not base_rev:
            meta_front, _cuerpo = extraer_metadatos_frontmatter(contenido_md)
            if "revid" in meta_front:
                try:
                    base_rev = int(meta_front["revid"])
                except (ValueError, TypeError):
                    base_rev = 0

        res = cliente.editar_pagina(titulo, wikitext, resumen=resumen, baserevid=base_rev)

        if res.get("exito"):
            if res.get("nochange"):
                print(_("up_no_change"))
                sin_cambios += 1
            else:
                new_rev = res.get("newrevid", "N/A")
                print(_("up_published_ok", rev=new_rev))
                exitos += 1

            estado.registrar_articulo(nom_archivo, titulo, calcular_sha256(ruta_md), res.get("newrevid", base_rev))
        else:
            if res.get("conflict"):
                print(_("up_conflict_detected", title=titulo))
                # Descargar versión remota de salvaguarda
                datos_servidor = cliente.descargar_contenido_pagina(titulo)
                ruta_conflicto = None
                if datos_servidor and datos_servidor.get("html"):
                    ruta_conflicto = os.path.join(output_dir, f"{nom_archivo}.servidor.conflict")
                    with open(ruta_conflicto, "w", encoding="utf-8") as f_c:
                        f_c.write(datos_servidor["html"])
                    print(_("up_backup_saved", path=ruta_conflicto))

                # Solicitar confirmación interactiva para forzar la subida
                desea_forzar = False
                if auto_confirmar_conflicto:
                    desea_forzar = True
                    print(_("up_autoconfirm"))
                elif sys.stdin.isatty():
                    try:
                        pregunta = _("up_prompt_force_conflict", file=nom_archivo)
                        resp = input(pregunta)
                        if parse_bool_response(resp) is True:
                            desea_forzar = True
                    except (EOFError, KeyboardInterrupt):
                        print(_("up_user_cancelled"))
                        desea_forzar = False
                else:
                    print(_("up_non_interactive_warning"))

                if desea_forzar:
                    print(_("up_forcing_upload", title=titulo), end="", flush=True)
                    resumen_forzado = f"{resumen} (Subida forzada tras resolver conflicto)"
                    # Omitir baserevid (baserevid=0) para forzar la edición incondicional
                    res_forzado = cliente.editar_pagina(titulo, wikitext, resumen=resumen_forzado, baserevid=0)
                    if res_forzado.get("exito"):
                        new_rev = res_forzado.get("newrevid", "N/A")
                        print(_("up_force_published_ok", rev=new_rev))
                        exitos += 1
                        estado.registrar_articulo(nom_archivo, titulo, calcular_sha256(ruta_md), res_forzado.get("newrevid", base_rev))
                    else:
                        fallos += 1
                        print(_("up_force_failed", err=res_forzado.get('error')))
                else:
                    conflictos += 1
                    print(_("up_skipped_conflict", file=nom_archivo))
            else:
                fallos += 1
                print(f" [ERROR] {res.get('error')}")

    if not dry_run:
        estado.guardar()

    print("\n" + "=" * 75)
    print(_("up_summary_banner"))
    print(_("up_summary_success", count=exitos))
    print(_("up_summary_nochange", count=sin_cambios))
    print(_("up_summary_conflicts", count=conflictos))
    print(_("up_summary_errors", count=fallos))
    print("=" * 75)
