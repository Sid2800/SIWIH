from core.services.server_image.request_service import RequestService
from core.utils.utilidades_textos import construir_nombre_dinamico
from imagenologia.models import Estudio
from core.constants.media_constants import AccionImagen
from core.constants.domain_constants import AccionEstudio
from django.core.exceptions import ValidationError
from core.exceptions import EvaluacionDominioError
from core.validators.main_validator import validar_entero_positivo
from django.conf import settings
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *



class MediaService:

    @staticmethod
    def _obtener_nombre_estudio(id_estudio):
        return (
            Estudio.objects
            .filter(id=id_estudio)
            .values_list("descripcion_estudio", flat=True)
            .first()
        )

    @staticmethod
    def obtener_imagenes_estudios(estudios, paciente_tipo, paciente_id):

        peticion = {
            'app': "RX",
            'origen_tipo': "EVALUACIONRXDETALLE",
            'origen_ids': [estudio['id'] for estudio in estudios],
            'paciente_tipo': paciente_tipo,
            'paciente_id': paciente_id
        }

        try:
            resultado = RequestService.consultar_media_server_LIST(peticion)

            imagenes_data = resultado["data"]

            mapa_imgs = {
                img['origen_id']: {
                    'url': f"{settings.IMAGE_SERVER_URL}{img['url']}",
                    'thumb': f"{settings.IMAGE_SERVER_URL}{img['miniatura']}"
                }
                for img in imagenes_data
            }

            for estudio in estudios:
                datos_img = mapa_imgs.get(estudio['id'])
                if datos_img:
                    estudio['url_imagen'] = datos_img['url']
                    estudio['url_thumb'] = datos_img['thumb']
                else:
                    estudio['url_imagen'] = None
                    estudio['url_thumb'] = None

            return estudios, False

        except Exception as e:
            log_error(
                f"[FALLO_MEDIA_LIST] paciente_id={paciente_id} estudios={len(estudios)} detalle={str(e)}",
                app=LogApp.MEDIA 
            )

            for estudio in estudios:
                estudio['url_imagen'] = None
                estudio['url_thumb'] = None

            return estudios, True


    @staticmethod
    def agregar_imagenes_evaluacion(estudios, archivos, paciente_tipo, paciente_id, usuario):
        """
        Procesa imágenes en modo AGREGAR.
        """

        warnings = []
        success = []

        for est in estudios:
            frontend_id = est.get("frontendId")
            id_detalle = est.get("idDetalle")
            id_estudio = est.get("id")

            archivo = archivos.get(f"archivo__{frontend_id}")
            accion_estudio = est.get('accionEstudio')

            if (
                not archivo
                or not id_detalle
                or accion_estudio == AccionEstudio.DELETE
            ):
                continue

            try:
                nombre_estudio = MediaService._obtener_nombre_estudio(id_estudio)

                payload = {
                    "app": "RX",
                    "origen_tipo": "EVALUACIONRXDETALLE",
                    "origen_id": id_detalle,
                    "paciente_tipo": paciente_tipo,
                    "paciente_id": paciente_id,
                    "archivo": archivo,
                    "tipo_imagen": nombre_estudio,
                    "usuario_id": usuario.id,
                    "usuario_nombre": construir_nombre_dinamico(
                        usuario, ["first_name", "last_name"]
                    )
                }

                RequestService.subir_imagen(payload)

                success.append(
                    f"Imagen del estudio {id_detalle} guardada correctamente"
                )

            except Exception as e:
                log_error(
                    f"[FALLO_SUBIDA] estudio_detalle={id_detalle} paciente_id={paciente_id} detalle={str(e)}",
                    app=LogApp.MEDIA
                )

                warnings.append(
                    f"No se pudo procesar imagen del estudio {id_detalle}"
                )

        return {
            "warnings": warnings,
            "success": success
        }


    @staticmethod
    def procesar_imagenes_evaluacion(estudios, archivos, paciente_tipo, paciente_id, usuario):
        warnings = []
        success = []

        for est in estudios:
            frontend_id = est.get("frontendId")
            id_detalle = est.get("idDetalle")
            accion = est.get("accionImagen")
            accion_estudio = est.get("accionEstudio")
            id_estudio = est.get("id")

            try:
                accion = AccionImagen(accion)
            except ValueError:
                raise ValidationError("Acción de imagen inválida.")

            try:
                accion_estudio = AccionEstudio(accion_estudio)
            except ValueError:
                raise ValidationError("Acción de estudio inválida.")

            if accion_estudio == AccionEstudio.DELETE:
                accion = AccionImagen.DELETE

            archivo = archivos.get(f"archivo__{frontend_id}")

            try:
                if accion == AccionImagen.STAY:
                    continue

                elif accion == AccionImagen.SYNC:

                    if not archivo:
                        log_warning(
                            f"[SYNC_SIN_ARCHIVO] estudio_detalle={id_detalle} paciente_id={paciente_id}",
                            app=LogApp.MEDIA
                        )
                        warnings.append(
                            f"No se recibió archivo para el estudio {id_detalle}"
                        )
                        continue

                    nombre_estudio = MediaService._obtener_nombre_estudio(id_estudio)

                    payload = {
                        "app": "RX",
                        "origen_tipo": "EVALUACIONRXDETALLE",
                        "origen_id": id_detalle,
                        "paciente_tipo": paciente_tipo,
                        "paciente_id": paciente_id,
                        "archivo": archivo,
                        "tipo_imagen": nombre_estudio,
                        "usuario_id": usuario.id,
                        "usuario_nombre": construir_nombre_dinamico(
                            usuario, ["first_name", "last_name"]
                        )
                    }

                    RequestService.subir_imagen(payload)

                    success.append(
                        f"Imagen del estudio {id_detalle} guardada correctamente"
                    )

                elif accion == AccionImagen.DELETE:

                    payload = {
                        "app": "RX",
                        "origen_tipo": "EVALUACIONRXDETALLE",
                        "origen_id": id_detalle,
                        "paciente_tipo": paciente_tipo,
                        "paciente_id": paciente_id,
                        "usuario_id": usuario.id,
                        "usuario_nombre": construir_nombre_dinamico(
                            usuario, ["first_name", "last_name"]
                        )
                    }

                    RequestService.desactivar_imagen(payload)

                    success.append(
                        f"Imagen del estudio {id_detalle} desactivada correctamente"
                    )

            except Exception as e:
                log_error(
                    f"[FALLO_PROCESO_IMAGEN] estudio_detalle={id_detalle} paciente_id={paciente_id} detalle={str(e)}",
                    app=LogApp.MEDIA
                )

                warnings.append(
                    f"No se pudo procesar imagen del estudio {id_detalle}"
                )

        return {
            "warnings": warnings,
            "success": success
        }


    @staticmethod
    def desactivar_imagenes_evaluacion(detalles_ids, paciente_tipo, paciente_id, usuario):
        warnings = []
        success = []

        try:
            if not isinstance(detalles_ids, list) or len(detalles_ids) == 0:
                raise ValidationError("Debes enviar una lista con más de un elemento.")

            validar_entero_positivo(paciente_id)
            validar_entero_positivo(paciente_tipo)

            payload = {
                "app": "RX",
                "origen_tipo": "EVALUACIONRXDETALLE",
                "paciente_tipo": paciente_tipo,
                "paciente_id": paciente_id,
                "origen_ids": detalles_ids,
                "usuario_id": usuario.id,
                "usuario_nombre": construir_nombre_dinamico(
                    usuario, ["first_name", "last_name"]
                )
            }

            resultado = RequestService.desactivar_imagenes_batch(payload)
            desactivadas = resultado.get("desactivadas", 0)

            if desactivadas == 0:
                log_warning(
                    f"[SIN_DESACTIVADAS] paciente_id={paciente_id} total_ids={len(detalles_ids)}",
                    app=LogApp.MEDIA
                )
                warnings.append("No se desactivaron imágenes.")

            else:
                success.append(
                    f"Se desactivaron correctamente {desactivadas} imágenes."
                )
                log_info(
                    f"Se desactivaron correctamente {desactivadas} imágenes.",
                    app=LogApp.MEDIA
                )

        except Exception as e:
            log_error(
                f"[FALLO_BATCH_DESACTIVAR] paciente_id={paciente_id} total_ids={len(detalles_ids) if isinstance(detalles_ids, list) else 0} detalle={str(e)}",
                app=LogApp.MEDIA
            )
            warnings.append("Error interno al desactivar imágenes.")

        return {
            "warnings": warnings,
            "success": success
        }


    @staticmethod
    def cambiar_imagenes_referencia(paciente_interno_id, paciente_externo_id):

        payload = {
            "paciente_interno_id": paciente_interno_id,
            "paciente_externo_id": paciente_externo_id,
        }

        try:
            resultado = RequestService.migrar_imagenes_externo_a_interno(payload)

            convertidas = resultado.get("convertidas", 0)

            if convertidas == 0:
                log_warning(
                    f"[SIN_MIGRACION] interno_id={paciente_interno_id} externo_id={paciente_externo_id}",
                    app=LogApp.MEDIA
                )

            return convertidas

        except Exception as e:
            log_error(
                f"[FALLO_MIGRACION] interno_id={paciente_interno_id} externo_id={paciente_externo_id} detalle={str(e)}",
                app=LogApp.MEDIA
            )

            raise EvaluacionDominioError(
                "No se pudieron migrar las imágenes del paciente externo."
            )
