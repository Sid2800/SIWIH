from paciente.models import Padre, Paciente
from core.utils.utilidades_textos import formatear_nombre_completo
from django.db import connections
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *

class PadreService:
    @staticmethod
    def obtener_padre_por_dni(dni, rol):
        if rol not in ["P", "M"]:
            if rol not in ["P", "M"]:
                log_warning(
                    f"[ROL_INVALIDO_PADRE] dni={dni} rol={rol}",
                    app=LogApp.PACIENTE
                )
                return {'error': "Rol inválido, debe ser 'P' o 'M'."}

        tipoP = "01" if rol == "P" else "02"

        # 1. buscar directamente en tabla PADRE
        padre = Padre.objects.filter(dni=dni, tipo=tipoP, paciente_ref__isnull=True).first()
        if padre:
            hijos = Paciente.objects.filter(padre=padre) if rol == "P" else Paciente.objects.filter(madre=padre)
            hijos_data = [
                {
                    "id": hijo.id,
                    "nombre": f"{hijo.primer_nombre} {hijo.segundo_nombre or ''}".strip(),
                    "apellido": f"{hijo.primer_apellido} {hijo.segundo_apellido or ''}".strip(),
                    "dni": hijo.dni,
                    "fecha_nacimiento": hijo.fecha_nacimiento,
                    "tipo": hijo.tipo.descripcion_tipo
                } for hijo in hijos
            ]
            return {
                "id": padre.id,
                "nombre1": padre.nombre1 or "",
                "nombre2": padre.nombre2 or "",
                "apellido1": padre.apellido1 or "",
                "apellido2": padre.apellido2 or "",
                "domicilio": padre.direccion.id if padre.direccion else 1,
                "sexo": "H" if padre.tipo == "01" else "M",
                "hijos": hijos_data
            }
        
        # 2. buscar como PACIENTE
        paciente = Paciente.objects.filter(dni=dni).select_related('padre').first()
        if paciente:

            padre = Padre.objects.filter(paciente_ref=paciente.id).first()
            hijos_data = []
            if padre:

                hijos = Paciente.objects.filter(padre=padre) if rol == "P" else Paciente.objects.filter(madre=padre)
                hijos_data = [
                    {
                        "id": hijo.id,
                        "nombre": f"{hijo.primer_nombre} {hijo.segundo_nombre or ''}".strip(),
                        "apellido": f"{hijo.primer_apellido} {hijo.segundo_apellido or ''}".strip(),
                        "dni": hijo.dni,
                        "fecha_nacimiento": hijo.fecha_nacimiento,
                        "tipo": hijo.tipo.descripcion_tipo
                    } for hijo in hijos
                ]
            return {
                "dni":paciente.dni,
                "nombre1": paciente.primer_nombre,
                "nombre2": paciente.segundo_nombre,
                "apellido1": paciente.primer_apellido,
                "apellido2": paciente.segundo_apellido,
                "sexo": paciente.sexo,
                "domicilio": paciente.sector.id if paciente.sector else "",
                "hijos": hijos_data or ""
            }
        
        # 3. buscar en el CENSO 2025
        try:
            with connections['censo2025'].cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        NUMERO_IDENTIDAD, PRIMER_NOMBRE, SEGUNDO_NOMBRE, 
                        PRIMER_APELLIDO, SEGUNDO_APELLIDO, 
                        CASE WHEN CODIGO_SEXO = 1 THEN 'H' 
                            WHEN CODIGO_SEXO = 2 THEN 'M' 
                            ELSE 'N/A' END AS SEXO,
                        CODIGO_LUGAR_POBLADO as domicilio
                    FROM censo2025_siwi.tbl_censo 
                    WHERE NUMERO_IDENTIDAD = %s;
                """, [dni])
                fila = cursor.fetchone()
                if fila:
                    return {
                        "dni": fila[0],
                        "nombre1": fila[1],
                        "nombre2": fila[2],
                        "apellido1": fila[3],
                        "apellido2": fila[4],
                        "sexo": fila[5],
                        "domicilio": fila[6]
                    }
        except Exception as e:
            log_error(
                f"[FALLO_CENSO_PADRE] dni={dni} detalle={str(e)}",
                app=LogApp.INTEGRACION
            )
            return {'error': "Error al consultar el censo."}
        # no se encontró en ninguna fuente
        return {'error': "No se encontró un padre/madre con ese DNI."}


    @staticmethod
    def liberar_campos_padre(paciente, madre):
        """Limpia los datos personales del padre cuando ya es paciente."""
        madre.nombre1 = None
        madre.nombre2 = None
        madre.apellido1 = None
        madre.apellido2 = None
        madre.direccion = None
        madre.paciente_ref = paciente
        madre.save()


    @staticmethod
    def agregar_o_actualizar_padre(dni, nombre1, nombre2, apellido1, apellido2, direccion, tipo="02"):
        """Crea o actualiza un registro de Padre."""

        try:
            # sin DNI → crear siempre
            if not dni and (nombre1 and apellido1):
                return Padre.objects.create(
                    dni=None,
                    tipo=tipo,
                    nombre1=nombre1.upper(),
                    nombre2=nombre2.upper() if nombre2 else None,
                    apellido1=apellido1.upper(),
                    apellido2=apellido2.upper() if apellido2 else None,
                    direccion_id=direccion if direccion else None
                )

            persona, creada = Padre.objects.get_or_create(
                dni=dni,
                tipo=tipo,
                defaults={
                    "nombre1": nombre1.upper(),
                    "nombre2": nombre2.upper() if nombre2 else None,
                    "apellido1": apellido1.upper(),
                    "apellido2": apellido2.upper() if apellido2 else None,
                    "direccion_id": direccion if direccion else None
                }
            )

            if not creada:
                cambios = False

                if nombre1 and persona.nombre1 != nombre1.upper():
                    persona.nombre1 = nombre1.upper()
                    cambios = True

                if nombre2 and persona.nombre2 != nombre2.upper():
                    persona.nombre2 = nombre2.upper()
                    cambios = True

                if apellido1 and persona.apellido1 != apellido1.upper():
                    persona.apellido1 = apellido1.upper()
                    cambios = True

                if apellido2 and persona.apellido2 != apellido2.upper():
                    persona.apellido2 = apellido2.upper()
                    cambios = True

                if direccion and persona.direccion_id != direccion:
                    persona.direccion_id = direccion
                    cambios = True

                if cambios:
                    persona.save()

            return persona

        except Exception as e:
            log_error(
                f"[FALLO_PADRE_UPSERT] dni={dni} tipo={tipo} detalle={str(e)}",
                app=LogApp.PACIENTE
            )
            raise
    

    @staticmethod
    def procesar_padre_o_madre(id, dni, nombre1, nombre2, apellido1, apellido2, direccion, tipo):
        """Asigna un padre/madre a un paciente, creando o actualizando registros."""
        
        def actualizar_datos_padre(padre):
            """Actualiza los datos del padre/madre solo si han cambiado."""
            cambios = False
            if padre.dni != dni:
                padre.dni = dni
                cambios = True
                

            if padre.nombre1 != nombre1.upper():
                padre.nombre1 = nombre1.upper()
                cambios = True
            if  padre.nombre2 != nombre2.upper():
                padre.nombre2 = nombre2.upper()
                cambios = True
            if padre.apellido1 != apellido1.upper():
                padre.apellido1 = apellido1.upper()
                cambios = True
            if padre.apellido2 != apellido2.upper():
                padre.apellido2 = apellido2.upper()
                cambios = True

            if dni:
                try:
                    paciente_padre = Paciente.objects.get(dni=dni)
                    PadreService.liberar_campos_padre(paciente_padre, padre)
                except Paciente.DoesNotExist:
                    pass

            if cambios:
                padre.save()

            return padre

        try:
            # Actualizar por ID
            if id:
                try:
                    padre = Padre.objects.get(id=id)
                    if not padre.paciente_ref:
                        return actualizar_datos_padre(padre)
                except Padre.DoesNotExist:
                    return None

            # Buscar por DNI
            if dni:
                try:
                    paciente_padre = Paciente.objects.get(dni=dni)
                    padre, _ = Padre.objects.get_or_create(
                        dni=dni,
                        tipo=tipo,
                        defaults={"paciente_ref": paciente_padre}
                    )
                    PadreService.liberar_campos_padre(paciente_padre, padre)
                    return padre

                except Paciente.DoesNotExist:
                    return PadreService.agregar_o_actualizar_padre(
                        dni, nombre1, nombre2, apellido1, apellido2, direccion, tipo
                    )

            # Crear sin DNI
            if nombre1 and apellido1:
                return PadreService.agregar_o_actualizar_padre(
                    None, nombre1, nombre2, apellido1, apellido2, direccion, tipo
                )

            return None

        except Exception as e:
            log_error(
                f"[FALLO_PROCESAR_PADRE] id={id} dni={dni} tipo={tipo} detalle={str(e)}",
                app=LogApp.PACIENTE
            )
            raise


    
    @staticmethod
    def obtener_detalles_padre(id_padre):
        """Obtiene detalles del padre por ID, verificando si es un paciente."""
        try:
            padre = Padre.objects.get(id=id_padre)

            # Si el padre está asociado a un paciente, obtener los datos de la tabla Paciente
            if padre.paciente_ref_id:
                try:
                    paciente = Paciente.objects.get(id=padre.paciente_ref_id)
                    return {
                        "id": padre.id or "",
                        "dni": paciente.dni or "",
                        "primer_nombre": paciente.primer_nombre or "",
                        "segundo_nombre": paciente.segundo_nombre or "",
                        "primer_apellido": paciente.primer_apellido or "",
                        "segundo_apellido": paciente.segundo_apellido or "",
                        "nombre_completo":formatear_nombre_completo(paciente.primer_nombre,paciente.segundo_nombre,paciente.primer_apellido,paciente.segundo_apellido)
                    }
                except Paciente.DoesNotExist:
                    log_error(
                        f"[PADRE_REFERENCIA_INVALIDA] padre_id={id_padre} paciente_ref={padre.paciente_ref_id}",
                        app=LogApp.PACIENTE
                    )
                    return {"error": "Paciente no encontrado, pero está referenciado."}

            # Si no tiene referencia a paciente, devolver los datos de la tabla Padre
            return {
                "id": padre.id or "",
                "dni": padre.dni or "",
                "primer_nombre": padre.nombre1 or "",
                "segundo_nombre": padre.nombre2 or "",
                "primer_apellido": padre.apellido1 or "",
                "segundo_apellido": padre.apellido2 or "",
                "nombre_completo":formatear_nombre_completo(padre.nombre1,padre.nombre2,padre.apellido1,padre.apellido2)

            }

        except Padre.DoesNotExist:
            return {"error": "Padre no encontrado"}

        except Exception as e:
            log_error(
                f"[FALLO_OBTENER_PADRE] id_padre={id_padre} detalle={str(e)}",
                app=LogApp.PACIENTE
            )
            return {"error": "Error interno al obtener datos del padre"}
