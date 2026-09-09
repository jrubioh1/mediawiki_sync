"""
Pruebas unitarias para la gestión y control de páginas vacías (mw_sync/empty_pages.py, state.py y client.py).
"""
import unittest
from unittest.mock import MagicMock, patch
import tempfile
import os
import shutil
import json

from mw_sync.client import MediaWikiClient
from mw_sync.state import SyncState
from mw_sync.empty_pages import (
    crear_plantilla_md_vacia,
    eliminar_pagina_remota,
    omitir_pagina_vacia,
    gestionar_paginas_vacias,
    listar_y_gestionar_paginas_vacias,
)
from mw_sync.downloader import ejecutar_descarga


class TestClientEliminarPagina(unittest.TestCase):
    def test_eliminar_pagina_exitoso(self):
        client = MediaWikiClient(url="https://example.com/api.php")
        client.obtener_token_csrf = MagicMock(return_value="test-token")
        client._api_post = MagicMock(return_value={
            "delete": {"title": "Pagina_Vacia", "reason": "Motivo", "logid": 42}
        })

        res = client.eliminar_pagina("Pagina_Vacia")
        self.assertTrue(res.get("exito"))
        self.assertEqual(res.get("title"), "Pagina_Vacia")
        self.assertEqual(res.get("logid"), 42)

    def test_eliminar_pagina_error_permisos(self):
        client = MediaWikiClient(url="https://example.com/api.php")
        client.obtener_token_csrf = MagicMock(return_value="test-token")
        client._api_post = MagicMock(return_value={
            "error": {"code": "permissiondenied", "info": "Solo administradores pueden borrar páginas."}
        })

        res = client.eliminar_pagina("Pagina_Vacia")
        self.assertFalse(res.get("exito"))
        self.assertEqual(res.get("code"), "permissiondenied")
        self.assertIn("Solo administradores", res.get("error"))

    def test_eliminar_pagina_excepcion_red(self):
        client = MediaWikiClient(url="https://example.com/api.php")
        client.obtener_token_csrf = MagicMock(return_value="test-token")
        client._api_post = MagicMock(side_effect=Exception("Fallo de red"))

        res = client.eliminar_pagina("Pagina_Vacia")
        self.assertFalse(res.get("exito"))
        self.assertIn("Fallo de red", res.get("error"))


class TestSyncStatePaginasVacias(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ruta_estado = os.path.join(self.test_dir, ".sync_state.json")
        self.estado = SyncState(self.ruta_estado)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_registro_y_consulta_paginas_vacias(self):
        self.estado.registrar_pagina_vacia("Articulo Vacio", "Articulo_Vacio.md", revid=10, accion="omitida")
        vacias = self.estado.obtener_paginas_vacias()
        self.assertIn("Articulo Vacio", vacias)
        self.assertEqual(vacias["Articulo Vacio"]["accion"], "omitida")
        self.assertEqual(vacias["Articulo Vacio"]["revid"], 10)

        # Comprobar si está omitida en la misma revisión
        self.assertTrue(self.estado.es_pagina_vacia_omitida("Articulo Vacio", rev_remota=10))

        # Si en remoto se actualizó con un revid mayor, deja de considerarse omitida
        self.assertFalse(self.estado.es_pagina_vacia_omitida("Articulo Vacio", rev_remota=11))
        self.assertNotIn("Articulo Vacio", self.estado.obtener_paginas_vacias())

    def test_eliminar_registro_vacia(self):
        self.estado.registrar_pagina_vacia("Test", "Test.md", revid=5, accion="omitida")
        self.assertIn("Test", self.estado.obtener_paginas_vacias())
        self.estado.eliminar_registro_vacia("Test")
        self.assertNotIn("Test", self.estado.obtener_paginas_vacias())

    def test_persistencia_en_json(self):
        self.estado.registrar_pagina_vacia("Articulo A", "Articulo_A.md", revid=1, accion="omitida")
        self.estado.guardar()

        # Recargar nuevo objeto desde disco
        estado2 = SyncState(self.ruta_estado)
        vacias = estado2.obtener_paginas_vacias()
        self.assertIn("Articulo A", vacias)
        self.assertEqual(vacias["Articulo A"]["revid"], 1)


class TestEmptyPagesManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ruta_estado = os.path.join(self.test_dir, ".sync_state.json")
        self.estado = SyncState(self.ruta_estado)
        self.mock_client = MagicMock()
        self.mock_client.base_url = "https://example.com"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_crear_plantilla_md_vacia(self):
        ruta_archivo = os.path.join(self.test_dir, "Pagina_Vacia.md")
        tam = crear_plantilla_md_vacia(
            cliente=self.mock_client,
            estado=self.estado,
            titulo="Pagina Vacia",
            nombre_archivo="Pagina_Vacia.md",
            ruta_archivo=ruta_archivo,
            revid=101
        )

        self.assertTrue(os.path.isfile(ruta_archivo))
        self.assertGreater(tam, 50)
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            contenido = f.read()
        self.assertIn("titulo: \"Pagina Vacia\"", contenido)
        self.assertIn("revid: 101", contenido)
        self.assertIn("# Pagina Vacia", contenido)

        # Comprobar que quedó registrada como artículo y como creada_local
        self.assertEqual(self.estado.obtener_revid("Pagina_Vacia.md"), 101)
        vacias = self.estado.obtener_paginas_vacias()
        self.assertEqual(vacias["Pagina Vacia"]["accion"], "creada_local")

    def test_eliminar_pagina_remota_exito(self):
        ruta_archivo = os.path.join(self.test_dir, "Pagina_Remota.md")
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            f.write("residual")

        self.mock_client.eliminar_pagina.return_value = {"exito": True, "title": "Pagina Remota"}

        ok, msg = eliminar_pagina_remota(
            cliente=self.mock_client,
            estado=self.estado,
            titulo="Pagina Remota",
            nombre_archivo="Pagina_Remota.md",
            ruta_archivo=ruta_archivo,
            revid=102
        )

        self.assertTrue(ok)
        self.assertFalse(os.path.exists(ruta_archivo))
        self.assertEqual(self.estado.obtener_paginas_vacias()["Pagina Remota"]["accion"], "eliminada_remoto")

    def test_gestionar_paginas_vacias_accion_create_md(self):
        items = [
            ("Articulo 1", "Articulo_1.md", os.path.join(self.test_dir, "Articulo_1.md"), 201),
            ("Articulo 2", "Articulo_2.md", os.path.join(self.test_dir, "Articulo_2.md"), 202),
        ]
        actualizados = []
        gestionar_paginas_vacias(
            cliente=self.mock_client,
            estado=self.estado,
            output_dir=self.test_dir,
            paginas_vacias=items,
            accion="create-md",
            articulos_actualizados_locales=actualizados
        )

        self.assertEqual(len(actualizados), 2)
        self.assertTrue(os.path.isfile(os.path.join(self.test_dir, "Articulo_1.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.test_dir, "Articulo_2.md")))

    def test_gestionar_paginas_vacias_accion_delete_remote(self):
        self.mock_client.eliminar_pagina.return_value = {"exito": True, "title": "Articulo Borrar"}
        items = [
            ("Articulo Borrar", "Articulo_Borrar.md", os.path.join(self.test_dir, "Articulo_Borrar.md"), 301)
        ]
        gestionar_paginas_vacias(
            cliente=self.mock_client,
            estado=self.estado,
            output_dir=self.test_dir,
            paginas_vacias=items,
            accion="delete-remote",
            auto_confirmar=True
        )

        self.mock_client.eliminar_pagina.assert_called_once_with(
            "Articulo Borrar", motivo="Página vacía eliminada por mediawiki_sync"
        )
        self.assertEqual(self.estado.obtener_paginas_vacias()["Articulo Borrar"]["accion"], "eliminada_remoto")

    def test_gestionar_paginas_vacias_accion_ignore(self):
        items = [
            ("Articulo Ignorar", "Articulo_Ignorar.md", os.path.join(self.test_dir, "Articulo_Ignorar.md"), 401)
        ]
        gestionar_paginas_vacias(
            cliente=self.mock_client,
            estado=self.estado,
            output_dir=self.test_dir,
            paginas_vacias=items,
            accion="ignore"
        )

        self.mock_client.eliminar_pagina.assert_not_called()
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, "Articulo_Ignorar.md")))
        self.assertEqual(self.estado.obtener_paginas_vacias()["Articulo Ignorar"]["accion"], "omitida")

    def test_gestionar_paginas_vacias_interactivo_crear(self):
        items = [
            ("Interactivo 1", "Interactivo_1.md", os.path.join(self.test_dir, "Interactivo_1.md"), 501)
        ]
        with patch("sys.stdin.isatty", return_value=True), \
             patch("builtins.input", return_value="1"):
            gestionar_paginas_vacias(
                cliente=self.mock_client,
                estado=self.estado,
                output_dir=self.test_dir,
                paginas_vacias=items,
                accion="ask"
            )

        self.assertTrue(os.path.isfile(os.path.join(self.test_dir, "Interactivo_1.md")))

    def test_listar_y_gestionar_paginas_vacias(self):
        self.estado.registrar_pagina_vacia("Omitida A", "Omitida_A.md", revid=601, accion="omitida")
        self.estado.guardar()

        with patch("sys.stdin.isatty", return_value=False):
            listar_y_gestionar_paginas_vacias(
                cliente=self.mock_client,
                output_dir=self.test_dir,
                accion="create-md"
            )

        self.assertTrue(os.path.isfile(os.path.join(self.test_dir, "Omitida_A.md")))


class TestDownloaderEmptyPages(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.mock_client = MagicMock()
        self.mock_client.base_url = "https://example.com"
        self.mock_client.obtener_catalogo_imagenes.return_value = []

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_descarga_detecta_pagina_vacia_y_aplica_accion(self):
        self.mock_client.obtener_lista_paginas.return_value = ["Pagina Vacia 1"]
        self.mock_client.obtener_revisiones_lote.return_value = {
            "Pagina Vacia 1": {"revid": 701, "timestamp": "2026-09-09T00:00:00Z"}
        }
        # Retorna html vacío
        self.mock_client.descargar_contenido_pagina.return_value = {
            "titulo": "Pagina Vacia 1",
            "html": "",
            "revid": 701
        }

        ejecutar_descarga(
            cliente=self.mock_client,
            output_dir=self.test_dir,
            empty_action="create-md"
        )

        ruta_esperada = os.path.join(self.test_dir, "Pagina_Vacia_1.md")
        self.assertTrue(os.path.isfile(ruta_esperada))
        with open(ruta_esperada, "r", encoding="utf-8") as f:
            contenido = f.read()
        self.assertIn("titulo: \"Pagina Vacia 1\"", contenido)
        self.assertIn("revid: 701", contenido)


if __name__ == "__main__":
    unittest.main()
