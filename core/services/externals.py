import pyodbc
from django.conf import settings
from django.db import connections
from core.constants.stored_procedures import SP_OBTENER_DISPENSACIONES_PACIENTE, SP_SIWI_PACIENTE_INSERTAR_ACTUALIZAR, SP_PACIENTE_SQLSERVER_SYNC


def sync_paciente_sqlserver(paciente_dict):
    """
    Llama al procedimiento almacenado PC_SIWI_PACIENTE_AGREGAR_ACTUALIZAR
    para insertar o actualizar un paciente en SQL Server usando pyodbc.
    """
    try:
        db = settings.DATABASES['BIT_LESP']
        conn_str = (
            f"DRIVER={{{db['OPTIONS']['driver']}}};"
            f"SERVER={db['HOST']},{db['PORT']};"
            f"DATABASE={db['NAME']};"
            f"UID={db['USER']};"
            f"PWD={db['PASSWORD']}"
        )
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()

        cursor.execute(f"""
            EXEC {SP_PACIENTE_SQLSERVER_SYNC} 
                @EXPEDIENTE=?,
                @APELLIDO_1_DEL_PACIENTE=?,
                @APELLIDO_2_DEL_PACIENTE=?,
                @NOMBRES_DEL_PACIENTE=?,
                @FECHA_DE_NACIMIENTO_DEL_P=?,
                @Sexo=?,
                @IDENTIDAD_DEL_PACIENTE=?,
                @NOMBRE_DEL_PADRE=?,
                @APELLIDO_DEL_PADRE=?,
                @IDENTIDAD_DEL_PADRE=?,
                @NOMBRE_DE_LA_MADRE=?,
                @APELLIDO_DE_LA_MADRE=?,
                @IDENTIDAD_DE_LA_MADRE=?,
                @NACIONALIDAD=?,
                @DIRECCION=?,
                @CIUDAD=?,
                @TELEFONO_DEL_PACIENTE=?,
                @ZONA_GEOGRAFICA=?,
                @OBSERVACIONES=?
        """, [
            paciente_dict["EXPEDIENTE"],
            paciente_dict["APELLIDO_1_DEL_PACIENTE"],
            paciente_dict["APELLIDO_2_DEL_PACIENTE"],
            paciente_dict["NOMBRES_DEL_PACIENTE"],
            paciente_dict["FECHA_DE_NACIMIENTO_DEL_P"],
            paciente_dict["Sexo"],
            paciente_dict["IDENTIDAD_DEL_PACIENTE"],
            paciente_dict["NOMBRE_DEL_PADRE"],
            paciente_dict["APELLIDO_DEL_PADRE"],
            paciente_dict["IDENTIDAD_DEL_PADRE"],
            paciente_dict["NOMBRE_DE_LA_MADRE"],
            paciente_dict["APELLIDO_DE_LA_MADRE"],
            paciente_dict["IDENTIDAD_DE_LA_MADRE"],
            paciente_dict["NACIONALIDAD"],
            paciente_dict["DIRECCION"],
            paciente_dict["CIUDAD"],
            paciente_dict["TELEFONO_DEL_PACIENTE"],
            paciente_dict["ZONA_GEOGRAFICA"],
            paciente_dict["OBSERVACIONES"]
        ])

        resultado = cursor.fetchone()
        cursor.close()
        conn.close()

        if not resultado:
            raise RuntimeError(
                f"SQL Server no devolvió resultado expediente={paciente_dict.get('EXPEDIENTE')}"
            )
        
        return resultado.resultado

    except Exception as e:
        raise RuntimeError(
            f"SQLSERVER_SYNC expediente={paciente_dict.get('EXPEDIENTE')} error={str(e)}"
        )

    

def sync_paciente_mysql(paciente_dict):
    try:
        with connections['salmi'].cursor() as cursor:
            # Ejecutar el procedimiento almacenado
            cursor.callproc(SP_SIWI_PACIENTE_INSERTAR_ACTUALIZAR, [
                paciente_dict["EXPEDIENTE"],
                paciente_dict["NOMBRES_DEL_PACIENTE"],
                paciente_dict["APELLIDO_1_DEL_PACIENTE"],
                paciente_dict["APELLIDO_2_DEL_PACIENTE"],
                'M' if paciente_dict["Sexo"] == 1 else 'F',
                paciente_dict["FECHA_DE_NACIMIENTO_DEL_P"],
                paciente_dict.get("IDENTIDAD_DEL_PACIENTE", "0"),
                paciente_dict.get("OCUPACION", "N"),
                paciente_dict.get("DIRECCION", "N"),
                paciente_dict.get("TELEFONO_DEL_PACIENTE", "0"),
                paciente_dict.get("TELEFONO_DEL_PACIENTE", "0"),
                paciente_dict.get("ESTADO_CIVIL", "N"),
                paciente_dict.get("NAC", "HN"),
                f"{paciente_dict.get('NOMBRE_DEL_PADRE', '')} {paciente_dict.get('APELLIDO_DEL_PADRE', '')}".strip(),
                f"{paciente_dict.get('NOMBRE_DE_LA_MADRE', '')} {paciente_dict.get('APELLIDO_DE_LA_MADRE', '')}".strip()
            ])

            # Si el SP retorna algo, lo leemos
            resultado = cursor.fetchone()
            if not resultado:
                raise RuntimeError(
                    f"MySQL no devolvió resultado expediente={paciente_dict.get('EXPEDIENTE')}"
                )
            
            return str(resultado[0])       
    
    except Exception as e:
        raise RuntimeError(
            f"Error al sincronizar MySQL expediente={paciente_dict.get('EXPEDIENTE')} detalle={str(e)}"
        )


def obtener_dispensacion_mysql(expediente, dni=0):
    try:
        with connections['salmi'].cursor() as cursor:
            cursor.callproc(SP_OBTENER_DISPENSACIONES_PACIENTE, [
                dni,
                expediente
            ])

            resultado = cursor.fetchall()

            return resultado or []

    except Exception as e:
        raise RuntimeError(
            f"Error al obtener dispensaciones expediente={expediente} dni={dni} detalle={str(e)}"
        )
    

