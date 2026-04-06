
from django.db import connections, OperationalError
from expediente.models import PacienteAsignacion
from core.services.servicio_service import ServicioService
from paciente.models import Paciente, Defuncion, Tipo, ObitoFetal
from imagenologia.models import PacienteExterno
from core.utils.utilidades_fechas import calcular_edad_texto, formatear_fecha_simple, obtener_edad_con_indicador
from core.utils.utilidades_textos import formatear_ubicacion_completo, formatear_nombre_completo
from core.validators.fecha_validator import validar_fecha
from django.db.models import Value, F, Max
from django.db.models.functions import Concat, Coalesce, TruncDate
from django.utils.timezone import now
from django.contrib.auth.models import User
from django.db import transaction
from datetime import datetime, date
from django.db import connection, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *
from core.constants.domain_constants import INDICADOR_ANIOS, EDAD_FERTIL_MAX, EDAD_FERTIL_MIN, GENERO_FEMENINO

class PacienteService:

    @staticmethod
    def obtener_paciente_censo(dni):
        """
        Busca un paciente en el censo por su número de identidad y verifica si está registrado en el sistema.

        Parámetros:
        - dni (str): Número de identidad del paciente.

        Retorna:
        - dict: Información del paciente si se encuentra en el censo, incluyendo su edad y ubicación.  
                Si el paciente está registrado en el sistema, se agrega su nombre.  
                En caso de error, devuelve un mensaje descriptivo.
        """
        if not dni:
            return {"error": "Se requiere un parámetro 'dni'."}

        try:
            with connections['censo2025'].cursor() as cursor:
                qry = """
                SELECT 
                    NUMERO_IDENTIDAD AS DNI,
                    PRIMER_NOMBRE AS NOMBRE1,
                    SEGUNDO_NOMBRE AS NOMBRE2,
                    PRIMER_APELLIDO AS APELLIDO1,
                    SEGUNDO_APELLIDO AS APELLIDO2,
                    CASE
                        WHEN CODIGO_SEXO = 1 THEN 'H'
                        WHEN CODIGO_SEXO = 2 THEN 'M'
                        ELSE 'N/A'
                    END AS SEXO,
                    REPLACE(FECHA_NACIMIENTO,'/','-') AS FECHA_NACIMIENTO,
                    DEPTO.codigo_departamento AS ID_DEPARTAMENTO,
                    MUNI.codigo_municipio AS ID_MUNICIPIO,
                    LP.codigo_lugar_poblado AS ID_LUGAR_POBLADO,
                    LP.nombre_lugar_poblado as NOMBRE_UBICACION
                FROM censo2025_siwi.tbl_censo AS CENSO
                INNER JOIN tbl_lugar_poblado AS LP ON CENSO.CODIGO_LUGAR_POBLADO = LP.codigo_lugar_poblado 
                INNER JOIN tbl_aldea AS ALDEA ON ALDEA.CODIGO_ALDEA = LP.codigo_aldea
                INNER JOIN tbl_municipio AS MUNI ON MUNI.codigo_municipio = ALDEA.CODIGO_MUNICIPIO
                INNER JOIN tbl_departamento AS DEPTO ON DEPTO.codigo_departamento = MUNI.codigo_departamento
                WHERE NUMERO_IDENTIDAD = %s;
                """
                cursor.execute(qry, [dni])
                filas = cursor.fetchall()

                columnas = [col[0] for col in cursor.description]
                datos = [dict(zip(columnas, fila)) for fila in filas]

                for dato in datos:
                    fecha_nacimiento = dato.get("FECHA_NACIMIENTO")
                    dato["EDAD"] = calcular_edad_texto(fecha_nacimiento) if fecha_nacimiento else None

                paciente = Paciente.objects.filter(dni=dni).first()
                if paciente:
                    for dato in datos:
                        dato["PACIENTE"] = f"{paciente.primer_nombre} {paciente.primer_apellido}"

                return {"data": datos}

        except OperationalError as e:
            log_error(
                f"[FALLO_CENSO] dni={dni} detalle={str(e)}",
                app=LogApp.INTEGRACION
            )
            return {"error": "No se pudo consultar el censo"}


    @staticmethod
    def obtener_pacientes(query=None):
        qs = Paciente.objects.filter(estado="A").annotate(
        nombre_completo=Concat(
            F("primer_nombre"), Value(" "),
            Coalesce(F("segundo_nombre"), Value("")), Value(" "),
            F("primer_apellido"), Value(" "),
            Coalesce(F("segundo_apellido"), Value(""))
            )
        )

        if query:
            qs = qs.filter(nombre_completo__icontains=query)

        return qs.values("id", "nombre_completo", "dni", "fecha_nacimiento", "sexo")


    @staticmethod
    def obtener_paciente_propietario(DNI):
        try:
            pacienteA = PacienteAsignacion.objects.select_related("paciente", "expediente").get(paciente__dni=DNI, estado="1")
            return pacienteA  
        except PacienteAsignacion.DoesNotExist:
            return None
            

    @staticmethod
    def listar_personas_censo(params, start, length, order_column, order_direction):
        where_clauses = []
        query_params = []

        if params.get("search_sexo"):
            where_clauses.append("censo.CODIGO_SEXO = %s")
            query_params.append(params["search_sexo"])

        if params.get("search_nombre1"):
            where_clauses.append("censo.PRIMER_NOMBRE LIKE %s")
            query_params.append(params["search_nombre1"].strip() + '%')

        if params.get("search_nombre2"):
            where_clauses.append("censo.SEGUNDO_NOMBRE LIKE %s")
            query_params.append(params["search_nombre2"].strip() + '%')

        if params.get("search_apellido1"):
            where_clauses.append("censo.PRIMER_APELLIDO LIKE %s")
            query_params.append(params["search_apellido1"].strip() + '%')

        if params.get("search_apellido2"):
            where_clauses.append("censo.SEGUNDO_APELLIDO LIKE %s")
            query_params.append(params["search_apellido2"].strip() + '%')

        # Si no hay criterios, devolver una lista vacía
        if len(query_params) < 3:
            return [], 0  # Retorna lista vacía y 0 registros filtrados

        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        columns = [
            "NUMERO_IDENTIDAD", "PRIMER_NOMBRE", "PRIMER_APELLIDO",
            "CODIGO_SEXO", "FECHA_NACIMIENTO", "NOMBRE_DEPARTAMENTO"
        ]
        order_by_column = columns[order_column]
        order_by_direction = order_direction.upper()

        try:
            with connections['censo2025'].cursor() as cursor:
                # Obtener número total de registros filtrados
                count_query = f"SELECT COUNT(*) FROM tbl_censo AS censo {where_clause}"
                cursor.execute(count_query, query_params)
                total_filtered = cursor.fetchone()[0]

                qry = f"""
                    SELECT *
                    FROM (
                        SELECT ROW_NUMBER() OVER (ORDER BY {order_by_column} {order_by_direction}) AS row_num,
                            censo.NUMERO_IDENTIDAD, censo.PRIMER_NOMBRE, censo.SEGUNDO_NOMBRE,
                            censo.PRIMER_APELLIDO, censo.SEGUNDO_APELLIDO,
                            CASE WHEN censo.CODIGO_SEXO = 1 THEN 'HOMBRE'
                                WHEN censo.CODIGO_SEXO = 2 THEN 'MUJER'
                            END AS SEXO,
                            censo.FECHA_NACIMIENTO, DEPTO.NOMBRE_DEPARTAMENTO AS DEPTO,
                            MUNI.NOMBRE_MUNICIPIO AS MUNI, LP.NOMBRE_LUGAR_POBLADO AS LUGAR
                        FROM censo2025_siwi.tbl_censo AS censo
                        INNER JOIN tbl_lugar_poblado AS LP ON censo.CODIGO_LUGAR_POBLADO = LP.codigo_lugar_poblado 
                        INNER JOIN tbl_aldea AS ALDEA ON ALDEA.CODIGO_ALDEA = LP.codigo_aldea
                        INNER JOIN tbl_municipio AS MUNI ON MUNI.codigo_municipio = ALDEA.CODIGO_MUNICIPIO
                        INNER JOIN tbl_departamento AS DEPTO ON DEPTO.codigo_departamento = MUNI.codigo_departamento 
                        {where_clause}
                    ) AS subquery
                    WHERE row_num BETWEEN {start + 1} AND {start + length}
                """

                cursor.execute(qry, query_params)
                filas = cursor.fetchall()

                columnas = [col[0] for col in cursor.description]
                datos = [dict(zip(columnas, fila)) for fila in filas]

            return datos, total_filtered  # Devuelve los datos y la cantidad total filtrada

        except Exception as e:
            log_error(
                f"[FALLO_LISTAR_CENSO] params={params} start={start} length={length} detalle={str(e)}",
                app=LogApp.INTEGRACION
            )
            return {'error': 'Error al consultar el censo'}, 0
        
    
    @staticmethod
    def listar_personas_censo_avanzada(params, start, length, order_column, order_direction):
        where_clauses = []
        query_params = []

  
        if params.get("search_sexo"):
            where_clauses.append("censo.CODIGO_SEXO = %s")
            query_params.append(params["search_sexo"])

        if params.get("search_nombre1"):
            where_clauses.append("censo.PRIMER_NOMBRE LIKE %s")
            query_params.append(params["search_nombre1"].strip() + '%')

        if params.get("search_nombre2"):
            where_clauses.append("censo.SEGUNDO_NOMBRE LIKE %s")
            query_params.append(params["search_nombre2"].strip() + '%')

        if params.get("search_apellido1"):
            where_clauses.append("censo.PRIMER_APELLIDO LIKE %s")
            query_params.append(params["search_apellido1"].strip() + '%')

        if params.get("search_apellido2"):
            where_clauses.append("censo.SEGUNDO_APELLIDO LIKE %s")
            query_params.append(params["search_apellido2"].strip() + '%')

        if not isinstance(order_column, int) or order_column >= len(columns):
            order_column = 0

        # Si no hay criterios, devolver una lista vacía
        if len(query_params) < 3:
            return [], 0  # Retorna lista vacía y 0 registros filtrados

        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        columns = [
            "NUMERO_IDENTIDAD",
            "PRIMER_NOMBRE",
            "SEGUNDO_NOMBRE",
            "PRIMER_APELLIDO",
            "SEGUNDO_APELLIDO",
            "NUMERO_IDENTIDAD",
            "NOMBRE_DEPARTAMENTO"
        ]
        order_by_column = columns[order_column]
        order_by_direction = "ASC" if order_direction.upper() != "DESC" else "DESC"

        try:
            with connections['censo2025'].cursor() as cursor:
                # Obtener número total de registros filtrados
                count_query = f"SELECT COUNT(*) FROM tbl_censo AS censo {where_clause}"
                cursor.execute(count_query, query_params)
                total_filtered = cursor.fetchone()[0]

                qry = f"""
                    SELECT *
                    FROM (
                        SELECT ROW_NUMBER() OVER (ORDER BY {order_by_column} {order_by_direction}) AS row_num,
                            censo.NUMERO_IDENTIDAD as dni, censo.PRIMER_NOMBRE as primer_nombre, censo.SEGUNDO_NOMBRE as segundo_nombre, 
                            censo.PRIMER_APELLIDO as primer_apellido, censo.SEGUNDO_APELLIDO as segundo_apellido,
                            "" as telefono,
                            "" as codigo,
                            "Censo" as origen,
                            DEPTO.NOMBRE_DEPARTAMENTO as sector__aldea__municipio__departamento__nombre_departamento,
                            DEPTO.CODIGO_DEPARTAMENTO AS sector__aldea__municipio__departamento__id,
                            muni.NOMBRE_MUNICIPIO AS sector__aldea__municipio__nombre_municipio,
                            muni.CODIGO_MUNICIPIO as sector__aldea__municipio__id,
                            lp.NOMBRE_LUGAR_POBLADO AS sector__nombre_sector,
                            lp.CODIGO_LUGAR_POBLADO as sector__id
                        FROM censo2025_siwi.tbl_censo AS censo
                        INNER JOIN tbl_lugar_poblado AS LP ON censo.CODIGO_LUGAR_POBLADO = LP.codigo_lugar_poblado 
                        INNER JOIN tbl_aldea AS ALDEA ON ALDEA.CODIGO_ALDEA = LP.codigo_aldea
                        INNER JOIN tbl_municipio AS MUNI ON MUNI.codigo_municipio = ALDEA.CODIGO_MUNICIPIO
                        INNER JOIN tbl_departamento AS DEPTO ON DEPTO.codigo_departamento = MUNI.codigo_departamento 
                        {where_clause}
                    ) AS subquery
                    WHERE row_num BETWEEN {start + 1} AND {start + length}
                """

                cursor.execute(qry, query_params)
                filas = cursor.fetchall()
                columnas = [col[0] for col in cursor.description]
                datos = [dict(zip(columnas, fila)) for fila in filas]

            return datos, total_filtered  # Devuelve los datos y la cantidad total filtrada

        except Exception as e:
            log_error(
                f"[FALLO_LISTAR_CENSO_AVANZADO] filtros={list(params.keys())} start={start} length={length} detalle={str(e)}",
                app=LogApp.INTEGRACION
            )
            return {'error': 'Error al consultar el censo'}, 0
        

    @staticmethod
    def obtener_defuncion(idPaciente):
        try:
            relaciones = ['sala','servicio_auxiliar','especialidad', 'registrado_por']
            defuncion = Defuncion.objects.select_related(*relaciones).get(paciente__id=idPaciente)
            return defuncion
        except Defuncion.DoesNotExist:
            return None
        
    @staticmethod
    def obtener_obito_id(idObito):
        try:
            relaciones = ['sala', 'registrado_por']
            obito = ObitoFetal.objects.select_related(*relaciones).get(id=idObito)
            return obito
        except ObitoFetal.DoesNotExist:
            return None
        
    @staticmethod
    def obtener_defuncion_id(idDefuncion):
        try:
            relaciones = ['sala', 'registrado_por','paciente']
            defuncion = Defuncion.objects.select_related(*relaciones).get(id=idDefuncion)
            return defuncion
        except Defuncion.DoesNotExist:
            return None


    @staticmethod
    def procesar_defuncion(defuncion):

        def actualizar_datos_defuncion(defuncionRegistro):
            """Actualiza los datos del padre/madre solo si han cambiado."""
            cambios = False
            try:
                if defuncionRegistro.fecha_defuncion != defuncion.fecha:
                    defuncionRegistro.fecha_defuncion = defuncion.fecha
                    cambios = True

                tipo = defuncion.tipo
                
                nueva_sala = None
                nueva_especialidad = None
                nuevo_aux = None

                if tipo != 2:
                    if defuncion.tipo_dependencia == 'sala':
                        nueva_sala = defuncion.dependencia
                        nueva_especialidad = None
                        nuevo_aux = None

                    elif defuncion.tipo_dependencia == 'especialidad':
                        nueva_sala = None
                        nueva_especialidad = defuncion.dependencia
                        nuevo_aux = None

                    elif defuncion.tipo_dependencia == 'servicio_auxiliar':
                        nueva_sala = None
                        nueva_especialidad = None
                        nuevo_aux = defuncion.dependencia


                # Comparar cambios
                if defuncionRegistro.sala != nueva_sala:
                    defuncionRegistro.sala = nueva_sala
                    cambios = True

                if defuncionRegistro.especialidad != nueva_especialidad:
                    defuncionRegistro.especialidad = nueva_especialidad
                    cambios = True

                if defuncionRegistro.servicio_auxiliar != nuevo_aux:
                    defuncionRegistro.servicio_auxiliar = nuevo_aux
                    cambios = True



                if defuncionRegistro.tipo_defuncion != tipo:
                    defuncionRegistro.tipo_defuncion = tipo
                    cambios= True

                if defuncionRegistro.motivo != defuncion.motivo:
                    defuncionRegistro.motivo = defuncion.motivo
                    cambios = True          

                if not cambios:
                    return False

                defuncionRegistro.save()
                return True
            
            except Exception as e:
                log_error(
                    f"[FALLO_ACTUALIZAR_DEFUNCION] id={defuncionRegistro.id} detalle={str(e)}",
                    app=LogApp.PACIENTE
                )
                raise

    
        
        #1 si exite id veamossi es un registro
        if defuncion.id:
            try:
                defuncionRegistro = Defuncion.objects.get(id=defuncion.id)
                return actualizar_datos_defuncion(defuncionRegistro)
            except Defuncion.DoesNotExist:
                return False
            except Exception:
                raise

                
        # si tiene id se lo vamos a marcalro como defuncion
        elif all([defuncion.fecha, defuncion.paciente_id]):
            if defuncion.tipo == 1 and not defuncion.dependencia:
                raise ValueError("Debe indicar una dependencia para defunción intrahospitalaria")
            
            
            try:
                with transaction.atomic():
                    kwargs = {
                        "fecha_defuncion": defuncion.fecha,
                        "tipo_defuncion": defuncion.tipo,
                        "motivo": defuncion.motivo,
                        "paciente_id": defuncion.paciente_id,
                        "registrado_por_id": defuncion.usuario_id,
                    }

                    campo = defuncion.tipo_dependencia
                    if campo:
                        kwargs[campo] = defuncion.dependencia

                    defNueva = Defuncion.objects.create(**kwargs)

                    # Cambiar estado del paciente a pasivo
                    PacienteService.paciente_a_pasivo(defNueva.paciente.id, defuncion.usuario_id)

                return True  # Todo salió bien
            
            except Exception as e:
                log_error(
                    f"[FALLO_CREAR_DEFUNCION] paciente={defuncion.paciente_id} detalle={str(e)}",
                    app=LogApp.PACIENTE
                )
                raise
        else:   
            log_warning(
                f"[DATOS_INCOMPLETOS_DEFUNCION] paciente={defuncion.paciente_id}",
                app=LogApp.PACIENTE
            )
            raise ValueError("Datos incompletos para registrar la defunción")


    @staticmethod
    def procesar_obito(obito):

        def actualizar_datos_obito(obitoRegistro):
            cambios = False
            try:
                if obitoRegistro.fecha_obito != obito.fecha:
                    obitoRegistro.fecha_obito = obito.fecha
                    cambios = True

                tipo = obito.tipo

                nueva_sala = None
                nueva_especialidad = None
                nuevo_aux = None

                if tipo != 2:
                    
                    if obito.tipo_dependencia == 'sala':
                        nueva_sala = obito.dependencia
                        nueva_especialidad = None
                        nuevo_aux = None

                    elif obito.tipo_dependencia == 'especialidad':
                        nueva_sala = None
                        nueva_especialidad = obito.dependencia
                        nuevo_aux = None

                    elif obito.tipo_dependencia == 'servicio_auxiliar':
                        nueva_sala = None
                        nueva_especialidad = None
                        nuevo_aux = obito.dependencia

                # Comparaciones
                if obitoRegistro.sala != nueva_sala:
                    obitoRegistro.sala = nueva_sala
                    cambios = True

                if obitoRegistro.especialidad != nueva_especialidad:
                    obitoRegistro.especialidad = nueva_especialidad
                    cambios = True

                if obitoRegistro.servicio_auxiliar != nuevo_aux:
                    obitoRegistro.servicio_auxiliar = nuevo_aux
                    cambios = True

                if obitoRegistro.tipo_defuncion != tipo:
                    obitoRegistro.tipo_defuncion = tipo
                    cambios = True

                if obitoRegistro.responsable_dni != obito.dni_responsable:
                    obitoRegistro.responsable_dni = obito.dni_responsable
                    cambios = True

                if obitoRegistro.responsable_nombre != obito.nombre_responsable:
                    obitoRegistro.responsable_nombre = obito.nombre_responsable
                    cambios = True

                if cambios:
                    obitoRegistro.save()
                    return True, obitoRegistro.id

                return False, None

            except Exception as e:
                log_error(
                    f"[FALLO_ACTUALIZAR_OBITO] id={obitoRegistro.id} detalle={str(e)}",
                    app=LogApp.PACIENTE
                )
                raise


        # UPDATE
        if obito.id:
            try:
                obitoRegistro = ObitoFetal.objects.get(id=obito.id)
                return actualizar_datos_obito(obitoRegistro)
            except ObitoFetal.DoesNotExist:
                return False, None
            except Exception:
                raise


        #  CREATE
        elif all([obito.fecha, obito.paciente_id]):

            if obito.tipo == 1 and not obito.dependencia:
                raise ValueError("Debe indicar una dependencia para óbito intrahospitalario")

            try:
                with transaction.atomic():
                    kwargs = {
                        "fecha_obito": obito.fecha,
                        "tipo_defuncion": obito.tipo,
                        "paciente_id": obito.paciente_id,
                        "responsable_dni": obito.dni_responsable,
                        "responsable_nombre": obito.nombre_responsable,
                        "registrado_por_id": obito.usuario_id,
                    }

                    campo = obito.tipo_dependencia
                    if campo:
                        kwargs[campo] = obito.dependencia

                    obitoNuevo = ObitoFetal.objects.create(**kwargs)

                return True, obitoNuevo.id

            except Exception as e:
                log_error(
                    f"[FALLO_CREAR_OBITO] paciente={obito.paciente_id} detalle={str(e)}",
                    app=LogApp.PACIENTE
                )
                raise

        else:
            log_warning(
                f"[DATOS_INCOMPLETOS_OBITO] paciente={obito.paciente_id}",
                app=LogApp.PACIENTE
            )
            raise ValueError("Datos incompletos para registrar el óbito")



    @staticmethod
    def procesar_entrega_cadaver(defuncion):

        if not defuncion.id:
            # si no viene id defuncion es porque es nueva
            try:
                defuncionRegistro = Defuncion.objects.get(paciente_id=defuncion.paciente_id)
            except Defuncion.DoesNotExist:
                return False, 0
        else:
            try:
                defuncionRegistro = Defuncion.objects.get(id=defuncion.id)
            except Defuncion.DoesNotExist:
                return False, 0

        try:
            with transaction.atomic():

                fecha_entrega = datetime.strptime(defuncion.fecha_entrega, "%Y-%m-%d").date()


                validar_fecha(fecha_entrega, anio_minimo=2000, permitir_futuro=False)
                if fecha_entrega < defuncionRegistro.fecha_defuncion:
                    raise ValidationError("La fecha de entrega no puede ser menor a la fecha de defunción.")

                defuncionRegistro.reponsable_dni = defuncion.reponsable_dni
                defuncionRegistro.reponsable_nombre = defuncion.reponsable_nombre
                defuncionRegistro.fecha_entrega = fecha_entrega
                defuncionRegistro.save()
                return True, defuncionRegistro.id

        except ValidationError:
            raise

        except Exception as e:
            log_error(
                f"[FALLO_ENTREGA_CADAVER] paciente={defuncion.paciente_id} id_defuncion={defuncion.id} detalle={str(e)}",
                app=LogApp.PACIENTE
            )
            raise


    @staticmethod
    def paciente_a_pasivo(idPaciente, idUsuario):
        # Intentar obtener al paciente (sin excluir el estado "P")
        try:
            paciente = Paciente.objects.get(id=idPaciente)
        except Paciente.DoesNotExist:
            raise Exception(f"Paciente con ID {idPaciente} no existe en la base de datos.")

        # Validar existencia del Usuario
        try:
            usuario = User.objects.get(id=idUsuario)
        except User.DoesNotExist:
            raise Exception(f"Usuario con ID {idUsuario} no encontrado.")

        # Si ya es pasivo, no hacemos nada y retornamos True (porque el objetivo ya se cumplió)
        if paciente.estado == "P":
            return True

        #  Si no es pasivo, procedemos a actualizarlo
        try:
            paciente.estado = "P"
            paciente.modificado_por = usuario
            paciente.fecha_modificado = now()
            paciente.save()
            return True
        except Exception as e:
            raise Exception(f"Error al guardar el estado pasivo para el paciente {idPaciente}: {str(e)}")



    @staticmethod
    def paciente_a_activo(idPaciente):
        updated = Paciente.objects.filter(id=idPaciente).update(estado="A")
        return updated > 0


    @staticmethod
    def comprobar_defuncion(paciente):
        return hasattr(paciente, 'defuncion') and paciente.defuncion is not None


    @staticmethod
    def comprobar_inactivo(idPaciente):
        return Paciente.objects.filter(
        id=idPaciente,
        estado="I",
        ).exists()


    @staticmethod
    def reclasificar_rn_a_hijo(ejecutar=False):

        try:
            with connection.cursor() as cursor:
                cursor.callproc("reclasificar_rn_a_hijo", [1 if ejecutar else 0])
                result = cursor.fetchall()

                if not result or len(result[0]) == 0:
                    log_warning(
                        f"[SIN_RESPUESTA_SP] reclasificar_rn_a_hijo ejecutar={ejecutar}",
                        app=LogApp.PACIENTE
                    )
                    return 0

                cantidad = result[0][0]

                log_info(
                    f"[RECLASIFICACION_RN] ejecutar={ejecutar} total={cantidad}",
                    app=LogApp.PACIENTE
                )

                return cantidad

        except Exception as e:
            log_error(
                f"[FALLO_SP_RECLASIFICAR] ejecutar={ejecutar} detalle={str(e)}",
                app=LogApp.PACIENTE
            )
            raise


    #OJO  SIN USO PERO POTENCIALMENTE NECESARIA
    @staticmethod
    def comprobar_reclasificar_pacientes_pasivos_ultima_visita(ejecutar=True):
        hoy = date.today()
        inicio_anio = date(hoy.year, 1, 1)
        pacientes = Paciente.objects.filter(estado="P").select_related('defuncion')
        pacientes_a_corregir = []

        for paciente in pacientes:
            defu =PacienteService.comprobar_defuncion(paciente)
            if defu:
                continue

            ultima_visita = paciente.get_ultima_visita(True)
            if not ultima_visita:
                continue

            if isinstance(ultima_visita, datetime):
                ultima_visita = ultima_visita.date()

            if ultima_visita >= inicio_anio:
                pacientes_a_corregir.append(paciente)

        if not ejecutar:
            return len(pacientes_a_corregir)

        # Si ejecutar=True, actualizamos los pacientes
        corregidos = 0
        for paciente in pacientes_a_corregir:
            actualizado = Paciente.objects.filter(id=paciente.id).update(estado="A")
            if actualizado:
                corregidos += 1

        return corregidos


    @staticmethod
    def obtener_tipos():# de paciente
        """Obtiene los tipos de identificacion psibles para un paciente."""
        tipos = Tipo.objects.all().values('id', 'descripcion_tipo')
        return list(tipos)


    # para replicar en BIT y en SALMI 
    # Método estático para crear el diccionario a partir del paciente
    @staticmethod
    def crear_paciente_objeto(paciente, padre, madre):
        return {
            "EXPEDIENTE": paciente.expediente_numero or '',
            "APELLIDO_1_DEL_PACIENTE": paciente.primer_apellido or '',
            "APELLIDO_2_DEL_PACIENTE": paciente.segundo_apellido or '',
            "NOMBRES_DEL_PACIENTE": f"{paciente.primer_nombre} {paciente.segundo_nombre or ''}".strip(),
            "FECHA_DE_NACIMIENTO_DEL_P": paciente.fecha_nacimiento,
            "Sexo": 1 if paciente.sexo =='H' else 2,
            "IDENTIDAD_DEL_PACIENTE": paciente.dni or '',
            "NOMBRE_DEL_PADRE": (
                f"{padre.get('primer_nombre', '')} {padre.get('segundo_nombre', '')}".strip()
                if padre else ''
            ),
            "APELLIDO_DEL_PADRE": (
                f"{padre.get('primer_apellido', '')} {padre.get('segundo_apellido', '')}".strip()
                if padre else ''
            ),
            "IDENTIDAD_DEL_PADRE": padre.get("dni", '') if padre else '',

            "NOMBRE_DE_LA_MADRE": (
                f"{madre.get('primer_nombre', '')} {madre.get('segundo_nombre', '')}".strip()
                if madre else ''
            ),
            "APELLIDO_DE_LA_MADRE": (
                f"{madre.get('primer_apellido', '')} {madre.get('segundo_apellido', '')}".strip()
                if madre else ''
            ),
            "IDENTIDAD_DE_LA_MADRE": madre.get("dni", '') if madre else '',
            "NACIONALIDAD": paciente.nacionalidad.descripcion_nacionalidad if paciente.nacionalidad else '',
            "NAC": paciente.nacionalidad.descripcion_corta if paciente.nacionalidad else '',
            "OCUPACION": paciente.ocupacion.descripcion_ocupacion if paciente.ocupacion else '',
            "ESTADO_CIVIL" : paciente.estado_civil.descripcion_estado_civil if paciente.estado_civil else '',
            "DIRECCION": formatear_ubicacion_completo(
                paciente.sector.aldea.municipio.departamento.nombre_departamento,
                paciente.sector.aldea.municipio.nombre_municipio,
                paciente.sector.nombre_sector
            ) if paciente.sector and paciente.sector.aldea and paciente.sector.aldea.municipio and paciente.sector.aldea.municipio.departamento else '',
            "CIUDAD": (
                paciente.sector.aldea.municipio.nombre_municipio
                if paciente.sector and paciente.sector.aldea and paciente.sector.aldea.municipio else ''
            ),
            "TELEFONO_DEL_PACIENTE": paciente.telefono or '',
            "ZONA_GEOGRAFICA": (
                paciente.sector.aldea.municipio.departamento.nombre_departamento
                if paciente.sector and paciente.sector.aldea and paciente.sector.aldea.municipio and paciente.sector.aldea.municipio.departamento else ''
            ),
            "OBSERVACIONES": paciente.observaciones or '',
        }


    #Informes y generador de reportes
    @staticmethod
    def GenerarDataPaciente(reporte_criterios, modo='resumido'):
        """
        Filtra y procesa datos de pacientes según criterios.
        Puede retornar datos detallados o un resumen agrupado.
        """
        try:
            qs = Paciente.objects.all()

            # --- Bloque de Filtros (se mantiene igual) ---
            if 'campoFiltro' in reporte_criterios and 'valorFiltro' in reporte_criterios:
                if reporte_criterios['campoFiltro'] != 'ninguno':
                    campo = reporte_criterios['campoFiltro']
                    valor = reporte_criterios['valorFiltro']
                    qs = qs.filter(**{campo: valor})

            if 'fechaIni' in reporte_criterios and reporte_criterios['fechaIni']:
                campo_fecha = reporte_criterios.get('interaccion', 'fecha_creado')
                qs = qs.filter(**{f"{campo_fecha}__gte": reporte_criterios['fechaIni']})

            if 'fechaFin' in reporte_criterios and reporte_criterios['fechaFin']:
                campo_fecha = reporte_criterios.get('interaccion', 'fecha_creado')
                qs = qs.filter(**{f"{campo_fecha}__lte": reporte_criterios['fechaFin']})
            

            # --- Lógica de Modo Detallado vs. Modo Resumido ---
            if modo == 'detallado':
                # Diccionario para nombres amigables
                agrupacion_campos = {
                    'creado_por_id': ('creado_por__username', 'Usuario creador'),
                    'modificado_por_id': ('modificado_por__username', 'Usuario editor'),
                    'sexo': ('sexo', 'Sexo'),
                    'sector__aldea__municipio_id': ('sector__aldea__municipio__nombre_municipio', 'Municipio'),
                    'sector__aldea__municipio__departamento_id': ('sector__aldea__municipio__departamento__nombre_departamento', 'Departamento'),
                    'estado': ('estado', 'Estado'),
                    'tipo_id': ('tipo__descripcion_tipo', 'Tipo de paciente'),
                    'zona_id': ('zona__nombre_zona', 'Zona Atencion'),
                }
                agrupacion_key = reporte_criterios.get('agrupacion', 'id')
                campo_agrupado, nombre_amigable = agrupacion_campos.get(agrupacion_key, (agrupacion_key, agrupacion_key))

                limite = 5000  # Límite de registros

                # Precargamos relaciones para evitar N+1
                qs = qs.select_related(
                    'creado_por',
                    'modificado_por',
                    'tipo',
                    'zona',
                    'sector__aldea__municipio__departamento'
                )

                qs_ordenado = qs.order_by(campo_agrupado, 'primer_nombre')[:limite]

                # Transformamos a lista de diccionarios lista para ReportLab
                lista_dicts = list(qs_ordenado.values(
                    'id',
                    'dni',
                    'expediente_numero',
                    'primer_nombre',
                    'segundo_nombre',
                    'primer_apellido',
                    'segundo_apellido',
                    'sexo',
                    'tipo__descripcion_tipo',
                    'tipo__id',
                    'zona_id',
                    'zona__nombre_zona',
                    'estado',
                    'sector__aldea__municipio__nombre_municipio',
                    'sector__aldea__municipio__id',
                    'sector__aldea__municipio__departamento__nombre_departamento',
                    'sector__aldea__municipio__departamento__id',
                    'creado_por__username',
                    'creado_por__first_name',
                    'creado_por__last_name',
                    'modificado_por__username',
                    'fecha_creado',
                    'modificado_por__first_name',
                    'modificado_por__last_name',
                    'fecha_nacimiento',
                    'fecha_modificado',
                ))

                return {
                    'campo_agrupado': campo_agrupado,
                    'etiqueta': nombre_amigable,
                    'data': lista_dicts
                }

            
            elif modo == 'resumido':
                # Si el modo es resumido, se ejecuta tu lógica actual
                agrupacion_campos = {
                    'creado_por_id': ('creado_por__username', 'usuario creador'),
                    'modificado_por_id': ('modificado_por__username', 'usuario editor'),
                    'sexo': ('sexo', 'Sexo'),
                    'sector__aldea__municipio_id': ('sector__aldea__municipio__nombre_municipio', 'Municipio'),
                    'sector__aldea__municipio__departamento_id': ('sector__aldea__municipio__departamento__nombre_departamento', 'Departamento'),
                    'estado': ('estado', 'Estado'),
                    'tipo_id': ('tipo__descripcion_tipo', 'Tipo de paciente'),
                    'zona_id': ('zona__nombre_zona', 'Zona Atencion'),
                }

                agrupacion_key = reporte_criterios.get('agrupacion', 'id')
                campo_agrupado, nombre_amigable = agrupacion_campos.get(agrupacion_key, (agrupacion_key, agrupacion_key))
                
                resumen_raw = qs.values(campo_agrupado).annotate(
                    total=models.Count('id')
                ).order_by('-total')

                total = qs.count()

                if total == 0:
                    log_warning(
                        f"[REPORTE_VACIO] modo={modo} criterios={reporte_criterios}",
                        app=LogApp.REPORTE
                    )
                    
                resumen = []
                for item in resumen_raw:
                    porcentaje = (item['total'] / total) * 100 if total > 0 else 0
                    resumen.append({
                        campo_agrupado: item[campo_agrupado],
                        'total': item['total'],
                        'porcentaje': round(porcentaje, 2)
                    })

                return {
                    'campo_agrupado': campo_agrupado,
                    'etiqueta': nombre_amigable,
                    'total': total,
                    'resumen': resumen
                }

        except Exception as e:
            log_error(
                    f"[FALLO_REPORTE_PACIENTE] modo={modo} criterios={str(reporte_criterios)} detalle={str(e)}",
                    app=LogApp.REPORTE
                )
            return None
            

    @staticmethod
    def llenarDatosCamposPaciente(form, paciente, numero_expediente=None):
        form.fields['dniPaciente'].initial = paciente.dni
        form.fields['numeroExpediente'].initial = str(numero_expediente).zfill(7) if numero_expediente else None
        form.fields['nombreCompletoPaciente'].initial = formatear_nombre_completo(
            paciente.primer_nombre, paciente.segundo_nombre,
            paciente.primer_apellido, paciente.segundo_apellido
        )
        form.fields['fechaNacimientoPaciente'].initial = formatear_fecha_simple(paciente.fecha_nacimiento)
        form.fields['edadPaciente'].initial = calcular_edad_texto(str(paciente.fecha_nacimiento))
        form.fields['sexoPaciente'].initial = paciente.get_sexo_display()
        form.fields['telefonoPaciente'].initial = paciente.telefono
        form.fields['direccionPaciente'].initial = formatear_ubicacion_completo(
            paciente.sector.aldea.municipio.departamento.nombre_departamento,
            paciente.sector.aldea.municipio.nombre_municipio,
            paciente.sector.nombre_sector
        )


    @staticmethod
    def esMujerEdadFertil(paciente):
        if not paciente:
            return False

        if paciente.sexo != GENERO_FEMENINO:
            return False

        if not paciente.fecha_nacimiento:
            return False

        fecha = paciente.fecha_nacimiento

        # Asegurar formato string si tu función lo requiere
        if not isinstance(fecha, str):
            fecha = fecha.strftime("%Y-%m-%d")

        numero, indicador = obtener_edad_con_indicador(fecha)

        if indicador != INDICADOR_ANIOS:
            return False

        edad = int(numero)

        return EDAD_FERTIL_MIN <= edad <= EDAD_FERTIL_MAX


    @staticmethod
    def obtener_obitos_por_paciente(paciente_id):

        qs = ObitoFetal.objects.filter(
            paciente_id=paciente_id,
            estado=1
        ).annotate(
            fecha=TruncDate('fecha_obito')
        ).order_by('fecha_obito')

        return list(
            qs.values(
                "id",
                "fecha",  #ya viene solo fecha
                "motivo",
                "responsable_nombre",
                "responsable_dni",
                "sala_id"
            )
        )
            