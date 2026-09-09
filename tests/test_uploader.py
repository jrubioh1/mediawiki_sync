"""
Pruebas unitarias para el módulo de subida (uploader.py),
especialmente la resolución interactiva y forzada de conflictos.
"""
import unittest
from unittest.mock import MagicMock, patch
import tempfile
import os
import shutil
from mw_sync.uploader import ejecutar_subida


class TestUploaderConflict(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.md_file = os.path.join(self.test_dir, "Articulo_Test.md")
        with open(self.md_file, "w", encoding="utf-8") as f:
            f.write("---\ntitulo: Articulo Test\nrevid: 100\n---\n# Articulo Test\n\nContenido local.")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_conflicto_confirmado_por_consola(self):
        mock_client = MagicMock()
        mock_client.api_url = "https://example.com/api.php"
        mock_client.editar_pagina.side_effect = [
            {"exito": False, "conflict": True, "error": "Edit conflict"},
            {"exito": True, "newrevid": 105}
        ]
        mock_client.descargar_contenido_pagina.return_value = {"html": "<p>Remoto</p>"}

        with patch("sys.stdin.isatty", return_value=True), \
             patch("builtins.input", return_value="s"):
            ejecutar_subida(mock_client, self.test_dir, archivo_especifico=self.md_file)

        self.assertEqual(mock_client.editar_pagina.call_count, 2)
        args2, kwargs2 = mock_client.editar_pagina.call_args_list[1]
        self.assertEqual(kwargs2.get("baserevid"), 0)

    def test_conflicto_rechazado_por_consola(self):
        mock_client = MagicMock()
        mock_client.api_url = "https://example.com/api.php"
        mock_client.editar_pagina.return_value = {"exito": False, "conflict": True, "error": "Edit conflict"}
        mock_client.descargar_contenido_pagina.return_value = {"html": "<p>Remoto</p>"}

        with patch("sys.stdin.isatty", return_value=True), \
             patch("builtins.input", return_value="n"):
            ejecutar_subida(mock_client, self.test_dir, archivo_especifico=self.md_file)

        self.assertEqual(mock_client.editar_pagina.call_count, 1)
        conflict_file = os.path.join(self.test_dir, "Articulo_Test.md.servidor.conflict")
        self.assertTrue(os.path.exists(conflict_file))

    def test_conflicto_auto_confirmar(self):
        mock_client = MagicMock()
        mock_client.api_url = "https://example.com/api.php"
        mock_client.editar_pagina.side_effect = [
            {"exito": False, "conflict": True, "error": "Edit conflict"},
            {"exito": True, "newrevid": 106}
        ]
        mock_client.descargar_contenido_pagina.return_value = {"html": "<p>Remoto</p>"}

        ejecutar_subida(mock_client, self.test_dir, archivo_especifico=self.md_file, auto_confirmar_conflicto=True)

        self.assertEqual(mock_client.editar_pagina.call_count, 2)
        args2, kwargs2 = mock_client.editar_pagina.call_args_list[1]
        self.assertEqual(kwargs2.get("baserevid"), 0)


if __name__ == "__main__":
    unittest.main()
