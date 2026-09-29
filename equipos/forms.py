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
    GarantiaDispositivo,
    MarcaDispositivo,
    ModalidadProcedencia,
    ModeloDispositivo,
    MotivoCierreGarantia,
    Procedencia,
    TipoDispositivo,
    TipoProcedencia,
    TecnologiaEquipo,
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


class ColoresOrdenadosField(forms.CharField):
    """Recibe los colores del equipo en el orden en que se agregaron.

    Llega como una lista de identificadores separados por coma ("7,3,12") que
    arma el navegador conforme el usuario los va agregando de uno en uno. No
    se usa un multiple de Django porque esos devuelven el orden del catalogo,
    y aqui el orden es justamente el dato: el primero es el principal.
    """

    def to_python(self, valor):
        texto = (valor or "").strip()

        if not texto:
            return []

        identificadores = []

        for parte in texto.split(","):
            parte = parte.strip()

            if not parte:
                continue

            if not parte.isdigit():
                raise forms.ValidationError("La lista de colores no es válida.")

            numero = int(parte)

            # Un color repetido no aporta nada y romperia la unicidad de la
            # tabla intermedia. Se descarta la repeticion, no la seleccion.
            if numero not in identificadores:
                identificadores.append(numero)

        catalogo = ColorDispositivo.objects.in_bulk(identificadores)

        if len(catalogo) != len(identificadores):
            raise forms.ValidationError(
                "Alguno de los colores elegidos ya no existe."
            )

        # in_bulk devuelve un diccionario sin orden util: se recorre la lista
        # original para conservar el que eligio el usuario.
        return [catalogo[numero] for numero in identificadores]


class ListaOcultaWidget(forms.HiddenInput):
    """Campo oculto que lleva varios identificadores en un solo valor.

    Los pinta separados por coma -"3,7"-, que es como los arma el navegador
    conforme el usuario va agregando. Sin esto el widget escribiria la lista
    de Python tal cual, "[3, 7]", y al reenviar el formulario esos corchetes
    no serian identificadores de nada.
    """

    def format_value(self, valor):
        if isinstance(valor, (list, tuple)):
            return ",".join(
                str(elemento) for elemento in valor if elemento not in (None, "")
            )

        return super().format_value(valor)


def _identificadores_de_lista(valor):
    """Separa "3,7" en ["3", "7"], y deja en paz lo que ya es una lista."""
    if not isinstance(valor, str):
        return valor

    return [
        parte
        for parte in (trozo.strip() for trozo in valor.split(","))
        if parte
    ]


class CategoriasAgregadasField(forms.ModelMultipleChoiceField):
    """Categorias secundarias que se van agregando de una en una.

    Llegan como una lista de identificadores separados por coma ("3,7"), la
    misma forma en que viajan los colores del equipo. Antes eran casillas: una
    por cada categoria del sistema, todas a la vista y todas por marcar. Un
    tipo hibrido suele tener una o dos categorias mas, asi que casi todas las
    casillas sobraban, y a medida que el hospital agrega categorias la lista
    se alarga sin que el formulario mejore.
    """

    widget = ListaOcultaWidget

    def clean(self, valor):
        # El campo es oculto, asi que llega un texto y no una lista.
        return super().clean(_identificadores_de_lista(valor))

    def has_changed(self, inicial, datos):
        # La clase padre compara conjuntos contando con que los datos son una
        # lista; con un texto acabaria comparando letras sueltas.
        def conjunto(valor):
            return {str(elemento) for elemento in (_identificadores_de_lista(valor) or [])}

        return conjunto(inicial) != conjunto(datos)


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
    # El navegador mantiene aqui la lista en el orden en que el usuario fue
    # agregando los colores. El campo va oculto: lo que se ve es el selector y
    # la lista, igual que al capturar diagnosticos.
    colores = ColoresOrdenadosField(
        required=False,
        label="Colores",
        widget=forms.HiddenInput(
            attrs={"id": "colores_dispositivo"},
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
            "marca",
            "modelo",
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

        # Los tres selectores van en cascada: el tipo manda, la marca se limita
        # a las que fabrican ese tipo y el modelo a los de esa marca para ese
        # tipo. El queryset no es solo lo que se ofrece en pantalla: es lo que
        # Django acepta al validar, asi que una combinacion imposible se
        # rechaza aunque llegue por un POST que se salte el navegador.
        tipo_en_juego = self._resolver_valor_en_juego("tipo")
        marca_en_juego = self._resolver_valor_en_juego("marca")

        if tipo_en_juego:
            self.fields["marca"].queryset = MarcaDispositivo.objects.filter(
                filtro_marca, tipos__id=tipo_en_juego
            ).distinct()
        else:
            self.fields["marca"].queryset = MarcaDispositivo.objects.none()
            # Sin tipo no hay marcas que ofrecer. El atributo deja el estado
            # explicito en el HTML, sin depender de que el JavaScript cargue.
            self.fields["marca"].widget.attrs["disabled"] = "disabled"

        self.fields["marca"].empty_label = "Sin especificar"
        self.fields["marca"].error_messages["invalid_choice"] = (
            "Esta marca no está registrada en el tipo de equipo elegido."
        )

        if tipo_en_juego and marca_en_juego:
            self.fields["modelo"].queryset = ModeloDispositivo.objects.filter(
                filtro_modelo,
                tipo_id=tipo_en_juego,
                marca_id=marca_en_juego,
            ).select_related("marca")
        else:
            self.fields["modelo"].queryset = ModeloDispositivo.objects.none()
            self.fields["modelo"].widget.attrs["disabled"] = "disabled"

        self.fields["modelo"].empty_label = "INDEFINIDO"
        # Sin esto el rechazo saldria como "Escoja una opcion valida", que no
        # explica que el problema es la combinacion tipo-marca-modelo.
        self.fields["modelo"].error_messages["invalid_choice"] = (
            "El modelo no corresponde al tipo y la marca elegidos."
        )
        self.fields["modelo"].widget.attrs["data-url-modelos"] = reverse(
            "buscar_modelos_equipos"
        )
        self.fields["marca"].widget.attrs["data-url-marcas"] = reverse(
            "buscar_marcas_equipos"
        )
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
        # Opciones del selector de colores y lista ya elegida. INDEFINIDO
        # queda fuera: con una lista, "no se sabe" se expresa no agregando
        # ninguno.
        self.colores_disponibles = ColorDispositivo.objects.filter(
            filtro_color
        ).exclude(nombre="INDEFINIDO")
        self.colores_elegidos = self._resolver_colores_elegidos()
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

    def _resolver_colores_elegidos(self):
        """Colores que el navegador debe pintar ya en la lista, en su orden.

        En un envio con errores manda lo que venia en el POST, para no perder
        lo que el usuario habia agregado. Al abrir la edicion, los del equipo
        guardado.
        """
        if self.is_bound:
            campo = self.fields["colores"]

            try:
                return campo.clean(self.data.get(self.add_prefix("colores")))
            except forms.ValidationError:
                return []

        if self.instance and self.instance.pk:
            return self.instance.colores_ordenados

        return []

    def _resolver_valor_en_juego(self, campo):
        """Identificador vigente de tipo o marca, para acotar la cascada.

        En un envio manda lo que llega en el POST, porque el usuario pudo
        haber cambiado de tipo o de marca. Al abrir la edicion, lo del equipo
        guardado. Si no hay ninguno, no se puede acotar nada.
        """
        if self.is_bound:
            valor = self.data.get(self.add_prefix(campo))
            return int(valor) if str(valor or "").isdigit() else None

        if self.instance and self.instance.pk:
            guardado = getattr(self.instance, f"{campo}_id", None)

            if guardado:
                return guardado

        valor = self.initial.get(campo)
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


class MarcaEnTipoForm(forms.Form):
    """Declara una marca dentro de un tipo de equipo.

    Un solo campo para dos gestos que el usuario no distingue: si la marca ya
    existe en el sistema se reutiliza, y si no, se crea. Antes eran dos pasos
    en dos sitios distintos -crear la marca global y luego encontrarla- y era
    justo donde la gente se perdia.

    Las marcas no se crean desde el formulario de equipos: alli solo se
    eligen. Concentrar el alta aqui evita que un error de tecleo genere
    marcas duplicadas mientras alguien registra un aparato con prisa.
    """

    nombre = forms.CharField(
        max_length=100,
        label="Marca",
        widget=forms.TextInput(
            attrs={
                "class": "formularioCampo-text",
                "id": "nombre_marca_catalogo",
                "list": "marcas_existentes_equipos",
                "placeholder": "Escriba o elija una marca",
                "autocomplete": "off",
            }
        ),
    )

    def __init__(self, *args, tipo=None, **kwargs):
        self.tipo = tipo
        super().__init__(*args, **kwargs)

    def clean_nombre(self):
        nombre = normalizar_nombre_catalogo(self.cleaned_data.get("nombre"))

        if not nombre:
            raise forms.ValidationError("Debe ingresar el nombre de la marca.")

        if self.tipo and self.tipo.marcas.filter(nombre=nombre).exists():
            raise forms.ValidationError(
                "Esta marca ya está registrada en este tipo de equipo."
            )

        return nombre

    def guardar(self):
        """Devuelve la marca ya vinculada al tipo, creandola si hace falta."""
        nombre = self.cleaned_data["nombre"]
        marca, creada = MarcaDispositivo.objects.get_or_create(nombre=nombre)

        if not marca.activo:
            # Reutilizar una marca desactivada es mas sano que crear un
            # duplicado: el nombre es unico y ya existe.
            marca.activo = True
            marca.save(update_fields=["activo"])

        self.tipo.marcas.add(marca)
        return marca, creada


class CatalogoSimpleForm(forms.Form):
    """Alta de una categoria o una tecnologia desde el modal del formulario.

    Las dos son lo mismo -un nombre y una descripcion opcional- asi que
    comparten formulario. El modelo concreto se pasa al construirlo, y de el
    sale tambien el mensaje del duplicado.
    """

    nombre = forms.CharField(
        max_length=100,
        label="Nombre",
        widget=forms.TextInput(
            attrs={
                "class": "formularioCampo-text",
                "placeholder": "Ej. NEUMATICO",
                "maxlength": 100,
            }
        ),
    )
    descripcion = forms.CharField(
        required=False,
        max_length=250,
        label="Descripción",
        widget=forms.TextInput(
            attrs={
                "class": "formularioCampo-text",
                "placeholder": "Opcional",
                "maxlength": 250,
            }
        ),
    )

    def __init__(self, *args, modelo=None, etiqueta="valor", **kwargs):
        self.modelo = modelo
        self.etiqueta = etiqueta
        super().__init__(*args, **kwargs)

    def clean_nombre(self):
        nombre = normalizar_nombre_catalogo(self.cleaned_data.get("nombre"))

        if not nombre:
            raise forms.ValidationError(
                f"Debe ingresar el nombre de la {self.etiqueta}."
            )

        if self.modelo.objects.filter(nombre=nombre).exists():
            raise forms.ValidationError(
                f"Ya existe una {self.etiqueta} con ese nombre."
            )

        return nombre

    def guardar(self):
        return self.modelo.objects.create(
            nombre=self.cleaned_data["nombre"],
            descripcion=self.cleaned_data.get("descripcion", ""),
        )


class TipoCatalogoForm(forms.ModelForm):
    """Alta y edicion de tipos de equipo desde la vista de catalogo.

    Igual que marcas y modelos, los tipos no se crean desde el formulario de
    equipos: alli solo se eligen. Este formulario sirve para las dos cosas
    porque el alta y la edicion piden exactamente los mismos datos; la
    diferencia esta en si llega o no una instancia.
    """

    # Se agregan de una en una, como los colores del equipo: se elige en el
    # desplegable, se pulsa agregar y queda en la lista. El campo que viaja al
    # servidor es oculto y lleva los identificadores separados por coma.
    categorias_secundarias = CategoriasAgregadasField(
        queryset=CategoriaEquipo.objects.none(),
        required=False,
        label="También pertenece a",
        widget=ListaOcultaWidget(
            attrs={"id": "categorias_secundarias_tipo_catalogo"}
        ),
    )

    class Meta:
        model = TipoDispositivo
        fields = [
            "nombre",
            "categoria",
            "tecnologia",
            "categorias_secundarias",
            "descripcion",
        ]
        labels = {
            "categoria": "Categoría principal",
            "tecnologia": "Tecnología",
            "categorias_secundarias": "También pertenece a",
        }
        help_texts = {
            "categoria": "Define qué área da el mantenimiento.",
            "tecnologia": (
                "Igual para todos los equipos de este tipo: no se pregunta "
                "en cada registro."
            ),
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
            "tecnologia": forms.Select(
                attrs={
                    "class": "formularioCampo-select",
                    "id": "tecnologia_tipo_catalogo",
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

        # Lo que el navegador tiene que pintar: el desplegable con las
        # categorias disponibles y la lista de las ya agregadas.
        self.categorias_disponibles = activas
        self.categorias_secundarias_elegidas = self._resolver_secundarias()

        # Misma regla para la tecnologia: una desactivada no se ofrece para
        # tipos nuevos, pero se conserva en la edicion del que ya la usa.
        filtro_tecnologia = Q(activo=True)

        if self.instance.pk and self.instance.tecnologia_id:
            filtro_tecnologia |= Q(pk=self.instance.tecnologia_id)

        self.fields["tecnologia"].queryset = TecnologiaEquipo.objects.filter(
            filtro_tecnologia
        )
        self.fields["tecnologia"].empty_label = "Seleccione la tecnología"

    def _resolver_secundarias(self):
        """Categorias secundarias que deben aparecer ya en la lista.

        En un envio con errores se devuelven las que venian en el POST, para
        no perder lo que el usuario habia agregado. Al abrir la edicion, las
        que tiene guardadas el tipo.
        """
        if self.is_bound:
            campo = self.fields["categorias_secundarias"]

            try:
                return list(
                    campo.clean(
                        self.data.get(self.add_prefix("categorias_secundarias"))
                    )
                )
            except forms.ValidationError:
                return []

        if self.instance and self.instance.pk:
            return list(self.instance.categorias_secundarias.all())

        return []

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
    """Alta de modelos dentro de una pareja tipo-marca concreta.

    Ni el tipo ni la marca son campos del formulario: vienen de lo que esta
    seleccionado en la pantalla, para que no se pueda colar un modelo bajo
    otro aparato manipulando el POST.
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

    def __init__(self, *args, tipo=None, marca=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tipo = tipo
        self.marca = marca
        # Se asignan ya en la instancia porque _post_clean() valida el modelo
        # antes de llegar a save(), y sin tipo ni marca la validacion fallaria
        # pidiendo campos que este formulario no expone.
        if tipo is not None:
            self.instance.tipo = tipo
        if marca is not None:
            self.instance.marca = marca

    def clean_nombre(self):
        nombre = normalizar_nombre_catalogo(self.cleaned_data.get("nombre"))

        if not nombre:
            raise forms.ValidationError("Debe ingresar el nombre del modelo.")

        if self.tipo is None or self.marca is None:
            raise forms.ValidationError(
                "Seleccione primero el tipo de equipo y la marca."
            )

        # El mismo nombre puede existir en otras marcas, y una marca puede
        # llamar igual a productos de tipos distintos: solo se comprueba
        # dentro de esta pareja. La restriccion de base cubre la carrera entre
        # dos envios simultaneos.
        duplicado = ModeloDispositivo.objects.filter(
            tipo=self.tipo, marca=self.marca, nombre=nombre
        ).exclude(pk=self.instance.pk)

        if duplicado.exists():
            raise forms.ValidationError(
                "Esta marca ya tiene un modelo con ese nombre para este tipo."
            )

        return nombre


class GarantiaForm(forms.ModelForm):
    """Alta de una garantia: la primera del equipo o una renovacion.

    La duracion se elige de una lista y el vencimiento lo calcula el modelo.
    Antes se pedia la fecha final y quien registraba tenia que contar anios de
    cabeza desde la factura, que es justo donde se equivocaba. "Otra" deja
    escribir el vencimiento a mano para los contratos que no caen en meses
    redondos.
    """

    DURACIONES = [
        ("", "Otra (escribir la fecha)"),
        (6, "6 meses"),
        (12, "1 año"),
        (24, "2 años"),
        (36, "3 años"),
        (60, "5 años"),
    ]

    meses = forms.TypedChoiceField(
        choices=DURACIONES,
        coerce=int,
        empty_value=None,
        required=False,
        label="Duración",
        widget=forms.Select(
            attrs={
                "class": "formularioCampo-select",
                "id": "meses_garantia",
            }
        ),
    )

    class Meta:
        model = GarantiaDispositivo
        fields = ["fecha_inicio", "meses", "fecha_fin", "referencia", "observaciones"]
        labels = {
            "referencia": "Contrato o factura",
            "fecha_fin": "Vence el",
        }
        widgets = {
            "fecha_inicio": forms.DateInput(
                attrs={
                    "class": "formularioCampo-date",
                    "id": "inicio_garantia",
                    "type": "date",
                },
                format="%Y-%m-%d",
            ),
            # Solo se escribe cuando el contrato da una fecha suelta. Con
            # inicio y duracion lo calcula el modelo.
            "fecha_fin": forms.DateInput(
                attrs={
                    "class": "formularioCampo-date",
                    "id": "fin_garantia",
                    "type": "date",
                },
                format="%Y-%m-%d",
            ),
            "referencia": forms.TextInput(
                attrs={
                    "class": "formularioCampo-text",
                    "id": "referencia_garantia",
                    "placeholder": "Opcional",
                    "maxlength": 100,
                }
            ),
            "observaciones": forms.Textarea(
                attrs={
                    "class": "formularioCampo-text no-resize",
                    "id": "observaciones_garantia",
                    "rows": 3,
                    "placeholder": "Opcional",
                }
            ),
        }

    def __init__(self, *args, dispositivo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.dispositivo = dispositivo
        # El vencimiento solo es obligatorio si no hay duracion que lo
        # calcule; la comprobacion real esta en clean().
        self.fields["fecha_fin"].required = False

        if dispositivo is not None:
            self.instance.dispositivo = dispositivo
            # Renovar es legitimo: la vista cierra la anterior y guarda esta
            # en la misma transaccion. Sin esto, la validacion veria las dos
            # abiertas a la vez y rechazaria la renovacion.
            self.instance.omitir_control_de_vigente = True

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get("fecha_inicio")
        meses = cleaned_data.get("meses")
        fin = cleaned_data.get("fecha_fin")

        if inicio and not meses and not fin:
            self.add_error(
                "fecha_fin",
                "Elija una duración o escriba la fecha de vencimiento.",
            )

        return cleaned_data


class CerrarGarantiaForm(forms.Form):
    """Termina a mano la garantia vigente, sin poner otra en su lugar.

    Pide el motivo porque cerrar una garantia antes de que venza es una
    decision administrativa: dentro de un ano nadie recordara si fue un
    incumplimiento del proveedor o una correccion de un dato mal registrado,
    y en el primer caso hay un reclamo detras.
    """

    motivo = forms.ChoiceField(
        choices=[
            (valor, etiqueta)
            for valor, etiqueta in MotivoCierreGarantia.choices
            # La renovacion no se elige aqui: se produce al registrar la
            # garantia nueva, y ese camino cierra la anterior por su cuenta.
            if valor != MotivoCierreGarantia.RENOVACION
        ],
        label="Motivo",
        widget=forms.Select(
            attrs={
                "class": "formularioCampo-select",
                "id": "motivo_cierre_garantia",
            }
        ),
    )
    detalle = forms.CharField(
        required=False,
        label="Detalle",
        widget=forms.Textarea(
            attrs={
                "class": "formularioCampo-text no-resize",
                "id": "detalle_cierre_garantia",
                "rows": 3,
                "placeholder": "Número de reclamo, acuerdo con el proveedor...",
            }
        ),
    )

    def clean_detalle(self):
        return (self.cleaned_data.get("detalle") or "").strip()

    def clean(self):
        cleaned_data = super().clean()

        # "Otro motivo" sin explicacion no informa de nada: dentro de un ano
        # la fila diria solo "otro" y habria que preguntar a quien la cerro.
        if (
            cleaned_data.get("motivo") == MotivoCierreGarantia.OTRO
            and not cleaned_data.get("detalle")
        ):
            self.add_error("detalle", "Explique el motivo del cierre.")

        return cleaned_data


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
