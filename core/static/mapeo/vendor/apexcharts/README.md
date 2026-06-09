# ApexCharts (local) — slot vendor

Fecha: 2026-05-28

Este directorio aloja la copia local de ApexCharts utilizada por el dashboard
de `mapeo_camas`. El entorno hospitalario no tiene acceso a internet, por lo
que la librería NO se descarga desde un CDN en runtime.

## Archivo esperado

```
mapeo_camas/static/mapeo_camas/vendor/apexcharts/apexcharts.min.js
```

## Cómo obtenerlo

Desde un equipo con internet (o desde el repositorio interno de paquetes):

1. Descargar la build minificada desde el release oficial de ApexCharts
   (versión sugerida: 3.x estable). Archivo:
   `apexcharts.min.js`
2. Copiar el archivo dentro de esta carpeta exactamente con ese nombre.
3. Verificar que el dashboard cargue sin errores en la consola del navegador.

> El template `dashboard.html` ya hace referencia al archivo vía
> `{% static 'mapeo_camas/vendor/apexcharts/apexcharts.min.js' %}`.
> Si se coloca con otro nombre, ajustar el `<script>` del template.

## Verificación

Tras colocar el archivo, ejecutar:

```
python manage.py collectstatic --noinput
```

(solo en entornos con `STATIC_ROOT` configurado).
