from core.services.server_image.request_service import RequestService
from core.utils.utilidades_textos import construir_nombre_dinamico
from imagenologia.models import Estudio
from core.constants.media_constants import AccionImagen
from core.constants.domain_constants import AccionEstudio
from django.core.exceptions import ValidationError
from core.exceptions import EvaluacionDominioError
from core.validators.main_validator import validar_entero_positivo
from django.conf import settings



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
            if not resultado["ok"]:
                return estudios, True

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

        except Exception:
            for estudio in estudios:
                estudio['url_imagen'] = None
                estudio['url_thumb'] = None

            return estudios, True


    @staticmethod
    def agregar_imagenes_evaluacion(estudios, archivos, paciente_tipo, paciente_id, usuario):
        """
        Procesa imágenes en modo AGREGAR.
        """
        print(archivos)
        warnings = []
        success = []

        for est in estudios:
            frontend_id = est.get("frontendId")
            id_detalle = est.get("idDetalle")
            id_estudio = est.get("id")

            # Buscar archivo enviado desde el form
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

                resultado = RequestService.subir_imagen(payload)

                if not resultado.get("ok"):
                    warnings.append(
                        f"No se pudo subir imagen del estudio {id_detalle}"
                    )
                else:
                    success.append(
                        f"Imagen del estudio {id_detalle} guardada correctamente"
                    )

            except Exception as e:
                warnings.append(
                    f"No se pudo procesar imagen del estudio {id_detalle}: {str(e)}"
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
            id_estudi = est.get("id")

            try:
                accion = AccionImagen(accion)
            except ValueError:
                raise ValidationError("Acción de imagen inválida.")

            try:
                accion_estudio = AccionEstudio(accion_estudio)
            except ValueError:
                raise ValidationError("Acción de estudio inválida.")
            
            # Si el estudio fue eliminado, la imagen debe eliminarse también
            if accion_estudio == AccionEstudio.DELETE:
                accion = AccionImagen.DELETE
            
            archivo = archivos.get(f"archivo__{frontend_id}")

            try:
                if accion == AccionImagen.STAY:
                    continue

                elif accion == AccionImagen.SYNC:
                    if not archivo:
                        warnings.append(
                            f"No se recibió archivo para el estudio {id_detalle}"
                        )
                        continue

                    nombreEstudio = MediaService._obtener_nombre_estudio(id_estudi)

                    payload = {
                        "app": "RX",
                        "origen_tipo": "EVALUACIONRXDETALLE",
                        "origen_id": id_detalle,
                        "paciente_tipo": paciente_tipo,
                        "paciente_id": paciente_id,
                        "archivo": archivo,
                        "tipo_imagen": nombreEstudio,
                        "usuario_id": usuario.id,
                        "usuario_nombre":  construir_nombre_dinamico(usuario, ["first_name", "last_name"])

                    }
                    resultado = RequestService.subir_imagen(payload)

                    if not resultado.get("ok"):
                        warnings.append(
                            f"No se pudo subir imagen del estudio {id_detalle}"
                        )
                    else:
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

                    resultado = RequestService.desactivar_imagen(payload)


                    if not resultado.get("ok"):
                        warnings.append(
                            f"No se pudo desactivar imagen del estudio {id_detalle}"
                        )
                    else:
                        success.append(
                            f"Imagen del estudio {id_detalle} desactivada correctamente"
                        )

            except Exception as e:
                warnings.append(
                    f"No se pudo procesar imagen del estudio {id_detalle} {e}"
                )

        return {
            "warnings": warnings,
            "success": success
        }
    

    @staticmethod
    def cambiar_imagenes_referencia( paciente_interno_id, paciente_externo_id):
        """
        Desactiva imágenes en batch para una evaluación inactivada.
        """

        payload = {
            "paciente_interno_id": paciente_interno_id,
            "paciente_externo_id": paciente_externo_id,
        }

        resultado = RequestService.migrar_imagenes_externo_a_interno(payload)

        if not resultado.get("ok"):

            raise EvaluacionDominioError(
                "No se pudieron migrar las imágenes del paciente externo."
            )
        
        return resultado.get("convertidas", 0)


    
    @staticmethod
    def desactivar_imagenes_evaluacion(detalles_ids,paciente_tipo, paciente_id, usuario):
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
                    "paciente_id":   paciente_id,
                    "origen_ids": detalles_ids,
                    "usuario_id": usuario.id,
                        "usuario_nombre": construir_nombre_dinamico(
                            usuario, ["first_name", "last_name"]
                        )
                }
            
            resultado = RequestService.desactivar_imagenes_batch(payload)

            if not resultado.get("ok"):
                warnings.append("No se logró desactivar las imágenes.")

            elif resultado.get("desactivadas"):
                success.append(
                    f"Se desactivaron correctamente {resultado.get('desactivadas')} imágenes."
                )

        except Exception as e:
            warnings.append(str(e))

        return {
            "warnings": warnings,
            "success": success
        }

