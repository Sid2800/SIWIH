from django.db.models import F
from servicio.models import Cama

print('=== CAMA 508 ===')
cama = Cama.objects.select_related('sala__servicio','cubiculo__sala__servicio').filter(numero_cama=508).first()

if cama is None:
    print('No se encontro cama con numero_cama=508')
else:
    print(f"Cama pk={cama.pk}, numero_cama={cama.numero_cama}")
    print(f"Sala directa: id={getattr(cama.sala,'id',None)}, nombre={getattr(cama.sala,'nombre',None)}, servicio_id={getattr(getattr(cama.sala,'servicio',None),'id',None)}, servicio_nombre={getattr(getattr(cama.sala,'servicio',None),'nombre',None)}")
    print(f"Sala via cubiculo: id={getattr(getattr(cama.cubiculo,'sala',None),'id',None)}, nombre={getattr(getattr(cama.cubiculo,'sala',None),'nombre',None)}, servicio_id={getattr(getattr(getattr(cama.cubiculo,'sala',None),'servicio',None),'id',None)}, servicio_nombre={getattr(getattr(getattr(cama.cubiculo,'sala',None),'servicio',None),'nombre',None)}")
    print(f"Cubiculo de la cama: id={getattr(cama.cubiculo,'id',None)}, numero={getattr(cama.cubiculo,'numero',None)}, nombre={getattr(cama.cubiculo,'nombre',None)}")

print('\n=== INCONSISTENCIAS GLOBALES (top 20) ===')
qs = Cama.objects.select_related('sala','cubiculo__sala').filter(cubiculo_id__isnull=False).exclude(sala_id=F('cubiculo__sala_id'))
print(f"Total inconsistencias: {qs.count()}")
for c in qs.order_by('numero_cama','pk')[:20]:
    print(f"numero_cama={c.numero_cama} | cama_pk={c.pk} | sala_directa={getattr(c.sala,'nombre',None)}(id={c.sala_id}) | sala_cubiculo={getattr(getattr(c.cubiculo,'sala',None),'nombre',None)}(id={getattr(c.cubiculo,'sala_id',None)})")
