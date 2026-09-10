"""
Pruebas unitarias para la resolución de colisiones de nombres de archivo,
mapeo de títulos y filtrado de redirecciones en MediaWiki Sync.
"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

from mw_sync.converters.html_to_md import sanitizar_nombre_archivo, asignar_nombres_archivos
from mw_sync.state import SyncState
from mw_sync.client import MediaWikiClient
from mw_sync.downloader import ejecutar_descarga


class TestResolucionColisiones(unittest.TestCase):
    def test_asignar_nombres_sin_colisiones(self):
        titulos = ["Manual de Usuario", "Guía de Inicio", "Preguntas Frecuentes"]
        mapa = asignar_nombres_archivos(titulos)
        self.assertEqual(mapa["Manual de Usuario"], "Manual_de_Usuario.md")
        self.assertEqual(mapa["Guía de Inicio"], "Guía_de_Inicio.md")
        self.assertEqual(mapa["Preguntas Frecuentes"], "Preguntas_Frecuentes.md")
        self.assertEqual(len(set(mapa.values())), 3)

    def test_asignar_nombres_con_puntos_colisiones(self):
        """Valida casos como 'Dictámenes de la CIPAE 2026-03-11' y 'Dictámenes de la CIPAE 2026-03-11.'"""
        titulos = ["Dictámenes de la CIPAE 2026-03-11", "Dictámenes de la CIPAE 2026-03-11."]
        mapa = asignar_nombres_archivos(titulos)
        self.assertEqual(len(set(mapa.values())), 2)
        archivos = list(mapa.values())
        self.assertIn("Dictámenes_de_la_CIPAE_2026-03-11.md", archivos)
        self.assertIn("Dictámenes_de_la_CIPAE_2026-03-11_1.md", archivos)

    def test_asignar_nombres_multiples_colisiones(self):
        """Valida casos de 3 colisiones como CIPAE 2026-02-25 con '', '.' y '..'"""
        titulos = [
            "Dictámenes de la CIPAE 2026-02-25",
            "Dictámenes de la CIPAE 2026-02-25.",
            "Dictámenes de la CIPAE 2026-02-25.."
        ]
        mapa = asignar_nombres_archivos(titulos)
        self.assertEqual(len(set(mapa.values())), 3)
        self.assertEqual(mapa["Dictámenes de la CIPAE 2026-02-25"], "Dictámenes_de_la_CIPAE_2026-02-25.md")
        self.assertEqual(mapa["Dictámenes de la CIPAE 2026-02-25."], "Dictámenes_de_la_CIPAE_2026-02-25_1.md")
        self.assertEqual(mapa["Dictámenes de la CIPAE 2026-02-25.."], "Dictámenes_de_la_CIPAE_2026-02-25_2.md")

    def test_asignar_nombres_dos_puntos_y_espacios(self):
        """Valida casos como 'Manual IAE: Anexo 1' vs 'Manual IAE:Anexo 1'"""
        titulos = ["Manual IAE: Anexo 1", "Manual IAE:Anexo 1"]
        mapa = asignar_nombres_archivos(titulos)
        self.assertEqual(len(set(mapa.values())), 2)
        self.assertEqual(mapa["Manual IAE: Anexo 1"], "Manual_IAE_Anexo_1.md")
        self.assertEqual(mapa["Manual IAE:Anexo 1"], "Manual_IAE_Anexo_1_1.md")

    def test_asignar_nombres_preserva_estado_existente(self):
        """Comprueba que si un archivo ya estaba registrado en el estado, se conserva su asignación."""
        mapa_estado = {
            "Manual IAE:Anexo 1": "Manual_IAE_Anexo_1.md"
        }
        titulos = ["Manual IAE: Anexo 1", "Manual IAE:Anexo 1"]
        mapa = asignar_nombres_archivos(titulos, estado=mapa_estado)
        self.assertEqual(mapa["Manual IAE:Anexo 1"], "Manual_IAE_Anexo_1.md")
        self.assertEqual(mapa["Manual IAE: Anexo 1"], "Manual_IAE_Anexo_1_1.md")


class TestStateTitleMapping(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.tmpdir, ".sync_state.json")
        self.state = SyncState(self.state_file)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_obtener_mapa_titulos_existentes(self):
        self.state.registrar_articulo("Articulo_A.md", "Artículo A", "hash1", revid=10)
        self.state.registrar_articulo("Articulo_B.md", "Artículo B", "hash2", revid=20)
        self.state.registrar_pagina_vacia("Página Vacía", "Pagina_Vacia.md", revid=30)

        mapa = self.state.obtener_mapa_titulos_existentes()
        self.assertEqual(mapa.get("Artículo A"), "Articulo_A.md")
        self.assertEqual(mapa.get("Artículo B"), "Articulo_B.md")
        self.assertEqual(mapa.get("Página Vacía"), "Pagina_Vacia.md")

        self.assertEqual(self.state.obtener_archivo_por_titulo("Artículo A"), "Articulo_A.md")
        self.assertEqual(self.state.obtener_archivo_por_titulo("Página Vacía"), "Pagina_Vacia.md")
        self.assertIsNone(self.state.obtener_archivo_por_titulo("Inexistente"))


class TestRedirectFiltering(unittest.TestCase):
    def test_client_apfilterredir_param(self):
        client = MediaWikiClient("https://example.com/api.php")
        client._api_get = MagicMock(return_value={"query": {"allpages": []}})

        # Por defecto debe pedir nonredirects
        client.obtener_lista_paginas(incluir_redirecciones=False)
        args, kwargs = client._api_get.call_args
        self.assertEqual(args[0].get("apfilterredir"), "nonredirects")

        # Con incluir_redirecciones=True debe pedir all
        client.obtener_lista_paginas(incluir_redirecciones=True)
        args, kwargs = client._api_get.call_args
        self.assertEqual(args[0].get("apfilterredir"), "all")


class TestDownloaderNoInfiniteLoopWithCollisions(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_descarga_incremental_resuelve_colisiones_sin_bucle(self):
        client = MagicMock()
        titulos = ["Dictámenes de la CIPAE 2026-03-11", "Dictámenes de la CIPAE 2026-03-11."]
        client.obtener_lista_paginas.return_value = titulos
        client.obtener_revisiones_lote.return_value = {
            "Dictámenes de la CIPAE 2026-03-11": {"revid": 100, "timestamp": "2026-03-11"},
            "Dictámenes de la CIPAE 2026-03-11.": {"revid": 101, "timestamp": "2026-03-11"}
        }

        def fake_descargar(titulo):
            return {
                "titulo": titulo,
                "html": f"<p>Contenido para {titulo}</p>",
                "revid": 100 if titulo == "Dictámenes de la CIPAE 2026-03-11" else 101
            }

        client.descargar_contenido_pagina.side_effect = fake_descargar
        client.base_url = "https://example.com"
        client.obtener_catalogo_imagenes.return_value = []

        # 1. Primera descarga
        ejecutar_descarga(client, self.tmpdir, no_imagenes=True)

        archivo_1 = os.path.join(self.tmpdir, "Dictámenes_de_la_CIPAE_2026-03-11.md")
        archivo_2 = os.path.join(self.tmpdir, "Dictámenes_de_la_CIPAE_2026-03-11_1.md")

        self.assertTrue(os.path.isfile(archivo_1), f"Debe existir {archivo_1}")
        self.assertTrue(os.path.isfile(archivo_2), f"Debe existir {archivo_2}")

        with open(archivo_1, "r", encoding="utf-8") as f:
            c1 = f.read()
        with open(archivo_2, "r", encoding="utf-8") as f:
            c2 = f.read()

        self.assertIn("Contenido para Dictámenes de la CIPAE 2026-03-11", c1)
        self.assertIn("Contenido para Dictámenes de la CIPAE 2026-03-11.", c2)

        # 2. Segunda descarga: AMBOS deben estar al día (0 artículos pendientes, sin bucle)
        ejecutar_descarga(client, self.tmpdir, no_imagenes=True)

        # Verificar el estado
        state = SyncState(os.path.join(self.tmpdir, ".sync_state.json"))
        self.assertEqual(state.obtener_revid("Dictámenes_de_la_CIPAE_2026-03-11.md"), 100)
        self.assertEqual(state.obtener_revid("Dictámenes_de_la_CIPAE_2026-03-11_1.md"), 101)


if __name__ == "__main__":
    unittest.main()
