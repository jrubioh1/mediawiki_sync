"""
Módulo de descarga incremental y concurrente (MediaWiki -> Markdown + Imágenes).
Usa ThreadPoolExecutor para paralelizar descargas y detección por revision ID (revid).
"""
import os
import time
import threading
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from mw_sync.client import MediaWikiClient
from mw_sync.state import SyncState, calcular_sha256
from mw_sync.converters.html_to_md import html_a_markdown, sanitizar_nombre_archivo


def ejecutar_descarga(cliente: MediaWikiClient, output_dir: str, forzar: bool = False,
                      no_imagenes: bool = False, max_hilos: int = 8):
    """
    Descarga o actualiza de manera incremental todos los artículos e imágenes de la MediaWiki.
    """
    print("\n" + "=" * 75)
    print("INICIANDO SINCRONIZACIÓN DESDE MEDIAWIKI (MODO INCREMENTAL CONCURRENTE)")
    print(f"Directorio de destino: {os.path.abspath(output_dir)}")
    print(f"Hilos de descarga:     {max_hilos}")
    print("=" * 75)

    os.makedirs(output_dir, exist_ok=True)
    images_dir = os.path.join(output_dir, "images")
    if not no_imagenes:
        os.makedirs(images_dir, exist_ok=True)

    ruta_estado = os.path.join(output_dir, ".sync_state.json")
    estado = SyncState(ruta_estado)
    lock_estado = threading.Lock()

    t_inicio = time.time()

    # 1. Obtener catálogo de artículos
    print("\n1/4. Obteniendo catálogo de artículos remotos...")
    titulos = cliente.obtener_lista_paginas()
    if not titulos:
        print("[AVISO] No se han encontrado artículos en la MediaWiki.")
        return

    print(f"Localizados {len(titulos)} artículos en la wiki.")

    # 2. Consultar revisiones remotas por lotes (50 por llamada) para comparación incremental
    print("2/4. Verificando revisiones en el servidor para detectar cambios...")
    revisiones_remotas = cliente.obtener_revisiones_lote(titulos)

    articulos_pendientes = []
    articulos_actualizados_locales = []

    for titulo in titulos:
        nombre_archivo = f"{sanitizar_nombre_archivo(titulo)}.md"
        ruta_archivo = os.path.join(output_dir, nombre_archivo)
        rev_remota = revisiones_remotas.get(titulo, {}).get("revid", 0)
        rev_local = estado.obtener_revid(nombre_archivo)

        existe_local = os.path.isfile(ruta_archivo) and os.path.getsize(ruta_archivo) > 50

        # Si forzar está activo, o no existe local, o la revisión remota es más nueva
        if forzar or not existe_local or (rev_remota > 0 and rev_remota != rev_local):
            articulos_pendientes.append((titulo, nombre_archivo, ruta_archivo, rev_remota))
        else:
            tam = os.path.getsize(ruta_archivo)
            articulos_actualizados_locales.append((titulo, nombre_archivo, tam))

    print(f"Estado del catálogo:")
    print(f"   - Artículos al día en local: {len(articulos_actualizados_locales)}")
    print(f"   - Artículos nuevos o con cambios: {len(articulos_pendientes)}")

    # 3. Descarga concurrente de artículos pendientes
    art_descargados = 0
    art_errores = 0

    if articulos_pendientes:
        print(f"\n3/4. Descargando {len(articulos_pendientes)} artículos con {max_hilos} hilos...")

        def _descargar_un_articulo(item):
            t_art, nom_f, ruta_f, rev_esperada = item
            datos_pag = cliente.descargar_contenido_pagina(t_art)
            if not datos_pag or not datos_pag.get("html"):
                return False, t_art, nom_f, 0, "Error al descargar contenido"

            md_content, imgs_articulo = html_a_markdown(datos_pag["html"], t_art)
            if not md_content.strip():
                return False, t_art, nom_f, 0, "Contenido vacío"

            revid_final = datos_pag.get("revid") or rev_esperada
            fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            url_articulo = f"{cliente.base_url}/index.php?title={urllib.parse.quote(t_art)}"

            doc_md = (
                f"---\n"
                f"titulo: \"{t_art}\"\n"
                f"revid: {revid_final}\n"
                f"url: \"{url_articulo}\"\n"
                f"fecha_sincronizacion: \"{fecha_actual}\"\n"
                f"---\n\n"
                f"# {t_art}\n\n"
                f"{md_content}\n"
            )

            with open(ruta_f, "w", encoding="utf-8") as f:
                f.write(doc_md)

            tam_bytes = len(doc_md.encode("utf-8"))
            h_sha256 = calcular_sha256(ruta_f)

            with lock_estado:
                estado.registrar_articulo(nom_f, t_art, h_sha256, revid_final)

            return True, t_art, nom_f, tam_bytes, imgs_articulo

        with ThreadPoolExecutor(max_workers=max_hilos) as executor:
            futuros = [executor.submit(_descargar_un_articulo, it) for it in articulos_pendientes]
            for idx, fut in enumerate(as_completed(futuros), 1):
                exito, t_art, nom_f, tam, extra = fut.result()
                if exito:
                    art_descargados += 1
                    articulos_actualizados_locales.append((t_art, nom_f, tam))
                    if idx % 10 == 0 or idx == len(articulos_pendientes):
                        print(f"  [{idx}/{len(articulos_pendientes)}] Descargado: {t_art} ({tam // 1024 + 1} KB)")
                else:
                    art_errores += 1
                    print(f"  [ERROR] Fallo en '{t_art}': {extra}")

    # 4. Descarga de imágenes
    if not no_imagenes:
        print("\n--- 4/4. Verificando catálogo de imágenes...")
        lista_imagenes = cliente.obtener_catalogo_imagenes()
        imagenes_pendientes = []

        for img in lista_imagenes:
            nom = img.get("name")
            url = img.get("url")
            if not nom or not url:
                continue
            ruta_local = os.path.join(images_dir, nom)
            if forzar or not os.path.isfile(ruta_local) or os.path.getsize(ruta_local) == 0:
                imagenes_pendientes.append((nom, url, ruta_local))

        print(f"Total imágenes en wiki: {len(lista_imagenes)} | Pendientes de descarga: {len(imagenes_pendientes)}")

        if imagenes_pendientes:
            print(f"Descargando {len(imagenes_pendientes)} imágenes concurrentemente...")

            def _descargar_una_imagen(it):
                nom, url, ruta_local = it
                ok = cliente.descargar_archivo_binario(url, ruta_local)
                if ok and os.path.isfile(ruta_local):
                    h_sha = calcular_sha256(ruta_local)
                    with lock_estado:
                        estado.registrar_imagen(nom, h_sha)
                    return True, nom
                return False, nom

            with ThreadPoolExecutor(max_workers=max_hilos) as img_exec:
                fut_imgs = [img_exec.submit(_descargar_una_imagen, it) for it in imagenes_pendientes]
                for idx, f in enumerate(as_completed(fut_imgs), 1):
                    ok, nom = f.result()
                    if idx % 25 == 0 or idx == len(imagenes_pendientes):
                        print(f"  Imágenes descargadas: {idx}/{len(imagenes_pendientes)}")

    # 5. Generar / actualizar índice general
    ruta_indice = os.path.join(output_dir, "00_INDICE_MEDIAWIKI.md")
    articulos_actualizados_locales.sort(key=lambda x: x[0].lower())
    with open(ruta_indice, "w", encoding="utf-8") as f:
        f.write("# INDICE GENERAL DE LA MEDIAWIKI\n\n")
        f.write(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total de artículos indexados: {len(articulos_actualizados_locales)}\n\n")
        f.write("| Título del Artículo | Archivo Local | Tamaño |\n")
        f.write("| :--- | :--- | :--- |\n")
        for t, nom, tam in articulos_actualizados_locales:
            f.write(f"| {t} | [{nom}](./{nom}) | {tam // 1024 + 1} KB |\n")

    estado.guardar()

    duracion = time.time() - t_inicio
    print("\n" + "=" * 75)
    print("SINCRONIZACIÓN FINALIZADA CON ÉXITO")
    print(f"Tiempo total:                      {duracion:.1f} segundos")
    print(f"Artículos nuevos / actualizados:   {art_descargados}")
    print(f"Artículos conservados sin cambios: {len(articulos_actualizados_locales) - art_descargados}")
    print(f"Errores en artículos:              {art_errores}")
    print(f"Índice actualizado:                {os.path.abspath(ruta_indice)}")
    print("=" * 75)
