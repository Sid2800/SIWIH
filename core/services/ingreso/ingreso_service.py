
from django.db import connections, OperationalError
from ingreso.models import Acompanante, Ingreso, RecepcionIngresoDetalleSala, RecepcionIngresoSala
from paciente.models import Paciente, Padre
from expediente.models import PacienteAsignacion
from servicio.models import Sala
from core.services.paciente_service import PacienteService
from core.services.mapeo_camas_service import MapeoCamasService
from django.db.models import Func, F, Q, OuterRef, Subquery, DateField, Value, Count
from django.db.models.functions import Concat
from django.db import transaction
from core.utils.utilidades_logging import *
from core.constants.domain_constants import LogApp

class IngresoService:

    @staticmethod
    def obtener_acompaniante(DNI):
        try:
            acompanianteM = Acompanante.objects.select_related("sector__aldea__municipio__departamento").get(dni=DNI)
            return {
                "id": acompanianteM.id if acompanianteM.id else "",
                "dni": acompanianteM.dni if acompanianteM.dni else "",
                "telefono": getattr(acompanianteM, "telefono", ""),
                "primer_nombre": getattr(acompanianteM, "primer_nombre", ""),
                "segundo_nombre": getattr(acompanianteM, "segundo_nombre", ""),
                "primer_apellido": getattr(acompanianteM, "primer_apellido", ""),
                "segundo_apellido": getattr(acompanianteM, "segundo_apellido", ""),
                "sector_id": acompanianteM.sector.id if acompanianteM.sector else None,
                "sector_nombre": acompanianteM.sector.nombre_sector if acompanianteM.sector else "",
                "municipio_id": acompanianteM.sector.aldea.municipio.id if acompanianteM.sector and acompanianteM.sector.aldea else None,
                "departamento_id": acompanianteM.sector.aldea.municipio.departamento.id if acompanianteM.sector and acompanianteM.sector.aldea and acompanianteM.sector.aldea.municipio else None,
            }
        except Acompanante.DoesNotExist:
            pass

        padre = Padre.objects.select_related("direccion__aldea__municipio__departamento").filter(
            Q(dni=DNI) & Q(paciente_ref__isnull=True)
        ).first()
        if padre:
            return {
                "dni": padre.dni if padre.dni else "",
                "telefono": getattr(padre, "telefono", ""),
                "primer_nombre": getattr(padre, "primer_nombre", getattr(padre, "nombre1", "")),
                "segundo_nombre": getattr(padre, "segundo_nombre", getattr(padre, "nombre2", "")),
                "primer_apellido": getattr(padre, "primer_apellido", getattr(padre, "apellido1", "")),
                "segundo_apellido": getattr(padre, "segundo_apellido", getattr(padre, "apellido2", "")),
                "sector_id": padre.direccion.id if padre.direccion else None,
                "sector_nombre": padre.direccion.nombre_sector if padre.direccion else "",
                "municipio_id": padre.direccion.aldea.municipio.id if padre.direccion and padre.direccion.aldea else None,
                "departamento_id": padre.direccion.aldea.municipio.departamento.id if padre.direccion and padre.direccion.aldea and padre.direccion.aldea.municipio else None,
            }

        paciente = Paciente.objects.select_related("sector__aldea__municipio__departamento").filter(dni=DNI).first()
        if paciente:
            return {
                "dni": paciente.dni if paciente.dni else "",
                "telefono": getattr(paciente, "telefono", ""),
                "primer_nombre": getattr(paciente, "primer_nombre", ""),
                "segundo_nombre": getattr(paciente, "segundo_nombre", ""),
                "primer_apellido": getattr(paciente, "primer_apellido", ""),
                "segundo_apellido": getattr(paciente, "segundo_apellido", ""),
                "sector_id": paciente.sector.id if paciente.sector else None,
                "sector_nombre": paciente.sector.nombre_sector if paciente.sector else "",
                "municipio_id": paciente.sector.aldea.municipio.id if paciente.sector and paciente.sector.aldea else None,
                "departamento_id": paciente.sector.aldea.municipio.departamento.id if paciente.sector and paciente.sector.aldea and paciente.sector.aldea.municipio else None,
            }

        acompanianteC = PacienteService.obtener_paciente_censo(DNI)
        if acompanianteC['data']:
            acompanianteC = acompanianteC['data'][0]
            return {
                "dni": acompanianteC.get("DNI", ""),
                "primer_nombre": acompanianteC.get("NOMBRE1", ""),
                "segundo_nombre": acompanianteC.get("NOMBRE2", ""),
                "primer_apellido": acompanianteC.get("APELLIDO1", ""),
                "segundo_apellido": acompanianteC.get("APELLIDO2", ""),
                "sector_id": acompanianteC.get("ID_LUGAR_POBLADO", None),
                "sector_nombre": acompanianteC.get("NOMBRE_UBICACION", ""),
                "municipio_id": acompanianteC.get("ID_MUNICIPIO", None),
                "departamento_id": acompanianteC.get("ID_DEPARTAMENTO", None),
            }

        return None

    @staticmethod
    def procesar_acompaniante(id, dni, nombre1, nombre2, apellido1, apellido2, sector, telefono):
        try:
            dni = dni or None
            def actualizar_datos_acompaniante(acompaniante):
                cambios = False

                if acompaniante.dni != dni:
                    acompaniante.dni = dni
                    cambios = True

                if acompaniante.primer_nombre != nombre1:
                    acompaniante.primer_nombre = nombre1
                    cambios = True
                
                if acompaniante.segundo_nombre != nombre2:
                    acompaniante.segundo_nombre = nombre2
                    cambios = True
                
                if acompaniante.primer_apellido != apellido1:
                    acompaniante.primer_apellido = apellido1
                    cambios = True

                if acompaniante.segundo_apellido != apellido2:
                    acompaniante.segundo_apellido = apellido2
                    cambios = True

                if acompaniante.sector_id != sector:
                    acompaniante.sector_id = sector
                    cambios = True

                if acompaniante.telefono != telefono:
                    acompaniante.telefono = telefono
                    cambios = True
                
                if cambios:
                    acompaniante.save()

                return acompaniante

            # Intentamos encontrar el acompañante por ID
            if id:
                try:
                    acompaniante = Acompanante.objects.get(id=id)
                    return actualizar_datos_acompaniante(acompaniante)
                except Acompanante.DoesNotExist:
                    pass  # Si no existe, continuamos buscando por DNI

            # Intentamos encontrar el acompañante por DNI
            if dni:
                try:
                    acompaniante = Acompanante.objects.get(dni=dni)
                    return actualizar_datos_acompaniante(acompaniante)
                except Acompanante.DoesNotExist:
                    pass  # Si no existe, intentamos crearlo

            # Si no encontramos por ID o DNI, creamos un nuevo acompañante
            if nombre1 and apellido1:
                with transaction.atomic():  # Para evitar problemas de concurrencia
                    acompaniante = Acompanante.objects.create(
                        primer_nombre=nombre1,
                        segundo_nombre=nombre2,
                        primer_apellido=apellido1,
                        segundo_apellido=apellido2,
                        dni=dni if dni else None,
                        telefono=telefono,
                        sector_id=sector
                    )
                    return acompaniante
            log_warning(
                f"No se pudo crear acompañante, datos insuficientes",
                app=LogApp.PACIENTE
            )

            return None
        except Exception:
            log_error(
                f"Error procesando acompañante DNI {dni}",
                app=LogApp.PACIENTE
            )
            raise
            
    @staticmethod
    def tiene_ingreso_activo(id_paciente):
        return Ingreso.objects.filter(
            Q(paciente_id=id_paciente) &
            Q(fecha_egreso__isnull=True) &
            Q(estado=1)
        ).exists()
    
    @staticmethod
    def obtener_salas_con_ingresos_activos():
        ingresos_activos = Ingreso.objects.filter(fecha_egreso__isnull=True, estado=1)
        salas_ids = ingresos_activos.values_list('sala_id', flat=True).distinct()
        salas = Sala.objects.filter(id__in=salas_ids,estado=True).values("id","nombre_sala")
        return salas
    
    @staticmethod
    def obtener_ingresos_activos():
        expediente_subquery = PacienteAsignacion.objects.filter(
            paciente=OuterRef('paciente_id'),
            estado=1
        ).order_by('-id').values('expediente__numero')[:1]

        ingresos = Ingreso.objects.annotate(
            expediente_numero=Subquery(expediente_subquery)
        ).filter(
            fecha_egreso__isnull=True,
            estado=1
        ).values(
            "id",
            "fecha_ingreso",
            "expediente_numero",
            "paciente_id",
            "paciente__dni",
            "paciente__primer_nombre",
            "paciente__primer_apellido",
            "sala__id",
        )
        return ingresos
    
    @staticmethod
    def obtener_ingresos_SDGI():
        expediente_subquery = PacienteAsignacion.objects.filter(
        paciente=OuterRef('paciente_id'),
        estado=1
        ).order_by('-id').values('expediente__numero')[:1]

        ingresos = Ingreso.objects.annotate(
            expediente_numero=Subquery(expediente_subquery)
        ).filter(
            fecha_recepcion_sdgi__isnull=True,
            fecha_egreso__isnull=False,
            estado=1
        ).values(
            "id",
            "fecha_ingreso",
            "fecha_egreso",
            "expediente_numero",
            "paciente_id",
            "paciente__dni",
            "paciente__primer_nombre",
            "paciente__primer_apellido",
            "sala__nombre_sala",
        ).order_by(
            "expediente_numero"
        )

        return ingresos
    
    @staticmethod
    def listar_ingresos_por_paciente(id_paciente):
        ingresos_qs = Ingreso.objects.filter(
            paciente_id=id_paciente,
            estado=1
        ).select_related(
            'sala__servicio',
            'modificado_por'
        ).prefetch_related(
            'recepcion_detalles_sala__recepcion__recibido_por',
            'recepcion_detalles_sdgi__recepcion__recibido_por'
        )

        ingresos = []
        for ingreso in ingresos_qs:
            # Recepción normal
            usuario_recibio = None
            try:
                recepcion_detalle = ingreso.recepcion_detalles_sala.first()
                if recepcion_detalle and recepcion_detalle.recepcion:
                    usuario_recibio = recepcion_detalle.recepcion.recibido_por.username
            except Exception:
                usuario_recibio = None

            # Recepción SDGI
            usuario_recibio_sdgi = None
            try:
                recepcion_detalle_sdgi = ingreso.recepcion_detalles_sdgi.first()
                if recepcion_detalle_sdgi and recepcion_detalle_sdgi.recepcion:
                    usuario_recibio_sdgi = recepcion_detalle_sdgi.recepcion.recibido_por.username
            except Exception:
                usuario_recibio_sdgi = None

            ingresos.append({
                "id": ingreso.id,
                "fecha_ingreso": ingreso.fecha_ingreso,
                "fecha_egreso": ingreso.fecha_egreso,
                "fecha_recepcion_sdgi": ingreso.fecha_recepcion_sdgi,
                "sala__nombre_sala": ingreso.sala.nombre_sala if ingreso.sala else None,
                "sala__servicio__nombre_corto": ingreso.sala.servicio.nombre_corto if ingreso.sala and ingreso.sala.servicio else None,
                "modificado_por__username": ingreso.modificado_por.username if ingreso.modificado_por else None,
                "fecha_modificado": ingreso.fecha_modificado,
                "usuario_recibio_egreso": usuario_recibio,
                "usuario_recibio_sdgi": usuario_recibio_sdgi,
            })

        return ingresos

    @staticmethod
    def GenerarDataIngreso(reporte_criterios, modo='resumido'):
        """
        Filtra y procesa datos de ingresos según criterios.
        Puede retornar datos detallados o un resumen agrupado.
        """
        try:
            qs = Ingreso.objects.all()
            qs = qs.filter(estado=1)

            # --- Bloque de Filtros ---
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
            agrupacion_campos = {
                'creado_por_id': ('creado_por__username', 'usuario creador'),
                'modificado_por_id': ('modificado_por__username', 'usuario editor'),
                'paciente__sector__aldea__municipio__departamento_id': (
                    'paciente__sector__aldea__municipio__departamento__nombre_departamento', 'Departamento'
                ),
                'sala__servicio_id': ('sala__servicio__nombre_servicio', 'servicio'),
                'sala__cama_numero_cama': ('sala__cama_numero_cama', '# Cama'),
                'sala_id': ('sala__nombre_sala', 'Sala'),
            }

            agrupacion_key = reporte_criterios.get('agrupacion', 'id')
            campo_agrupado, nombre_amigable = agrupacion_campos.get(
                agrupacion_key,
                (agrupacion_key, agrupacion_key)
            )

            if modo == 'detallado':
                limite = 5000  # Límite de registros para evitar sobrecarga

                # Precargamos relaciones para evitar N+1
                qs = qs.select_related(
                    'paciente', 'sala', 'sala__servicio', 'creado_por', 'modificado_por'
                ).prefetch_related(
                    'recepcion_detalles_sala__recepcion__recibido_por',  # Usuario que recibió en SDGI
                    'recepcion_detalles_sdgi__recepcion__recibido_por'
                )


                qs_ordenado = qs.order_by(campo_agrupado, 'fecha_ingreso')[:limite]

                # Transformamos a lista de diccionarios
                lista_dicts = list(qs_ordenado.values(
                    'id',
                    'paciente__dni',
                    'paciente__expediente_numero',
                    'paciente__primer_nombre',
                    'paciente__primer_apellido',
                    'paciente__sector__aldea__municipio__departamento__nombre_departamento',
                    'sala__nombre_sala',
                    'sala__servicio__nombre_servicio',
                    'zona_id',
                    'zona__nombre_zona',
                    'cama__numero_cama',
                    'fecha_creado',
                    'fecha_ingreso',
                    'fecha_egreso',
                    'fecha_recepcion_sdgi',
                    'creado_por__username',
                    'creado_por__first_name',
                    'creado_por__last_name',
                    'modificado_por__username',
                    'modificado_por__first_name',
                    'modificado_por__last_name',
                    'recepcion_detalles_sala__recepcion__recibido_por__username',
                    'recepcion_detalles_sdgi__recepcion__recibido_por__username'
                ))

                return {
                    'campo_agrupado': campo_agrupado,
                    'etiqueta': nombre_amigable,
                    'data': lista_dicts
                }

            elif modo == 'resumido':
                # Lógica de agrupación y resumen
                if agrupacion_key == 'sala_id':
                    qs_con_combinacion = qs.annotate(
                        nombre_combinado_sala_servicio=Concat(
                            'sala__nombre_sala',
                            Value(' | '),
                            'sala__servicio__nombre_servicio'
                        )
                    )

                    resumen_raw = qs_con_combinacion.values('nombre_combinado_sala_servicio').annotate(
                        total=Count('id')
                    ).order_by('-total')

                    nombre_amigable = "Sala y Servicio"
                    campo_agrupado = 'nombre_combinado_sala_servicio'
                else:
                    resumen_raw = qs.values(campo_agrupado).annotate(
                        total=Count('id')
                    ).order_by('-total')

                total = qs.count()
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
                    f"Error al generar data de ingreso: {e}",
                    app=LogApp.INGRESOS
                )
            return None
        

    @staticmethod

    def inactivar_ingreso(ingresoId, usuario):
        """
        Inactiva un ingreso y libera la cama asignada de forma atómica.

        Solo puede inactivarse un ingreso que:
          - Exista con el id proporcionado.
          - No haya sido recibido por SDGI (fecha_recepcion_sdgi es None).
          - Esté en estado Activo (estado=1).

        Pasos dentro de transaction.atomic():
          1. Cambia el estado del ingreso a Inactivo (estado=2).
          2. Cierra la AsignacionCamaPaciente activa del paciente y registra
             la transición OCUPADA → LIBRE en HistorialEstadoCama.

        Usar atomic() garantiza que el ingreso no quede inactivo con la cama
        aún marcada como ocupada, ni la cama liberada sin que el ingreso cambie.

        Parámetros:
          ingresoId (int): PK del ingreso a inactivar.
          usuario (User):  usuario que ejecuta la acción (se registra en historial).

        Retorna:
          True  si se inactivó correctamente.
          False si no se encontró un ingreso que cumpla las condiciones.
        """
        ingreso = Ingreso.objects.filter(
            id=ingresoId,
            fecha_recepcion_sdgi__isnull=True,
            estado=1
        ).first()

        if ingreso:
            with transaction.atomic():
                # Paso 1: marcar el ingreso como inactivo
                ingreso.estado = 2
                ingreso.save(update_fields=["estado"])

                # Paso 2: liberar la cama - cierra la asignación activa del paciente
                # y registra OCUPADA → LIBRE en HistorialEstadoCama
                if ingreso.paciente_id:
                    MapeoCamasService.cerrar_asignacion_activa_paciente(
                        paciente_id=ingreso.paciente_id,
                        usuario=usuario,
                        cama_id=ingreso.cama_id,
                    )

            return True

        return False