"""
Conversor de HTML renderizado por MediaWiki a Markdown estructurado y limpio.
Diseñado para funcionar sin dependencias externas (usando html.parser nativo)
con soporte opcional para BeautifulSoup4 si está presente.
"""
import re
import urllib.parse
from html.parser import HTMLParser


def sanitizar_nombre_archivo(titulo: str) -> str:
    """Convierte un título de MediaWiki en un nombre de archivo local seguro."""
    s = titulo.strip()
    # Eliminar prefijos de namespaces comunes si se desea, o sanitizar caracteres prohibidos
    s = re.sub(r'[\\/*?:"<>|]', "_", s)
    s = re.sub(r'[\s_]+', "_", s)
    s = s.strip("._")
    return s if s else "articulo_sin_titulo"


def normalizar_enlace_wiki_a_md(href: str) -> str:
    """
    Convierte una URL interna de MediaWiki a un enlace relativo a archivo .md local.
    Ej: /mediawiki/index.php/Manual_Inicio -> ./Manual_Inicio.md
        /mediawiki/index.php?title=Manual_Inicio&action=edit -> ./Manual_Inicio.md
    """
    if not href:
        return href

    # Si es un ancla local (#Seccion) o URL externa, dejar tal cual
    if href.startswith(("#", "http://", "https://", "mailto:", "tel:", "ftp://")):
        return href

    # Detectar enlaces MediaWiki estándar
    # Formato 1: ...index.php?title=Nombre_Pagina...
    m_query = re.search(r'index\.php\?title=([^&#]+)', href)
    if m_query:
        titulo_raw = urllib.parse.unquote(m_query.group(1))
        # Si es un enlace de edición, no convertir a .md si no queremos
        nombre_md = sanitizar_nombre_archivo(titulo_raw)
        return f"./{nombre_md}.md"

    # Formato 2: ...index.php/Nombre_Pagina o /wiki/Nombre_Pagina
    m_path = re.search(r'(?:index\.php/|/wiki/)([^?&#]+)', href)
    if m_path:
        titulo_raw = urllib.parse.unquote(m_path.group(1))
        nombre_md = sanitizar_nombre_archivo(titulo_raw)
        return f"./{nombre_md}.md"

    return href


class StandaloneHTMLToMarkdown(HTMLParser):
    """
    Parser HTML a Markdown nativo, robusto y sin dependencias.
    Controla estrictamente la profundidad de exclusión (skip_depth)
    para evitar cualquier fuga de TOC, [editar], navboxes o scripts.
    Preserva niveles de anidación de listas y genera etiquetas descriptivas
    para evitar enlaces vacíos.
    """

    def __init__(self):
        super().__init__()
        self.output = []
        self.images = []
        self.link_stack = []
        self.table_data = []
        self.current_row = []
        self.in_table = False
        self.in_cell = False
        self.cell_buffer = []

        # Control de listas y anidación
        self.list_depth = 0
        self.list_types = []

        # Control de exclusión de elementos indeseados
        self.skip_depth = 0
        self.skip_tags = {'script', 'style', 'nav', 'footer', 'header', 'noscript'}
        self.skip_classes = {
            'toc', 'mw-editsection', 'mw-jump-link', 'printfooter',
            'navbox', 'metadata', 'mw-editsection-bracket', 'mw-empty-elt'
        }
        self.skip_ids = {'toc', 'jump-to-nav'}

        # Buffer para encabezados (h1 - h6)
        self.in_heading = False
        self.heading_level = 1
        self.heading_buffer = []

    def _generar_etiqueta_fallback(self, href: str) -> str:
        """Genera un texto descriptivo accesible cuando un enlace no tiene texto interno."""
        if not href:
            return "Enlace"

        # Caso ancla local: #1993 -> Año 1993, #Seccion -> Seccion
        if href.startswith('#'):
            ancla = href[1:].strip().replace('_', ' ')
            if ancla.isdigit() and len(ancla) == 4:
                return f"Año {ancla}"
            return urllib.parse.unquote(ancla) if ancla else "Sección"

        # Caso URL externa
        if href.startswith(('http://', 'https://')):
            try:
                parsed = urllib.parse.urlparse(href)
                dominio = parsed.netloc or parsed.path
                return dominio.lstrip("www.") if dominio else href
            except Exception:
                return href

        # Caso artículo MediaWiki
        m_query = re.search(r'title=([^&#]+)', href)
        if m_query:
            t = urllib.parse.unquote(m_query.group(1)).replace('_', ' ')
            return t.split(':')[-1] if ':' in t else t

        m_path = re.search(r'(?:index\.php/|/wiki/)([^?&#]+)', href)
        if m_path:
            t = urllib.parse.unquote(m_path.group(1)).replace('_', ' ')
            return t.split(':')[-1] if ':' in t else t

        return "Ver documento"

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = set(attrs_dict.get('class', '').split())
        tag_id = attrs_dict.get('id', '')

        # Si ya estamos en una zona de exclusión, aumentar profundidad
        if self.skip_depth > 0:
            self.skip_depth += 1
            return

        # Verificar si este tag debe iniciar una zona de exclusión
        debe_omitir = (
            tag in self.skip_tags
            or bool(classes & self.skip_classes)
            or tag_id in self.skip_ids
        )
        if debe_omitir:
            self.skip_depth = 1
            return

        # Listas y niveles de anidación
        if tag in ('ul', 'ol'):
            self.list_depth += 1
            self.list_types.append(tag)
            return

        # Encabezados
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.in_heading = True
            self.heading_level = int(tag[1])
            self.heading_buffer = []
            return

        if self.in_heading:
            return

        # Formato de bloque y salto de línea
        if tag == 'p':
            self.output.append('\n\n')
        elif tag == 'br':
            self.output.append('\n')
        elif tag in ('b', 'strong'):
            self.output.append('**')
        elif tag in ('i', 'em'):
            self.output.append('*')
        elif tag == 'code':
            self.output.append('`')
        elif tag == 'pre':
            self.output.append('\n```\n')
        elif tag == 'li':
            indent = '  ' * max(0, self.list_depth - 1)
            marker = '- ' if (not self.list_types or self.list_types[-1] == 'ul') else '1. '
            self.output.append(f'\n{indent}{marker}')
        elif tag == 'blockquote':
            self.output.append('\n> ')
        elif tag == 'a':
            href = attrs_dict.get('href', '')
            # Si el enlace es un contenedor de archivo/imagen (/Archivo: o class image), no envolverlo
            es_enlace_archivo = (
                'image' in classes
                or '/Archivo:' in href
                or '/File:' in href
                or bool(re.search(r'title=(?:Archivo|File):', href))
            )
            if es_enlace_archivo:
                self.link_stack.append({'href': href, 'is_image_wrapper': True, 'start_index': len(self.output)})
            else:
                self.link_stack.append({'href': href, 'is_image_wrapper': False, 'start_index': len(self.output)})
                self.output.append('[')
        elif tag == 'img':
            src = attrs_dict.get('src', '')
            alt = attrs_dict.get('alt', '').strip()
            if src:
                parts = src.split('/')
                if '/thumb/' in src and len(parts) >= 2:
                    fname = urllib.parse.unquote(parts[-2])
                else:
                    fname = urllib.parse.unquote(parts[-1])
                fname = fname.split('?')[0]
                if not alt or alt == fname:
                    alt = fname
                self.images.append({'nombre': fname, 'src_original': src, 'alt': alt})
                self.output.append(f'![{alt}](images/{fname})')
        elif tag == 'table':
            self.in_table = True
            self.table_data = []
        elif tag == 'tr' and self.in_table:
            self.current_row = []
        elif tag in ('th', 'td') and self.in_table:
            self.in_cell = True
            self.cell_buffer = []

    def handle_endtag(self, tag):
        # Manejo estricto de decremento en zona de exclusión
        if self.skip_depth > 0:
            self.skip_depth -= 1
            return

        # Listas y niveles de anidación
        if tag in ('ul', 'ol'):
            if self.list_depth > 0:
                self.list_depth -= 1
            if self.list_types:
                self.list_types.pop()
            return

        # Cierre de encabezados
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6') and self.in_heading:
            texto_h = ''.join(self.heading_buffer).strip()
            # Limpiar redlinks incrustados en encabezados (ej: [a) Titulo](./A.md)...)
            texto_h = re.sub(r'\[([^\]]+)\]\([^\)]*action=edit[^\)]*\)[^ \t\n]*', r'\1', texto_h)
            # Limpiar cualquier resto de corchetes o artefactos de sección
            texto_h = re.sub(r'\[editar.*?\]', '', texto_h, flags=re.IGNORECASE)
            texto_h = re.sub(r'\]+$', '', texto_h).strip()
            if texto_h:
                hashes = '#' * self.heading_level
                self.output.append(f"\n\n{hashes} {texto_h}\n\n")
            self.in_heading = False
            self.heading_buffer = []
            return

        if self.in_heading:
            return

        if tag in ('b', 'strong'):
            self.output.append('**')
        elif tag in ('i', 'em'):
            self.output.append('*')
        elif tag == 'code':
            self.output.append('`')
        elif tag == 'pre':
            self.output.append('\n```\n')
        elif tag == 'a' and self.link_stack:
            info = self.link_stack.pop()
            if info['is_image_wrapper']:
                # No cerramos enlace para no crear [![img](images/foo)](/mediawiki/Archivo:foo)
                pass
            else:
                # Comprobar si el enlace quedó sin texto interior
                idx_inicio = info['start_index']
                texto_interior = ''.join(self.output[idx_inicio + 1:]).strip()
                if not texto_interior:
                    fallback_label = self._generar_etiqueta_fallback(info['href'])
                    self.output.append(fallback_label)

                href_md = normalizar_enlace_wiki_a_md(info['href'])
                self.output.append(f']({href_md})')
        elif tag in ('th', 'td') and self.in_table:
            self.in_cell = False
            # Las celdas de markdown no deben contener saltos de línea sin escapar
            contenido = ' '.join(''.join(self.cell_buffer).split())
            contenido = contenido.replace('|', r'\|')
            self.current_row.append(contenido)
        elif tag == 'tr' and self.in_table:
            if self.current_row:
                self.table_data.append(self.current_row)
        elif tag == 'table' and self.in_table:
            self.in_table = False
            if self.table_data:
                num_cols = max(len(row) for row in self.table_data)
                if num_cols > 0:
                    self.output.append('\n\n')
                    header = self.table_data[0] + [''] * (num_cols - len(self.table_data[0]))
                    self.output.append('| ' + ' | '.join(header) + ' |\n')
                    self.output.append('| ' + ' | '.join(['---'] * num_cols) + ' |\n')
                    for row in self.table_data[1:]:
                        padded = row + [''] * (num_cols - len(row))
                        self.output.append('| ' + ' | '.join(padded) + ' |\n')
                    self.output.append('\n')

    def handle_data(self, data):
        if self.skip_depth > 0:
            return

        if self.in_heading:
            self.heading_buffer.append(data)
            return

        if self.in_cell:
            self.cell_buffer.append(data)
        else:
            self.output.append(data)

    def get_markdown(self) -> str:
        text = ''.join(self.output)

        # 1. Eliminar artefactos de líneas con solo asteriscos sueltos (ej: **** o ********)
        text = re.sub(r'^\s*\*{2,}\s*$', '', text, flags=re.MULTILINE)

        # 2. Limpiar negritas vacías sin afectar saltos de línea legítimos: ** **
        text = re.sub(r'\*\*[ \t]*\*\*', '', text)

        # 3. Limpiar restos de [editar] y corchetes dangling
        text = re.sub(r'\[editar.*?\]', '', text, flags=re.IGNORECASE)

        # 4. Eliminar texto residual de pie de imagen de la intranet
        text = re.sub(r'(\!\[.*?\]\(.*?\))\s*Portal de entrada de la Intranet', r'\1', text)

        # 5. Reparar negritas no cerradas al final de línea
        text = re.sub(r'^\*\*([^\*\n]+)$', r'**\1**', text, flags=re.MULTILINE)

        # 6. Normalizar espacios y saltos de línea excesivos
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


def html_a_markdown(html_raw: str, titulo: str = "") -> tuple[str, list[dict]]:
    """
    Punto de entrada para convertir HTML a Markdown.
    Devuelve (texto_markdown, lista_imagenes_detectadas).
    """
    if not html_raw or not html_raw.strip():
        return "", []

    parser = StandaloneHTMLToMarkdown()
    parser.feed(html_raw)
    return parser.get_markdown(), parser.images
