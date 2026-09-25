from django import forms
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from core.constants.choices_constants import EstadoRegistro
from core.validators.image_validator import validar_imagen_basica
from expediente.models import ExpedienteUbicacion
from rrhh.models import Empleado

from .models import (
    AreaGestora,
    BajaDispositivo,
    CategoriaEquipo,
    ColorDispositivo,
    CriticidadDispositivo,
    Dispositivo,
    EstadoDispositivo,
    MarcaDispositivo,
    ModalidadProcedencia,
    ModeloDispositivo,
    Procedencia,
    TipoDispositivo,
    TipoProcedencia,
    TipoTecnologiaDispositivo,
    UbicacionFisica,
    normalizar_inventario_bienes_nacionales,
    normalizar_inventario_numero_ficha,
    normalizar_nombre_catalogo,
)


class CostoLempirasField(forms.DecimalField):
    """Costo escrito como se usa en Honduras: L 1,234.56

    Honduras separa los decimales con punto y los miles con coma, al reves que
    España. Como el proyecto usa LANGUAGE_CODE = "es", Django asume el formato
    español: muestra 1234,56 en pantalla pero solo acepta 1234.56 al escribir.
    El usuario ve una coma, escribe una coma y recibe "Introduzca un numero",
    de ahi la impresion de que el campo no admite decimales.

    Este campo acepta las dos convenciones y las normaliza antes de convertir.
    """

    #: Se aplica una sola regla: el ULTIMO separador que aparece es el decimal
    #: y los anteriores son de miles. La unica excepcion es un separador solo
    #: seguido de exactamente tres digitos ("1,500"), que siempre es de miles.
    #: Con dos decimales no existe un importe valido que se escriba asi.
    SEPARADORES = (".", ",")

    def to_python(self, valor):
        if isinstance(valor, str):
            valor = self._normalizar(valor)
        return super().to_python(valor)

    @classmethod
    def _normalizar(cls, texto):
        # Se quitan espacios normales y duros: Django usa el espacio duro como
        # separador de miles en español y puede llegar de un copiar y pegar.
        texto = texto.strip().replace(" ", "").replace("\xa0", "")

        if not texto:
            return texto

        # "L", "L." o "Lps" delante del importe es habitual al copiar de otro
        # documento. Se retira para no romper la conversion.
        sin_moneda = texto.lstrip("LlPpSs.").strip()
        if sin_moneda and sin_moneda[0].isdigit():
            texto = sin_moneda

        posiciones = [
            (texto.rfind(sep), sep) for sep in cls.SEPARADORES if sep in texto
        ]

        if not posiciones:
            return texto

        _, decimal = max(posiciones)
        decimales = texto.rsplit(decimal, 1)[1]

        # Un unico separador con tres digitos detras es de miles, no decimal.
        if len(posiciones) == 1 and len(decimales) == 3:
            return texto.replace(decimal, "")

        entero = texto.rsplit(decimal, 1)[0]
        for sep in cls.SEPARADORES:
            entero = entero.replace(sep, "")

        return f"{entero}.{decimales}"


TIPOS_IMAGEN_DISPOSITIVO = (
    ("GENERAL", "General"),
    ("INVENTARIO", "Inventario"),
    ("PLACA_SERIE", "Placa o serie"),
    ("ESTADO_FISICO", "Estado físico"),
    ("ACCESORIOS", "Accesorios"),
    ("OTRA", "Otra"),
)


class SelectRemoto(forms.Select):
    """Select cuyas opciones las trae Select2 del servidor, no el HTML.

    Django dibuja una <option> por cada elemento del queryset. Con un catalogo
    de cientos de procedencias eso son cientos de lineas en cada carga del
    formulario, y ademas inutiles: Select2 va a pedirlas por AJAX de todos
    modos. Aqui solo se dibuja la opcion vacia y la que este seleccionada, que
    es lo unico que el navegador necesita para mostrar el valor actual.

    El queryset del campo no se toca: sigue completo para que la validacion
    acepte cualquier procedencia activa que el usuario elija en el desplegable.
    """

    def optgroups(self, name, value, attrs=None):
        seleccionados = {str(v) for v in value if v not in (None, "")}
        grupos = []

        for grupo, opciones, indice in super().optgroups(name, value, attrs):
            visibles = [
                opcion
                for opcion in opciones
                if opcion["value"] in ("", None)
                or str(opcion["value"]) in seleccionados
            ]
            if visibles:
                grupos.append((grupo, visibles, indice))

        return grupos


# Personaliza la etiqueta visible del select de empleados.
# Select2 usa este texto cuando ya hay un responsable seleccionado.
class EmpleadoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, empleado):
        return f"{empleado.dni} - {empleado.nombre_completo}"


class IteradorUbicaciones(forms.models.ModelChoiceIterator):
    """Separa el catalogo de ubicaciones en clinicas y no clinicas.

    Son cuarenta y tantas opciones de dos naturalezas distintas. En una lista
    corrida hay que leerlas todas para encontrar la propia; agrupadas, el
    usuario salta directo a su mitad. El tipo ya viene en la fila, asi que no
    hace falta consultar nada mas para armar los grupos.
    """

    def __iter__(self):
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)

        clinicas = []
        no_clinicas = []

        for ubicacion in self.queryset:
            destino = (
                clinicas
                if ubicacion.tipo == ExpedienteUbicacion.TIPO_CLINICA
                else no_clinicas
            )
            destino.append(self.choice(ubicacion))

        if clinicas:
            yield ("Áreas clínicas", clinicas)

        if no_clinicas:
            yield ("Unidades no clínicas", no_clinicas)


class UbicacionChoiceField(forms.ModelChoiceField):
    iterator = IteradorUbicaciones

    def label_from_instance(self, ubicacion):
        # El catalogo antepone "[CLÍNICA]" a su nombre. Dentro de un grupo que
        # ya se llama asi, el prefijo solo alarga cada linea.
        texto = str(ubicacion)
        return texto.split("] ", 1)[-1] if texto.startswith("[") else texto


class BajaDispositivoForm(forms.ModelForm):
    # La fotografia firmada no pertenece a la base principal; el formulario la
    # valida para que la vista pueda enviarla a SIWIH Images antes de confirmar.
    ficha_firmada = forms.ImageField(
        required=True,
        validators=[validar_imagen_basica],
        label="Ficha firmada",
        widget=forms.FileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "id": "ficha_firmada_dispositivo",
                "hidden": True,
            }
        ),
    )

    class Meta:
        model = BajaDispositivo
        fields = [
            "habitacion_estancia",
            "motivo",
        ]
        widgets = {
            "habitacion_estancia": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "habitacion_estancia_baja",
                    "maxlength": 100,
                }
            ),
            "motivo": forms.Textarea(
                attrs={
                    "class": "formularioCampo-text no-resize",
                    "id": "motivo_baja_dispositivo",
                    "rows": 4,
                }
            ),
        }

    def __init__(self, *args, requiere_ficha=True, **kwargs):
        super().__init__(*args, **kwargs)
        # La previsualizacion PDF usa los textos, pero se genera antes de que
        # exista la fotografia firmada.
        self.fields["ficha_firmada"].required = requiere_ficha

        # El input real va oculto porque la interfaz es la zona de arrastre.
        # Un control required + hidden no se puede enfocar, asi que el
        # navegador cancela el envio sin poder mostrar el mensaje y el boton
        # parece muerto. La obligatoriedad se mantiene en el servidor y
        # tramiteBajaEquipo.js avisa antes de enviar.
        self.fields["ficha_firmada"].widget.use_required_attribute = (
            lambda initial: False
        )

    def clean_motivo(self):
        motivo = (self.cleaned_data.get("motivo") or "").strip()
        if not motivo:
            raise forms.ValidationError("Debe ingresar el motivo de baja.")
        return motivo

    def clean_habitacion_estancia(self):
        return (
            self.cleaned_data.get("habitacion_estancia") or ""
        ).strip()

    def clean_ficha_firmada(self):
        archivo = self.cleaned_data.get("ficha_firmada")
        if not archivo:
            return archivo

        if (
            archivo.content_type != "image/webp"
            or not archivo.name.lower().endswith(".webp")
        ):
            raise forms.ValidationError(
                "La ficha debe prepararse en formato WebP antes de guardarse."
            )
        return archivo


class ImagenDispositivoForm(forms.Form):
    # Las imágenes viven en SIWIH Images. Este formulario solo valida el
    # contrato HTTP y limita la selección a categorías que aún no existen.
    tipo_imagen = forms.ChoiceField(
        choices=TIPOS_IMAGEN_DISPOSITIVO,
        label="Tipo de fotografía",
        widget=forms.Select(
            attrs={
                "class": "formularioCampo-select",
                "id": "tipo_imagen_dispositivo",
            }
        ),
    )
    archivo = forms.ImageField(
        validators=[validar_imagen_basica],
        widget=forms.FileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "id": "imagen_archivo_dispositivo",
                "hidden": True,
            }
        ),
    )

    def __init__(self, *args, tipos_ocupados=None, **kwargs):
        super().__init__(*args, **kwargs)
        tipos_ocupados = set(tipos_ocupados or [])
        disponibles = [
            opcion
            for opcion in TIPOS_IMAGEN_DISPOSITIVO
            if opcion[0] not in tipos_ocupados
        ]

        # SIWIH Images exige GENERAL como primera fotografía de un equipo.
        if not tipos_ocupados:
            disponibles = [
                opcion for opcion in disponibles if opcion[0] == "GENERAL"
            ]

        self.fields["tipo_imagen"].choices = disponibles

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        if (
            archivo.content_type != "image/webp"
            or not archivo.name.lower().endswith(".webp")
        ):
            raise forms.ValidationError(
                "La fotografía debe convertirse a formato WebP antes de guardarse."
            )
        return archivo


class DispositivoCreateForm(forms.ModelForm):
    # Este mismo formulario se reutiliza para registrar y editar equipos.
    # Ademas de campos de Dispositivo, maneja la asignacion inicial/actual.
    FRECUENCIA_CHOICES = [
        (1, "Mensual"),
        (3, "Trimestral"),
        (6, "Semestral"),
        (12, "Anual"),
    ]
    # Duraciones que aparecen en los contratos reales. "Otra" deja escribir el
    # vencimiento a mano para los casos que no encajan en meses redondos.
    GARANTIA_CHOICES = [
        ("", "Sin garantía"),
        (6, "6 meses"),
        (12, "1 año"),
        (24, "2 años"),
        (36, "3 años"),
        (60, "5 años"),
    ]

    ubicacion = UbicacionChoiceField(
        queryset=ExpedienteUbicacion.objects.none(),
        label="Unidad o área",
        widget=forms.Select(
            attrs={
                "class": "formularioCampo-select",
                "id": "ubicacion_dispositivo",
            }
        ),
    )
    # Texto libre con sugerencias: la zona se escribe la primera vez y queda
    # en el catalogo con su identificador, asi la siguiente vez se elige de la
    # lista en lugar de volver a teclearla.
    ubicacion_fisica = forms.CharField(
        required=False,
        max_length=120,
        label="Ubicación física",
        widget=forms.TextInput(
            attrs={
                "class": "formularioCampo-text",
                "id": "ubicacion_fisica_dispositivo",
                "list": "ubicaciones_fisicas_equipos",
                "placeholder": "Ej. SALA 3 - CAMA 12",
                "autocomplete": "off",
            }
        ),
    )
    responsable = EmpleadoChoiceField(
        queryset=Empleado.objects.none(),
        label="Empleado a cargo",
        widget=forms.Select(
            attrs={
                "class": "formularioCampo-select",
                "id": "responsable_dispositivo",
                "data-placeholder": "Buscar por DNI o nombre",
            }
        ),
    )
    frecuencia_mantenimiento_meses = forms.TypedChoiceField(
        choices=[("", "Sin frecuencia definida"), *FRECUENCIA_CHOICES],
        coerce=int,
        empty_value=None,
        required=False,
        label="Frecuencia de mantenimiento",
        widget=forms.Select(
            attrs={
                "class": "formularioCampo-select",
                "id": "frecuencia_dispositivo",
            }
        ),
    )
    # La duracion se elige de una lista y el vencimiento lo calcula el modelo.
    # Antes se pedia la fecha final y quien registraba tenia que contar anios
    # de cabeza desde la factura, que es justo donde se equivocaba.
    garantia_meses = forms.TypedChoiceField(
        choices=GARANTIA_CHOICES,
        coerce=int,
        empty_value=None,
        required=False,
        label="Duración de la garantía",
        widget=forms.Select(
            attrs={
                "class": "formularioCampo-select",
                "id": "garantia_meses_dispositivo",
            }
        ),
    )
    # Se declara aparte para aceptar el importe escrito a la hondureña. Va como
    # texto y no como <input type="number">: ese control depende del idioma del
    # navegador y, con la configuracion en español, llega a rechazar el punto
    # decimal segun el equipo desde el que se registre. inputmode="decimal"
    # conserva el teclado numerico en telefono y tablet.
    costo_adquisicion = CostoLempirasField(
        required=False,
        max_digits=12,
        decimal_places=2,
        min_value=0,
        label="Costo de adquisición",
        widget=forms.TextInput(
            attrs={
                "class": "formularioCampo-text",
                "id": "costo_dispositivo",
                "inputmode": "decimal",
                "placeholder": "Ej. 1,234.56",
            }
        ),
    )
    # La imagen vive en SIWIH Images, por eso es un campo auxiliar y no forma
    # parte del modelo Dispositivo de la base principal.
    foto_general = forms.ImageField(
        required=False,
        validators=[validar_imagen_basica],
        widget=forms.FileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "id": "foto_general_dispositivo",
                "hidden": True,
            }
        ),
    )

    class Meta:
        model = Dispositivo
        fields = [
            "tipo",
            "tipo_tecnologia",
            "marca",
            "modelo",
            "colores",
            "area_gestora",
            "modalidad_procedencia",
            "procedencia",
            "numero_referencia",
            "numero_serie",
            "inventario_bienes_nacionales",
            "inventario_numero_ficha",
            "estado",
            "criticidad",
            "frecuencia_mantenimiento_meses",
            "vida_util_anios",
            "fecha_instalacion",
            "fecha_inicio_garantia",
            "garantia_meses",
            "fecha_fin_garantia",
            "costo_adquisicion",
            "observaciones",
        ]
        widgets = {
            "tipo": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "tipo_dispositivo",
                }
            ),
            "tipo_tecnologia": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "tipo_tecnologia_dispositivo",
                }
            ),
            "marca": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "marca_dispositivo",
                }
            ),
            "modelo": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "modelo_dispositivo",
                }
            ),
            "area_gestora": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "area_gestora_dispositivo",
                }
            ),
            "modalidad_procedencia": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "modalidad_procedencia_dispositivo",
                }
            ),
            # SelectRemoto en lugar de Select: las opciones las trae Select2 del
            # servidor y no hace falta incrustar el catalogo entero en el HTML.
            "procedencia": SelectRemoto(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "procedencia_dispositivo",
                }
            ),
            "numero_referencia": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "numero_referencia_dispositivo",
                    "placeholder": "Opcional",
                }
            ),
            # Casillas y no un multiple nativo: en un select multiple hay que
            # saber que se marca con Ctrl, y en tablet no hay Ctrl.
            "colores": forms.CheckboxSelectMultiple(
                attrs={
                    "class": "equipos-registro__casillas",
                    "id": "colores_dispositivo",
                }
            ),
            "numero_serie": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "serie_dispositivo",
                    "placeholder": "Opcional",
                }
            ),
            "inventario_bienes_nacionales": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "inventario_bienes_nacionales",
                    "placeholder": "Opcional",
                }
            ),
            # El campo del modelo sigue llamandose inventario_numero_ficha; solo
            # cambia como se presenta. Renombrarlo obligaria a una migracion sin
            # ninguna ganancia en la base.
            "inventario_numero_ficha": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "inventario_numero_ficha",
                    "placeholder": "212300",
                    "inputmode": "numeric",
                    "maxlength": "15",
                }
            ),
            "estado": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "estado_dispositivo",
                }
            ),
            "criticidad": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "criticidad_dispositivo",
                }
            ),
            "fecha_instalacion": forms.DateInput(
                attrs={
                    "class": "formularioCampo-date",
                    "id": "instalacion_dispositivo",
                    "type": "date",
                },
                format="%Y-%m-%d",
            ),
            "fecha_inicio_garantia": forms.DateInput(
                attrs={
                    "class": "formularioCampo-date",
                    "id": "inicio_garantia_dispositivo",
                    "type": "date",
                },
                format="%Y-%m-%d",
            ),
            # Solo se escribe cuando el contrato da una fecha suelta que no
            # cuadra con meses redondos. Con inicio y duracion lo calcula el
            # modelo y el campo se muestra de solo lectura.
            "fecha_fin_garantia": forms.DateInput(
                attrs={
                    "class": "formularioCampo-date",
                    "id": "garantia_dispositivo",
                    "type": "date",
                },
                format="%Y-%m-%d",
            ),
            "vida_util_anios": forms.NumberInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "vida_util_dispositivo",
                    "min": "1",
                    "max": "60",
                    "inputmode": "numeric",
                    "placeholder": "Opcional",
                }
            ),
            # El widget lo define CostoLempirasField mas abajo; aqui no se
            # declara para no pisarlo.
            "observaciones": forms.Textarea(
                attrs={
                    "class": "formularioCampo-text no-resize",
                    "id": "observaciones_dispositivo",
                    "rows": 4,
                    "placeholder": "Ingrese observaciones",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        # En edicion la vista envia asignacion_actual para precargar ubicacion
        # y responsable. En registro ese valor llega vacio.
        self.asignacion_actual = kwargs.pop("asignacion_actual", None)
        formulario_vinculado = (
            (args and args[0] is not None)
            or kwargs.get("data") is not None
            or kwargs.get("files") is not None
        )

        if self.asignacion_actual and not formulario_vinculado:
            initial = kwargs.get("initial", {}).copy()
            initial.setdefault("ubicacion", self.asignacion_actual.ubicacion_id)
            initial.setdefault("responsable", self.asignacion_actual.responsable_id)

            if self.asignacion_actual.ubicacion_fisica_id:
                initial.setdefault(
                    "ubicacion_fisica",
                    self.asignacion_actual.ubicacion_fisica.nombre,
                )

            kwargs["initial"] = initial

        super().__init__(*args, **kwargs)

        # F/ se muestra como prefijo fijo en el HTML; el usuario solo edita
        # los digitos. Al guardar, el normalizador vuelve a agregarlo.
        if not self.is_bound:
            ficha = str(self.initial.get("inventario_numero_ficha") or "").strip()
            if ficha.upper().startswith("F/"):
                self.initial["inventario_numero_ficha"] = ficha[2:].strip()

        # Los catalogos inactivos no se muestran para nuevos registros, pero si
        # el equipo ya usa uno, se conserva en la edicion para no romper historico.
        filtro_tipo = Q(activo=True)
        filtro_marca = Q(activo=True)
        filtro_modelo = Q(activo=True)
        filtro_area_gestora = Q(activo=True)
        filtro_color = Q(activo=True)
        filtro_procedencia = Q(activo=True)

        if self.instance and self.instance.pk:
            if self.instance.tipo_id:
                filtro_tipo |= Q(pk=self.instance.tipo_id)
            if self.instance.marca_id:
                filtro_marca |= Q(pk=self.instance.marca_id)
            if self.instance.modelo_id:
                filtro_modelo |= Q(pk=self.instance.modelo_id)
            if self.instance.area_gestora_id:
                filtro_area_gestora |= Q(pk=self.instance.area_gestora_id)
            # Un color desactivado despues del registro sigue apareciendo en la
            # edicion del equipo que lo usa, para no borrarlo sin querer.
            colores_en_uso = list(
                self.instance.colores.values_list("pk", flat=True)
            )
            if colores_en_uso:
                filtro_color |= Q(pk__in=colores_en_uso)
            if self.instance.procedencia_id:
                filtro_procedencia |= Q(pk=self.instance.procedencia_id)

        # El tipo tambien se busca por AJAX: el catalogo pasa del centenar de
        # entradas y volcarlas en el HTML alarga cada carga sin necesidad.
        self.fields["tipo"].queryset = TipoDispositivo.objects.filter(filtro_tipo)
        self.fields["tipo"].empty_label = "Seleccione el tipo de equipo"
        self.fields["tipo"].widget.attrs["data-url-tipos"] = reverse(
            "buscar_tipos_equipos"
        )

        # Marca y modelo se cargan por AJAX, asi que el HTML solo necesita
        # contener la opcion ya elegida. Cargar los catalogos completos serian
        # cientos de <option> inutiles en cada carga de pagina.
        self.fields["marca"].queryset = MarcaDispositivo.objects.filter(filtro_marca)
        self.fields["marca"].empty_label = "Sin especificar"

        # El modelo depende de la marca: su queryset se limita a los modelos de
        # la marca en juego. Si llega un modelo de otra marca, queda fuera del
        # queryset y Django lo rechaza. Eso cubre a la vez las dos reglas:
        # rechazar la combinacion invalida y no conservar un modelo que ya no
        # corresponde tras cambiar de marca.
        marca_en_juego = self._resolver_marca_en_juego()

        if marca_en_juego:
            self.fields["modelo"].queryset = ModeloDispositivo.objects.filter(
                filtro_modelo, marca_id=marca_en_juego
            ).select_related("marca")
        else:
            self.fields["modelo"].queryset = ModeloDispositivo.objects.none()

        self.fields["modelo"].empty_label = "INDEFINIDO"
        # Sin esto el rechazo saldria como "Escoja una opcion valida", que no
        # explica que el problema es la pareja marca-modelo.
        self.fields["modelo"].error_messages["invalid_choice"] = (
            "El modelo seleccionado no pertenece a la marca elegida."
        )
        self.fields["modelo"].widget.attrs["data-url-modelos"] = reverse(
            "buscar_modelos_equipos"
        )
        self.fields["marca"].widget.attrs["data-url-marcas"] = reverse(
            "buscar_marcas_equipos"
        )

        if not marca_en_juego:
            # Sin marca no hay nada que elegir; el navegador tambien lo bloquea,
            # pero el atributo deja el estado explicito en el HTML.
            self.fields["modelo"].widget.attrs["disabled"] = "disabled"
        self.fields["area_gestora"].queryset = AreaGestora.objects.filter(
            filtro_area_gestora
        ).exclude(nombre="INDEFINIDO")
        self.fields["area_gestora"].empty_label = "Seleccione el area gestora"
        self.fields["procedencia"].queryset = Procedencia.objects.filter(
            filtro_procedencia
        )
        self.fields["procedencia"].empty_label = "Seleccione la procedencia"
        self.fields["procedencia"].widget.attrs["data-url-procedencias"] = reverse(
            "buscar_procedencias_equipos"
        )
        self.fields["modalidad_procedencia"].choices = [
            ("", "Seleccione la modalidad"),
            *ModalidadProcedencia.choices,
        ]
        self.fields["tipo_tecnologia"].choices = [
            ("", "Seleccione el tipo de tecnología"),
            *TipoTecnologiaDispositivo.choices,
        ]
        # Sin garantia se expresa dejando los tres campos vacios. Y no se
        # limita el calendario: se registran equipos instalados hace anios,
        # con garantia ya vencida, y saber cuando vencio sigue siendo util.
        self.fields["fecha_fin_garantia"].required = False

        # INDEFINIDO queda fuera: con una lista de colores, "no se sabe" se
        # expresa no marcando ninguno.
        self.fields["colores"].required = False
        self.fields["colores"].queryset = ColorDispositivo.objects.filter(
            filtro_color
        ).exclude(nombre="INDEFINIDO")
        self.fields["estado"].choices = [
            (EstadoDispositivo.OPERATIVO, EstadoDispositivo.OPERATIVO.label),
            (
                EstadoDispositivo.EN_MANTENIMIENTO,
                EstadoDispositivo.EN_MANTENIMIENTO.label,
            ),
            (
                EstadoDispositivo.FUERA_DE_SERVICIO,
                EstadoDispositivo.FUERA_DE_SERVICIO.label,
            ),
            (
                EstadoDispositivo.REPUESTO_PENDIENTE,
                EstadoDispositivo.REPUESTO_PENDIENTE.label,
            ),
        ]
        self.fields["criticidad"].choices = [
            *CriticidadDispositivo.choices,
        ]
        # El catalogo de ubicaciones es compartido: si una fila se desactiva,
        # la que ya usa el equipo se conserva para poder editarlo igual.
        filtro_ubicacion = Q(estado=True)

        if self.asignacion_actual and self.asignacion_actual.ubicacion_id:
            filtro_ubicacion |= Q(pk=self.asignacion_actual.ubicacion_id)

        self.fields["ubicacion"].queryset = (
            ExpedienteUbicacion.objects
            .filter(filtro_ubicacion)
            .select_related(
                "unidad_clinica__area_atencion__servicio",
                "unidad_clinica__sala",
                "unidad_clinica__servicio_aux",
                "unidad_clinica__establecimiento_ext",
                "unidad_no_clinica",
            )
            .order_by("tipo", "id")
        )

        responsable_id = None
        if self.is_bound:
            responsable_id = self.data.get(self.add_prefix("responsable"))
        else:
            responsable_id = self.initial.get("responsable")

        # Para no cargar miles de empleados en el HTML, el select inicia vacio.
        # Select2 consulta buscar_empleados() por AJAX y aqui solo se acepta el
        # empleado seleccionado cuando el formulario se envia.
        if responsable_id and str(responsable_id).isdigit():
            filtro_responsable = Q(pk=responsable_id)

            if self.is_bound:
                filtro_responsable &= Q(estado=EstadoRegistro.ACTIVO)

            self.fields["responsable"].queryset = Empleado.objects.filter(
                filtro_responsable
            )

        self.fields["ubicacion"].empty_label = "Seleccione la unidad o área"
        self.fields["responsable"].empty_label = "Buscar empleado a cargo"
        # El navegador la usa como lista de sugerencias del campo de zona.
        self.ubicaciones_fisicas = UbicacionFisica.objects.filter(
            activo=True
        ).values_list("nombre", flat=True)

    def _resolver_marca_en_juego(self):
        """Marca vigente para acotar los modelos disponibles.

        En un envio manda lo que llega en el POST, porque el usuario pudo haber
        cambiado de marca. Al abrir la edicion, la del equipo guardado.
        """
        if self.is_bound:
            valor = self.data.get(self.add_prefix("marca"))
            return int(valor) if str(valor or "").isdigit() else None

        if self.instance and self.instance.pk and self.instance.marca_id:
            return self.instance.marca_id

        valor = self.initial.get("marca")
        return int(valor) if str(valor or "").isdigit() else None

    def clean_ubicacion_fisica(self):
        """Convierte lo escrito en una fila del catalogo de zonas.

        El campo se teclea, pero no se guarda como texto: se busca la zona por
        nombre normalizado y, si no existe, se crea. Asi "sala 3" y "SALA 3"
        acaban siendo la misma fila y el siguiente registro la elige de la
        lista de sugerencias en lugar de volver a escribirla.
        """
        nombre = normalizar_nombre_catalogo(
            self.cleaned_data.get("ubicacion_fisica")
        )

        if not nombre:
            return None

        zona, _ = UbicacionFisica.objects.get_or_create(
            nombre=nombre,
            defaults={"activo": True},
        )

        if not zona.activo:
            # Reutilizar una zona desactivada es mas sano que crear un
            # duplicado: el nombre es unico y ya existe.
            zona.activo = True
            zona.save(update_fields=["activo"])

        return zona

    def clean_numero_serie(self):
        # Una cadena vacia se guarda como NULL para permitir varios equipos sin serie.
        return (self.cleaned_data.get("numero_serie") or "").strip() or None

    def clean_foto_general(self):
        # Los equipos nuevos requieren una foto GENERAL. En edicion no se exige
        # porque las imagenes existentes se administran en SIWIH Images.
        archivo = self.cleaned_data.get("foto_general")

        if not self.instance.pk and not archivo:
            raise forms.ValidationError(
                "Debe agregar una foto general del equipo."
            )

        if archivo and not archivo.name.lower().endswith(".webp"):
            raise forms.ValidationError(
                "La foto debe convertirse a formato WebP antes de guardarse."
            )

        return archivo

    def clean_inventario_bienes_nacionales(self):
        return normalizar_inventario_bienes_nacionales(
            self.cleaned_data.get("inventario_bienes_nacionales")
        )

    def clean_inventario_numero_ficha(self):
        return normalizar_inventario_numero_ficha(
            self.cleaned_data.get("inventario_numero_ficha")
        )

    def clean(self):
        """Revisa la garantia como conjunto, no campo por campo.

        Los tres campos solo tienen sentido juntos: la duracion necesita un
        inicio para poder contarse, y el vencimiento se escribe a mano unica-
        mente cuando no hay duracion que lo calcule. El modelo hace la cuenta
        al guardar; aqui se avisa antes para que el usuario lo corrija.
        """
        cleaned_data = super().clean()
        inicio = cleaned_data.get("fecha_inicio_garantia")
        meses = cleaned_data.get("garantia_meses")
        fin = cleaned_data.get("fecha_fin_garantia")

        if meses and not inicio:
            self.add_error(
                "fecha_inicio_garantia",
                "Indique desde cuándo corre la garantía para calcular su "
                "vencimiento.",
            )
        elif inicio and not meses and not fin:
            self.add_error(
                "fecha_fin_garantia",
                "Elija una duración o escriba la fecha de vencimiento.",
            )

        if inicio and fin and fin < inicio:
            self.add_error(
                "fecha_fin_garantia",
                "El vencimiento no puede ser anterior al inicio de la garantía.",
            )

        return cleaned_data


class ProcedenciaCatalogoForm(forms.ModelForm):
    """Alta y edición de personas o empresas que originan equipos."""

    class Meta:
        model = Procedencia
        fields = [
            "nombre", "tipo", "rtn", "telefono", "telefono_alterno",
            "contacto", "correo",
        ]
        labels = {
            "rtn": "RTN",
            "telefono": "Teléfono",
            "telefono_alterno": "Teléfono alterno",
            # "Contacto" a secas se leia como un dato de contacto cualquiera y
            # se rellenaba con un numero. El nombre completo despeja la duda.
            "contacto": "Persona de contacto",
        }
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "nombre_procedencia_catalogo",
                    "placeholder": "Nombre de la empresa o persona",
                    "maxlength": 150,
                }
            ),
            "tipo": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "tipo_procedencia_catalogo",
                }
            ),
            "rtn": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "rtn_procedencia_catalogo",
                    "placeholder": "Opcional",
                    "maxlength": 20,
                }
            ),
            "telefono": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "telefono_procedencia_catalogo",
                    "placeholder": "Opcional",
                    "maxlength": 30,
                }
            ),
            "telefono_alterno": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "telefono_alterno_procedencia_catalogo",
                    "placeholder": "Opcional",
                    "maxlength": 30,
                }
            ),
            "contacto": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "contacto_procedencia_catalogo",
                    "placeholder": "Opcional",
                    "maxlength": 150,
                }
            ),
            "correo": forms.EmailInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "correo_procedencia_catalogo",
                    "placeholder": "Opcional",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].choices = [
            ("", "Seleccione el tipo"),
            *TipoProcedencia.choices,
        ]

    def clean_nombre(self):
        nombre = normalizar_nombre_catalogo(self.cleaned_data.get("nombre"))

        if not nombre:
            raise forms.ValidationError("Debe ingresar la procedencia.")

        duplicada = Procedencia.objects.filter(nombre=nombre).exclude(
            pk=self.instance.pk
        )
        if duplicada.exists():
            raise forms.ValidationError(
                "Ya existe una procedencia con ese nombre."
            )

        return nombre

    def clean_rtn(self):
        rtn = (self.cleaned_data.get("rtn") or "").strip() or None

        if rtn is not None:
            duplicada = Procedencia.objects.filter(rtn=rtn).exclude(
                pk=self.instance.pk
            )
            if duplicada.exists():
                raise forms.ValidationError(
                    "Ya existe una procedencia con este RTN."
                )

        return rtn


class MarcaCatalogoForm(forms.ModelForm):
    """Alta de marcas desde la vista de catalogo.

    Las marcas no se crean desde el formulario de equipos: alli solo se eligen.
    Concentrar el alta en un solo sitio evita que un error de tecleo genere
    marcas duplicadas mientras alguien registra un aparato con prisa.
    """

    class Meta:
        model = MarcaDispositivo
        fields = ["nombre", "descripcion"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "nombre_marca_catalogo",
                    "placeholder": "Ingrese Marca",
                    "maxlength": 100,
                }
            ),
            "descripcion": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "descripcion_marca_catalogo",
                    "placeholder": "Opcional",
                    "maxlength": 250,
                }
            ),
        }

    def clean_nombre(self):
        nombre = normalizar_nombre_catalogo(self.cleaned_data.get("nombre"))

        if not nombre:
            raise forms.ValidationError("Debe ingresar el nombre de la marca.")

        duplicada = MarcaDispositivo.objects.filter(nombre=nombre).exclude(
            pk=self.instance.pk
        )
        if duplicada.exists():
            raise forms.ValidationError("Ya existe una marca con ese nombre.")

        return nombre


class TipoCatalogoForm(forms.ModelForm):
    """Alta y edicion de tipos de equipo desde la vista de catalogo.

    Igual que marcas y modelos, los tipos no se crean desde el formulario de
    equipos: alli solo se eligen. Este formulario sirve para las dos cosas
    porque el alta y la edicion piden exactamente los mismos datos; la
    diferencia esta en si llega o no una instancia.
    """

    class Meta:
        model = TipoDispositivo
        fields = ["nombre", "categoria", "categorias_secundarias", "descripcion"]
        labels = {
            "categoria": "Categoría principal",
            "categorias_secundarias": "También pertenece a",
        }
        help_texts = {
            "categoria": "Define qué área da el mantenimiento.",
            "categorias_secundarias": (
                "Solo para equipos híbridos, como un ecógrafo con estación "
                "de trabajo."
            ),
        }
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "nombre_tipo_catalogo",
                    "placeholder": "Ej. MONITOR DE SIGNOS VITALES",
                    "maxlength": 100,
                }
            ),
            "categoria": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "categoria_tipo_catalogo",
                }
            ),
            "categorias_secundarias": forms.CheckboxSelectMultiple(
                attrs={
                    "class": "equipos-registro__casillas",
                    "id": "categorias_secundarias_tipo_catalogo",
                }
            ),
            "descripcion": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "descripcion_tipo_catalogo",
                    "placeholder": "Opcional",
                    "maxlength": 250,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Una categoria desactivada no se ofrece para clasificar tipos nuevos,
        # pero se conserva en la edicion del tipo que ya la usa.
        filtro = Q(activo=True)

        if self.instance.pk and self.instance.categoria_id:
            filtro |= Q(pk=self.instance.categoria_id)

        activas = CategoriaEquipo.objects.filter(filtro)
        self.fields["categoria"].queryset = activas
        self.fields["categoria"].empty_label = "Seleccione la categoría"
        self.fields["categorias_secundarias"].queryset = activas
        self.fields["categorias_secundarias"].required = False

    def clean(self):
        """Una categoria secundaria repetida no aporta nada.

        La principal ya clasifica el tipo; volver a marcarla como secundaria
        solo produce una etiqueta duplicada en las pantallas y en los
        reportes.
        """
        cleaned_data = super().clean()
        principal = cleaned_data.get("categoria")
        secundarias = cleaned_data.get("categorias_secundarias")

        if principal and secundarias and principal in secundarias:
            self.add_error(
                "categorias_secundarias",
                "La categoría principal ya está incluida; no hace falta "
                "repetirla aquí.",
            )

        return cleaned_data

    def clean_nombre(self):
        # normalizar_nombre_catalogo recorta espacios y pasa a mayusculas, asi
        # que "  monitor " y "MONITOR" acaban siendo el mismo nombre y la
        # comprobacion de abajo los detecta como duplicados.
        nombre = normalizar_nombre_catalogo(self.cleaned_data.get("nombre"))

        if not nombre:
            raise forms.ValidationError("Debe ingresar el nombre del tipo.")

        duplicado = TipoDispositivo.objects.filter(nombre=nombre).exclude(
            pk=self.instance.pk
        )
        if duplicado.exists():
            raise forms.ValidationError("Ya existe un tipo de equipo con ese nombre.")

        return nombre


class ModeloCatalogoForm(forms.ModelForm):
    """Alta de modelos dentro de una marca concreta.

    La marca no es un campo del formulario: viene de la marca seleccionada en
    la pantalla, para que no se pueda crear un modelo bajo otra marca
    manipulando el POST.
    """

    class Meta:
        model = ModeloDispositivo
        fields = ["nombre", "descripcion"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "nombre_modelo_catalogo",
                    "placeholder": "Ingrese Modelo",
                    "maxlength": 100,
                }
            ),
            "descripcion": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "descripcion_modelo_catalogo",
                    "placeholder": "Opcional",
                    "maxlength": 250,
                }
            ),
        }

    def __init__(self, *args, marca=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.marca = marca
        # Se asigna ya en la instancia porque _post_clean() valida el modelo
        # antes de llegar a save(), y sin marca la validacion fallaria pidiendo
        # un campo que este formulario no expone.
        if marca is not None:
            self.instance.marca = marca

    def clean_nombre(self):
        nombre = normalizar_nombre_catalogo(self.cleaned_data.get("nombre"))

        if not nombre:
            raise forms.ValidationError("Debe ingresar el nombre del modelo.")

        if self.marca is None:
            raise forms.ValidationError("Seleccione primero una marca.")

        # El mismo nombre puede existir en otras marcas; solo se comprueba
        # dentro de esta. La restriccion de base cubre la carrera entre dos
        # envios simultaneos.
        duplicado = ModeloDispositivo.objects.filter(
            marca=self.marca, nombre=nombre
        ).exclude(pk=self.instance.pk)

        if duplicado.exists():
            raise forms.ValidationError(
                "Esta marca ya tiene un modelo con ese nombre."
            )

        return nombre


class SalidaGarantiaForm(forms.Form):
    """Registra que el equipo salio a reparacion.

    No pide la fecha: la pausa se anota el dia que se ejecuta. Se decidio asi
    porque el inventario arranca de cero y no hay historico que reconstruir;
    un campo de fecha solo abriria la puerta a equivocarse al teclearla.
    """

    motivo = forms.CharField(
        label="Motivo",
        widget=forms.Textarea(
            attrs={
                "class": "formularioCampo-text no-resize",
                "rows": 3,
            }
        ),
    )

    def __init__(self, *args, dispositivo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.dispositivo = dispositivo

    def clean_motivo(self):
        return (self.cleaned_data.get("motivo") or "").strip()


class RetornoGarantiaForm(forms.Form):
    """Cierra la pausa. Los dias fuera se suman aqui al vencimiento.

    Tampoco pide la fecha: el retorno se anota el dia que el equipo vuelve.
    """

    observaciones_retorno = forms.CharField(
        label="Observaciones",
        widget=forms.Textarea(
            attrs={
                "class": "formularioCampo-text no-resize",
                "rows": 3,
            }
        ),
    )

    def __init__(self, *args, pausa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pausa = pausa

    def clean_observaciones_retorno(self):
        return (self.cleaned_data.get("observaciones_retorno") or "").strip()
