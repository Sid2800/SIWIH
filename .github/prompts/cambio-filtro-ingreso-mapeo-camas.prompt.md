---
name: "Cambio filtro ingreso mapeo camas"
description: "Aplica un cambio minimo en mapeo_camas para actualizar filtro de ingreso, transiciones a OCUPADA y observaciones de historial."
argument-hint: "Confirma si hay codigos de observacion existentes para CONSULTA_EXTERNA->OCUPADA y PRE_ALTA->OCUPADA"
agent: "agent"
model: "GPT-5 (copilot)"
---
Actua como desarrollador senior en este proyecto Django y realiza un cambio minimo, seguro y enfocado solo en el modulo mapeo_camas.

Objetivo funcional:
1. Actualizar el filtro de ingreso para que solo incluya estos estados como opciones validas de transicion: VACIA, CONSULTA_EXTERNA y PRE_ALTA.
2. Mostrar claramente el estado actual de la cama dentro del filtro o flujo de ingreso (debe quedar visible para el usuario).

Reglas de negocio:
1. Debe permitirse cambiar de CONSULTA_EXTERNA a OCUPADA.
2. Debe permitirse cambiar de PRE_ALTA a OCUPADA.
3. Al hacer transicion hacia OCUPADA desde esos estados, guardar historial con observacion especifica segun origen:
4. CONSULTA_EXTERNA -> OCUPADA: observacion explicita de paso desde consulta externa.
5. PRE_ALTA -> OCUPADA: observacion explicita de paso desde pre-alta.
6. Mantener las demas reglas actuales no relacionadas.

Alcance y restricciones:
1. Cambios minimos y directos, sin refactor innecesario.
2. No tocar fuera de mapeo_camas salvo estricta necesidad; si hace falta, justificar antes.
3. No romper permisos, sesiones de mapeo, ni validaciones existentes.
4. Reutilizar observaciones o catalogos existentes; si falta catalogo, crear migracion de datos idempotente.

Implementacion esperada:
1. Backend:
2. Ajustar validaciones y transiciones para aceptar CONSULTA_EXTERNA -> OCUPADA y PRE_ALTA -> OCUPADA.
3. Ajustar origen de opciones del filtro para incluir solo VACIA, CONSULTA_EXTERNA y PRE_ALTA.
4. Guardar en historial la observacion correcta segun estado origen.
5. Frontend o template:
6. Mostrar estado actual de cama en la zona del filtro o modal de ingreso de forma visible y consistente con el estilo existente.
7. Verificar que el usuario vea simultaneamente:
8. Estado actual de cama.
9. Opciones permitidas del filtro (VACIA, CONSULTA_EXTERNA, PRE_ALTA).

Criterios de aceptacion:
1. En UI, el filtro de ingreso muestra estado actual y solo las opciones permitidas.
2. CONSULTA_EXTERNA -> OCUPADA funciona y registra historial correcto.
3. PRE_ALTA -> OCUPADA funciona y registra historial correcto.
4. No se afectan otras transiciones no relacionadas.
5. No se introducen errores de permisos.

Validacion obligatoria:
1. Ejecutar py manage.py check.
2. Probar manualmente flujo en mapa con una cama en CONSULTA_EXTERNA y otra en PRE_ALTA.
3. Confirmar en historial la observacion correcta de cada transicion.
4. Reportar archivos tocados y resumen breve por archivo.

Salida esperada:
1. Entregar primero un resumen corto de la solucion aplicada.
2. Luego listar archivos tocados con una linea por archivo y su cambio principal.
3. Finalmente reportar resultado de validaciones (check y pruebas manuales).
