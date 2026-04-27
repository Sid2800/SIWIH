from referencia.models import Referencia_diagnostico, Respuesta_diagnostico, Referencia, Respuesta
from core.utils.utilidades_fechas import generar_rango_mes, filtro_rango_fecha
from django.db.models import Q, F, Case, When, Value, CharField, Count, Sum, IntegerField
from django.db.models.functions import  Concat, Trim
from core.utils.utilidades_fechas import calcular_edad_texto
from core.utils.utilidades_calculos import calcular_porcentaje
from core.utils.utilidades_textos import formatear_dni, formatear_expediente, construir_nombre_dinamico
from django.utils.timezone import localtime
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *

class RefInformeService:
    
    @staticmethod 
    def generarDataInformeReferencia(mes, anio, indice =1, mayor_complejidad = False): # indice seria el columna que agrupara
        """
        Filtra y agrupa datos de ingresos según criterios, calculando totales y porcentajes para resúmenes.
        Retorna la data procesada lista para la generación de reportes.
        """
        try:
            inicio, fin = generar_rango_mes(mes=mes, anio=anio)
        except Exception as e:
            log_error(
                f"Error generando rango de fechas mes {mes} año {anio}",
                app=LogApp.REPORTE
            )
            return {"error": "Error generando rango de fecha"}

        # tipo de referencia (1 = enviadas, 0 = recibidas)
        tipo_ref = 1 if indice in [1, 2, 3, 5] else 0

        # campo de fecha a usar
        campo_fecha = "fecha_elaboracion" if tipo_ref == 1 else "fecha_recepcion"

        #  consulta a la BD
        try:
            qs = Referencia.objects.filter(
                estado=1,
                tipo=tipo_ref,
                **filtro_rango_fecha(campo_fecha, inicio, fin)
            ).select_related(
                'institucion_destino__nivel_complejidad_institucional',
                'motivo'
            )

            # Filtros opcionales según mayor_complejidad
            if mayor_complejidad:
                qs = qs.filter(
                    institucion_destino__nivel_complejidad_institucional__nivel_complejidad__gte=4
                ).exclude(
                    institucion_destino__nivel_complejidad_institucional__nivel_complejidad=8  # quitamos privadas
                )

        except Exception as e:
            log_error(
                f"Error consultando referencias mes {mes} año {anio}",
                app=LogApp.REPORTE
            )
            return {"error": "Error consultando datos"}

        # ---------------------------------------------------------------------
        # LoGICA DEL ÍNDICE (sin try porque no necesita capturar todo)
        # ---------------------------------------------------------------------

        # Definir mapeo simple de índices → campo + título
        if indice == 1:  # referencias enviadas por especialidad
            etiqueta = "Especialidad destino"
            resumen_raw = (
                qs.values('especialidad_destino__nombre_referencia_especialidad', 'especialidad_destino_id')
                .annotate(conteo=Count('id'))
                .order_by('-conteo', 'especialidad_destino__nombre_referencia_especialidad')
            )
            key_nombre = 'especialidad_destino__nombre_referencia_especialidad'

        elif indice == 2:  # referencias enviadas por institución
            etiqueta = "Institución destino"
            resumen_raw = (
                qs.filter(institucion_destino__nivel_complejidad_institucional__nivel_complejidad__gte=4)
                .annotate(
                    institucion=Concat(
                        'institucion_destino__nivel_complejidad_institucional__siglas',
                        Value('-'),
                        'institucion_destino__nombre_institucion_salud'
                    )
                )
                .values('institucion')
                .annotate(conteo=Count('id'))
                .order_by('-conteo', 'institucion')
            )
            key_nombre = 'institucion'

        elif indice == 3:  # motivo de envío
            etiqueta = "Motivo de envio"
            resumen_raw = (
                qs.filter(institucion_destino__nivel_complejidad_institucional__nivel_complejidad__gte=4)
                .values('motivo__nombre_motivo_envio')
                .annotate(conteo=Count('id'))
                .order_by('-conteo', 'motivo__nombre_motivo_envio')
            )
            key_nombre = 'motivo__nombre_motivo_envio'

        elif indice == 5:  # envío según sala/area_atencion/aux
            etiqueta = "UNIDA CLINICA"

            resumen_raw = (
                qs.annotate(
                    unidad_clinica_nombre=Case(
                        # SALA
                        When(
                            unidad_clinica_refiere__sala__isnull=False,
                            then=Concat(
                                Value('HOSP | '),
                                F('unidad_clinica_refiere__sala__nombre_sala')
                            )
                        ),

                        # AREA ATENCION
                        When(
                            unidad_clinica_refiere__area_atencion__isnull=False,
                            then=Case(
                                When(
                                    unidad_clinica_refiere__area_atencion__servicio_id=1000,
                                    then=Concat(
                                        Value('EMER | '),
                                        F('unidad_clinica_refiere__area_atencion__nombre_area_atencion')
                                    )
                                ),
                                When(
                                    unidad_clinica_refiere__area_atencion__servicio_id=700,
                                    then=Concat(
                                        Value('OBST | '),
                                        F('unidad_clinica_refiere__area_atencion__nombre_area_atencion')
                                    )
                                ),
                                default=Concat(
                                    Value('CEXT | '),
                                    F('unidad_clinica_refiere__area_atencion__nombre_area_atencion')
                                ),
                                output_field=CharField()
                            )
                        ),

                        # SERVICIO AUX
                        When(
                            unidad_clinica_refiere__servicio_aux__isnull=False,
                            then=Concat(
                                Value('SAUX | '),
                                F('unidad_clinica_refiere__servicio_aux__nombre_servicio_a')
                            )
                        ),

                        default=Value('Sin asignar'),
                        output_field=CharField()
                    )
                )
                .values('unidad_clinica_nombre')
                .annotate(conteo=Count('id'))
                .order_by('-conteo', 'unidad_clinica_nombre')
            )
            key_nombre = 'unidad_clinica_nombre'

        elif indice == 8:  # REFERENCIAS RECIBIDAS SEGÚN EVALUACIÓN
            # Vienen de la SESAL

            opciones = {1: 'SI', 2: 'NO', 3: 'N/C'}

            oportunas = (
                qs.filter(institucion_origen__proveedor_salud_id=6)
                .values('oportuna')
                .annotate(conteo=Count('id'))
                .order_by('-conteo', 'oportuna')
            )

            justifiadas = (
                qs.filter(institucion_origen__proveedor_salud_id=6)
                .values('justificada')
                .annotate(conteo=Count('id'))
                .order_by('-conteo', 'justificada')
            )

            tabla_final = []
            total_oportunas = sum(int(f['conteo']) for f in oportunas)
            total_justificadas = sum(int(f['conteo']) for f in justifiadas)

            tabla_final.append(("__HEADER__", f"OPORTUNAS-{total_oportunas}",
                                calcular_porcentaje(total_oportunas, total_oportunas)))

            for fila in oportunas:
                tabla_final.append((
                    opciones.get(fila['oportuna']),
                    fila['conteo'],
                    calcular_porcentaje(fila['conteo'], total_oportunas)
                ))

            tabla_final.append(("__HEADER__", f"JUSTIFICADAS-{total_justificadas}",
                                calcular_porcentaje(total_justificadas, total_justificadas)))

            for fila in justifiadas:
                tabla_final.append((
                    opciones.get(fila['justificada']),
                    fila['conteo'],
                    calcular_porcentaje(fila['conteo'], total_justificadas)
                ))

            tabla_final.append(("TOTAL REFERENCIAS", str(total_oportunas), "100.00%"))

            return {
                'total': total_oportunas,
                'tabla': tabla_final,
                'etiqueta': "EVALUACION"
            }

        else:
            log_warning(
                f"Índice inválido {indice} en informe referencia",
                app=LogApp.REPORTE
            )
            return {'error': 'Índice no válido'}

        # ---------------------------------------------------------------------
        # Construcción de tabla general para índices 1, 2, 3 y 5
        # ---------------------------------------------------------------------

        total = qs.count()
        tabla_final = []

        for item in resumen_raw:
            nombre = item[key_nombre][:38] if item[key_nombre] else '—'
            conteo = item['conteo']
            tabla_final.append((
                nombre,
                conteo,
                calcular_porcentaje(conteo, total, decimales=2, mostrar_simbolo=True)
            ))

        tabla_final.append(("TOTAL", total, "100 %"))

        return {
            'total': total,
            'tabla': tabla_final,
            'etiqueta': etiqueta,
            'top3': list(resumen_raw)[:3] if indice == 1 else None
        }


    @staticmethod
    def generarDataInformeSeguimientoTIC(mes,anio):
        try:
            inicio, fin = generar_rango_mes(mes=mes, anio=anio)
        except Exception as e:
            log_error(
                f"Error generando rango fechas TIC mes {mes} año {anio}",
                app=LogApp.REPORTE
            )
            return {"error": "Error generando rango de fechas"}

        # TRY 2 — consulta a la BD
        try:
            qs = (
                Referencia.objects
                .filter(
                    estado=1,
                    tipo=1,
                    **filtro_rango_fecha("fecha_elaboracion", inicio, fin),
                    institucion_destino__nivel_complejidad_institucional__nivel_complejidad__gte=4
                )
                .select_related('seguimiento_tic')
            )
        except Exception as e:
            log_error(
                f"Error consultando referencias TIC mes {mes} año {anio}",
                app=LogApp.REPORTE
            )
            return {"error": "Error consultando referencias TIC"}

        # --- LÓGICA (sin try) ---

        total = qs.count()


        sin_seguimiento = qs.filter(
            seguimiento_tic__isnull=True
        ).count()

        sin_metodo = qs.filter(
            seguimiento_tic__isnull=False,
            seguimiento_tic__metodo_comunicacion__isnull=True
        ).count()

        con_comunicacion = qs.filter(
            seguimiento_tic__isnull=False,
            seguimiento_tic__establece_comunicacion=True
        ).count()

        sin_comunicacion = qs.filter(
            seguimiento_tic__isnull=False,
            seguimiento_tic__establece_comunicacion=False
        ).count()

        tabla_final = [
            ("SIN SEGUIMIENTO", sin_seguimiento, calcular_porcentaje(sin_seguimiento, total)),
            ("SIN FORMA DE COMUNICACION", sin_metodo, calcular_porcentaje(sin_metodo, total)),
            ("SEGUIMIENTO REALIZADO", con_comunicacion, calcular_porcentaje(con_comunicacion, total)),
            ("NO SE ESTABLECE COMUNICACION", sin_comunicacion, calcular_porcentaje(sin_comunicacion, total)),
            ("TOTAL DE REFERENCIAS", total, "100.00%"),
        ]

        return {
            'total': total,
            'tabla': tabla_final,
            'etiqueta': "Seguimiento"
        }


    @staticmethod
    def generarDataInformeRefRecibidasGestor(mes,anio, indice = 6, recibida = 0):
        try:
            inicio, fin = generar_rango_mes(mes=mes, anio=anio)
        except Exception as e:
            log_error(
                f"Error generando rango fechas gestor mes {mes} año {anio}",
                app=LogApp.REPORTE
            )
            return {"error": "Error generando rango de fechas"}

        tabla_final = []
        total_general = 0

        AREAS = {
            1: "EMERGENCIA OBTETRICA",
            2: "EMERGENCIA GENERAL",
            3: "CONSULTA EXTERNA"
        }

        campo_fecha = "fecha_elaboracion" if recibida == 1 else "fecha_recepcion"

        # consulta a BD
        try:
            qs = (
                Referencia.objects
                .filter(
                    estado=1,
                    tipo=recibida,
                    **filtro_rango_fecha(campo_fecha, inicio, fin)
                )
                .select_related(
                    'institucion_origen__gestor',
                    'institucion_origen__proveedor_salud'
                )
            )
        except Exception as e:
            log_error(
                f"Error consultando referencias gestor mes {mes} año {anio}",
                app=LogApp.REPORTE
            )
            return {"error": "Error consultando datos de referencias"}


        if indice == 6:
            # GESTOR
            tabla_final, total = RefInformeService.generar_tabla_por_gestor(qs, incluir_total=True)
            etiqueda = "GESTOR"
            total_general = total

        elif indice == 7:
            # AREA QUE CAPTA / GESTOR
            etiqueda = "AREA QUE CAPTA / GESTOR"

            total_general = qs.count()

            for area in [1, 2, 3]:
                qs_filtrado = qs.filter(atencion_requerida=area)
                tabla, total = RefInformeService.generar_tabla_por_gestor(qs_filtrado)

                tabla_final.append((
                    "__HEADER__",
                    f"{AREAS.get(area)}-{str(total)}",
                    calcular_porcentaje(total, total_general)
                ))

                tabla_final.extend(tabla)

            tabla_final.append(("TOTAL", total_general, "100%"))

        elif indice == 10:
            # AREA CAPTA / GESTOR
            etiqueda = "AREA CAPTA / GESTOR"
            tabla_final = []
            total_general_ref = 0
            total_general_resp = 0
            total_general_der = 0

            for area in [1, 2, 3]:
                resultado = RefInformeService.generar_tabla_referencia_respuestas_gestor(qs, area)

                tabla_area = resultado["tabla"]
                total_area = resultado["total_area"]
                total_respuestas_area = resultado["total_respuestas"]
                total_derivadas_area = resultado["total_derivadas"]

                # HEADER DEL ÁREA (6 columnas)
                tabla_final.append((
                    "__HEADER__",
                    f"{AREAS.get(area)}-{str(total_area)}",
                    total_respuestas_area,
                    calcular_porcentaje(total_respuestas_area, total_area),
                    total_derivadas_area,
                    calcular_porcentaje(total_derivadas_area, total_respuestas_area),
                ))

                tabla_final.extend(tabla_area)

                # Acumular totales generales
                total_general_ref += total_area
                total_general_resp += total_respuestas_area
                total_general_der += total_derivadas_area

            # TOTAL GENERAL
            tabla_final.append((
                "TOTAL GENERAL",
                total_general_ref,
                total_general_resp,
                calcular_porcentaje(total_general_resp, total_general_ref),
                total_general_der,
                calcular_porcentaje(total_general_der, total_general_resp),
            ))

            total_general = total_general_ref

        elif indice == 11:
            etiqueda = "GESTOR | N. COMPLEJIDAD"

            resultado = RefInformeService.generar_tabla_referencia_enviada_nivel(qs)

            tabla_final = resultado["tabla"]
            total_general = resultado["total_general"]

        else:
            log_warning(
                f"Índice inválido {indice} en informe gestor",
                app=LogApp.REPORTE
            )
            return {"error": "Índice no válido"}

        return {
            'total': total_general,
            'tabla': tabla_final,
            'etiqueta': etiqueda
        }
        

    @staticmethod
    def generar_tabla_por_gestor(qs, incluir_total=False):
        """
        Recibe un queryset de Referencias y devuelve una tabla de conteos por red de origen.
        Ordenado globalmente por conteo.
        """
        total = qs.count()
        tabla_final = []

        # === GESTORES ===
        gestores = (
            qs.filter(institucion_origen__gestor_id__in=[1, 2, 3, 4])
            .values('institucion_origen__gestor__nombre_gestor')
            .annotate(conteo=Count('id'))
        )

        # === OTRAS REDES ===
        otras_redes = qs.exclude(
            Q(institucion_origen__gestor_id__in=[1, 2, 3, 4]) |
            Q(institucion_origen__region_salud_id=10) |
            Q(institucion_origen__proveedor_salud_id__in=[4, 5])
        ).count()

        # === PRIVADA ===
        privada = qs.filter(institucion_origen__proveedor_salud_id=5).count()

        # === OTROS ===
        otros = qs.filter(institucion_origen__proveedor_salud_id=4).count()

        # ORDENAR
        rows = []
        # --- Gestores ---
        for g in gestores:
            rows.append({
                "nombre": g["institucion_origen__gestor__nombre_gestor"],
                "conteo": g["conteo"],
            })

        # --- Otras redes ---
        if otras_redes > 0:
            rows.append({
                "nombre": "OTRAS REDES",
                "conteo": otras_redes,
            })

        # --- Privada ---
        if privada > 0:
            rows.append({
                "nombre": "PRIVADA",
                "conteo": privada,
            })

        # --- Otros ---
        if otros > 0:
            rows.append({
                "nombre": "OTROS",
                "conteo": otros,
            })

    
        rows = sorted(rows, key=lambda x: x["conteo"], reverse=True)

        # =TABLA FINAL
        for r in rows:
            tabla_final.append((
                r["nombre"],
                r["conteo"],
                calcular_porcentaje(r["conteo"],total),
            ))

        # === TOTAL GENERAL ===
        if incluir_total:
            tabla_final.append(("TOTAL DE REFERENCIAS", total, "100.00%"))

        return tabla_final, total


    @staticmethod
    def generar_tabla_referencia_respuestas_gestor(qs, area):

        tabla_final = []

        # Filtrar por área primero
        qs = qs.filter(atencion_requerida = area)
        total_area = qs.count()

        # === GESTORES ===
        gestores = (
            qs.filter(institucion_origen__gestor_id__in=[1, 2, 3, 4])
            .values('institucion_origen__gestor__nombre_gestor')
            .annotate(
                conteo=Count('id'),
                respuestas=Sum(
                    Case(
                        When(respuesta__isnull=False, then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                ),
                derivadas=Sum(
                    Case(
                        When(respuesta__seguimiento_referencia__isnull=False, then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                )
            )
            .order_by('-conteo', 'institucion_origen__gestor__nombre_gestor')
        )

        # === OTRAS REDES ===
        otras_redes = qs.exclude(
            Q(institucion_origen__gestor_id__in=[1, 2, 3, 4]) |
            Q(institucion_origen__region_salud_id=10) |
            Q(institucion_origen__proveedor_salud_id__in=[4, 5])
        ).aggregate(
            conteo=Count('id'),
            respuestas=Sum(
                Case(
                    When(respuesta__isnull=False, then=1),
                    default=0,
                    output_field=IntegerField()
                )
            ),
            derivadas=Sum(
                Case(
                    When(respuesta__seguimiento_referencia__isnull=False, then=1),
                    default=0,
                    output_field=IntegerField()
                )
            )
        )

        # === PRIVADAS ===
        privadas = qs.aggregate(
            referencias = Sum(Case(
                When(institucion_origen__proveedor_salud_id=5, then=1),
                default=0, output_field=IntegerField()
            )),
            respuestas = Sum(Case(
                When(institucion_origen__proveedor_salud_id=5, respuesta__isnull=False, then=1),
                default=0, output_field=IntegerField()
            )),
            derivadas = Sum(Case(
                When(institucion_origen__proveedor_salud_id=5, respuesta__seguimiento_referencia__isnull=False, then=1),
                default=0, output_field=IntegerField()
            )),
        )

        # === OTROS (proveedor 4) ===
        otros = qs.aggregate(
            referencias = Sum(Case(
                When(institucion_origen__proveedor_salud_id=4, then=1),
                default=0, output_field=IntegerField()
            )),
            respuestas = Sum(Case(
                When(institucion_origen__proveedor_salud_id=4, respuesta__isnull=False, then=1),
                default=0, output_field=IntegerField()
            )),
            derivadas = Sum(Case(
                When(institucion_origen__proveedor_salud_id=4, respuesta__seguimiento_referencia__isnull=False, then=1),
                default=0, output_field=IntegerField()
            )),
        )

        # ========= UNIFICAR TODAS LAS FILAS EN UNA SOLA LISTA ==========
        rows = []

        # --- GESTORES ---
        for g in gestores:
            rows.append({
                "nombre": g['institucion_origen__gestor__nombre_gestor'],
                "conteo": int(g['conteo']),
                "respuestas": int(g['respuestas']),
                "derivadas": int(g['derivadas']),
            })

        # --- OTRAS REDES ---
        if otras_redes['conteo'] > 0:
            rows.append({
                "nombre": "OTRAS REDES",
                "conteo": int(otras_redes['conteo']),
                "respuestas": int(otras_redes['respuestas']),
                "derivadas": int(otras_redes['derivadas']),
            })

        # --- PRIVADA ---
        if privadas['referencias'] > 0:
            rows.append({
                "nombre": "PRIVADA",
                "conteo": int(privadas['referencias']),
                "respuestas": int(privadas['respuestas']),
                "derivadas": int(privadas['derivadas']),
            })

        # --- OTROS ---
        if otros['referencias'] > 0:
            rows.append({
                "nombre": "OTROS",
                "conteo": int(otros['referencias']),
                "respuestas": int(otros['respuestas']),
                "derivadas": int(otros['derivadas']),
            })

        # ========= ORDENAR FINAL ==========
        rows = sorted(rows, key=lambda x: x["conteo"], reverse=True)

        # ========= ARMAR TABLA FINAL ==========
        tabla_final = []
        total_respuestas = 0
        total_derivadas = 0

        for r in rows:
            pct_res = calcular_porcentaje(r["respuestas"], r["conteo"])
            pct_der = calcular_porcentaje(r["derivadas"], r["respuestas"])

            tabla_final.append((
                r["nombre"],
                r["conteo"],
                r["respuestas"],
                pct_res,
                r["derivadas"],
                pct_der
            ))

            total_respuestas += r["respuestas"]
            total_derivadas += r["derivadas"]

        return {
            "tabla": tabla_final,
            "total_area": total_area,
            "total_respuestas": total_respuestas,
            "total_derivadas": total_derivadas,
        }
            
    @staticmethod
    def generar_tabla_referencia_enviada_nivel(qs):

        tabla_final = []

        # Filtrar por área primero
        total_area = qs.count()

        # === GESTORES ===
        gestores = (
            qs.filter(
                institucion_destino__gestor_id__in=[1, 2, 3, 4],
                institucion_destino__nivel_complejidad_institucional__nivel_complejidad__in=[1,2,3]
            )
            .values('institucion_destino__gestor__nombre_gestor')
            .annotate(
                total=Count('id'),
                UAPS=Sum(
                    Case(
                        When(institucion_destino__nivel_complejidad_institucional_id=1, then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                ),
                CIS=Sum(
                    Case(
                        When(institucion_destino__nivel_complejidad_institucional_id=2, then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                ),
                SMI=Sum(
                    Case(
                        When(institucion_destino__nivel_complejidad_institucional_id=3, then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                ),
                ZPP=Sum(
                    Case(
                        When(institucion_destino__nivel_complejidad_institucional_id=8, then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                ),
            )
            .order_by('-total', 'institucion_destino__gestor__nombre_gestor')
        )

        # === OTRAS REDES ===
        
        otras_redes = qs.exclude(
                Q(institucion_destino__gestor_id__in=[1,2,3,4]) | 
                Q(institucion_destino__region_salud_id=10) |
                Q(institucion_destino__proveedor_salud_id__in=[4,5])
            ).filter(
                institucion_destino__nivel_complejidad_institucional__nivel_complejidad__lte=3
            ).aggregate(
                total=Count('id'),

                UAPS=Sum(
                    Case(
                        When(institucion_destino__nivel_complejidad_institucional_id=1, then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                ),

                CIS=Sum(
                    Case(
                        When(institucion_destino__nivel_complejidad_institucional_id=2, then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                ),

                SMI=Sum(
                    Case(
                        When(institucion_destino__nivel_complejidad_institucional_id=3, then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                ),

                ZPP=Sum(
                    Case(
                        When(institucion_destino__nivel_complejidad_institucional_id=8, then=1),
                        default=0,
                        output_field=IntegerField()
                    )
                ),
            )
        


        # ========= UNIFICAR TODAS LAS FILAS EN UNA SOLA LISTA ==========
        rows = []

        # --- GESTORES ---
        for g in gestores:
            rows.append({
                "nombre": g['institucion_destino__gestor__nombre_gestor'],
                "UAPS": int(g['UAPS']),
                "CIS": int(g['CIS']),
                "SMI": int(g['SMI']),
                "ZPP": int(g['ZPP']),
                "total": int(g['total']),
            })

        # --- OTRAS REDES ---
        if otras_redes['total'] > 0:
            rows.append({
                "nombre": "OTRAS REDES",
                "UAPS": int(otras_redes['UAPS']),
                "CIS": int(otras_redes['CIS']),
                "SMI": int(otras_redes['SMI']),
                "ZPP": int(otras_redes['ZPP']),
                "total": int(otras_redes['total']),

            })

    

        # ========= ORDENAR FINAL ==========
        rows = sorted(rows, key=lambda x: x["total"], reverse=True)


        # ========= ARMAR TABLA FINAL ==========
        tabla_final = []
        total_UAPS = 0
        total_CIS = 0
        total_SMI = 0
        total_ZPP = 0
        total_general = 0

        # --- Primero calculamos los totales ---
        for r in rows:
            total_UAPS += r["UAPS"]
            total_CIS += r["CIS"]
            total_SMI += r["SMI"]
            total_ZPP += r["ZPP"]
            total_general += r["total"]

        # --- Luego construimos la tabla con % por fila ---
        for r in rows:
            pct = calcular_porcentaje(r["total"], total_general)

            tabla_final.append((
                r["nombre"],
                r["UAPS"],
                r["CIS"],
                r["SMI"],
                r["ZPP"],
                r["total"],
                pct,             # ← este es el porcentaje por fila
            ))

        # ========= AGREGAR TOTAL GENERAL ==========
        tabla_final.append((
            "TOTAL GENERAL",
            total_UAPS,
            total_CIS,
            total_SMI,
            total_ZPP,
            total_general,
            '100.0 %'  # siempre 100% del total
        ))

        return {
            "tabla": tabla_final,
            "total_general": total_general,
        }

    @staticmethod
    def generarDataInformeRespuesta(mes, anio, indice =1):

        try:
            # Calcular fechas del mes
            inicio, fin = generar_rango_mes(mes=mes, anio=anio)

            tabla_final = []

            qs = (
            Respuesta.objects
            .filter(
                referencia__tipo=0,
                **filtro_rango_fecha("fecha_atencion", inicio, fin)
            )
            .select_related(
                'referencia', 
                'unidad_clinica_responde__sala',
                'unidad_clinica_responde__area_atencion',
                'unidad_clinica_responde__servicio_aux',
            )
)
            
            if indice == 1: #referencias enviadas por area_atencion
                etiqueta = "UNIDAD CLINICA RESPONDE"
                resumen_raw = (
                    qs.annotate(
                        area_responde=Case(

                            When(
                                unidad_clinica_responde__sala__isnull=False,
                                then=Concat(
                                    Value('HOSP | '),
                                    F('unidad_clinica_responde__sala__nombre_sala')
                                )
                            ),

                            When(
                                unidad_clinica_responde__area_atencion__isnull=False,
                                then=Case(
                                    When(
                                        unidad_clinica_responde__area_atencion__servicio_id=1000,
                                        then=Concat(
                                            Value('EMER | '),
                                            F('unidad_clinica_responde__area_atencion__nombre_area_atencion')
                                        )
                                    ),
                                    When(
                                        unidad_clinica_responde__area_atencion__servicio_id=700,
                                        then=Concat(
                                            Value('OBST | '),
                                            F('unidad_clinica_responde__area_atencion__nombre_area_atencion')
                                        )
                                    ),
                                    default=Concat(
                                        Value('CEXT | '),
                                        F('unidad_clinica_responde__area_atencion__nombre_area_atencion')
                                    ),
                                    output_field=CharField()
                                )
                            ),

                            When(
                                unidad_clinica_responde__servicio_aux__isnull=False,
                                then=Concat(
                                    Value('SAUX | '),
                                    F('unidad_clinica_responde__servicio_aux__nombre_servicio_a')
                                )
                            ),

                            default=Value('Sin asignar'),
                            output_field=CharField()
                        )
                    )
                    .values('area_responde')
                    .annotate(conteo=Count('id'))
                    .order_by('-conteo', 'area_responde')
                )

                key_nombre = 'area_responde'


            else:
                log_warning(
                    f"Índice inválido {indice} en informe respuesta",
                    app=LogApp.REPORTE
                )
                return {'error': 'Índice no válido'}
            
            # Conteo total general
            total = qs.count()
            tabla_final = []

            # Construir la tabla final
            for item in resumen_raw:
                nombre = item[key_nombre][:38] if item[key_nombre] else '—'
                conteo = item['conteo']
                porcentaje = (conteo / total * 100) if total > 0 else 0
                tabla_final.append((nombre, conteo, f"{round(porcentaje, 2)} %"))

            # Agregar fila total
            tabla_final.append(("TOTAL", total, "100 %"))

            return {
                'total': total,
                'tabla': tabla_final,
                'etiqueta': etiqueta
            }
        
        except Exception as e:
                log_error(
                        f"Error al generar data del informe referencias",
                        app=LogApp.REPORTE
                    )
                return None
        

    @staticmethod
    def generarDetalleInforme1ReferenciaEspecialidad(mes, anio, top3):
        try:
            inicio, fin = generar_rango_mes(mes=mes, anio=anio)
        except Exception as e:
            log_error(
                f"Error generando rango fechas detalle especialidad mes {mes} año {anio}",
                app=LogApp.REPORTE
            )
            return {"error": "Error generando rango de fechas"}

        id_ref = []

        # ¿consultas principales por especialidad
        try:
            # ================= LISTA POR ESPECIALIDAD =================
            for esp in top3:
                esp_id = esp['especialidad_destino_id']
                nombre = esp['especialidad_destino__nombre_referencia_especialidad']

                qs = (
                    Referencia.objects
                    .filter(
                        tipo=1,
                        fecha_elaboracion__range=(inicio, fin),
                        institucion_destino__nivel_complejidad_institucional__nivel_complejidad__gte=4,
                        especialidad_destino_id=esp_id
                    )
                    .exclude(
                        institucion_destino__nivel_complejidad_institucional__nivel_complejidad=8
                    )
                    .values_list('id', flat=True)
                )

                ids = list(qs)

                id_ref.append({
                    'especialidad': nombre,
                    'conteo': len(ids),
                    'referencias': ids,
                })

        except Exception as e:
            log_error(
                f"Error consultando referencias Top3 especialidad mes {mes} año {anio}",
                app=LogApp.REPORTE
            )
            return {"error": "Error consultando referencias del Top 3"}

        # ================= OBTENER DIAGNÓSTICOS POR REFERENCIA =================
        top3_diagnosticos_referencia = []

        # consultas de diagnóstico
        try:
            for bloque in id_ref:
                items_referencia = []

                for ref_id in bloque['referencias']:

                    diag_qs = (
                        Referencia_diagnostico.objects
                        .filter(referencia_id=ref_id, estado=True)
                        .select_related('diagnostico')
                        .annotate(
                            diag=Concat(
                                Trim('diagnostico__nombre_diagnostico'),
                                Case(
                                    When(
                                        detalle__isnull=False,
                                        then=Concat(
                                            Value(" ("),
                                            Trim('detalle'),
                                            Value(")")
                                        )
                                    ),
                                    default=Value(""),
                                    output_field=CharField()
                                ),
                                output_field=CharField()
                            )
                        )
                        .values('diag')
                    )

                    texto = ", ".join(item['diag'] for item in diag_qs) 
                    

                    items_referencia.append(texto + ".")

                top3_diagnosticos_referencia.append({
                    'especialidad': bloque['especialidad'],
                    'total': bloque['conteo'],
                    'items': items_referencia
                })

        except Exception as e:
            log_error(
                f"Error obteniendo diagnósticos Top3 especialidad mes {mes} año {anio}",
                app=LogApp.REPORTE
            )
            return {"error": "Error obteniendo diagnósticos del Top 3"}

        # ================= RETORNO FINAL =================
        return top3_diagnosticos_referencia
        

        

    @staticmethod
    def generarDataFormatoReferencia(id_referencia):  # 0 recibidas 1 enviadas

        relaciones = [
            # paciente y procedencia
            'paciente__sector__aldea__municipio__departamento',

            # institucion origen
            'institucion_origen',
            'institucion_origen__region_salud',
            'institucion_origen__nivel_complejidad_institucional',
            'institucion_origen__proveedor_salud',

            # institucion destino
            'institucion_destino',
            'institucion_destino__region_salud',
            'institucion_destino__nivel_complejidad_institucional',
            'institucion_destino__proveedor_salud',
            'institucion_destino__direccion__aldea__municipio__departamento',

            # elaborado por
            'elaborada_por',

            'especialidad_destino',
        ]

        try:
            referencia = (
                Referencia.objects
                .select_related(*relaciones)
                .get(id=id_referencia)
            )
        except Referencia.DoesNotExist:
            log_warning(
                f"Referencia {id_referencia} no encontrada para formato",
                app=LogApp.REFERENCIAS
            )
            raise ValueError("La referencia solicitada no existe.")

        except Referencia.MultipleObjectsReturned:
            log_error(
                f"Múltiples referencias encontradas con id {id_referencia}",
                app=LogApp.REFERENCIAS
            )
            raise ValueError("Se encontraron múltiples referencias, lo cual no debería ocurrir.")

        except Exception:
            log_error(
                f"Error obteniendo referencia {id_referencia}",
                app=LogApp.REFERENCIAS
            )
            raise
        
        try:
            diag_qs = (
                Referencia_diagnostico.objects
                .filter(referencia_id=id_referencia, estado=True)
                .select_related('diagnostico')
                .annotate(
                    diag=Concat(
                        Trim('diagnostico__nombre_diagnostico'),
                        Case(
                            When(
                                detalle__isnull=False,
                                then=Concat(
                                    Value(" ("),
                                    Trim('detalle'),
                                    Value(")")
                                )
                            ),
                            default=Value(""),
                            output_field=CharField()
                        ),
                        output_field=CharField()
                    )
                )
                .values_list('diag', flat=True)
                .order_by('id')
            )

            texto = " - ".join(diag_qs)

        except Exception:
            log_error(
                f"Error obteniendo diagnósticos referencia {id_referencia}",
                app=LogApp.REFERENCIAS
            )
            raise

        fecha_local_fecha_elaboracion = localtime(referencia.fecha_elaboracion)

        fecha_local_fecha_recepcion = None
        if referencia.fecha_recepcion is not None:
            fecha_local_fecha_recepcion = localtime(referencia.fecha_recepcion)

        paciente_data = {
            # Paciente
            "dni": formatear_dni(referencia.paciente.dni),
            "expediente": formatear_expediente(referencia.paciente.expediente_numero),
            "nombres": construir_nombre_dinamico(referencia.paciente, ["primer_nombre", "segundo_nombre"]),
            "apellido1": referencia.paciente.primer_apellido,
            "apellido2": referencia.paciente.segundo_apellido,
            "telefono": referencia.paciente.telefono,
            "sexo": referencia.paciente.sexo,
            "fecha_nacimiento": referencia.paciente.fecha_nacimiento,
            "edad_texto": calcular_edad_texto(referencia.paciente.fecha_nacimiento),

            # Procedencia (todo plano, sin anidar)
            "departamento": referencia.paciente.sector.aldea.municipio.departamento.nombre_departamento,
            "municipio": referencia.paciente.sector.aldea.municipio.nombre_municipio,
            "direccion": referencia.paciente.sector.nombre_sector,
        }


        referencia_data = {
            # ref
            "ref_id": referencia.id,
            "ref_tipo": referencia.tipo,
            "ref_motivo": referencia.motivo_id,
            "ref_motivo_detalle": referencia.motivo_detalle,
            "ref_diagnosticos": texto,
            "ref_atencion": referencia.atencion_requerida,
            "ref_atencion_descripcion": referencia.get_atencion_requerida_display(),
            "ref_fecha_elaboracion_dia": fecha_local_fecha_elaboracion.day,
            "ref_fecha_elaboracion_mes": fecha_local_fecha_elaboracion.month,
            "ref_fecha_elaboracion_anio": fecha_local_fecha_elaboracion.year,
            "ref_fecha_elaboracion_hora": fecha_local_fecha_elaboracion.strftime("%H:%M"),
            "ref_elaborado_por": referencia.elaborada_por_id,
            "ref_elaborado_descripcion": referencia.elaborada_por.nombre_tipo_personal,
            "ref_oportuna": referencia.oportuna,
            "ref_justificada": referencia.justificada,
            "ref_especialidad_destino": (
                referencia.especialidad_destino.nombre_referencia_especialidad
                if getattr(referencia, "especialidad_destino", None)
                else ""
            ), 
        }


            # instituciones (origen y destino siempre disponibles)
        referencia_data.update({
            # institucion origen
            "institucion_nombre": f"{referencia.institucion_origen.nivel_complejidad_institucional.siglas}-{referencia.institucion_origen.nombre_institucion_salud}",
            "institucion_red": f"#{referencia.institucion_origen.region_salud.codigo}-{referencia.institucion_origen.region_salud.nombre_region_salud}",
            "institucion_proveedor_salud": referencia.institucion_origen.proveedor_salud.nombre_proveedor_salud,
            "institucion_proveedor_salud_id": referencia.institucion_origen.proveedor_salud.id,
            "institucion_nivel": referencia.institucion_origen.nivel_complejidad_institucional.siglas,
            "institucion_centralizado": referencia.institucion_origen.centralizado,
            "institucion_complejidad": referencia.institucion_origen.nivel_complejidad_institucional.nivel_complejidad,
            "institucion_complejidad_nombre": referencia.institucion_origen.nivel_complejidad_institucional.siglas,
            

            # institucion destino
            "institucion_dest_complejidad": referencia.institucion_destino.nivel_complejidad_institucional.nivel_complejidad,
            "institucion_dest_complejidad_nombre": referencia.institucion_destino.nivel_complejidad_institucional.detalle_nivel_complejidad,
            "instirucion_dest_nombre": f"{referencia.institucion_destino.nivel_complejidad_institucional.siglas}-{referencia.institucion_destino.nombre_institucion_salud}",
            "institucion_dest_direccion": f"{referencia.institucion_destino.direccion.aldea.municipio.nombre_municipio}, {referencia.institucion_destino.direccion.aldea.municipio.departamento.nombre_departamento}" if  referencia.institucion_destino.direccion else "",
        })

        # fecha recepcion (solo si existe)
        if fecha_local_fecha_recepcion:
            referencia_data.update({
                "ref_fecha_recepcion_dia": fecha_local_fecha_recepcion.day,
                "ref_fecha_recepcion_mes": fecha_local_fecha_recepcion.month,
                "ref_fecha_recepcion_anio": fecha_local_fecha_recepcion.year,
                "ref_fecha_recepcion_hora": fecha_local_fecha_recepcion.strftime("%H:%M"),
            })
        else:
            referencia_data.update({
                "ref_fecha_recepcion_dia": "",
                "ref_fecha_recepcion_mes": "",
                "ref_fecha_recepcion_anio": "",
                "ref_fecha_recepcion_hora": "",
            })

        return referencia_data, paciente_data


    @staticmethod
    def generarDataFormatoRespuesta(id_respuesta):  # 0 recibidas 1 enviadas

        relaciones = [
            'referencia__paciente__sector__aldea__municipio__departamento',

            'referencia__institucion_origen',
            'referencia__institucion_origen__region_salud',
            'referencia__institucion_origen__nivel_complejidad_institucional',
            'referencia__institucion_origen__proveedor_salud',
            'referencia__institucion_origen__direccion__aldea__municipio__departamento',

            'referencia__institucion_destino',
            'referencia__institucion_destino__region_salud',
            'referencia__institucion_destino__nivel_complejidad_institucional',
            'referencia__institucion_destino__proveedor_salud',
            'referencia__institucion_destino__direccion__aldea__municipio__departamento',

            'area_seguimiento_area_atencion',
            'institucion_destino',
            'institucion_destino__nivel_complejidad_institucional',
            'institucion_destino__direccion__aldea__municipio__departamento',

            'seguimiento_referencia',
            'seguimiento_referencia__institucion_destino',
            'seguimiento_referencia__institucion_destino__nivel_complejidad_institucional',
            'seguimiento_referencia__institucion_destino__direccion__aldea__municipio__departamento',
            'seguimiento_referencia__especialidad_destino',

            'elaborada_por',
        ]

        #respuesta
        try:
            respuesta = (
                Respuesta.objects
                .select_related(*relaciones)
                .get(id=id_respuesta)
            )

        except Respuesta.DoesNotExist:
            log_warning(
                f"Respuesta {id_respuesta} no encontrada para formato",
                app=LogApp.REFERENCIAS
            )
            raise ValueError("La respuesta solicitada no existe.")

        except Respuesta.MultipleObjectsReturned:
            log_error(
                f"Múltiples respuestas encontradas con id {id_respuesta}",
                app=LogApp.REFERENCIAS
            )
            raise ValueError("Se encontraron múltiples respuestas, lo cual no debería ocurrir.")

        except Exception:
            log_error(
                f"Error obteniendo respuesta {id_respuesta}",
                app=LogApp.REFERENCIAS
            )
            raise
        
        #diagnostico
        try:
            diag_qs = (
                Respuesta_diagnostico.objects
                .filter(respuesta_id=id_respuesta, estado=True)
                .select_related('diagnostico')
                .annotate(
                    diag=Concat(
                        Trim('diagnostico__nombre_diagnostico'),
                        Case(
                            When(
                                detalle__isnull=False,
                                then=Concat(Value(" ("), Trim('detalle'), Value(")"))
                            ),
                            default=Value(""),
                            output_field=CharField()
                        ),
                        output_field=CharField()
                    )
                )
                .values_list('diag', flat=True)
                .order_by('id')
            )

            texto = " - ".join(diag_qs)

        except Exception:
            log_error(
                f"Error obteniendo diagnósticos respuesta {id_respuesta}",
                app=LogApp.REFERENCIAS
            )
            raise
        
        #fechas
        fecha_local_fecha_elaboracion = localtime(respuesta.fecha_elaboracion)
        fecha_local_fecha_recepcion = (
            localtime(respuesta.fecha_recepcion)
            if respuesta.fecha_recepcion else None
        )

        ref = respuesta.referencia
        pac = ref.paciente

        #paciente

        paciente_data = {
            "dni": formatear_dni(pac.dni),
            "expediente": formatear_expediente(pac.expediente_numero),
            "nombres": construir_nombre_dinamico(pac, ["primer_nombre", "segundo_nombre"]),
            "apellido1": pac.primer_apellido,
            "apellido2": pac.segundo_apellido,
            "telefono": pac.telefono,
            "sexo": pac.sexo,
            "fecha_nacimiento": pac.fecha_nacimiento,
            "edad_texto": calcular_edad_texto(pac.fecha_nacimiento),
            "departamento": pac.sector.aldea.municipio.departamento.nombre_departamento,
            "municipio": pac.sector.aldea.municipio.nombre_municipio,
            "direccion": pac.sector.nombre_sector,
        }

        respuesta_data = {
            "ref_id": ref.id,
            "ref_tipo": ref.tipo,
            "res_motivo": respuesta.motivo_id,
            "res_motivo_detalle": respuesta.motivo_detalle,
            "res_diagnosticos": texto,
            "res_atencion": respuesta.atencion_requerida,
            "res_atencion_descripcion": respuesta.get_atencion_requerida_display(),
            "res_fecha_elaboracion_dia": fecha_local_fecha_elaboracion.day,
            "res_fecha_elaboracion_mes": fecha_local_fecha_elaboracion.month,
            "res_fecha_elaboracion_anio": fecha_local_fecha_elaboracion.year,
            "res_fecha_elaboracion_hora": fecha_local_fecha_elaboracion.strftime("%H:%M"),
            "res_elaborado_por": respuesta.elaborada_por_id,
            "res_elaborado_descripcion": respuesta.elaborada_por.nombre_tipo_personal,
        }

        inst_or = ref.institucion_origen
        inst_dest = ref.institucion_destino

        respuesta_data.update({
            "institucion_or_nombre": f"{inst_or.nivel_complejidad_institucional.siglas}-{inst_or.nombre_institucion_salud}",
            "institucion_or_red": f"#{inst_or.region_salud.codigo}-{inst_or.region_salud.nombre_region_salud}",
            "institucion_or_proveedor_salud": inst_or.proveedor_salud.nombre_proveedor_salud,
            "institucion_or_proveedor_salud_id": inst_or.proveedor_salud.id,
            "institucion_or_nivel": inst_or.nivel_complejidad_institucional.siglas,
            "institucion_or_centralizado": inst_or.centralizado,
            "institucion_or_complejidad": inst_or.nivel_complejidad_institucional.nivel_complejidad,
            "institucion_or_complejidad_nombre": inst_or.nivel_complejidad_institucional.siglas,

            "institucion_resp_complejidad": inst_dest.nivel_complejidad_institucional.nivel_complejidad,
            "institucion_resp_complejidad_nombre": inst_dest.nivel_complejidad_institucional.detalle_nivel_complejidad,
            "institucion_resp_nombre": f"{inst_dest.nivel_complejidad_institucional.siglas}-{inst_dest.nombre_institucion_salud}",
            "institucion_resp_direccion": f"{inst_dest.direccion.aldea.municipio.nombre_municipio}, {inst_dest.direccion.aldea.municipio.departamento.nombre_departamento}",
            "institucion_resp_red": f"#{inst_dest.region_salud.codigo}-{inst_dest.region_salud.nombre_region_salud}",
            "institucion_resp_proveedor_salud_id": inst_dest.proveedor_salud.id,
            "institucion_resp_centralizado": inst_dest.centralizado,
            "institucion_resp_complejidad": inst_dest.nivel_complejidad_institucional.nivel_complejidad,
            "institucion_resp_complejidad_nombre": inst_dest.nivel_complejidad_institucional.siglas,
        })


            # Según el seguimiento mandar data extra
            # Caso 1: seguimiento por area_atencion (no se agrega institución)
            # Caso 2: seguimiento institucional (primer nivel, usar institucion_destino)
            # Caso 3: seguimiento deriva en nueva referencia (usar destino de seguimiento)


        if respuesta.area_seguimiento_area_atencion:
            tipo_seguimiento = 1
        elif respuesta.institucion_destino:
            tipo_seguimiento = 2
        elif respuesta.seguimiento_referencia:
            tipo_seguimiento = 3
        else:
            tipo_seguimiento = 0

        if tipo_seguimiento == 1:
            respuesta_data.update({
                "seguimiento_area": respuesta.area_seguimiento_area_atencion.nombre_area_atencion,
                "institucion_seg_direccion": f"{inst_or.direccion.aldea.municipio.nombre_municipio}, {inst_or.direccion.aldea.municipio.departamento.nombre_departamento}" if inst_or.direccion else "",
            })

        elif tipo_seguimiento == 2:
            inst = respuesta.institucion_destino
            respuesta_data.update({
                "institucion_seg_nombre": f"{inst.nivel_complejidad_institucional.siglas}-{inst.nombre_institucion_salud}",
                "institucion_seg_complejidad": inst.nivel_complejidad_institucional.nivel_complejidad,
                "institucion_seg_complejidad_nombre": inst.nivel_complejidad_institucional.siglas,
                "institucion_seg_direccion": f"{inst.direccion.aldea.municipio.nombre_municipio}, {inst.direccion.aldea.municipio.departamento.nombre_departamento}" if inst.direccion else "",
            })

        elif tipo_seguimiento == 3:
            seg_ref = respuesta.seguimiento_referencia
            inst = seg_ref.institucion_destino
            respuesta_data.update({
                "institucion_seg_nombre": f"{inst.nivel_complejidad_institucional.siglas}-{inst.nombre_institucion_salud}",
                "institucion_seg_complejidad": inst.nivel_complejidad_institucional.nivel_complejidad,
                "institucion_seg_complejidad_nombre": inst.nivel_complejidad_institucional.siglas,
                "institucion_seg_area_atencion": (
                    seg_ref.especialidad_destino.nombre_referencia_especialidad
                    if seg_ref.especialidad_destino else ""
                ),
                "institucion_seg_direccion": f"{inst.direccion.aldea.municipio.nombre_municipio}, {inst.direccion.aldea.municipio.departamento.nombre_departamento}" if inst.direccion else "",
            })

        respuesta_data["tipo_seguimiento"] = tipo_seguimiento

        return respuesta_data, paciente_data

