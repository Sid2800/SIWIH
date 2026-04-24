from django.db import models
from django.utils.timezone import localtime
from core.utils.utilidades_fechas import formatear_fecha_simple
from ubicacion.models import Sector
from django.contrib.auth.models import User
from servicio.models import Zona, Sala, ServiciosAux, Area_atencion, Unidad_clinica
from core.utils.utilidades_textos import construir_nombre_dinamico
from django.db import connections

TIPO_DEFUNCION = [
        (1, "Intrahospitalaria"),
        (2, "Extrahospitalaria"),
    ]

class Nacionalidad(models.Model):
    descripcion_nacionalidad = models.CharField(max_length=100, unique=True, verbose_name="Nacionalidad")
    descripcion_corta = models.CharField(max_length=5, null=True, blank=True)
    estado = models.BooleanField(default=1, verbose_name="Estado (activo/inactivo)")

    class Meta:
        verbose_name = "Nacionalidad"
        verbose_name_plural = "Nacionalidades"
        ordering = ["descripcion_nacionalidad",]

    def __str__(self):
        return self.descripcion_nacionalidad


class Estado_civil(models.Model):
    descripcion_estado_civil = models.CharField(max_length=50, unique=True, verbose_name="Estado Civil")
    estado = models.BooleanField(default=1, verbose_name="Estado (activo/inactivo)")

    class Meta:
        verbose_name = "Estado Civil"
        verbose_name_plural = "Estados Civiles"
        ordering = ["descripcion_estado_civil",]

    def __str__(self):
        return f"{self.descripcion_estado_civil}"


class Ocupacion(models.Model):
    descripcion_ocupacion = models.CharField(max_length=50, unique=True, verbose_name="Ocupacion")
    estado = models.BooleanField(default=1, verbose_name="Estado (activo/inactivo)")

    class Meta:
        verbose_name = "Ocupacion"
        verbose_name_plural = "Ocupaciones"
        ordering = ["descripcion_ocupacion",]

    def __str__(self):
        return f"{self.descripcion_ocupacion}"
    

class Etnia(models.Model):
    codigo = models.CharField(
        max_length=2,
        unique=True,
        verbose_name="Codigo Etnia"
    )

    descripcion_etnia = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Etnia"
    )

    estado = models.BooleanField(
        default=1,
        verbose_name="Estado (activo/inactivo)"
    )

    class Meta:
        verbose_name = "Etnia"
        verbose_name_plural = "Etnias"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.descripcion_etnia}"
    

class Padre(models.Model):
    dni = models.CharField(max_length=50, unique=True, verbose_name="Numero de identificacion", blank=True, null=True, db_index=True)
    nombre1 = models.CharField(verbose_name="primer nombre", max_length=100,blank=True,null=True )
    nombre2 = models.CharField(verbose_name="segundo nombre", max_length=100,blank=True,null=True)
    apellido1 = models.CharField(verbose_name="primer apelllido", max_length=100, blank=True,null=True)
    apellido2 = models.CharField(verbose_name="segundo apelllido", max_length=100, blank=True,null=True)
    direccion = models.ForeignKey(Sector, on_delete=models.PROTECT, verbose_name="Direccion", null=True, blank=True) 
    paciente_ref = models.ForeignKey("paciente.Paciente", related_name="Paciente_ref", verbose_name="paciente_ref", on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.CharField(
        verbose_name="Parentezco",
        max_length=2,
        choices=[
            ("01", "Padre"),
            ("02", "Madre"),
        ],
        default="02"
    )
    fecha_creado = models.DateTimeField(verbose_name="Creado", auto_now_add=True)
    fecha_modificado = models.DateTimeField(verbose_name="Editado", auto_now=True)

    class Meta:
        verbose_name = "Madre/Padre"
        verbose_name_plural = "Madre/Padre"
        ordering = ["fecha_modificado", "nombre1","nombre2"]

    def __str__(self):
        return f"{self.tipo} - {self.nombre1} - {self.apellido1}"
    

class Tipo(models.Model):
    descripcion_tipo = models.CharField(max_length=50, unique=True, verbose_name="Tipos")
    descripcion_corta = models.CharField(max_length=5, null=True, blank=True)
    
    estado = models.BooleanField(default=1, verbose_name="Estado (activo/inactivo)")

    class Meta:
        verbose_name = "Tipo"
        verbose_name_plural = "Tipos"
        ordering = ["descripcion_tipo",]

    def __str__(self):
        return f"{self.descripcion_tipo}"
    

class Clasificacion_diagnostico(models.Model):
    descripcion_clasificacion = models.CharField(max_length=50, unique=True, verbose_name="Tipos")
    estado = models.BooleanField(default=1, verbose_name="Estado (activo/inactivo)")

    class Meta:
        verbose_name = "Clasificacion_diagnostico"
        verbose_name_plural = "Clasificaciones"
        ordering = ["descripcion_clasificacion",]

    def __str__(self):
        return f"{self.descripcion_clasificacion}"
    

class Defuncion(models.Model):
    paciente = models.OneToOneField("Paciente", on_delete=models.CASCADE, related_name="defuncion")
    fecha_defuncion = models.DateField(verbose_name="Fecha de defunción")
    unidad_clinica = models.ForeignKey(Unidad_clinica,on_delete=models.PROTECT, null=True, blank=True)
    motivo = models.CharField(max_length=255, null=True, blank=True, verbose_name="Motivo del fallecimiento")
    fecha_entrega = models.DateField(null=True, blank=True, verbose_name="Fecha de entrega de cadaver")
    reponsable_nombre = models.CharField(max_length=40, null=True, blank=True, verbose_name="reponsable cadaver")
    reponsable_dni = models.CharField(max_length=40, null=True, blank=True, verbose_name="reponsable cadaver")
    registrado_por = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="Registrado por")
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")

    tipo_defuncion = models.PositiveSmallIntegerField(
        choices=TIPO_DEFUNCION,
        default=1
    )

    class Meta:
        verbose_name = "Defuncion"
        verbose_name_plural = "Defunciones"
        ordering = ["fecha_defuncion"]

    def __str__(self):
        return f"{self.paciente} - {self.fecha_defuncion}"



class ObitoFetal(models.Model):
    paciente = models.ForeignKey("Paciente", on_delete=models.PROTECT, related_name="obitos_fetales", verbose_name="Paciente (madre)")
    fecha_obito = models.DateField( verbose_name="Fecha de óbito fetal")
    unidad_clinica = models.ForeignKey(Unidad_clinica,on_delete=models.PROTECT, null=True, blank=True)
    motivo = models.CharField(max_length=255, null=True, blank=True, verbose_name="Motivo")
    responsable_dni = models.CharField(max_length=40, null=True, blank=True, verbose_name="DNI responsable")
    responsable_nombre = models.CharField(max_length=40, null=True, blank=True, verbose_name="Responsable")
    registrado_por = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="Registrado por")
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")
    estado = models.BooleanField(default=1, verbose_name="Estado (activo/inactivo)")
    tipo_defuncion = models.PositiveSmallIntegerField(
        choices=TIPO_DEFUNCION,
        default=1
    )

    class Meta:
        verbose_name = "Obito Fetal"
        verbose_name_plural = "Obitos Fetales"
        ordering = ["-fecha_obito"]

    def __str__(self):
        return f"{self.paciente} - {self.fecha_obito}"


class Paciente(models.Model):
    dni = models.CharField(max_length=50, unique=True, verbose_name="Numero de identificacion",blank=True, null=True, db_index=True)
    primer_nombre = models.CharField(verbose_name="Primer nombre", max_length=100)
    segundo_nombre = models.CharField(
        verbose_name="Segundo nombre", max_length=100,
        blank=True, null=True)
    primer_apellido = models.CharField(verbose_name="Primer apellido",max_length=100)
    segundo_apellido = models.CharField(
        verbose_name="Segundo apellido",max_length=100,
        blank=True, null=True)
    fecha_nacimiento = models.DateField(verbose_name="Fecha de nacimiento", db_index=True)
    telefono = models.CharField(
        verbose_name="Telefono",
        null=True,
        blank=True,
        max_length=12      
        )
    estado = models.CharField(
        verbose_name="Estado",
        max_length=1,
        choices=[("A", "Activo"), ("P", "Pasivo"), ("I", "Inactivo")],
        default="A",
        db_index=True
    )
    sexo = models.CharField(
        verbose_name="Sexo",
        max_length=1,
        choices=[("H", "Hombre"), ("M", "Mujer"), ("N", "No identificado")],
        default="M"
    )
    estado_civil = models.ForeignKey(
        Estado_civil,
        on_delete=models.PROTECT,
        null=False,
        default=2
    )
    ocupacion = models.ForeignKey(
        Ocupacion,
        on_delete=models.PROTECT,
        null=False,
        default=4
    )
    etnia = models.ForeignKey(
        Etnia,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Etnia"
    )
    madre = models.ForeignKey(
        Padre,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hijos_madre',
        verbose_name="Madre"
    )
    padre = models.ForeignKey(
        Padre,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hijos_padre',
        verbose_name="Padre"
    )
    tipo = models.ForeignKey(
        Tipo,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        related_name='paciente_tipos',
        verbose_name="Tipo Identificacion paciente",
        default=1
    )
    clasificacion = models.ForeignKey(
        Clasificacion_diagnostico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paciente_clasificacion',
        verbose_name="Clasificacion paciente"
    )
    nacionalidad = models.ForeignKey(
        Nacionalidad,
        on_delete=models.PROTECT,
        null=False,
        verbose_name="Nacionalidad",
        default=1
    )
    zona = models.ForeignKey(
        Zona,
        on_delete=models.PROTECT,
        null=False,
        verbose_name="Zona"
    )
    sai = models.BooleanField(default=False, verbose_name="PacienteSAI", db_index=True) 
    adolescente = models.BooleanField(default=False, verbose_name="PacienteAdolescente", db_index=True)
    fecha_sai = models.DateField(null=True, blank=True, verbose_name="FechaSAI")
    orden_gemelar = models.PositiveSmallIntegerField(verbose_name="Numero de gestacion", null=True, blank=True)
    observaciones = models.TextField(verbose_name="Observaciones", null=True,blank=True)
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE, verbose_name="Domicilio") 
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='pacientes_creados')
    fecha_modificado = models.DateTimeField(verbose_name="Editado", auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='pacientes_modificados')
    expediente_numero = models.CharField(max_length=20, blank=True, null=True, db_index=True)

    def get_ultima_visita(self, fecha=False ):
        ultima_atencion = self.atenciones.order_by('-fecha_atencion').first()
        ultimo_ingreso = self.pacientes_ingresados.filter(estado=1).order_by('-fecha_ingreso').first()

        fecha_ultima = None

        if ultima_atencion and ultimo_ingreso:
            # Compara las dos fechas
            if ultima_atencion.fecha_atencion > ultimo_ingreso.fecha_ingreso:
                fecha_ultima = ultima_atencion.fecha_atencion
            else:
                fecha_ultima = ultimo_ingreso.fecha_ingreso

        elif ultima_atencion:
            fecha_ultima = ultima_atencion.fecha_atencion
        elif ultimo_ingreso:
            fecha_ultima = ultimo_ingreso.fecha_ingreso

        if fecha_ultima:
            #convertir a hora local
            fecha_local = localtime(fecha_ultima)

            if fecha == True:
                return fecha_local
            else:
                return formatear_fecha_simple(fecha_local)
        return None

    def get_extranjeroPasaporte(self):
        tipo = self.tipo_id
        nacionalidad = self.nacionalidad_id

        if nacionalidad != 1:
            return True  # Es extranjero
        if nacionalidad == 1 and tipo == 2:
            return True  # Hondureño usando pasaporte (inválido)
        return False  # Hondureño con documento válido

    class Meta:
        indexes = [
            models.Index(fields=["estado", "sai", "adolescente"], name="idx_estado_sai_adol"),
        ]
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"
        ordering = ["fecha_modificado", "primer_nombre"]

    def __str__(self):
        campos = ("primer_nombre", "segundo_nombre", "primer_apellido")
        return f"{construir_nombre_dinamico(self,campos)}"
    

    