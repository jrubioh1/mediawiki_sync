"""
Conversor bidireccional de Markdown a Wikitext para MediaWiki.
Soporta encabezados limpios, enlaces locales/wikilinks, listas anidadas por indentación,
tablas, imágenes, citas y bloques de código.
"""
import os
import re
import json
import urllib.parse

_MAPA_TITULOS_CACHE = None


def obtener_mapa_titulos_global() -> dict[str, str]:
    """Carga y cachea el mapa de archivos a títulos de MediaWiki desde .sync_state.json."""
    global _MAPA_TITULOS_CACHE
    if _MAPA_TITULOS_CACHE is not None:
        return _MAPA_TITULOS_CACHE

    mapa = {}
    rutas_candidatas = [
        os.path.join(os.getcwd(), "wiki_docs", ".sync_state.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "wiki_docs", ".sync_state.json")
    ]
    for r in rutas_candidatas:
        if os.path.exists(r):
            try:
                with open(r, "r", encoding="utf-8") as f:
                    d = json.load(f)
                articulos = d.get("articulos", {})
                for k, v in articulos.items():
                    if "titulo" in v:
                        mapa[k] = v["titulo"]
                        if k.endswith(".md"):
                            mapa[k[:-3]] = v["titulo"]
                break
            except Exception:
                pass

    _MAPA_TITULOS_CACHE = mapa
    return _MAPA_TITULOS_CACHE


def extraer_metadatos_frontmatter(texto_md: str) -> tuple[dict, str]:
    """Extrae metadatos del frontmatter YAML (si existe) y devuelve (metadatos, cuerpo_md)."""
    meta = {}
    cuerpo = texto_md

    # Soporte para BOM UTF-8 y delimitadores ---
    m_fm = re.match(r'^\ufeff?---\s*\n(.*?)\n---\s*\n', texto_md, flags=re.DOTALL)
    if m_fm:
        bloque_fm = m_fm.group(1)
        cuerpo = texto_md[m_fm.end():]
        for linea in bloque_fm.splitlines():
            linea = linea.strip()
            if not linea or linea.startswith('#') or ':' not in linea:
                continue
            k, v = linea.split(':', 1)
            k = k.strip()
            v = v.strip().strip('"\'')
            meta[k] = v

    return meta, cuerpo


def markdown_a_wikitext(texto_md: str, mapa_titulos: dict = None, dir_docs: str = None) -> str:
    """
    Convierte un texto en Markdown a Wikitext compatible con MediaWiki.
    """
    # 1. Extraer frontmatter
    _, md = extraer_metadatos_frontmatter(texto_md)

    # 2. Proteger bloques de código (```lang ... ```)
    bloques_codigo = []
    def guardar_bloque_codigo(match):
        lang = match.group(1).strip() if match.group(1) else ''
        codigo = match.group(2)
        idx = len(bloques_codigo)
        if lang:
            tag = f'<syntaxhighlight lang="{lang}">\n{codigo}\n</syntaxhighlight>'
        else:
            tag = f'<pre>\n{codigo}\n</pre>'
        bloques_codigo.append(tag)
        return f'\x01CB{idx}\x01'

    md = re.sub(r'```(\w*)\n?(.*?)```', guardar_bloque_codigo, md, flags=re.DOTALL)

    # 3. Proteger código en línea (`codigo`)
    codigos_inline = []
    def guardar_codigo_inline(match):
        idx = len(codigos_inline)
        codigos_inline.append(f'<code>{match.group(1)}</code>')
        return f'\x01IC{idx}\x01'

    md = re.sub(r'`([^`\n]+)`', guardar_codigo_inline, md)

    # 4. Limpiar encabezados que contengan [editar] o artefactos residuales
    def limpiar_encabezado(m):
        hashes = m.group(1)
        texto = m.group(2).strip()
        texto = re.sub(r'\[editar.*?\]', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'\]+$', '', texto).strip()
        return f"{hashes} {texto}"

    md = re.sub(r'^(#{1,6})\s+(.+)$', limpiar_encabezado, md, flags=re.MULTILINE)

    # 5. Encabezados (# H1 a ###### H6)
    md = re.sub(r'^######\s+(.*?)\s*#*$', r'====== \1 ======', md, flags=re.MULTILINE)
    md = re.sub(r'^#####\s+(.*?)\s*#*$', r'===== \1 =====', md, flags=re.MULTILINE)
    md = re.sub(r'^####\s+(.*?)\s*#*$', r'==== \1 ====', md, flags=re.MULTILINE)
    md = re.sub(r'^###\s+(.*?)\s*#*$', r'=== \1 ===', md, flags=re.MULTILINE)
    md = re.sub(r'^##\s+(.*?)\s*#*$', r'== \1 ==', md, flags=re.MULTILINE)
    md = re.sub(r'^#\s+(.*?)\s*#*$', r'= \1 =', md, flags=re.MULTILINE)

    # 6. Tablas Markdown a Wikitext {| class="wikitable"
    def convertir_tabla(match):
        lineas = [l.strip() for l in match.group(0).strip().split('\n') if l.strip()]
        if len(lineas) < 2:
            return match.group(0)
        cabecera_raw = lineas[0]
        separador_raw = lineas[1]
        if not re.search(r'\|?\s*:?-+:?\s*\|', separador_raw):
            return match.group(0)

        def extraer_celdas(fila_str):
            s = fila_str.strip()
            if s.startswith('|'):
                s = s[1:]
            if s.endswith('|'):
                s = s[:-1]
            celdas = re.split(r'(?<!\\)\|', s)
            return [c.strip().replace(r'\|', '|') for c in celdas]

        cabeceras = extraer_celdas(cabecera_raw)
        out = ['{| class="wikitable"', '! ' + ' !! '.join(cabeceras)]
        for fila in lineas[2:]:
            celdas = extraer_celdas(fila)
            out.append('|-')
            out.append('| ' + ' || '.join(celdas))
        out.append('|}\n')
        return '\n' + '\n'.join(out) + '\n'

    tabla_regex = re.compile(r'((?:^\|.+?\|\s*$\n?){2,})', re.MULTILINE)
    md = tabla_regex.sub(convertir_tabla, md)

    # 7. Imágenes: ![alt](images/archivo.ext) o ![alt](./images/archivo.ext)
    def sustituir_imagen(m):
        alt = m.group(1).strip()
        ruta = m.group(2).strip()
        fname = ruta.split('/')[-1].split('\\')[-1]
        if alt and alt != fname:
            return f'[[Archivo:{fname}|thumb|{alt}]]'
        return f'[[Archivo:{fname}]]'

    md = re.sub(r'!\[(.*?)\]\((.*?)\)', sustituir_imagen, md)

    # 8. Enlaces
    def sustituir_enlace(m):
        texto = m.group(1).strip()
        destino = m.group(2).strip()

        # Manejar anclas (#seccion) si están presentes en el destino
        anchor = ""
        destino_base = destino
        if '#' in destino:
            partes = destino.split('#', 1)
            destino_base = partes[0]
            anchor = '#' + partes[1].replace(' ', '_')

        # Enlace local a archivo .md: [Texto](./Articulo.md#Seccion) o [Texto](Articulo.md)
        if destino_base.endswith('.md'):
            nom = destino_base[:-3]
            if nom.startswith('./') or nom.startswith('.\\'):
                nom = nom[2:]
            nom = nom.split('/')[-1].split('\\')[-1]
            nom_archivo = f"{nom}.md"

            # 1. Resolver título real de MediaWiki desde mapa o cache de .sync_state.json
            mapa = mapa_titulos if mapa_titulos is not None else obtener_mapa_titulos_global()
            titulo_pagina = mapa.get(nom_archivo) or mapa.get(nom)

            # 2. Fallback: buscar en frontmatter local si existe el archivo
            if not titulo_pagina and dir_docs:
                ruta_local = os.path.join(dir_docs, nom_archivo)
                if os.path.isfile(ruta_local):
                    try:
                        with open(ruta_local, "r", encoding="utf-8") as f_md:
                            m_fm, _ = extraer_metadatos_frontmatter(f_md.read(2048))
                            if "titulo" in m_fm:
                                titulo_pagina = m_fm["titulo"]
                    except Exception:
                        pass

            # 3. Fallback final: reemplazar guiones bajos por espacios
            if not titulo_pagina:
                titulo_pagina = nom.replace('_', ' ')

            target_wiki = f"{titulo_pagina}{anchor}"
            if (texto == titulo_pagina or texto == nom) and not anchor:
                return f'[[{titulo_pagina}]]'
            return f'[[{target_wiki}|{texto}]]'

        # Enlace legacy /mediawiki/index.php...
        if 'index.php' in destino or '/wiki/' in destino:
            m_tit = re.search(r'(?:title=|index\.php/|/wiki/)([^&#]+)', destino)
            if m_tit:
                titulo_pagina = urllib.parse.unquote(m_tit.group(1)).replace('_', ' ')
                target_wiki = f"{titulo_pagina}{anchor}"
                if texto == titulo_pagina and not anchor:
                    return f'[[{titulo_pagina}]]'
                return f'[[{target_wiki}|{texto}]]'

        if destino.startswith(('http://', 'https://', 'ftp://', 'mailto:')):
            return f'[{destino} {texto}]'
        elif destino.startswith('#'):
            ancla_pura = destino.lstrip('#').replace(' ', '_')
            return f'[[#{ancla_pura}|{texto}]]'

        return f'[[{destino}|{texto}]]'

    md = re.sub(r'(?<!\!)\[(.*?)\]\((.*?)\)', sustituir_enlace, md)

    # 9. Listas ordenadas y desordenadas (preservando jerarquía contextual y suprimiendo líneas vacías)
    def procesar_listas_contextuales(lineas):
        stack = []
        salida = []
        lineas_en_blanco_pendientes = 0

        for linea in lineas:
            stripped = linea.strip()
            if not stripped:
                if stack:
                    lineas_en_blanco_pendientes += 1
                else:
                    salida.append(linea)
                continue

            m_bullet = re.match(r'^([ \t]*)[-+*][ \t]+(.*)$', linea)
            m_num = re.match(r'^([ \t]*)\d+\.[ \t]+(.*)$', linea)

            if m_bullet or m_num:
                if m_bullet:
                    indent = len(m_bullet.group(1).replace('\t', '  '))
                    contenido = m_bullet.group(2)
                    tipo = 'B'
                else:
                    indent = len(m_num.group(1).replace('\t', '  '))
                    contenido = m_num.group(2)
                    tipo = 'N'

                profundidad = 1 + (indent // 2)

                # Si cambia el tipo en el nivel raíz tras líneas en blanco, se trata de una lista nueva independiente
                if profundidad == 1 and stack and stack[0] != tipo and lineas_en_blanco_pendientes > 0:
                    salida.append('')
                    stack = []

                if profundidad <= len(stack):
                    stack = stack[:profundidad - 1]
                    stack.append(tipo)
                else:
                    while len(stack) < profundidad - 1:
                        stack.append(stack[-1] if stack else tipo)
                    stack.append(tipo)

                prefix = ''.join(stack)
                # Al ser elemento de lista consecutivo del mismo bloque, se suprimen líneas vacías
                lineas_en_blanco_pendientes = 0
                salida.append(f'\x01LIST_{prefix}\x01 {contenido}')
            else:
                stack = []
                if lineas_en_blanco_pendientes > 0:
                    salida.append('')
                lineas_en_blanco_pendientes = 0
                salida.append(linea)

        return salida

    lineas_procesadas = procesar_listas_contextuales(md.splitlines())
    md = '\n'.join(lineas_procesadas)

    # 9.5 Proteger palabras mágicas de MediaWiki (ej. __TOC__, __NOTOC__, __NOEDITSECTION__)
    palabras_magicas = []
    def guardar_palabra_magica(match):
        idx = len(palabras_magicas)
        palabras_magicas.append(match.group(0))
        return f'\x01MW{idx}\x01'

    md = re.sub(r'__(?:TOC|FORCETOC|NOTOC|NOEDITSECTION|INDEX|NOINDEX|NOCONTENTCONVERT|NOCC|NOTITLECONVERT|NOTC)__', guardar_palabra_magica, md)

    # 10. Negritas y Cursivas
    md = re.sub(r'\*\*\*(.*?)\*\*\*', r"'''''\1'''''", md)
    md = re.sub(r'\*\*(.*?)\*\*', r"'''\1'''", md)
    md = re.sub(r'__([^_]+)__', r"'''\1'''", md)
    # Cursiva sólo si no forma parte de marcadores de lista o palabras
    md = re.sub(r'(?<![\*\w])\*([^\*\n]+?)\*(?![\*\w])', r"''\1''", md)
    md = re.sub(r'(?<![_\w])_([^_\n]+?)_(?![_\w])', r"''\1''", md)

    # 11. Citas tipo blockquote (> cita)
    def sustituir_cita(m):
        bloque = [re.sub(r'^>\s?', '', l) for l in m.group(0).split('\n')]
        return '<blockquote>\n' + '\n'.join(bloque).strip() + '\n</blockquote>\n'

    md = re.sub(r'((?:^>.*$\n?)+)', sustituir_cita, md, flags=re.MULTILINE)

    # 12. Líneas horizontales
    md = re.sub(r'^(?:---|\*\*\*|___)\s*$', '----', md, flags=re.MULTILINE)

    # 13. Restaurar códigos inline, bloques de código, palabras mágicas y marcadores de lista
    for i, tag in enumerate(codigos_inline):
        md = md.replace(f'\x01IC{i}\x01', tag)
    for i, tag in enumerate(bloques_codigo):
        md = md.replace(f'\x01CB{i}\x01', tag)
    for i, tag in enumerate(palabras_magicas):
        md = md.replace(f'\x01MW{i}\x01', tag)
    md = re.sub(r'\x01LIST_([BN]+)\x01', lambda m: m.group(1).replace('B', '*').replace('N', '#'), md)

    return md.strip()
