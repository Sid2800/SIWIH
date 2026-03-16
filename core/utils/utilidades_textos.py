
import re
import unicodedata


def formatear_nombre_completo(primer_nombre, segundo_nombre, primer_apellido, segundo_apellido):
    return " ".join(
        [p.strip() for p in [primer_nombre, segundo_nombre, primer_apellido, segundo_apellido] if p]
    )

    


def formatear_ubicacion_completo(departamento, municipio, sector):
    return ", ".join(filter(None, [departamento, municipio, sector]))


def formatear_dni(dni):
    """Formatea un DNI en el formato ####-####-#####"""
    if not dni:
        return ""
    else:
        if len(dni) == 13 and dni.isdigit():  # Verifica que tenga 13 dígitos
            return f"{dni[:4]}-{dni[4:8]}-{dni[8:]}"
        
    return dni 

def formatear_expediente(numero):
    """
    Convierte un número a un string de 6 dígitos, completando con ceros a la izquierda.
    
    :param numero: Número a formatear.
    :return: String de 7 dígitos.
    """
    return str(numero).zfill(6)


def generar_slug(text):
    # Normaliza para quitar acentos
    text = unicodedata.normalize('NFD', text)
    text = text.encode('ascii', 'ignore').decode('utf-8')

    # Convierte a minúsculas y quita espacios extras
    text = text.lower().strip()

    # Reemplaza espacios por guiones
    text = re.sub(r'\s+', '-', text)

    # Elimina caracteres no alfanuméricos excepto guiones
    text = re.sub(r'[^\w\-]', '', text)

    # Reemplaza múltiples guiones por uno solo
    text = re.sub(r'-{2,}', '-', text)

    return text


# une en un strig varios campos de obejto si tienen valor 
def construir_nombre_dinamico(obj, campos):
    return " ".join(
            filter(None, [getattr(obj, campo, "") for campo in campos])
        ).strip()