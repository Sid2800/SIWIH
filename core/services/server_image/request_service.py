from core.services.server_image.auth_service import traer_server_token, ImageServerAuthError
from core.constants.image_server_enpoints import BUSCAR_ARCHIVOS,  SUBIR_IMAGEN, DESACTIVAR_IMAGEN, DESACTIVAR_IMAGEN_BATCH, MIGRAR_IMAGENES_EXTERNO_INTERNO
from core.constants.media_constants  import AppValida, OrigenValido, TipoPaciente
from django.conf import settings
import json
from types import SimpleNamespace
import requests
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *

class RequestService:

    @staticmethod
    def _validar_argumentos_peticion(peticion: SimpleNamespace):
        """
        Valida que la app y el origen estén dentro de los permitidos.
        Lanza un ValueError si algo está mal.
        """
        try:
            AppValida(peticion.app)
        except ValueError:
            raise ValueError(f"App '{peticion.app}' no es válida.")

        try:
            OrigenValido(peticion.origen_tipo)
        except ValueError:
            raise ValueError(f"Origen '{peticion.origen_tipo}' no es válido.")
        
        try:
            TipoPaciente(peticion.paciente_tipo)
        except ValueError:
            raise ValueError(f"Tipo '{peticion.paciente_tipo}' no es válido.")



    @staticmethod
    def consultar_media_server_LIST(peticion_dict):
        peticion = SimpleNamespace(**peticion_dict)

        try:
            RequestService._validar_argumentos_peticion(peticion)

            url = f"{settings.IMAGE_SERVER_URL}{BUSCAR_ARCHIVOS}"
            token = traer_server_token()
            payload = {
                "app": peticion.app,
                "origen_tipo": peticion.origen_tipo,
                "origen_ids": peticion.origen_ids,  # ← importante
                "paciente_tipo": peticion.paciente_tipo,
                "paciente_id": peticion.paciente_id
            }

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=10
            )

            print(response)

            response.raise_for_status()

            return {
                "ok": True,
                "data": response.json()
            }
        
        except ImageServerAuthError as e:
            log_error(
                "Error autenticación media server",
                app=LogApp.MEDIA
            )
            return {"ok": False, "error": str(e)}

        except ValueError as ve:
            return {
                "ok": False,
                "error": str(ve)
            }

        except requests.exceptions.HTTPError as e:
            log_warning(
                f"HTTP error media server status={e.response.status_code}",
                app=LogApp.MEDIA
            )
            return {
                "ok": False,
                "error": e.response.text[:500]
            }

        except requests.exceptions.RequestException as e:
            log_error(
                "Error conexión media server LIST",
                app=LogApp.MEDIA
            )
            return {
                "ok": False,
                "error": str(e)
            }

    @staticmethod
    def subir_imagen(peticion_dict):
        peticion = SimpleNamespace(**peticion_dict)

        try:
            RequestService._validar_argumentos_peticion(peticion)

            url = f"{settings.IMAGE_SERVER_URL}{SUBIR_IMAGEN}"
            token = traer_server_token()

            headers = {
                "Authorization": f"Bearer {token}"
            }

            files = {
                "archivo": (
                    peticion.archivo.name,
                    peticion.archivo,
                    peticion.archivo.content_type
                )
            }

            data = {
                "app": peticion.app,
                "origen_tipo": peticion.origen_tipo,
                "origen_id": peticion.origen_id,
                "paciente_tipo": peticion.paciente_tipo,
                "paciente_id": peticion.paciente_id,
                "tipo_imagen": peticion.tipo_imagen,
                "usuario_snapshot": json.dumps({
                    "id": peticion.usuario_id,
                    "nombre": peticion.usuario_nombre,
                    "sistema": "SIWI-HOSPITAL"
                })
            }

            response = requests.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=20
            )

            
            try:
                response_json = response.json()
            except ValueError:
                response_json = {
                    "error": response.text[:500]
                }


            if response.status_code >= 400:
                log_warning(
                    f"Error subida imagen status={response.status_code}",
                    app=LogApp.MEDIA
                )
                return {
                    "ok": False,
                    "error": response_json
                }

            return {
                "ok": True,
                "data": response_json
            }

        except ValueError as ve:
            return {
                "ok": False,
                "error": str(ve)
            }

        except requests.exceptions.RequestException as e:
            log_error(
                "Error conexión subir imagen",
                app=LogApp.MEDIA
            )
            return {
                "ok": False,
                "error": f"Error de conexión con servidor de imágenes: {str(e)}"
            }
        

    @staticmethod
    def desactivar_imagen(peticion_dict):
        peticion = SimpleNamespace(**peticion_dict)

        try:
            RequestService._validar_argumentos_peticion(peticion)
            url = f"{settings.IMAGE_SERVER_URL}{DESACTIVAR_IMAGEN}"
            token = traer_server_token()

            headers ={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            payload = {
                "app": peticion.app,
                "origen_tipo": peticion.origen_tipo,
                "origen_id": peticion.origen_id,
                "paciente_tipo": peticion.paciente_tipo,
                "paciente_id": peticion.paciente_id,
                "usuario_snapshot": json.dumps({
                        "id": peticion.usuario_id,
                        "nombre": peticion.usuario_nombre,
                        "sistema": "SIWI-HOSPITAL"
                    })
                }

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=10
            )

            try:
                response_json = response.json()
            except ValueError:
                response_json = {
                    "error": response.text[:500]
                }

            if response.status_code >= 400:
                log_warning(
                    f"Error desactivar imagen status={response.status_code}",
                    app=LogApp.MEDIA
                )

            return {
                "ok": True,
                "data": response_json
            }
            

        except ValueError as ve:
            return {
                "ok": False,
                "error": str(ve)
            }

        except requests.exceptions.RequestException as e:
            log_error(
                "Error conexión desactivar imagen",
                app=LogApp.MEDIA
            )
            return {
                "ok": False,
                "error": f"Error de conexión con servidor de imágenes: {str(e)}"
            }
        

    @staticmethod
    def desactivar_imagenes_batch(peticion_dict):

        peticion = SimpleNamespace(**peticion_dict)
        try:
            # Validación mínima específica para batch
            if not isinstance(peticion.origen_ids, list) or not peticion.origen_ids:
                raise ValueError("origen_ids debe ser una lista no vacía")

            url = f"{settings.IMAGE_SERVER_URL}{DESACTIVAR_IMAGEN_BATCH}"
            token = traer_server_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            payload = {
                "app": peticion.app,
                "origen_tipo": peticion.origen_tipo,
                "paciente_tipo": peticion.paciente_tipo,
                "paciente_id": peticion.paciente_id,
                "origen_ids": peticion.origen_ids,
                "usuario_snapshot": json.dumps({
                        "id": peticion.usuario_id,
                        "nombre": peticion.usuario_nombre,
                        "sistema": "SIWI-HOSPITAL"
                    })
                }
            

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=10
            )

            try:
                response_json = response.json()
            except ValueError:
                response_json = {"error": response.text[:500]}

            if response.status_code >= 400:
                return {
                    "ok": False,
                    "error": response_json
                }

            return {
                "ok": True,
                "desactivadas": response_json.get("desactivadas", 0)
            }

        except ValueError as ve:
            return {
                "ok": False,
                "error": str(ve)
            }

        except requests.exceptions.RequestException as e:
            return {
                "ok": False,
                "error": f"Error de conexión con servidor de imágenes: {str(e)}"
            }
        

    @staticmethod
    def migrar_imagenes_externo_a_interno(peticion_dict):

        peticion = SimpleNamespace(**peticion_dict)
        try:
            # Validación mínima específica para batch
            if not peticion.paciente_externo_id  or not peticion.paciente_externo_id:
                raise ValueError("faltan parametros para ejectutar esta peticion")
            
            url = f"{settings.IMAGE_SERVER_URL}{MIGRAR_IMAGENES_EXTERNO_INTERNO}"
            print(url)
            token = traer_server_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            payload = {
                "paciente_interno_id": peticion.paciente_interno_id,
                "paciente_externo_id": peticion.paciente_externo_id,
                }
            

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=10
            )

            try:
                response_json = response.json()
            except ValueError:
                response_json = {"error": response.text[:500]}

            if response.status_code >= 400:
                return {
                    "ok": False,
                    "error": response_json
                }

            return {
                "ok": True,
                "convertidas": response_json.get("convertidas", 0)
            }

        except ValueError as ve:
            return {
                "ok": False,
                "error": str(ve)
            }

        except requests.exceptions.RequestException as e:
            return {
                "ok": False,
                "error": f"Error de conexión con servidor de imágenes: {str(e)}"
            }