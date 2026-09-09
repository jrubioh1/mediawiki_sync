"""
Módulo de saneamiento y reparación de archivos Markdown existentes.
Limpia artefactos de [editar], corchetes rotos, asteriscos huérfanos (****),
y reescribe enlaces internos para navegación offline coherente.
"""
import os
import re
import urllib.parse
from mw_sync.converters.html_to_md import sanitizar_nombre_archivo, normalizar_enlace_wiki_a_md


def limpiar_contenido_markdown(contenido: str) -> tuple[str, bool]:
    """
    Sanea el texto Markdown de un archivo existente.
    Repara enlaces vacíos, desenvuelve imágenes locales, corrige negritas,
    elimina artefactos de plantillas y de edición, y normaliza enlaces internos.
    Devuelve (nuevo_contenido, ha_cambiado).
    """
    original = contenido

    # 1. Separar Frontmatter (si existe) para no tocar metadatos legítimos
    m_fm = re.match(r'^(\ufeff?---\s*\n.*?\n---\s*\n)', contenido, flags=re.DOTALL)
    if m_fm:
        frontmatter = m_fm.group(1)
        cuerpo = contenido[len(frontmatter):]
    else:
        frontmatter = ""
        cuerpo = contenido

    # 2. Desempaquetar imágenes locales envueltas en enlaces a /mediawiki/... o .md
    cuerpo = re.sub(r'\[(\!\[.*?\]\(.*?\))\]\(/mediawiki/index\.php/Archivo:[^\)]+\)', r'\1', cuerpo)
    cuerpo = re.sub(r'\[(\!\[.*?\]\(.*?\))\]\(/mediawiki/[^\)]+\)', r'\1', cuerpo)
    cuerpo = re.sub(r'\[(\!\[.*?\]\(.*?\))\]\(\./Archivo_[^\)]+\.md\)', r'\1', cuerpo)

    # 3. Eliminar texto residual de intranet en pies de fotos
    cuerpo = re.sub(r'(\!\[.*?\]\(.*?\))\s*Portal de entrada de la Intranet', r'\1', cuerpo)
    cuerpo = re.sub(r'Portal de entrada de la Intranet', '', cuerpo)

    # 4. Limpiar encabezados con fallos de redlinks y parámetros action=edit
    cuerpo = re.sub(r'^(#{1,6})\s*\[([^\]]+)\]\([^\)]*\)[^ \t\n]*', r'\1 \2', cuerpo, flags=re.MULTILINE)

    # 5. Limpiar encabezados que contengan [editar] o corchetes sobrantes
    def limpiar_encabezado(m):
        hashes = m.group(1)
        texto = m.group(2).strip()
        texto = re.sub(r'\*{2,}\s*$', '', texto)
        texto = re.sub(r'\[editar\]\([^\)]*\)\]*', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'\[.*?action=edit.*?\]\([^\)]*\)\]*', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'\([^\)]*action=edit[^\)]*\)\]*', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'\[editar.*?\]', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'\]+$', '', texto).strip()
        texto = re.sub(r'^\*\*\s*(.*?)\s*\*\*$', r'\1', texto).strip()
        texto = texto.replace('**', '').strip()
        return f"{hashes} {texto}"

    cuerpo = re.sub(r'^(#{1,6})\s+(.+)$', limpiar_encabezado, cuerpo, flags=re.MULTILINE)

    # 6. Eliminar secciones de sumario vacías consecutivas
    cuerpo = re.sub(r'(?:^###+\s+SUMARIO\s*$\n*)+', '', cuerpo, flags=re.MULTILINE)

    # 7. Corregir enlaces de TOC con paréntesis rotos
    cuerpo = re.sub(r'-\s*\[([0-9.]+\s+[a-zA-Z0-9]\)[^\]]+)\]\(#([a-zA-Z0-9])\)_([^\)]+)\)', r'- [\1](#\2_\3)', cuerpo)

    # 8. Reparar enlaces vacíos: [](url)
    def sustituir_enlace_vacio(m):
        target = m.group(1).strip()
        if not target:
            return ""

        # Anclas de año: #1993
        if re.match(r'^#\d{4}$', target):
            return f"[Año {target[1:]}]({target})"

        # Anclas de sección
        if target.startswith('#'):
            ancla = target[1:].replace('_', ' ').strip()
            return f"[{ancla}]({target})" if ancla else ""

        # URL externa
        if target.startswith(('http://', 'https://')):
            try:
                p = urllib.parse.urlparse(target)
                dom = p.netloc.lstrip('www.') or target
                return f"[{dom}]({target})"
            except Exception:
                return f"[{target}]({target})"

        # Archivo Markdown general
        if target.endswith('.md'):
            base = target[:-3].lstrip('./').replace('_', ' ')
            return f"[{base}]({target})"

        return f"[Ver documento]({target})"

    cuerpo = re.sub(r'\[\s*\]\((.*?)\)', sustituir_enlace_vacio, cuerpo)

    # 10. Evaluar y limpiar plantillas MediaWiki no renderizadas ({{#if: ...}})
    cuerpo = re.sub(r'\{\{#if:\s*\|.*?\}\}', '', cuerpo)
    def repl_if(m):
        cond = m.group(1).strip()
        rest = m.group(2).split('|')
        then_part = rest[0].strip() if rest else ''
        return then_part if cond else ''
    cuerpo = re.sub(r'\{\{#if:\s*([^|]+)\|([^}]*)\}\}', repl_if, cuerpo)
    cuerpo = re.sub(r'\[\[\|left\|thumb\|200px\|\]\]', '', cuerpo)

    # 11. Reparar líneas con negritas sin cerrar: **INFORME o ***RELACION -> **TEXTO**
    def reparar_negrita_linea(m):
        txt = m.group(1).strip()
        return f"**{txt}**"

    cuerpo = re.sub(r'^\*{2,3}([^\*\n]+)$', reparar_negrita_linea, cuerpo, flags=re.MULTILINE)

    # 12. Normalizar listas enumeradas pegadas: ej: 1-[ -> 1. [
    cuerpo = re.sub(r'^(\d+)-\[(.*?)\]', r'\1. [\2]', cuerpo, flags=re.MULTILINE)

    # 13. Eliminar líneas compuestas únicamente por asteriscos (**** o ********)
    cuerpo = re.sub(r'^\s*\*+\s*$', '', cuerpo, flags=re.MULTILINE)

    # 14. Eliminar asteriscos defectuosos al final de línea (3 o más asteriscos, o tras punto ej: "...****")
    cuerpo = re.sub(r'(\*{3,})\s*$', '', cuerpo, flags=re.MULTILINE)
    cuerpo = re.sub(r'(?<=\.)\*{3,}\s*$', '', cuerpo, flags=re.MULTILINE)

    # 15. Corregir negritas rotas con saltos de línea: **\n\n TEXTO ** -> **TEXTO**
    cuerpo = re.sub(r'\*\*\s*\n+\s*([^\n\*]+?)\s*\*\*', r'**\1**', cuerpo)

    # 16. Eliminar negritas vacías: ** **
    cuerpo = re.sub(r'\*\*[ \t]*\*\*', '', cuerpo)

    # 17. Convertir enlaces a imágenes de intranet (/mediawiki/images/...) a ruta local images/
    cuerpo = re.sub(r'\[(.*?)\]\(/mediawiki/images/[0-9a-f]/[0-9a-f]{2}/([^\)]+)\)', r'[\1](images/\2)', cuerpo)

    # 18. Convertir enlaces internos de MediaWiki a rutas relativas Markdown (.md)
    def sustituir_enlace_interno(m):
        texto = m.group(1)
        url = m.group(2)
        if url.startswith('/mediawiki/index.php') or url.startswith('index.php'):
            url_norm = normalizar_enlace_wiki_a_md(url)
            return f"[{texto}]({url_norm})"
        return m.group(0)

    cuerpo = re.sub(r'(?<!\!)\[(.*?)\]\((.*?)\)', sustituir_enlace_interno, cuerpo)

    # 19. Normalizar saltos de línea excesivos
    cuerpo = re.sub(r'\n{3,}', '\n\n', cuerpo).strip()

    resultado = (frontmatter.strip() + "\n\n" + cuerpo).strip() + "\n"
    ha_cambiado = (resultado != original)
    return resultado, ha_cambiado


def sanear_directorio(directorio: str, dry_run: bool = False) -> tuple[int, int]:
    """
    Recorre todos los archivos .md en el directorio y aplica saneamiento.
    Devuelve (total_revisados, total_modificados).
    """
    if not os.path.isdir(directorio):
        print(f"[ERROR] El directorio {directorio} no existe.")
        return 0, 0

    archivos = [f for f in os.listdir(directorio) if f.endswith(".md") and not re.match(r'^\d{2}_INDICE', f)]
    total = len(archivos)
    modificados = 0

    print(f"[INFO] Iniciando saneamiento de {total} archivos Markdown en {directorio}...")

    for f in archivos:
        ruta = os.path.join(directorio, f)
        try:
            with open(ruta, "r", encoding="utf-8") as fp:
                contenido = fp.read()

            nuevo_contenido, cambio = limpiar_contenido_markdown(contenido)
            if cambio:
                modificados += 1
                if not dry_run:
                    with open(ruta, "w", encoding="utf-8") as fp:
                        fp.write(nuevo_contenido)
        except Exception as e:
            print(f"[AVISO] Error procesando {f}: {e}")

    print(f"[OK] Saneamiento finalizado: {modificados} de {total} archivos fueron limpiados y corregidos.")
    return total, modificados

