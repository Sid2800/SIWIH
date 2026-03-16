from django.db import models

class Area(models.Model):
   nombre_area = models.CharField(max_length=100, unique=True)

   class Meta:
      verbose_name = "Área"
      verbose_name_plural = "Áreas"
      ordering = ['nombre_area']

   def __str__(self):
      return self.nombre_area


class Departamento(models.Model):
   nombre_departamento = models.CharField(max_length=100, unique=True, db_index=True)
   created = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
   updated = models.DateTimeField(auto_now=True, verbose_name="Editado")

   class Meta:
      verbose_name = "Departamento"
      verbose_name_plural = "Departamentos"
      ordering = ['updated', 'nombre_departamento']

   def __str__(self):
      return self.nombre_departamento


class Municipio(models.Model):
   nombre_municipio = models.CharField(max_length=150, db_index=True)
   departamento = models.ForeignKey(Departamento, on_delete=models.CASCADE, related_name="municipios")
   created = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
   updated = models.DateTimeField(auto_now=True, verbose_name="Editado")


   class Meta:
      constraints = [
         models.UniqueConstraint(fields=['nombre_municipio', 'departamento'], name='unique_municipio_departamento')
      ]
      verbose_name = "Municipio"
      verbose_name_plural = "Municipios"
      ordering = ['updated', 'nombre_municipio']

   def __str__(self):
      return f"{self.nombre_municipio}-{self.departamento.nombre_departamento}"


class Aldea(models.Model):
   nombre_aldea = models.CharField(max_length=150, db_index=True)
   municipio = models.ForeignKey(Municipio, on_delete=models.CASCADE, related_name="aldeas")
   created = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
   updated = models.DateTimeField(auto_now=True, verbose_name="Editado")

   class Meta:
      verbose_name = "Aldea"
      verbose_name_plural = "Aldeas"
      ordering = ['updated', 'nombre_aldea']

   def __str__(self):
      return f"{self.nombre_aldea} - {self.municipio.nombre_municipio}"


class Sector(models.Model):
   nombre_sector = models.CharField(max_length=200, db_index=True)
   aldea = models.ForeignKey(Aldea, on_delete=models.CASCADE, related_name="sectores")
   area = models.ForeignKey(Area, on_delete=models.CASCADE)
   created = models.DateTimeField(auto_now_add=True)
   updated = models.DateTimeField(auto_now=True)

   class Meta:
      verbose_name = "Sector"
      verbose_name_plural = "Sectores"
      ordering = ['updated', 'nombre_sector']

   def __str__(self):
      return f"{self.nombre_sector} - {self.aldea.municipio.nombre_municipio}"
