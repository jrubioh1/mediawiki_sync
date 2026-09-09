"""
Pruebas de Integración End-to-End (E2E) contra un servidor MediaWiki real.
Estas pruebas se ejecutan en CI (GitHub Actions) levantando un contenedor Docker efímero.
En local se omiten automáticamente si no se define la variable MW_TEST_LIVE=1.
"""
import unittest
import os
import shutil
import tempfile
import time

from mw_sync.client import MediaWikiClient
from mw_sync.downloader import ejecutar_descarga
from mw_sync.uploader import ejecutar_subida
from mw_sync.state import SyncState


class TestLiveMediaWikiE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Omitir si no se ejecuta en entorno de CI / prueba viva
        if not os.getenv("MW_TEST_LIVE"):
            raise unittest.SkipTest("Pruebas E2E en vivo omitidas (actívalas con MW_TEST_LIVE=1)")

        cls.api_url = os.getenv("MW_TEST_LIVE_URL", "http://localhost:8080/api.php")
        cls.wiki_user = os.getenv("MW_TEST_WIKI_USER", "TestAdmin")
        cls.wiki_pass = os.getenv("MW_TEST_WIKI_PASS", "TestPass123")

        cls.client = MediaWikiClient(
            url=cls.api_url,
            wiki_user=cls.wiki_user,
            wiki_password=cls.wiki_pass
        )

        ok, name = cls.client.test_conexion()
        if not ok:
            raise unittest.SkipTest(f"No se pudo conectar a MediaWiki en {cls.api_url}: {name}")

        ok_login, msg = cls.client.login()
        if not ok_login:
            raise unittest.SkipTest(f"Fallo de login en MediaWiki para {cls.wiki_user}: {msg}")

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_01_conexion_y_autenticacion(self):
        """Valida que la conexión Action API y el login con tokens de sesión son válidos."""
        user_info = self.client.obtener_informacion_usuario()
        self.assertEqual(user_info.get("name"), self.wiki_user)
        self.assertIn("user", user_info.get("groups", []))

    def test_02_subida_de_articulo_markdown(self):
        """Crea un archivo Markdown local y lo sube con éxito a la MediaWiki viva."""
        titulo_art = f"Articulo_E2E_{int(time.time())}"
        f_name = f"{titulo_art}.md"
        ruta_md = os.path.join(self.test_dir, f_name)

        with open(ruta_md, "w", encoding="utf-8") as f:
            f.write(f"---\ntitulo: \"{titulo_art}\"\n---\n\n# {titulo_art}\n\nTexto de prueba E2E.\n")

        # Subir el artículo
        ejecutar_subida(
            cliente=self.client,
            output_dir=self.test_dir,
            archivo_especifico=ruta_md,
            forzar=True
        )

        # Comprobar que existe en la MediaWiki real
        datos_remotos = self.client.descargar_contenido_pagina(titulo_art)
        self.assertIsNotNone(datos_remotos)
        self.assertIn("Texto de prueba E2E", datos_remotos.get("html", ""))

    def test_03_descarga_incremental_e_indice(self):
        """Descarga artículos desde la MediaWiki y valida la generación de Markdown y 00_INDICE_MEDIAWIKI.md."""
        # 1. Crear un artículo directamente en la wiki
        titulo = "Pagina_Descarga_E2E"
        res = self.client.editar_pagina(titulo, "Contenido para probar descarga incremental.", resumen="Setup E2E")
        self.assertTrue(res.get("exito"))

        # 2. Ejecutar descarga en carpeta local limpia
        dir_descarga = os.path.join(self.test_dir, "descarga")
        ejecutar_descarga(self.client, dir_descarga, empty_action="ignore")

        # 3. Comprobar que el archivo .md y el índice se generaron
        f_esperado = os.path.join(dir_descarga, f"{titulo}.md")
        self.assertTrue(os.path.isfile(f_esperado))

        ruta_indice = os.path.join(dir_descarga, "00_INDICE_MEDIAWIKI.md")
        self.assertTrue(os.path.isfile(ruta_indice))
        with open(ruta_indice, "r", encoding="utf-8") as f:
            indice_txt = f.read()
        self.assertIn(titulo, indice_txt)

    def test_04_deteccion_de_conflictos(self):
        """Comprueba que una edición externa en el servidor genera copia de seguridad .conflict."""
        titulo = f"Conflicto_E2E_{int(time.time())}"
        # 1. Crear versión inicial en wiki
        res1 = self.client.editar_pagina(titulo, "Versión Original Remota", resumen="Creación inicial")
        revid_original = res1.get("newrevid")

        # 2. Crear archivo local asociado a esa revisión
        f_name = f"{titulo}.md"
        ruta_md = os.path.join(self.test_dir, f_name)
        with open(ruta_md, "w", encoding="utf-8") as f:
            f.write(f"---\ntitulo: \"{titulo}\"\nrevid: {revid_original}\n---\n\n# {titulo}\n\nMi cambio local.\n")

        # 3. Simular que otro usuario edita la página en el servidor (nuevo revid)
        res2 = self.client.editar_pagina(titulo, "Versión Editada por Tercero", resumen="Edición ajena")
        self.assertTrue(res2.get("exito"))

        # 4. Intentar subir sin auto-confirmar y en modo no interactivo
        ejecutar_subida(
            cliente=self.client,
            output_dir=self.test_dir,
            archivo_especifico=ruta_md,
            auto_confirmar_conflicto=False
        )

        # 5. Validar que se creó el archivo de conflicto de respaldo
        archivo_conflicto = f"{ruta_md}.servidor.conflict"
        self.assertTrue(os.path.isfile(archivo_conflicto), "Debe crearse el archivo .servidor.conflict")

    def test_05_gestion_pagina_vacia_crear_plantilla(self):
        """Comprueba que una página vacía en la wiki puede convertirse en plantilla .md local."""
        titulo_vacia = f"Vacia_Crear_E2E_{int(time.time())}"
        # Crear página vacía en el servidor
        res = self.client.editar_pagina(titulo_vacia, "", resumen="Página vacía E2E")
        self.assertTrue(res.get("exito"))

        dir_descarga = os.path.join(self.test_dir, "vacias_create")
        ejecutar_descarga(self.client, dir_descarga, empty_action="create-md")

        ruta_md = os.path.join(dir_descarga, f"{titulo_vacia}.md")
        self.assertTrue(os.path.isfile(ruta_md), "El archivo .md plantilla debe haber sido creado")
        with open(ruta_md, "r", encoding="utf-8") as f:
            contenido = f.read()
        self.assertIn(f"titulo: \"{titulo_vacia}\"", contenido)
        self.assertIn(f"# {titulo_vacia}", contenido)

        # Comprobar que en el estado está registrada como creada_local
        estado = SyncState(os.path.join(dir_descarga, ".sync_state.json"))
        vacias = estado.obtener_paginas_vacias()
        self.assertIn(titulo_vacia, vacias)
        self.assertEqual(vacias[titulo_vacia]["accion"], "creada_local")

    def test_06_gestion_pagina_vacia_borrado_remoto(self):
        """Comprueba que una página vacía puede eliminarse directamente del servidor remoto."""
        titulo_borrar = f"Vacia_Borrar_E2E_{int(time.time())}"
        # Crear página en el servidor
        res = self.client.editar_pagina(titulo_borrar, "", resumen="Página vacía a borrar E2E")
        self.assertTrue(res.get("exito"))

        # Validar que existe en la lista de páginas
        self.assertIn(titulo_borrar, self.client.obtener_lista_paginas())

        # Ejecutar descarga con acción de borrado remoto automático
        dir_descarga = os.path.join(self.test_dir, "vacias_delete")
        ejecutar_descarga(self.client, dir_descarga, empty_action="delete-remote", auto_confirmar=True)

        # Validar que ya no existe en la lista de páginas del servidor
        self.assertNotIn(titulo_borrar, self.client.obtener_lista_paginas())


if __name__ == "__main__":
    unittest.main()
