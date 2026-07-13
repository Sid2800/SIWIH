# Pendientes del modulo de Equipos

## Eliminacion definitiva de equipos

- Implementar una accion administrativa distinta de "dar de baja".
- Reservarla para registros duplicados, pruebas o errores de captura.
- Mostrarla solo a administradores con un permiso especifico.
- Solicitar confirmacion y motivo obligatorio.
- Impedir la eliminacion si el equipo tiene mantenimientos u otro historial que deba conservarse.
- Eliminar primero sus archivos, miniaturas y registros mediante la API del servidor de imagenes.
- Si la API de imagenes no responde, no eliminar el equipo de la base principal.
- Ejecutar la eliminacion mediante una solicitud POST, nunca mediante GET.
- No agregar un modulo ni submenu nuevo; ubicar la accion al final de la vista de edicion.
