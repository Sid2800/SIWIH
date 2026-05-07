# Usuario Location/Service Unit Assignment - RRHH Integration

## Overview
This feature automatically assigns and tracks the service unit (unidad de servicio) of users who create solicitudes (expedition loan requests) by leveraging the RRHH (Recursos Humanos) database relationships.

## Database Relationship Chain
The implementation uses the following relationship chain to ensure users are registered in the RRHH system:

```
django.contrib.auth.models.User
    ↓ (OneToOneField usuario)
rrhh.models.Empleado
    ↓ (OneToOneField empleado)
rrhh.models.PersonalNoClinico OR rrhh.models.PersonalSalud
    ↓ (ForeignKey servicio_unidad)
servicio.models.Unidad (ServicoUnidad)
```

### Relationship Details:
1. **User → Empleado**: Via `Empleado.usuario` OneToOneField
2. **Empleado → PersonalNoClinico**: Via `PersonalNoClinico.empleado` OneToOneField
3. **Empleado → PersonalSalud**: Via `PersonalSalud.empleado` OneToOneField (alternative path)
4. **PersonalNoClinico/PersonalSalud → ServicioUnidad**: Via ForeignKey to `servicio.models.Unidad`

## Database Changes

### New Field in SolicitudPrestamo Model
```python
servicio_unidad = models.ForeignKey(
    'servicio.Unidad',
    on_delete=models.PROTECT,
    null=True,
    blank=True,
    related_name='solicitudes_prestamo',
    verbose_name='Unidad de Servicio del Solicitante',
    help_text='Obtenida automáticamente del registro en RRHH del usuario solicitante'
)
```

**Migration**: `s_exp/migrations/0012_add_servicio_unidad_to_solicitud.py`

## Implementation Details

### Helper Functions in `s_exp/views.py`

#### `_get_servicio_unidad_from_rrhh(user)`
**Purpose**: Retrieve the user's service unit through the RRHH relationship chain.

**Signature**:
```python
def _get_servicio_unidad_from_rrhh(user):
    """
    Obtiene la Unidad de Servicio del usuario mediante la cadena de relaciones RRHH.

    Recorre la cadena: User → Empleado → PersonalNoClinico → ServicioUnidad

    Retorna:
        - Tuple: (servicio_unidad_obj, es_valido)
        - servicio_unidad_obj: La instancia de ServicioUnidad o None si no existe
        - es_valido: True si el usuario está registrado en RRHH, False en caso contrario
    """
```

**Return Value**:
- `(servicio_unidad_obj, es_valido)` tuple
- `servicio_unidad_obj`: Instance of `servicio.models.Unidad` or `None`
- `es_valido`: `True` if user is registered in RRHH, `False` otherwise

**Behavior**:
1. Verifies user has associated `Empleado` record
2. First tries to fetch from `PersonalNoClinico` (administrative/non-clinical staff)
3. Falls back to `PersonalSalud` (clinical staff) if PersonalNoClinico doesn't exist
4. Returns `(None, True)` if user is in RRHH but without unit assignment
5. Returns `(None, False)` if user is not in RRHH at all

### Updated API: `crear_solicitud_api(request)`

**Changes**:
1. Calls `_get_servicio_unidad_from_rrhh()` to get user's service unit
2. **Validates** that user is registered in RRHH (returns 403 Forbidden if not)
3. Passes `servicio_unidad` to `SolicitudPrestamo.objects.create()`

**Error Handling**:
```python
servicio_unidad, es_registrado_rrhh = _get_servicio_unidad_from_rrhh(request.user)
if not es_registrado_rrhh:
    return JsonResponse({
        "error": "El usuario no está registrado en el sistema RRHH (Recursos Humanos). Contacte al administrador."
    }, status=403)
```

### Model Method: `SolicitudPrestamo.get_servicio_unidad`

**Purpose**: Property that provides fallback mechanism to retrieve service unit.

```python
@property
def get_servicio_unidad(self):
    """
    Retorna la unidad de servicio de la solicitud.

    Intenta devolver el servicio_unidad almacenado directamente.
    Si no existe, intenta obtenerlo desde la cadena RRHH del usuario.
    """
```

**Logic**:
1. Returns stored `servicio_unidad` if exists
2. Falls back to RRHH chain traversal if not stored
3. Returns `None` if no unit can be found

## API Response Updates

### `listar_solicitudes_api()` (Admin View)
**Added to Response**:
```python
"servicio_unidad": s.servicio_unidad.nombre_unidad if s.servicio_unidad else ""
```

### `mis_solicitudes_api()` (User Tracking View)
**Added to Response**:
```python
"servicio_unidad": s.servicio_unidad.nombre_unidad if s.servicio_unidad else ""
```

### Query Optimization
Both APIs now use `.select_related('servicio_unidad')` to prevent N+1 queries:
```python
qs = SolicitudPrestamo.objects.select_related('usuario', 'servicio_unidad').annotate(...)
```

## Validation & Constraints

### User Registration Validation
- **When**: At the moment of creating a `SolicitudPrestamo`
- **What**: Checks if user has `Empleado` record linked via `usuario` field
- **Error**: Returns 403 Forbidden with descriptive message
- **Message**: "El usuario no está registrado en el sistema RRHH (Recursos Humanos). Contacte al administrador."

### Data Integrity
- `servicio_unidad` field allows `null=True, blank=True` to handle:
  - Legacy records created before this field existed
  - Users registered in RRHH but without unit assignment
  - Future schema flexibility

## Usage Examples

### Creating a Solicitud (User-Initiated)
```python
# In crear_solicitud_api()
servicio_unidad, es_registrado_rrhh = _get_servicio_unidad_from_rrhh(request.user)

if not es_registrado_rrhh:
    # User not in RRHH system
    return JsonResponse({
        "error": "El usuario no está registrado en el sistema RRHH..."
    }, status=403)

solicitud = SolicitudPrestamo.objects.create(
    usuario=request.user,
    motivo=motivo,
    observaciones=observaciones or None,
    area_destino=area_destino or None,
    servicio_unidad=servicio_unidad,  # Automatically assigned
    tiempo_sugerido_horas=tiempo_sugerido_horas,
)
```

### Retrieving Solicitud with Unit Information
```python
# Admin view
solicitudes = SolicitudPrestamo.objects.select_related(
    'usuario',
    'servicio_unidad'
).filter(...)

for solicitud in solicitudes:
    unit_name = solicitud.servicio_unidad.nombre_unidad if solicitud.servicio_unidad else "N/A"
    # Use unit_name in response or display
```

### Using Fallback Property
```python
# If direct field access is not guaranteed
unit = solicitud.get_servicio_unidad  # Returns from field or RRHH chain
```

## Testing Recommendations

### Unit Tests to Implement
1. **Test RRHH Chain Traversal**
   - User with complete chain (Empleado → PersonalNoClinico → Unidad)
   - User with Empleado but no PersonalNoClinico
   - User with PersonalSalud instead of PersonalNoClinico
   - User not in RRHH system

2. **Test API Validation**
   - Creating solicitud with valid RRHH user
   - Attempt to create solicitud with non-RRHH user (should return 403)
   - Verify `servicio_unidad` is correctly populated in response

3. **Test Data Consistency**
   - Stored `servicio_unidad` matches RRHH chain at creation time
   - Historical solicitudes without servicio_unidad still function
   - Fallback property returns correct value

### Manual Testing
1. Create test user in Django auth
2. Create corresponding `Empleado` record
3. Create `PersonalNoClinico` or `PersonalSalud` with a `servicio_unidad`
4. Attempt to create `SolicitudPrestamo` - should succeed with unit assignment
5. Verify `servicio_unidad` appears in API responses

## Performance Considerations

### Database Optimization
- **select_related()**: Used for `usuario` and `servicio_unidad` in list APIs
- **N+1 Prevention**: Foreign key relationships are eagerly loaded
- **Index Consideration**: May benefit from index on `usuario` field in future

### Traversal Complexity
- RRHH chain traversal involves up to 3 OneToOne follows and 1 ForeignKey follow
- Cost is **O(1)** per user (fixed depth relationship chain)
- Acceptable for request-time validation

## Future Enhancements

### Potential Improvements
1. **Cache user's RRHH mapping**: Store in session to avoid repeated traversal
2. **Batch validation**: Pre-validate all users before bulk operations
3. **Admin interface**: Display `servicio_unidad` in Django admin for `SolicitudPrestamo`
4. **Audit logging**: Track which users couldn't be resolved in RRHH
5. **Analytics**: Report on solicitudes by service unit (now easy with FK)

### Migration Path
- Current schema supports `null=True` for backward compatibility
- No existing data needs alteration
- Can gradually migrate old records to populate `servicio_unidad`

## Related Files

### Modified Files
- `s_exp/models.py`: Added `servicio_unidad` field to `SolicitudPrestamo`
- `s_exp/views.py`: 
  - Added `_get_servicio_unidad_from_rrhh()` function
  - Updated `crear_solicitud_api()` to validate and populate unit
  - Updated `listar_solicitudes_api()` and `mis_solicitudes_api()` to include unit in responses
  - Added `get_servicio_unidad` property to `SolicitudPrestamo`

### Migration Files
- `s_exp/migrations/0012_add_servicio_unidad_to_solicitud.py`: Adds field to database

### Model Dependencies
- `rrhh.models.Empleado`: User link point
- `rrhh.models.PersonalNoClinico`: Administrative staff unit assignment
- `rrhh.models.PersonalSalud`: Clinical staff unit assignment
- `servicio.models.Unidad`: Service unit definition

## Troubleshooting

### User Can't Create Solicitud (403 Error)
**Possible Cause**: User not registered in RRHH

**Solution**:
1. Check `rrhh_empleado` table for `usuario_id = user.id`
2. Check `rrhh_personalnoclinico` for `empleado_id`
3. Check `servicio.Unidad` assignment in `rrhh_personalnoclinico.servicio_unidad_id`
4. Create missing RRHH records if needed

### Solicitud Created But `servicio_unidad` is NULL
**Possible Cause**: User in RRHH but no unit assigned

**Solution**:
1. Check if `rrhh_personalnoclinico.servicio_unidad_id` is NULL
2. Assign a service unit to the PersonalNoClinico record
3. New solicitudes will capture the unit after assignment

### N+1 Queries in API
**Check**: Ensure `.select_related('servicio_unidad')` is used in querysets
**Verify**: Use Django Debug Toolbar to profile query counts

---

**Implementation Date**: 2026-05-07
**Version**: 1.0
**Status**: Production Ready
