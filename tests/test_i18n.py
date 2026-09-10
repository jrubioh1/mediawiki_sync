"""
Pruebas unitarias para el módulo de internacionalización (i18n).
"""
import os
import unittest
from unittest.mock import patch

from mw_sync.i18n import (
    TRANSLATIONS,
    IDIOMAS_SOPORTADOS,
    set_language,
    get_language,
    detectar_idioma_sistema,
    init_language,
    t,
    _,
    parse_bool_response,
    is_spanish,
    is_english,
)


class TestI18nModule(unittest.TestCase):
    def setUp(self):
        self.original_lang = get_language()

    def tearDown(self):
        set_language(self.original_lang)

    def test_idiomas_soportados(self):
        self.assertIn("es", IDIOMAS_SOPORTADOS)
        self.assertIn("en", IDIOMAS_SOPORTADOS)

    def test_set_and_get_language(self):
        set_language("en")
        self.assertEqual(get_language(), "en")
        self.assertTrue(is_english())
        self.assertFalse(is_spanish())

        set_language("es")
        self.assertEqual(get_language(), "es")
        self.assertTrue(is_spanish())
        self.assertFalse(is_english())

    def test_set_language_normalization_and_fallback(self):
        # Prefijos regionales como en_US o es_ES
        set_language("en_US.UTF-8")
        self.assertEqual(get_language(), "en")

        set_language("es_ES")
        self.assertEqual(get_language(), "es")

        # Idioma no soportado (debe hacer fallback a es)
        set_language("fr")
        self.assertEqual(get_language(), "es")

        # Idioma None o vacío
        set_language("")
        self.assertEqual(get_language(), "es")

    def test_catalog_parity(self):
        """Valida que todas las claves definidas en español existan también en inglés y viceversa."""
        claves_es = set(TRANSLATIONS["es"].keys())
        claves_en = set(TRANSLATIONS["en"].keys())

        faltan_en_ingles = claves_es - claves_en
        faltan_en_espanol = claves_en - claves_es

        self.assertEqual(faltan_en_ingles, set(), f"Claves presentes en español pero ausentes en inglés: {faltan_en_ingles}")
        self.assertEqual(faltan_en_espanol, set(), f"Claves presentes en inglés pero ausentes en español: {faltan_en_espanol}")

    def test_translation_and_formatting(self):
        set_language("es")
        txt_es = _("cli_server", url="https://wiki.ejemplo.es")
        self.assertEqual(txt_es, "Servidor:     https://wiki.ejemplo.es")

        set_language("en")
        txt_en = _("cli_server", url="https://wiki.ejemplo.es")
        self.assertEqual(txt_en, "Server:       https://wiki.ejemplo.es")

    def test_missing_key_fallback(self):
        # Clave inexistente en ambos catálogos
        self.assertEqual(t("clave_totalmente_inexistente"), "clave_totalmente_inexistente")

    def test_detectar_idioma_sistema(self):
        with patch.dict(os.environ, {"MW_LANG": "en"}, clear=False):
            self.assertEqual(detectar_idioma_sistema(), "en")

        with patch.dict(os.environ, {"MW_LANG": "es"}, clear=False):
            self.assertEqual(detectar_idioma_sistema(), "es")

        with patch.dict(os.environ, {"MW_LANG": "", "LANG": "en_GB.UTF-8"}, clear=False):
            self.assertEqual(detectar_idioma_sistema(), "en")

        with patch.dict(os.environ, {"MW_LANG": "", "LANG": "es_MX.UTF-8"}, clear=False):
            self.assertEqual(detectar_idioma_sistema(), "es")

    def test_parse_bool_response(self):
        # Afirmativos
        for afirmativo in ("s", "si", "sí", "y", "yes", "true", "1", "YES", "SI"):
            self.assertTrue(parse_bool_response(afirmativo), f"Fallo con {afirmativo}")

        # Negativos
        for negativo in ("n", "no", "false", "0", "NO", "N"):
            self.assertFalse(parse_bool_response(negativo), f"Fallo con {negativo}")

        # Inválidos o vacíos
        self.assertIsNone(parse_bool_response(""))
        self.assertIsNone(parse_bool_response(None))
        self.assertIsNone(parse_bool_response("quizas"))

    def test_cli_version_flag(self):
        from io import StringIO
        import contextlib
        from mw_sync.cli import main
        from mw_sync import __version__

        out = StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as cm:
            main(["--version"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn(__version__, out.getvalue())

    def test_cli_lang_override(self):
        from mw_sync.cli import main
        with patch("mw_sync.cli.sanear_directorio", return_value=(0, 0)):
            main(["--lang", "en", "--sanitize", "--dir", "/tmp"])
            self.assertEqual(get_language(), "en")

        with patch("mw_sync.cli.sanear_directorio", return_value=(0, 0)):
            main(["--lang", "es", "--sanitize", "--dir", "/tmp"])
            self.assertEqual(get_language(), "es")


if __name__ == "__main__":
    unittest.main()
