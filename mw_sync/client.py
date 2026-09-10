"""
Cliente HTTP para la API de MediaWiki.
Soporta HTTP Basic Auth, sesiones, reintentos con backoff, tokens CSRF,
consultas por lotes (batch revisions) y detección de conflictos (baserevid).
"""
import os
import ssl
import json
import time
import uuid
import base64
import mimetypes
import urllib.parse
import urllib.request
import urllib.error
import http.cookiejar
from mw_sync.config import EXTENSIONES_MULTIMEDIA, DEFAULT_CONFIG

try:
    import requests
    import urllib3
    from requests.auth import HTTPBasicAuth
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def es_pagina_de_contenido(titulo: str) -> bool:
    """Filtra páginas especiales, de sistema o archivos multimedia."""
    t_lower = titulo.lower().strip()
    for ext in EXTENSIONES_MULTIMEDIA:
        if t_lower.endswith(ext):
            return False
    prefijos_sistema = (
        "archivo:", "file:", "media:", "especial:", "special:",
        "plantilla:", "template:", "categoría:", "category:", "ayuda:", "help:"
    )
    return not t_lower.startswith(prefijos_sistema)


class MediaWikiClient:
    """Cliente de alto rendimiento para interactuar con MediaWiki Action API."""

    def __init__(self, url: str, http_user: str = None, http_password: str = None,
                 wiki_user: str = None, wiki_password: str = None,
                 verify_ssl: bool = False, ca_bundle: str = None, user_agent: str = None,
                 user: str = None, password: str = None):
        self.api_url = url.strip()
        self.base_url = self.api_url.split("/api.php")[0]
        # Capa 1: Apache / Proxy (HTTP Basic Auth)
        self.http_user = http_user or user
        self.http_password = http_password or password
        # Capa 2: MediaWiki (Action API Login)
        self.wiki_user = wiki_user
        self.wiki_password = wiki_password
        # Atributos de compatibilidad
        self.user = self.wiki_user or self.http_user
        self.password = self.wiki_password or self.http_password
        self.verify_ssl = ca_bundle if ca_bundle else verify_ssl
        self.user_agent = user_agent or DEFAULT_CONFIG["USER_AGENT"]
        self._csrf_token = None

        self.timeout = float(os.getenv("MW_TIMEOUT", "10.0"))

        self.session = None
        self.opener = None

        if HAS_REQUESTS:
            self.session = requests.Session()
            self.session.verify = self.verify_ssl
            self.session.headers.update({"User-Agent": self.user_agent})

            # Política de reintentos automáticos
            retries = Retry(
                total=2,
                backoff_factor=0.3,
                status_forcelist=[500, 502, 503, 504, 429]
            )
            adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)

            if self.http_user and self.http_password:
                self.session.auth = HTTPBasicAuth(self.http_user, self.http_password)
        else:
            self.cookie_jar = http.cookiejar.CookieJar()
            handlers = [urllib.request.HTTPCookieProcessor(self.cookie_jar)]
            if not verify_ssl and not ca_bundle:
                ctx = ssl._create_unverified_context()
                handlers.append(urllib.request.HTTPSHandler(context=ctx))
            elif ca_bundle:
                ctx = ssl.create_default_context(cafile=ca_bundle)
                handlers.append(urllib.request.HTTPSHandler(context=ctx))

            if self.http_user and self.http_password:
                passman = urllib.request.HTTPPasswordMgrWithDefaultRealm()
                passman.add_password(None, self.api_url, self.http_user, self.http_password)
                handlers.append(urllib.request.HTTPBasicAuthHandler(passman))
            self.opener = urllib.request.build_opener(*handlers)

    def _api_get(self, params: dict) -> dict:
        params["format"] = "json"
        if HAS_REQUESTS:
            r = self.session.get(self.api_url, params=params, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        else:
            url = self.api_url + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            with self.opener.open(req, timeout=25.0) as resp:
                return json.loads(resp.read().decode("utf-8"))

    def _api_post(self, data: dict) -> dict:
        data["format"] = "json"
        if HAS_REQUESTS:
            r = self.session.post(self.api_url, data=data, timeout=self.timeout * 2)
            r.raise_for_status()
            return r.json()
        else:
            payload = urllib.parse.urlencode(data).encode("utf-8")
            req = urllib.request.Request(self.api_url, data=payload, headers={"User-Agent": self.user_agent})
            with self.opener.open(req, timeout=self.timeout * 2) as resp:
                return json.loads(resp.read().decode("utf-8"))

    def test_conexion(self) -> tuple[bool, str]:
        """Verifica la conectividad con la API y devuelve (éxito, mensaje)."""
        try:
            data = self._api_get({"action": "query", "meta": "siteinfo"})
            sitename = data.get("query", {}).get("general", {}).get("sitename", "MediaWiki")
            return True, sitename
        except Exception as e:
            return False, str(e)

    def login(self) -> tuple[bool, str]:
        """Inicia sesión en MediaWiki usando la Action API."""
        if not self.wiki_user or not self.wiki_password:
            return False, "No se han configurado credenciales de MediaWiki (MW_WIKI_USER / MW_WIKI_PASS)"

        # 1. MediaWiki moderno (>= 1.27): obtener logintoken
        login_token = None
        try:
            tok_data = self._api_get({"action": "query", "meta": "tokens", "type": "login"})
            login_token = tok_data.get("query", {}).get("tokens", {}).get("logintoken")
        except Exception:
            login_token = None

        if login_token:
            payload = {
                "action": "login",
                "lgname": self.wiki_user,
                "lgpassword": self.wiki_password,
                "lgtoken": login_token
            }
            try:
                res = self._api_post(payload)
            except Exception as e:
                return False, f"Fallo en la petición de login: {e}"

            login_res = res.get("login", {})
            result = login_res.get("result")

            if result == "Success":
                self._csrf_token = None
                self.obtener_token_csrf(forzar=True)
                usuario = login_res.get("lgusername", self.wiki_user)
                return True, f"Sesión iniciada con éxito como '{usuario}'"
            elif result == "NeedToken":
                payload["lgtoken"] = login_res.get("token")
                res2 = self._api_post(payload)
                if res2.get("login", {}).get("result") == "Success":
                    self._csrf_token = None
                    self.obtener_token_csrf(forzar=True)
                    return True, f"Sesión iniciada con éxito como '{self.wiki_user}'"
                return False, res2.get("login", {}).get("reason", str(res2))
            else:
                return False, login_res.get("reason", str(login_res))

        # 2. MediaWiki legacy (< 1.27)
        try:
            res = self._api_post({
                "action": "login",
                "lgname": self.wiki_user,
                "lgpassword": self.wiki_password
            })
            login_res = res.get("login", {})
            if login_res.get("result") == "NeedToken":
                token = login_res.get("token")
                res2 = self._api_post({
                    "action": "login",
                    "lgname": self.wiki_user,
                    "lgpassword": self.wiki_password,
                    "lgtoken": token
                })
                if res2.get("login", {}).get("result") == "Success":
                    self._csrf_token = None
                    self.obtener_token_csrf(forzar=True)
                    return True, f"Sesión iniciada con éxito como '{self.wiki_user}'"
                return False, res2.get("login", {}).get("reason", str(res2))
            elif login_res.get("result") == "Success":
                self._csrf_token = None
                self.obtener_token_csrf(forzar=True)
                return True, f"Sesión iniciada con éxito como '{self.wiki_user}'"
            return False, login_res.get("reason", str(login_res))
        except Exception as e:
            return False, f"Fallo en autenticación MediaWiki: {e}"

    def obtener_informacion_usuario(self) -> dict:
        """Consulta el estado del usuario actual (nombre, si es anónimo y grupos a los que pertenece)."""
        try:
            data = self._api_get({
                "action": "query",
                "meta": "userinfo",
                "uiprop": "groups|rights"
            })
            return data.get("query", {}).get("userinfo", {})
        except Exception:
            return {}

    def obtener_token_csrf(self, forzar: bool = False) -> str:
        """Obtiene el token CSRF para realizar ediciones seguras."""
        if self._csrf_token and not forzar:
            return self._csrf_token

        # 1. MediaWiki moderno (>= 1.27)
        try:
            data = self._api_get({"action": "query", "meta": "tokens", "type": "csrf"})
            tok = data.get("query", {}).get("tokens", {}).get("csrftoken")
            if tok and tok != "+\\":
                self._csrf_token = tok
                return tok
        except Exception:
            pass

        # 2. MediaWiki anterior
        try:
            data = self._api_get({"action": "tokens", "type": "edit"})
            tok = data.get("tokens", {}).get("edittoken")
            if tok and tok != "+\\":
                self._csrf_token = tok
                return tok
        except Exception:
            pass

        # 3. Fallback a token de edición por página
        try:
            data = self._api_get({"action": "query", "prop": "info", "intoken": "edit", "titles": "Main_Page"})
            pages = data.get("query", {}).get("pages", {})
            for _, pinfo in pages.items():
                tok = pinfo.get("edittoken")
                if tok:
                    self._csrf_token = tok
                    return tok
        except Exception:
            pass

        self._csrf_token = "+\\"
        return self._csrf_token

    def obtener_lista_paginas(self, namespace: int = 0, incluir_redirecciones: bool = False) -> list[str]:
        """Recupera la lista completa de artículos con paginación, omitiendo redirecciones por defecto."""
        titulos = []
        apcontinue = None

        while True:
            params = {
                "action": "query",
                "list": "allpages",
                "aplimit": 500,
                "apnamespace": namespace,
                "apfilterredir": "all" if incluir_redirecciones else "nonredirects"
            }
            if apcontinue:
                params["apcontinue"] = apcontinue

            try:
                data = self._api_get(params)
            except Exception as e:
                print(f"[AVISO] Error al obtener artículos: {e}")
                break

            paginas = data.get("query", {}).get("allpages", [])
            for p in paginas:
                t = p.get("title", "").strip()
                if t and es_pagina_de_contenido(t) and t not in titulos:
                    titulos.append(t)

            if "continue" in data and "apcontinue" in data["continue"]:
                apcontinue = data["continue"]["apcontinue"]
            else:
                break

        return titulos

    def obtener_revisiones_lote(self, titulos: list[str]) -> dict[str, dict]:
        """
        Consulta las revisiones más recientes de un grupo de páginas en bloques de 50.
        Devuelve un diccionario: {titulo: {"revid": int, "timestamp": str}}
        """
        resultado = {}
        # Procesar en lotes de 50 (límite de la API de MediaWiki para usuarios estándar)
        tam_lote = 50
        for i in range(0, len(titulos), tam_lote):
            lote = titulos[i:i + tam_lote]
            pipe_titulos = "|".join(lote)
            try:
                data = self._api_get({
                    "action": "query",
                    "prop": "revisions",
                    "rvprop": "ids|timestamp",
                    "titles": pipe_titulos
                })
                pages = data.get("query", {}).get("pages", {})
                for _, pinfo in pages.items():
                    t = pinfo.get("title")
                    revs = pinfo.get("revisions", [])
                    if t and revs:
                        rev_actual = revs[0]
                        resultado[t] = {
                            "revid": rev_actual.get("revid", 0),
                            "timestamp": rev_actual.get("timestamp", "")
                        }
            except Exception as e:
                print(f"[AVISO] Error consultando lote de revisiones: {e}")

        return resultado

    def obtener_catalogo_imagenes(self) -> list[dict]:
        """Obtiene la lista de todas las imágenes subidas al wiki con su URL."""
        imagenes = []
        aicontinue = None

        while True:
            params = {
                "action": "query",
                "list": "allimages",
                "ailimit": 500,
                "aiprop": "url|size|mime|timestamp|sha1"
            }
            if aicontinue:
                params["aicontinue"] = aicontinue

            try:
                data = self._api_get(params)
                items = data.get("query", {}).get("allimages", [])
                for item in items:
                    imagenes.append({
                        "name": item.get("name"),
                        "url": item.get("url"),
                        "size": item.get("size", 0),
                        "mime": item.get("mime", ""),
                        "sha1": item.get("sha1", ""),
                        "timestamp": item.get("timestamp", "")
                    })

                if "continue" in data and "aicontinue" in data["continue"]:
                    aicontinue = data["continue"]["aicontinue"]
                else:
                    break
            except Exception as e:
                print(f"[AVISO] Error consultando catálogo de imágenes: {e}")
                break

        return imagenes

    def descargar_contenido_pagina(self, titulo: str) -> dict | None:
        """Descarga el HTML renderizado y metadatos de un artículo."""
        try:
            data = self._api_get({
                "action": "parse",
                "page": titulo,
                "prop": "text|revid|displaytitle"
            })
            parse_data = data.get("parse", {})
            html = parse_data.get("text", {}).get("*", "")
            revid = parse_data.get("revid", 0)

            return {
                "titulo": titulo,
                "html": html,
                "revid": revid
            }
        except Exception:
            return None

    def descargar_archivo_binario(self, url: str, ruta_destino: str) -> tuple[bool, str]:
        """
        Descarga un archivo binario (imagen o documento) en streaming.
        Devuelve una tupla (éxito: bool, motivo_o_error: str).
        """
        try:
            p_api = urllib.parse.urlparse(self.api_url)
            p_url = urllib.parse.urlparse(url)

            # Extraer ruta del recurso
            ruta_recurso = p_url.path if p_url.path else url
            if not ruta_recurso.startswith("/"):
                ruta_recurso = "/" + ruta_recurso

            # Directorio del script MediaWiki (ej. /mediawiki si api_url es /mediawiki/api.php)
            script_dir = os.path.dirname(p_api.path).rstrip("/")

            candidatos_url = []

            # Candidato 1: Mismo scheme y netloc de la API, manteniendo la ruta provista
            url_1 = urllib.parse.urlunparse((p_api.scheme, p_api.netloc, ruta_recurso, "", p_url.query, ""))
            candidatos_url.append(url_1)

            # Candidato 2: Si la wiki está bajo un subdirectorio y la ruta no lo incluye (ej: /images vs /mediawiki/images)
            if script_dir and script_dir != "/" and not ruta_recurso.startswith(script_dir + "/"):
                ruta_con_script = script_dir + ruta_recurso
                url_2 = urllib.parse.urlunparse((p_api.scheme, p_api.netloc, ruta_con_script, "", p_url.query, ""))
                candidatos_url.append(url_2)

            # Si la URL original era completa con otro host/scheme, agregarla como último recurso
            if p_url.scheme and p_url.netloc and url not in candidatos_url:
                candidatos_url.append(url)

            os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)

            headers_req = {"User-Agent": self.user_agent}
            auth_obj = None
            if HAS_REQUESTS and self.http_user and self.http_password:
                auth_obj = HTTPBasicAuth(self.http_user, self.http_password)
            if self.http_user and self.http_password:
                raw_token = f"{self.http_user}:{self.http_password}".encode("latin1")
                headers_req["Authorization"] = f"Basic {base64.b64encode(raw_token).decode('ascii')}"

            ultimo_error = "Sin candidatos de descarga disponibles"

            for u_cand in candidatos_url:
                try:
                    if HAS_REQUESTS and self.session is not None:
                        r = self.session.get(u_cand, stream=True, timeout=30.0, auth=auth_obj, headers=headers_req)
                        if r.status_code == 200:
                            with open(ruta_destino, "wb") as f:
                                for chunk in r.iter_content(chunk_size=65536):
                                    if chunk:
                                        f.write(chunk)
                            return True, ""
                        else:
                            ultimo_error = f"HTTP {r.status_code} ({r.reason}) en {u_cand}"
                    else:
                        req = urllib.request.Request(u_cand, headers=headers_req)
                        with self.opener.open(req, timeout=30.0) as resp:
                            status = getattr(resp, "status", getattr(resp, "code", 200))
                            if status == 200:
                                with open(ruta_destino, "wb") as f:
                                    while chunk := resp.read(65536):
                                        f.write(chunk)
                                return True, ""
                            else:
                                reason = getattr(resp, "reason", "Error")
                                ultimo_error = f"HTTP {status} ({reason}) en {u_cand}"
                except urllib.error.HTTPError as e_http:
                    ultimo_error = f"HTTP {e_http.code} ({e_http.reason}) en {u_cand}"
                except Exception as e_cand:
                    ultimo_error = f"{type(e_cand).__name__}: {e_cand} en {u_cand}"

            return False, ultimo_error
        except Exception as e:
            return False, f"Excepción general: {e}"

    def editar_pagina(self, titulo: str, wikitext: str, resumen: str, baserevid: int = 0) -> dict:
        """
        Publica una página en MediaWiki con protección contra conflictos (baserevid).
        """
        token = self.obtener_token_csrf()
        payload = {
            "action": "edit",
            "title": titulo,
            "text": wikitext,
            "summary": resumen,
            "token": token
        }
        if baserevid > 0:
            payload["baserevid"] = baserevid

        try:
            res = self._api_post(payload)
        except Exception as e:
            return {"exito": False, "error": str(e)}

        if "error" in res:
            err = res["error"]
            codigo = err.get("code", "")
            info = err.get("info", str(err))
            es_conflicto = (codigo in ("editconflict", "cascadeprotected", "protectedpage"))
            return {"exito": False, "error": info, "conflict": es_conflicto, "code": codigo}

        edit_info = res.get("edit", {})
        if edit_info.get("result") == "Success":
            return {
                "exito": True,
                "nochange": "nochange" in edit_info,
                "newrevid": edit_info.get("newrevid"),
                "oldrevid": edit_info.get("oldrevid")
            }
        return {"exito": False, "error": str(res)}

    def eliminar_pagina(self, titulo: str, motivo: str = "Página vacía eliminada por mediawiki_sync") -> dict:
        """
        Elimina una página en MediaWiki mediante action=delete (requiere permisos de administrador).
        """
        token = self.obtener_token_csrf()
        payload = {
            "action": "delete",
            "title": titulo,
            "reason": motivo,
            "token": token
        }

        try:
            res = self._api_post(payload)
        except Exception as e:
            return {"exito": False, "error": str(e)}

        if "error" in res:
            err = res["error"]
            codigo = err.get("code", "")
            info = err.get("info", str(err))
            return {"exito": False, "error": info, "code": codigo}

        delete_info = res.get("delete", {})
        if "title" in delete_info:
            return {
                "exito": True,
                "title": delete_info.get("title"),
                "logid": delete_info.get("logid")
            }
        return {"exito": False, "error": str(res)}

    def subir_archivo(self, nombre_archivo: str, ruta_local: str, comentario: str) -> dict:
        """Sube o actualiza un archivo multimedia en la MediaWiki."""
        token = self.obtener_token_csrf()
        mime_type, _ = mimetypes.guess_type(ruta_local)
        if not mime_type:
            mime_type = "application/octet-stream"

        try:
            with open(ruta_local, "rb") as f:
                file_bytes = f.read()

            if HAS_REQUESTS:
                archivos = {"file": (nombre_archivo, file_bytes, mime_type)}
                datos = {
                    "action": "upload",
                    "filename": nombre_archivo,
                    "token": token,
                    "comment": comentario,
                    "ignorewarnings": "1",
                    "format": "json"
                }
                r = self.session.post(self.api_url, data=datos, files=archivos, timeout=60.0)
                res = r.json()
            else:
                boundary = f"----WebKitBoundary{uuid.uuid4().hex}"
                lines = []
                fields = {
                    "action": "upload",
                    "filename": nombre_archivo,
                    "token": token,
                    "comment": comentario,
                    "ignorewarnings": "1",
                    "format": "json"
                }
                for k, v in fields.items():
                    lines.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode("utf-8"))
                lines.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{nombre_archivo}\"\r\nContent-Type: {mime_type}\r\n\r\n".encode("utf-8"))
                lines.append(file_bytes)
                lines.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
                payload = b"".join(lines)
                headers = {
                    "User-Agent": self.user_agent,
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Content-Length": str(len(payload))
                }
                req = urllib.request.Request(self.api_url, data=payload, headers=headers)
                with self.opener.open(req, timeout=60.0) as resp:
                    res = json.loads(resp.read().decode("utf-8"))

            if "error" in res:
                return {"exito": False, "error": res["error"].get("info", str(res["error"]))}

            upload_info = res.get("upload", {})
            if upload_info.get("result") == "Success":
                return {"exito": True, "info": upload_info}

            return {"exito": False, "error": str(res)}
        except Exception as e:
            return {"exito": False, "error": str(e)}
