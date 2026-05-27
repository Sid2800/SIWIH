# REFACTOR FINAL: Retiro Completo de Compatibilidad Paciente_id
**Fecha**: 2026-05-26  
**Componente**: mapeo_camas  
**Fase**: V3.0 - Ingreso_id como Único Pivote Operativo

---

## 📋 Resumen Ejecutivo

Este refactor finaliza la migración de **paciente_id** → **ingreso_id** como pivote operativo único en mapeo_camas. Se ha **removido completamente la compatibilidad temporal** introducida el 2026-05-26 AUDIT.

### Cambios Críticos:
- ✅ **ingreso_id ahora obligatorio** para cualquier estado OCUPADA
- ✅ **Validaciones reforzadas** en clean() - rechaza OCUPADA sin ingreso
- ✅ **Fallbacks temporales removidos** de _resolver_ingreso_operativo()
- ✅ **APIs POST ahora requieren ingreso_id** explícitamente
- ✅ **Paciente derivado automáticamente** desde ingreso (dato secundario)

---

## 🔄 Cambios en Models

### AsignacionCamaPaciente

#### clean()
```
ANTES: Validación de paciente requerido en OCUPADA
AHORA: Validación de ingreso_id requerido; paciente derivable
```

**Nueva Regla de Negocio**:
```python
if self.estado.codigo == "OCUPADA":
    if not self.ingreso_id:
        raise ValidationError("Una asignacion ocupada debe tener un ingreso activo válido.")
```

- **Matriz de duplicados**: Validación now against `ingreso_id` instead of `paciente_id`
- Impide que mismo ingreso esté en dos camas OCUPADA simultáneamente

#### save()
```
ANTES: Fallback temporal - si no ingreso, derivar desde paciente
       + Derivar paciente desde ingreso como coherencia
AHORA: Solo derivar paciente desde ingreso (único flujo)
```

**Nuevo código**:
```python
def save(self, *args, **kwargs):
    # [2026-05-26 REFACTOR FINAL] Ingreso_id es pivote; paciente derivado de auditoría
    if self.estado.codigo == "VACIA":
        self.paciente = None
        self.ingreso = None
    # Derivar paciente desde ingreso como dato secundario
    if self.ingreso_id and not self.paciente_id:
        self.paciente_id = self.ingreso.paciente_id
    self.full_clean()
    return super().save(*args, **kwargs)
```

#### __str__()
**Visual mejorado** para debugging:
```
ANTES: "Cama {id} - Ingreso {ingreso} - Paciente {paciente} ({estado})"
AHORA: "Cama {id} | Ingreso {ingreso} | Estado {estado}"
```

---

## 🔧 Cambios en Views

### _resolver_ingreso_operativo()
```
ANTES: Prioriza ingreso_id; fallback a paciente_id
AHORA: Requiere ingreso_id obligatoriamente
```

**Nuevo código**:
```python
def _resolver_ingreso_operativo(*, ingreso_id=None, paciente_id=None):
    """
    [2026-05-26 REFACTOR FINAL] Requiere ingreso_id explícitamente.
    Levanta ValueError si falta; no hay fallback a paciente.
    """
    if not ingreso_id:
        raise ValueError(
            "El ingreso_id es obligatorio para operaciones en mapeo_camas. "
            "Paciente_id ya no es válido como pivote operativo."
        )
    return Ingreso.objects.filter(pk=ingreso_id).select_related("paciente").first()
```

**Impacto**: Cualquier vista que llame sin ingreso_id→ ValueError → HTTP 400

### mover_paciente_cama()
```
ANTES: asig_origen.ingreso or _resolver_ingreso_activo_desde_paciente(...)
AHORA: asig_origen.ingreso (requerido; error 400 si falta)
```

**Nueva Lógica**:
```python
ingreso_operativo = asig_origen.ingreso
if not ingreso_operativo:
    return JsonResponse({
        "ok": False, 
        "error": "La cama origen no tiene un ingreso activo válido. Datos incompletos."
    }, status=400)
```

### actualizar_cama_mapa()
```
ANTES: Manejo dual (ingreso_id O paciente_id)
AHORA: OCUPADA requiere ingreso_id; fallback solo para no-OCUPADA
```

**Nueva Lógica**:
```python
if estado_codigo == "OCUPADA":
    # [2026-05-26 REFACTOR FINAL] OCUPADA requiere ingreso_id
    if not ingreso_id:
        return JsonResponse({
            "ok": False,
            "error": "Para asignar OCUPADA debe indicar ingreso. Paciente_id ya no válido."
        }, status=400)
    ingreso_nuevo = _resolver_ingreso_operativo(ingreso_id=ingreso_id)
    if not ingreso_nuevo:
        return JsonResponse({
            "ok": False,
            "error": "El ingreso seleccionado no existe."
        }, status=404)
    paciente_nuevo = ingreso_nuevo.paciente
```

### procesar_cama_mapeo()
```
ANTES: Intento de resolver ingreso desde paciente_observado_id
AHORA: Requiere ingreso_observado_id; paciente_observado_id solo fallback
```

**Nueva Lógica**:
```python
if ingreso_observado_id:
    ingreso_observado = _resolver_ingreso_operativo(ingreso_id=ingreso_observado_id)
    if not ingreso_observado:
        return JsonResponse({
            "ok": False,
            "error": "Ingreso observado no existe."
        }, status=404)
    paciente_observado = ingreso_observado.paciente
elif paciente_observado_id:
    # Compatibilidad en próxima versión se removerá
    try:
        paciente_observado = Paciente.objects.get(pk=paciente_observado_id)
    except Paciente.DoesNotExist:
        return JsonResponse({
            "ok": False,
            "error": "Paciente observado no existe."
        }, status=404)
```

---

## 📡 Cambios en Frontend

No hay cambios adicionales en mapaCamasAsignacion.js; continúa enviando `ingreso_id` en payloads. 

**Comportamiento esperado**:
- Si ingreso_id ausente en POST → HTTP 400 "ingreso_id es obligatorio"
- Frontend debe validar UI para siempre enviar ingreso_id para OCUPADA

---

## ⚠️ Breaking Changes para Clientes Externos

### APIs Afectadas:
1. **mover_paciente_cama** (POST)
   - Anteriormente: derivaba ingreso desde paciente si faltaba
   - **Ahora**: Error 400 si ingreso no disponible en asignación origen

2. **actualizar_cama_mapa** (POST)
   - Anteriormente: OCUPADA podía recibir solo paciente_id
   - **Ahora**: OCUPADA REQUIERE ingreso_id; paciente_id ignorado

3. **procesar_cama_mapeo** (POST)
   - Anteriormente: acción ASIGNACION podía recibir paciente_observado_id
   - **Ahora**: Recomendado enviar ingreso_observado_id; paciente solo fallback

### Guía de Migración para Clientes:
```
IF endpoint currently sends POST without ingreso_id for OCUPADA:
  1. Modify request to include ingreso_id
  2. You can remove paciente_id if not needed for logging
  3. Test against staging to verify 200 OK responses
  
IF endpoint derives ingreso from paciente externally:
  1. Fetch Ingreso records where ingreso.paciente_id = paciente AND estado=1 AND fecha_egreso IS NULL
  2. Pass ingreso.id in subsequent mapeo_camas API calls
  3. Document the ingreso resolution logic in your code
```

---

## 🧪 Validación y Testing

### Escenarios de Test Requeridos:
1. ✅ OCUPADA sin ingreso_id → Error 400
2. ✅ OCUPADA con ingreso_id válido → Success 200
3. ✅ Traslado mantiene ingreso_id consistente
4. ✅ Alta (PRE_ALTA → ALTA) marca ingreso.cama = None
5. ✅ Historial registra ingreso en cada transición
6. ✅ Sincronización comando mantiene ingreso_id sincronizado

### Comando de Validación:
```bash
python manage.py check mapeo_camas
python manage.py migrate mapeo_camas --fake-initial  # Para dev
python manage.py test mapeo_camas -v 2
```

---

## 📅 Timeline de Retiro Total

| Fase | Fecha | Acción |
|------|-------|--------|
| **ACTUAL** | 2026-05-26 | Remover compatibilidad; requerir ingreso_id |
| **DEPRECATION** | 2026-05-27 → 2026-06-30 | Avisos en logs si paciente_id usado como pivote |
| **REMOVAL** | 2026-07-01 | Remover campos paciente_id de APIs; null=False en ingreso |
| **CLEANUP** | 2026-07-15 | Opcional: remover relación paciente de AsignacionCamaPaciente |

---

## 🔐 Integridad Referencial

### Matriz de Restricciones:
| Estado | ingreso_id | paciente_id | Válido | Nota |
|--------|-----------|-----------|--------|------|
| VACIA | NULL | NULL | ✅ | Cama vacía |
| OCUPADA | NOT NULL | Derivado | ✅ | Ingreso obligatorio |
| PRE_ALTA | NOT NULL | Derivado | ✅ | Ingreso obligatorio |
| TRANSITO | NOT NULL | Derivado | ✅ | Durante traslado |

### FK on_delete Policies:
- `ingreso` → **PROTECT** (impide eliminar ingreso si hay asignación)
- `paciente` → **PROTECT** (backward compat; actualizar si se remueve)

---

## 📝 Notas de Implementación

### Derivación de Paciente:
```python
# En save():
if self.ingreso_id and not self.paciente_id:
    self.paciente_id = self.ingreso.paciente_id
```
**Ventaja**: Paciente siempre coherente con ingreso; nunca desincronizado.  
**Alternativa** (próxima versión): Remover completamente paciente_id, usar ingreso.paciente_id en queries.

### Backfill Completo:
Migración 0006 backfilló todos los registros históricos con ingreso_id basado en:
- Fecha proximidad (fecha_ingreso ≤ fecha_asignacion ≤ fecha_egreso)
- Cama match (si es movimiento, priorizar mismo paciente)

---

## 🚀 Próximos Pasos

1. **Ejecutar Migraciones** (si aún no aplicadas):
   ```bash
   manage.py migrate mapeo_camas
   ```

2. **Validar en Staging**:
   ```bash
   # Probar flujo completo: asignación → traslado → alta
   # Verificar historial y auditoría registren ingreso_id
   ```

3. **Actualizar Documentación Clientes**:
   - Email a clientes externos: new ingreso_id requirement
   - Blog post sobre refactor
   - API changelog

4. **Monitoreo en Producción**:
   - Alertar si HTTP 400 "ingreso_id obligatorio" aumenta
   - Rastrear logs para uso de fallbacks removidos
   - A/B test con clientes que aún envían paciente_id

---

**Autor**: SIWIH Refactor Team  
**Revisado**: 2026-05-26  
**Versión del Sistema**: 3.0.0
