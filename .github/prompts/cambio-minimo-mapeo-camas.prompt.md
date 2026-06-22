---
name: "Cambio Minimo Mapeo Camas"
description: "Usar cuando: necesites un cambio minimo, directo y local en mapeo_camas, sin refactor general ni cambios fuera del modulo salvo justificacion previa"
argument-hint: "Describe el ajuste puntual o bug a corregir en mapeo_camas"
agent: "agent"
model: "GPT-5 (copilot)"
---

Quiero que resuelvas un cambio minimo, directo y local en el modulo mapeo_camas.

Objetivo:
- Resolver solo el ajuste puntual solicitado por el usuario dentro de mapeo_camas.
- Evitar refactor general, limpieza no pedida o expansion de alcance.

Reglas obligatorias:
- Toca solo lo minimo necesario.
- Prioriza cambios dentro de mapeo_camas.
- No modifiques core ni otras apps salvo que sea estrictamente indispensable.
- Si necesitas salir de mapeo_camas, explicalo primero y justifica por que no se puede resolver localmente.
- No cambies logica adyacente si no afecta directamente el problema.
- Mantén el estilo actual del proyecto.
- Reutiliza patrones visuales y tecnicos existentes.
- No agregues estilos innecesarios.
- En frontend, evita agregar borders nuevos.
- Agrega comentario con la fecha actual en cambios relevantes usando la convencion del proyecto.

Reglas de permisos del proyecto:
- Si la vista es GET o de visualizacion, usa UnidadRolRequiredMixin cuando aplique.
- Si la operacion es POST o modifica datos, usa verificar_permisos_usuario() explicito cuando aplique la regla del proyecto.
- No mezcles la estrategia de permisos si no corresponde.

Forma de trabajo:
1. Primero identifica el archivo y el punto exacto donde se controla el comportamiento.
2. Formula una hipotesis local y falsable del problema antes del primer edit.
3. Haz el cambio mas pequeño posible en ese punto.
4. Despues del primer edit, ejecuta una validacion puntual del flujo afectado.
5. Si la validacion falla, corrige solo ese mismo slice antes de ampliar alcance.
6. Al final responde solo con:
   - que cambiaste,
   - por que ese era el punto correcto,
   - que validaste.

Contexto funcional a respetar:
- Cuando el problema sea del flujo de mapeo, revisar solo el tramo exacto involucrado, por ejemplo iniciar mapeo, confirmar cama, finalizar mapeo o cancelar mapeo.
- Si el ajuste involucra mapa de camas, mantener consistencia con la tabla operativa y con la UI ya existente.
- Si hay modales o alertas, mantener el patron visual ya usado por el proyecto.

Toma como solicitud puntual el texto que el usuario escriba al invocar este prompt y usalo como el objetivo concreto del cambio.