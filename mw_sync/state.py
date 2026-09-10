"""
Módulo de Gestión de Estado (.sync_state.json) y control de versiones por SHA-256.
"""
import os
import json
import time
import hashlib
from datetime import datetime
from mw_sync.i18n import _


def calcular_sha256(ruta_archivo: str) -> str:
    """Calcula el hash SHA256 de un archivo para control de modificaciones."""
    h = hashlib.sha256()
    with open(ruta_archivo, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class SyncState:
    """
    Gestiona el registro de estado de sincronización.
    Permite detectar cambios locales y remotos de forma rápida.
    """

    def __init__(self, ruta_estado: str):
        self.ruta = ruta_estado
        self.datos = {
            "articulos": {},
            "imagenes": {},
            "paginas_vacias": {},
            "ultima_sincronizacion": None,
            "version_esquema": "3.0"
        }
        self.cargar()

    def cargar(self):
        if os.path.exists(self.ruta):
            try:
                with open(self.ruta, "r", encoding="utf-8") as f:
                    cargados = json.load(f)
                    if isinstance(cargados, dict):
                        self.datos.update(cargados)
                        if "paginas_vacias" not in self.datos:
                            self.datos["paginas_vacias"] = {}
            except Exception as e:
                print(_("state_read_error", path=self.ruta, err=e))

    def guardar(self):
        self.datos["ultima_sincronizacion"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(os.path.abspath(self.ruta)), exist_ok=True)
        try:
            temp_file = self.ruta + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.datos, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, self.ruta)
        except Exception as e:
            print(_("state_save_error", err=e))

    def registrar_articulo(self, nombre_archivo: str, titulo: str, hash_sha256: str, revid: int = 0):
        self.datos["articulos"][nombre_archivo] = {
            "titulo": titulo,
            "hash": hash_sha256,
            "revid": revid,
            "mtime": time.time()
        }

    def registrar_imagen(self, nombre_archivo: str, hash_sha256: str, sha1_remoto: str = ""):
        self.datos["imagenes"][nombre_archivo] = {
            "hash": hash_sha256,
            "sha1": sha1_remoto,
            "mtime": time.time()
        }

    def obtener_sha1_imagen(self, nombre_archivo: str) -> str | None:
        return self.datos.get("imagenes", {}).get(nombre_archivo, {}).get("sha1")

    def obtener_revid(self, nombre_archivo: str) -> int:
        return self.datos["articulos"].get(nombre_archivo, {}).get("revid", 0)

    def obtener_hash(self, nombre_archivo: str) -> str | None:
        if nombre_archivo in self.datos["articulos"]:
            return self.datos["articulos"][nombre_archivo].get("hash")
        if nombre_archivo in self.datos["imagenes"]:
            return self.datos["imagenes"][nombre_archivo].get("hash")
        return None

    def obtener_mapa_titulos_existentes(self) -> dict[str, str]:
        """Devuelve un mapeo {titulo: nombre_archivo} de todos los artículos y páginas vacías registradas."""
        mapa = {}
        for nom, info in self.datos.get("articulos", {}).items():
            t = info.get("titulo")
            if t:
                mapa[t] = nom
        for t, info in self.datos.get("paginas_vacias", {}).items():
            arch = info.get("archivo")
            if arch and t not in mapa:
                mapa[t] = arch
        return mapa

    def obtener_archivo_por_titulo(self, titulo: str) -> str | None:
        """Devuelve el nombre de archivo asociado a un título si ya está registrado."""
        for nom, info in self.datos.get("articulos", {}).items():
            if info.get("titulo") == titulo:
                return nom
        vacias = self.datos.get("paginas_vacias", {})
        if titulo in vacias:
            return vacias[titulo].get("archivo")
        return None

    def sincronizar_hashes_locales(self, output_dir: str):
        """Recalcula y actualiza los hashes de todos los archivos locales existentes."""
        for f in os.listdir(output_dir):
            if f.endswith(".md") and f != "00_INDICE_MEDIAWIKI.md":
                ruta = os.path.join(output_dir, f)
                h = calcular_sha256(ruta)
                if f in self.datos["articulos"]:
                    self.datos["articulos"][f]["hash"] = h
        self.guardar()

    def registrar_pagina_vacia(self, titulo: str, nombre_archivo: str, revid: int = 0, accion: str = "omitida"):
        """
        Registra una página vacía y la acción realizada sobre ella.
        Acciones posibles:
          - 'omitida': se ignora en descargas posteriores mientras no cambie el revid.
          - 'creada_local': se generó el archivo .md vacío localmente para rellenar.
          - 'eliminada_remoto': se eliminó del servidor MediaWiki.
        """
        if "paginas_vacias" not in self.datos:
            self.datos["paginas_vacias"] = {}
        self.datos["paginas_vacias"][titulo] = {
            "archivo": nombre_archivo,
            "revid": revid,
            "accion": accion,
            "mtime": time.time()
        }

    def es_pagina_vacia_omitida(self, titulo: str, rev_remota: int) -> bool:
        """
        Comprueba si la página está registrada como vacía y omitida.
        Si la revisión remota es mayor a la registrada, significa que alguien
        la editó en la wiki, por lo que deja de considerarse omitida.
        """
        vacias = self.datos.get("paginas_vacias", {})
        if titulo in vacias:
            info = vacias[titulo]
            if info.get("accion") == "omitida":
                if rev_remota <= info.get("revid", 0):
                    return True
                else:
                    # Se ha editado en la wiki; eliminamos del registro de vacías
                    del vacias[titulo]
                    return False
        return False

    def obtener_paginas_vacias(self) -> dict:
        """Devuelve el diccionario de páginas vacías registradas."""
        return self.datos.get("paginas_vacias", {})

    def eliminar_registro_vacia(self, titulo: str):
        """Elimina el registro de una página vacía."""
        if "paginas_vacias" in self.datos and titulo in self.datos["paginas_vacias"]:
            del self.datos["paginas_vacias"][titulo]

