"""
Pruebas unitarias para el autodescubrimiento de .env y resolución de directorio (wiki_docs).
"""
import unittest
import tempfile
import os
import shutil
from unittest.mock import patch, MagicMock
from pathlib import Path

from mw_sync.config import actualizar_config_desde_directorio, DEFAULT_CONFIG
from mw_sync import cli


class TestConfigDirectoryDiscovery(unittest.TestCase):
    def setUp(self):
        self.tmp_root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_root)

    def test_dir_proyecto_sin_mw_output_dir_con_wiki_docs(self):
        """
        Si se pasa --dir apuntando a la raíz del proyecto donde hay .env y wiki_docs/,
        debe redirigir automáticamente a wiki_docs/.
        """
        project_dir = os.path.join(self.tmp_root, "wiki_clientes")
        wiki_docs_dir = os.path.join(project_dir, "wiki_docs")
        os.makedirs(wiki_docs_dir, exist_ok=True)

        env_file = os.path.join(project_dir, ".env")
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("MW_URL=https://clientes.empresa.com/api.php\nMW_WIKI_USER=cliente_user\n")

        with open(os.path.join(wiki_docs_dir, "Manual.md"), "w", encoding="utf-8") as f:
            f.write("# Manual de Clientes\n")

        resuelto = actualizar_config_desde_directorio(project_dir)
        self.assertEqual(resuelto, str(Path(wiki_docs_dir).resolve()))
        self.assertEqual(DEFAULT_CONFIG["OUTPUT_DIR"], str(Path(wiki_docs_dir).resolve()))
        self.assertEqual(DEFAULT_CONFIG["MEDIAWIKI_URL"], "https://clientes.empresa.com/api.php")
        self.assertEqual(DEFAULT_CONFIG["WIKI_USER"], "cliente_user")

    def test_dir_proyecto_nuevo_sin_wiki_docs_existente(self):
        """
        Si es un proyecto nuevo (descarga inicial) donde sólo existe el .env en la raíz,
        debe redirigir por convención a <proyecto>/wiki_docs.
        """
        project_dir = os.path.join(self.tmp_root, "wiki_nueva")
        os.makedirs(project_dir, exist_ok=True)

        env_file = os.path.join(project_dir, ".env")
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("MW_URL=https://nueva.empresa.com/api.php\n")

        resuelto = actualizar_config_desde_directorio(project_dir)
        esperado = str(Path(project_dir).resolve() / "wiki_docs")
        self.assertEqual(resuelto, esperado)
        self.assertEqual(DEFAULT_CONFIG["OUTPUT_DIR"], esperado)

    def test_dir_proyecto_con_mw_output_dir_relativo(self):
        """
        Si en el .env se define MW_OUTPUT_DIR=./mi_doc_personalizada,
        debe resolverse relativo a la carpeta del proyecto donde reside el .env.
        """
        project_dir = os.path.join(self.tmp_root, "wiki_custom")
        os.makedirs(project_dir, exist_ok=True)

        env_file = os.path.join(project_dir, ".env")
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("MW_URL=https://custom.empresa.com/api.php\nMW_OUTPUT_DIR=./mi_doc_personalizada\n")

        resuelto = actualizar_config_desde_directorio(project_dir)
        esperado = str(Path(project_dir).resolve() / "mi_doc_personalizada")
        self.assertEqual(resuelto, esperado)
        self.assertEqual(DEFAULT_CONFIG["OUTPUT_DIR"], esperado)

    def test_dir_apuntando_directamente_a_wiki_docs(self):
        """
        Si el usuario pasa directamente la subcarpeta wiki_docs en --dir,
        no debe anidar wiki_docs/wiki_docs y debe detectar el .env del padre.
        """
        project_dir = os.path.join(self.tmp_root, "wiki_directa")
        wiki_docs_dir = os.path.join(project_dir, "wiki_docs")
        os.makedirs(wiki_docs_dir, exist_ok=True)

        env_file = os.path.join(project_dir, ".env")
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("MW_URL=https://directa.empresa.com/api.php\n")

        resuelto = actualizar_config_desde_directorio(wiki_docs_dir)
        esperado = str(Path(wiki_docs_dir).resolve())
        self.assertEqual(resuelto, esperado)
        self.assertEqual(DEFAULT_CONFIG["OUTPUT_DIR"], esperado)
        self.assertEqual(DEFAULT_CONFIG["MEDIAWIKI_URL"], "https://directa.empresa.com/api.php")

    def test_cli_main_upload_con_dir_proyecto(self):
        """
        Verifica que al ejecutar 'mw-sync --upload --dir /ruta/al/proyecto',
        ejecutar_subida reciba output_dir apuntando a /ruta/al/proyecto/wiki_docs.
        """
        project_dir = os.path.join(self.tmp_root, "wiki_test_cli")
        wiki_docs_dir = os.path.join(project_dir, "wiki_docs")
        os.makedirs(wiki_docs_dir, exist_ok=True)

        env_file = os.path.join(project_dir, ".env")
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("MW_URL=https://test.cli.empresa.com/api.php\nMW_WIKI_USER=user_cli\n")

        with patch("mw_sync.cli.MediaWikiClient") as mock_client_cls, \
             patch("mw_sync.cli.ejecutar_subida") as mock_subida:
            mock_client_inst = MagicMock()
            mock_client_inst.test_conexion.return_value = (True, "TestWiki")
            mock_client_inst.login.return_value = (True, "OK")
            mock_client_cls.return_value = mock_client_inst

            # Ejecución simulada con --dry-run
            cli.main(["--upload", "--dir", project_dir, "--dry-run"])

            mock_subida.assert_called_once()
            _, kwargs = mock_subida.call_args
            esperado = str(Path(wiki_docs_dir).resolve())
            self.assertEqual(kwargs.get("output_dir"), esperado)

    def test_upload_archivo_relativo_dentro_de_output_dir(self):
        """
        Verifica que al especificar un archivo relativo como '--file Pagina.md'
        junto a un output_dir distinto de cwd, el uploader lo encuentre en output_dir.
        """
        from mw_sync.uploader import ejecutar_subida

        project_dir = os.path.join(self.tmp_root, "wiki_test_file")
        wiki_docs_dir = os.path.join(project_dir, "wiki_docs")
        os.makedirs(wiki_docs_dir, exist_ok=True)
        md_path = os.path.join(wiki_docs_dir, "Articulo_Relativo.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Articulo Relativo\n\nContenido.")

        mock_client = MagicMock()
        mock_client.api_url = "https://example.com/api.php"
        mock_client.editar_pagina.return_value = {"exito": True, "newrevid": 200}

        # Pasamos solo el nombre de archivo "Articulo_Relativo.md"
        ejecutar_subida(
            cliente=mock_client,
            output_dir=wiki_docs_dir,
            archivo_especifico="Articulo_Relativo.md",
            forzar=True
        )

        mock_client.editar_pagina.assert_called_once()
        self.assertEqual(mock_client.editar_pagina.call_args[0][0], "Articulo Relativo")

    def test_variable_en_os_environ(self):
        """
        Verifica que si MW_OUTPUT_DIR está en os.environ (sin .env),
        se resuelva adecuadamente hacia la ruta del sistema operativo.
        """
        ruta_os = os.path.join(self.tmp_root, "os_docs_dir")
        os.makedirs(ruta_os, exist_ok=True)

        with patch("pathlib.Path.cwd", return_value=Path(self.tmp_root)):
            with patch.dict(os.environ, {"MW_OUTPUT_DIR": ruta_os}, clear=False):
                # Simulamos ejecución sin pasar --dir
                resuelto = actualizar_config_desde_directorio(None)
                self.assertEqual(resuelto, str(Path(ruta_os).resolve()))
                self.assertEqual(DEFAULT_CONFIG["OUTPUT_DIR"], str(Path(ruta_os).resolve()))


if __name__ == "__main__":
    unittest.main()

