"""
Pruebas unitarias para los conversores HTML -> Markdown y Markdown -> Wikitext.
"""
import unittest
from mw_sync.converters.html_to_md import html_a_markdown
from mw_sync.converters.md_to_wikitext import markdown_a_wikitext
from mw_sync.converters.sanitizer import limpiar_contenido_markdown


class TestHTMLToMarkdown(unittest.TestCase):
    def test_eliminar_editar_y_toc(self):
        html = """
        <h2><span class="mw-headline" id="Sec1">Título</span>
            <span class="mw-editsection"><span class="mw-editsection-bracket">[</span><a href="/edit">editar</a><span class="mw-editsection-bracket">]</span></span>
        </h2>
        <div id="toc" class="toc">
            <h2>Contenido</h2>
            <ul><li>Item 1</li></ul>
        </div>
        <p>Párrafo principal.</p>
        """
        md, imgs = html_a_markdown(html, "Prueba")
        self.assertNotIn("editar", md)
        self.assertNotIn("Contenido", md)
        self.assertIn("## Título", md)
        self.assertIn("Párrafo principal.", md)

    def test_enlace_interno_convertido(self):
        html = '<p>Ver <a href="/mediawiki/index.php/Articulo_Ejemplo">Artículo</a>.</p>'
        md, _ = html_a_markdown(html, "Prueba")
        self.assertIn("[Artículo](./Articulo_Ejemplo.md)", md)

    def test_imagenes(self):
        html = '<p><img src="/images/thumb/a/a1/foto.png/300px-foto.png" alt="Mi Foto"></p>'
        md, imgs = html_a_markdown(html, "Prueba")
        self.assertIn("![Mi Foto](images/foto.png)", md)
        self.assertEqual(len(imgs), 1)
        self.assertEqual(imgs[0]["nombre"], "foto.png")


    def test_enlace_vacio_genera_etiqueta_accesible(self):
        html = '<p>Consulta <a href="/mediawiki/index.php/Articulo_Ejemplo_1993-01-20"></a>.</p>'
        md, _ = html_a_markdown(html, "Prueba")
        self.assertIn("[Articulo Ejemplo 1993-01-20](./Articulo_Ejemplo_1993-01-20.md)", md)

    def test_listas_anidadas_html(self):
        html = '<ul><li>Nivel 1<ul><li>Nivel 2</li></ul></li></ul>'
        md, _ = html_a_markdown(html, "Prueba")
        self.assertIn("- Nivel 1\n  - Nivel 2", md)


class TestMarkdownToWikitext(unittest.TestCase):
    def test_encabezados_limpios(self):
        md = "## Mi Sección [editar]\n\nContenido"
        wt = markdown_a_wikitext(md)
        self.assertEqual(wt, "== Mi Sección ==\nContenido")

    def test_listas_anidadas(self):
        md = "- Nivel 1\n  - Nivel 2\n    - Nivel 3"
        wt = markdown_a_wikitext(md)
        lineas = wt.splitlines()
        self.assertEqual(lineas[0], "* Nivel 1")
        self.assertEqual(lineas[1], "** Nivel 2")
        self.assertEqual(lineas[2], "*** Nivel 3")

    def test_enlaces_locales_a_wikilinks(self):
        md = "Consulta [Guía de Uso](./Guia_de_Uso.md)."
        wt = markdown_a_wikitext(md)
        self.assertIn("[[Guia de Uso|Guía de Uso]]", wt)

    def test_enlaces_con_dos_puntos_resueltos(self):
        md = "Véase [Instrucción Técnica 6](./Manual_IAE_Instrucción_Técnica_6.md)."
        mapa = {"Manual_IAE_Instrucción_Técnica_6.md": "Manual IAE: Instrucción Técnica 6"}
        wt = markdown_a_wikitext(md, mapa_titulos=mapa)
        self.assertIn("[[Manual IAE: Instrucción Técnica 6|Instrucción Técnica 6]]", wt)

    def test_enlace_con_ancla_a_wikilink(self):
        md = "Ver [Sección A](./Manual_IAE.md#Seccion_A)."
        wt = markdown_a_wikitext(md)
        self.assertIn("[[Manual IAE#Seccion_A|Sección A]]", wt)

    def test_tabla_con_pipe_escapado(self):
        md = "| Cabecera 1 | Cabecera 2 |\n| --- | --- |\n| Valor con \\| barra | Normal |"
        wt = markdown_a_wikitext(md)
        self.assertIn("Valor con | barra || Normal", wt)

    def test_palabras_magicas_preservadas(self):
        md = "__TOC__\n\nTexto con __negrita__."
        wt = markdown_a_wikitext(md)
        self.assertIn("__TOC__", wt)
        self.assertIn("'''negrita'''", wt)

    def test_listas_anidadas_con_negrita(self):
        md = "- Item 1\n  - ** a) ** Subitem con negrita\n    - **Importante:** Detalle"
        wt = markdown_a_wikitext(md)
        lineas = wt.splitlines()
        self.assertEqual(lineas[0], "* Item 1")
        self.assertEqual(lineas[1], "** ''' a) ''' Subitem con negrita")
        self.assertEqual(lineas[2], "*** '''Importante:''' Detalle")

    def test_listas_numeradas_suprimen_lineas_en_blanco(self):
        md = "1. Item 1\n\n1. Item 2\n  - Subviñeta\n\n1. Item 3"
        wt = markdown_a_wikitext(md)
        lineas = wt.splitlines()
        self.assertEqual(lineas[0], "# Item 1")
        self.assertEqual(lineas[1], "# Item 2")
        self.assertEqual(lineas[2], "#* Subviñeta")
        self.assertEqual(lineas[3], "# Item 3")

    def test_listas_independientes_separadas_por_linea_vacia(self):
        md = "1. Item 1\n2. Item 2\n\n- Viñeta nueva"
        wt = markdown_a_wikitext(md)
        lineas = wt.splitlines()
        self.assertEqual(lineas[0], "# Item 1")
        self.assertEqual(lineas[1], "# Item 2")
        self.assertEqual(lineas[2], "")
        self.assertEqual(lineas[3], "* Viñeta nueva")



class TestSanitizer(unittest.TestCase):
    def test_limpiar_markdown_defectuoso(self):
        defectuoso = (
            "---\ntitulo: Test\n---\n\n"
            "### Título Sucio [editar](/url)]****\n"
            "****\n"
            "Texto con [Link](/mediawiki/index.php/Destino).\n"
        )
        limpio, cambio = limpiar_contenido_markdown(defectuoso)
        self.assertTrue(cambio)
        self.assertNotIn("editar", limpio)
        self.assertNotIn("****", limpio)
        self.assertIn("### Título Sucio", limpio)
        self.assertIn("[Link](./Destino.md)", limpio)

    def test_desenvolver_imagenes_intranet(self):
        defectuoso = "[![foto.png](images/foto.png)](/mediawiki/index.php/Archivo:foto.png)Portal de entrada de la Intranet"
        limpio, cambio = limpiar_contenido_markdown(defectuoso)
        self.assertTrue(cambio)
        self.assertEqual(limpio.strip(), "![foto.png](images/foto.png)")

    def test_reparar_redlinks_en_encabezados(self):
        defectuoso = "##### [a) Seccion.](./A.md)_Seccion.&action=edit&redlink=1).&action=edit&section=1)"
        limpio, cambio = limpiar_contenido_markdown(defectuoso)
        self.assertTrue(cambio)
        self.assertIn("##### a) Seccion.", limpio)

    def test_reparar_enlaces_vacios_y_plantillas(self):
        defectuoso = (
            "[](./Articulo_Ejemplo_1993-01-20.md)\n\n"
            "{{#if: Archivo:Logo 1.png | Logotipo | }}\n"
            "{{#if:  | [[|left|thumb|200px|]] | }}"
        )
        limpio, cambio = limpiar_contenido_markdown(defectuoso)
        self.assertTrue(cambio)
        self.assertIn("[Articulo Ejemplo 1993-01-20](./Articulo_Ejemplo_1993-01-20.md)", limpio)
        self.assertIn("Logotipo", limpio)
        self.assertNotIn("{{#if", limpio)


class TestMediaWikiClientAuth(unittest.TestCase):
    def test_dual_auth_init(self):
        from mw_sync.client import MediaWikiClient
        c = MediaWikiClient(
            url="https://ejemplo.com/api.php",
            http_user="apache_user",
            http_password="apache_pass",
            wiki_user="wiki_editor",
            wiki_password="wiki_pass"
        )
        self.assertEqual(c.http_user, "apache_user")
        self.assertEqual(c.http_password, "apache_pass")
        self.assertEqual(c.wiki_user, "wiki_editor")
        self.assertEqual(c.wiki_password, "wiki_pass")


if __name__ == "__main__":
    unittest.main()
