from ingreso.models import Ingreso
from django.utils import timezone
from core.utils.utilidades_textos import construir_nombre_dinamico, formatear_dni
from core.utils.utilidades_fechas import obtener_edad_con_indicador, calcular_edad_texto
from core.services.expediente_service import ExpedienteService
from core.services.servicio_service import ServicioService



class IngresoFormatosService:

    @staticmethod
    def construir_data_hoja_hospitalizacion(ingreso_id):
        try:
            ingreso_obj = Ingreso.objects.select_related(
                "acompaniante",
                "acompaniante__sector__aldea__municipio__departamento",
                "sala__servicio",
                "cama__sala__servicio",
                "paciente__padre",
                "paciente__madre",
                "paciente__etnia",
                "paciente__sector__aldea__municipio__departamento",
                "creado_por",
                "modificado_por",
                "zona",
            ).get(id=ingreso_id)

        except Ingreso.DoesNotExist:
            raise Exception("Ingreso no encontrado")
    
        # Helpers internos
        def _validar_extranjero_o_hondureno_con_pasaporte(tipo, nacionalidad):
                if not nacionalidad:
                    return False
                if nacionalidad != 1:
                    return True
                if nacionalidad == 1 and tipo == 2:
                    return True
                return False
    

        # Datos Usuario
        usuario_nick = (
            ingreso_obj.creado_por.username.upper()
            if ingreso_obj.creado_por else ""
        )

        usuario_nombre = (
            f"{ingreso_obj.creado_por.first_name} {ingreso_obj.creado_por.last_name}".strip().upper()
            if ingreso_obj.creado_por else ""
        )

        paciente = ingreso_obj.paciente

        if paciente:
            expediente_obj = ExpedienteService.obtener_expediente_activo_paciente(paciente.id)
            expediente = str(expediente_obj.numero).zfill(7) if expediente_obj else "0000000"

            tipo = paciente.tipo.id if paciente.tipo else ""
            nacionalidad = paciente.nacionalidad.id if paciente.nacionalidad else ""

            nombres = construir_nombre_dinamico(paciente, ["primer_nombre", "segundo_nombre"])
            apellido1= construir_nombre_dinamico(paciente, ["primer_apellido",])
            apellido2 = construir_nombre_dinamico(paciente, ["segundo_apellido",])
            

            dni = paciente.dni or ""
            fechaNac = paciente.fecha_nacimiento

            edad, edadT = obtener_edad_con_indicador(str(fechaNac)) if fechaNac else ("00", "")

            sexo = "1" if paciente.sexo == "H" else "2"

            estCivil = paciente.estado_civil.id if paciente.estado_civil else ""
            ocupacion = paciente.ocupacion.id if paciente.ocupacion else ""
            telefono_paciente = paciente.telefono or ""
            etnia = f"{paciente.etnia.descripcion_etnia} ({paciente.etnia.codigo})" if paciente.etnia else ""

            if paciente.sector:
                depto = paciente.sector.aldea.municipio.departamento.nombre_departamento
                muni = paciente.sector.aldea.municipio.nombre_municipio
                ubicacion = paciente.sector.nombre_sector
            else:
                depto, muni, ubicacion = "", "", ""

        else:
            expediente = "0000000"
            tipo = nacionalidad = nombres = apellidos = dni = ""
            fechaNac = None
            edad, edadT = "00", ""
            sexo = estCivil = ocupacion = telefono_paciente = ""
            depto = muni = ubicacion = ""


        # Acompaniante
        acompaniante = ingreso_obj.acompaniante

        if acompaniante:
            nombre_contacto = construir_nombre_dinamico(
                acompaniante,
                ["primer_nombre", "segundo_nombre", "primer_apellido", "segundo_apellido"],
            )
            telefono_contacto = acompaniante.telefono or ""

            if acompaniante.sector:
                direccion_contacto = (
                    f"{acompaniante.sector.aldea.municipio.departamento.nombre_departamento} "
                    f"{acompaniante.sector.aldea.municipio.nombre_municipio} "
                    f"{acompaniante.sector.nombre_sector}"
                )[:38].strip()
            else:
                direccion_contacto = ""
        else:
            nombre_contacto = telefono_contacto = direccion_contacto = ""

        # Padres
        nombrePadre = dniPadre = ""
        nombreMadre = dniMadre = ""

        if paciente and paciente.padre:
            if paciente.padre.paciente_ref:
                padre = paciente.padre.paciente_ref
                atrib = ["primer_nombre", "segundo_nombre", "primer_apellido", "segundo_apellido"]
            else:
                padre = paciente.padre
                atrib = ["nombre1", "nombre2", "apellido1", "apellido2"]

            nombrePadre = construir_nombre_dinamico(padre, atrib)
                        
            dniPadre = formatear_dni(padre.dni) if padre.dni else ""
        else:
            nombrePadre = ""
            dniPadre = ""

        if paciente and paciente.madre:
            if paciente.madre.paciente_ref:
                madre = paciente.madre.paciente_ref
                atrib = ["primer_nombre", "segundo_nombre", "primer_apellido", "segundo_apellido"]
            else:
                madre = paciente.madre
                atrib = ["nombre1", "nombre2", "apellido1", "apellido2"]

            nombreMadre = construir_nombre_dinamico(madre, atrib)
            dniMadre = formatear_dni(madre.dni) if madre.dni else ""
        else:
            nombreMadre = ""
            dniMadre = ""


        #ingreso
        zonaIngreso = ingreso_obj.zona.codigo if ingreso_obj.zona else ""
        if zonaIngreso == 4:
            zonaIngreso = 2

        sala = ingreso_obj.sala.nombre_sala if ingreso_obj.sala else ""

        servicio = (
            ingreso_obj.cama.sala.servicio.nombre_servicio if ingreso_obj.cama
            else ingreso_obj.sala.servicio.nombre_servicio if ingreso_obj.sala
            else ""
        )

        idservicio = (
            ingreso_obj.cama.sala.servicio_id if ingreso_obj.cama
            else ingreso_obj.sala.servicio_id if ingreso_obj.sala
            else ""
        )

        fechaIngreso = timezone.localtime(ingreso_obj.fecha_ingreso) if ingreso_obj.fecha_ingreso else None

        cama = str(ingreso_obj.cama.numero_cama) if ingreso_obj.cama else ""


        #Ingreso
        zonaIngreso = ingreso_obj.zona.codigo if ingreso_obj.zona else ""
        if zonaIngreso == 4:
            zonaIngreso = 2

        sala = ingreso_obj.sala.nombre_sala if ingreso_obj.sala else ""

        servicio = (
            ingreso_obj.cama.sala.servicio.nombre_servicio if ingreso_obj.cama
            else ingreso_obj.sala.servicio.nombre_servicio if ingreso_obj.sala
            else ""
        )

        idservicio = (
            ingreso_obj.cama.sala.servicio_id if ingreso_obj.cama
            else ingreso_obj.sala.servicio_id if ingreso_obj.sala
            else ""
        )

        fechaIngreso = timezone.localtime(ingreso_obj.fecha_ingreso) if ingreso_obj.fecha_ingreso else None

        cama = str(ingreso_obj.cama.numero_cama) if ingreso_obj.cama else ""

        #insitucion Agregada a posteriori para incluir la hija de referencia preciamente llenada
        institucion=ServicioService.obtener_institucion_heac_reporte()

        #Impresion
        return {
            "usuario": {
                "usuario_nick":usuario_nick,
                "usuario_nombre":usuario_nombre,
            },

            "institucion": institucion,

            "paciente": {
                "expediente": expediente,
                "tipo_identificacion": tipo,
                "nacionalidad_id": nacionalidad,
                "es_extranjero_o_pasaporte": _validar_extranjero_o_hondureno_con_pasaporte(tipo, nacionalidad),
                "nombres": nombres,
                "apellido1": apellido1,
                "apellido2": apellido2,
                "dni": dni,
                "fecha_nacimiento": fechaNac,
                "edad_texto": calcular_edad_texto(fechaNac),
                "edad_valor": edad,
                "edad_tipo": edadT,
                "sexo": sexo,
                "estado_civil_id": estCivil,
                "ocupacion_id": ocupacion,
                "etnia": etnia,
                "telefono": telefono_paciente,
                "departamento": depto,
                "municipio": muni,
                "direccion": ubicacion,
            },
            "padres": {
                "nombre_padre": nombrePadre,
                "dni_padre": dniPadre,
                "nombre_madre": nombreMadre,
                "dni_madre": dniMadre,
            },
            "acompaniante": {
                "nombre": nombre_contacto,
                "telefono": telefono_contacto,
                "direccion": direccion_contacto,
            },
            "ingreso": {
                "zona_codigo": zonaIngreso,
                "sala": sala,
                "servicio": servicio,
                "servicio_id": idservicio,
                "fecha_ingreso": fechaIngreso,
                "cama": cama,
            },
        }
