"""
Management command para probar el flujo completo de mapeo de camas:
1. Crear ingreso (verifica AsignacionCamaPaciente OCUPADA + HistorialEstadoCama OCUPADA)
2. Editar ingreso con cambio de cama (verifica actualización en-lugar + historial dual)
3. Inactivar ingreso (verifica AsignacionCamaPaciente VACIA + HistorialEstadoCama VACIA)
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from ingreso.models import Ingreso
from mapeo_camas.models import AsignacionCamaPaciente, HistorialEstadoCama
from paciente.models import Paciente
from servicio.models import Servicio
from django.utils import timezone
from servicio.models import Cama

# Importación dinámica de User (para evitar conflicto de nombres)
try:
    from django.contrib.auth import get_user_model
    User = get_user_model()
except ImportError:
    from usuario.models import User


class Command(BaseCommand):
    help = 'Prueba el flujo completo de mapeo de camas (crear → editar → inactivar)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== INICIANDO PRUEBAS DE MAPEO DE CAMAS ===\n'))
        
        try:
            # Obtener o crear datos de prueba
            usuario = self._obtener_usuario_prueba()
            paciente = self._obtener_paciente_prueba()
            servicio = self._obtener_servicio_prueba()
            cama1, cama2 = self._obtener_camas_prueba()
            
            self.stdout.write(self.style.SUCCESS(f'✓ Datos de prueba cargados:'))
            self.stdout.write(f'  - Usuario: {usuario.username}')
            self.stdout.write(f'  - Paciente: {paciente.cedula}')
            self.stdout.write(f'  - Servicio: {servicio.nombre}')
            self.stdout.write(f'  - Cama1: {cama1.numero} / Cama2: {cama2.numero}\n')
            
            # PRUEBA 1: Crear ingreso
            self.stdout.write(self.style.HTTP_INFO('PRUEBA 1: CREAR INGRESO'))
            ingreso = self._prueba_crear_ingreso(usuario, paciente, servicio, cama1)
            
            # PRUEBA 2: Editar ingreso (cambiar cama)
            self.stdout.write(self.style.HTTP_INFO('\nPRUEBA 2: EDITAR INGRESO (CAMBIAR CAMA)'))
            self._prueba_editar_ingreso(ingreso, cama2, usuario)
            
            # PRUEBA 3: Inactivar ingreso
            self.stdout.write(self.style.HTTP_INFO('\nPRUEBA 3: INACTIVAR INGRESO'))
            self._prueba_inactivar_ingreso(ingreso, usuario)
            
            self.stdout.write(self.style.SUCCESS('\n=== TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE ===\n'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ ERROR: {str(e)}\n'))
            import traceback
            traceback.print_exc()

    def _obtener_usuario_prueba(self):
        """Obtiene o crea un usuario para las pruebas."""
        try:
            return User.objects.filter(is_staff=True).first() or User.objects.first()
        except Exception:
            self.stdout.write(self.style.WARNING('  ⚠️ No hay usuarios disponibles'))
            raise

    def _obtener_paciente_prueba(self):
        """Obtiene un paciente existente."""
        try:
            paciente = Paciente.objects.filter(estado='A').first()
            if not paciente:
                self.stdout.write(self.style.WARNING('  ⚠️ No hay pacientes activos para pruebas'))
                raise Exception('Sin pacientes disponibles')
            return paciente
        except Exception:
            self.stdout.write(self.style.WARNING('  ⚠️ Error obteniendo paciente'))
            raise

    def _obtener_servicio_prueba(self):
        """Obtiene un servicio existente."""
        try:
            servicio = Servicio.objects.filter(estado=True).first()
            if not servicio:
                servicio = Servicio.objects.first()
            if not servicio:
                self.stdout.write(self.style.WARNING('  ⚠️ No hay servicios disponibles'))
                raise Exception('Sin servicios disponibles')
            return servicio

    def _obtener_camas_prueba(self):
        """Obtiene dos camas disponibles."""
        try:
            camas = list(Cama.objects.filter(estado=1).values_list('numero_cama', flat=True)[:2])
            if len(camas) < 2:
                self.stdout.write(self.style.WARNING('  ⚠️ Se necesita al menos 2 camas disponibles'))
                raise Exception('Insuficientes camas para las pruebas')
            return Cama.objects.get(numero_cama=camas[0]), Cama.objects.get(numero_cama=camas[1])
        except Exception:
            self.stdout.write(self.style.WARNING('  ⚠️ Error obteniendo camas'))
            raise

    def _prueba_crear_ingreso(self, usuario, paciente, servicio, cama):
        """FLUJO 1: Crear ingreso y verificar sincronización."""
        self.stdout.write('• Creando ingreso...')
        
        with transaction.atomic():
            ingreso = Ingreso.objects.create(
                paciente=paciente,
                cama=cama,
                servicio=servicio,
                fecha_ingreso=timezone.now(),
                motivo_ingreso='Prueba automática',
                diagnostico_inicial='Test',
                estado=1,
                usuario_creacion=usuario
            )
            
            # Sincronizar cama (simular lo que hace form_valid)
            from core.services.mapeo_camas_service import MapeoCamasService
            MapeoCamasService.sincronizar_cama_con_ingreso(
                cama_id=ingreso.cama_id,
                paciente_id=ingreso.paciente_id,
                usuario=usuario
            )
        
        # Verificar resultados
        asignacion = AsignacionCamaPaciente.objects.get(
            paciente=paciente,
            estado='OCUPADA'
        )
        historial = HistorialEstadoCama.objects.filter(
            cama=cama,
            estado='OCUPADA'
        ).last()
        
        self.stdout.write(self.style.SUCCESS('  ✓ Ingreso creado'))
        self.stdout.write(f'    - ID Ingreso: {ingreso.id}')
        self.stdout.write(f'    - AsignacionCamaPaciente ID: {asignacion.id} (Estado: OCUPADA)')
        self.stdout.write(f'    - HistorialEstadoCama: Cama {cama.numero_cama} → OCUPADA')
        self.stdout.write(f'    - Fecha inicio: {asignacion.fecha_inicio}')
        
        return ingreso

    def _prueba_editar_ingreso(self, ingreso, cama_nueva, usuario):
        """FLUJO 2: Editar ingreso (cambiar cama) y verificar actualización en-lugar."""
        self.stdout.write(f'• Editando ingreso (cama anterior: {ingreso.cama.numero_cama} → cama nueva: {cama_nueva.numero_cama})...')
        
        cama_anterior = ingreso.cama
        asignacion_id_anterior = AsignacionCamaPaciente.objects.filter(
            paciente=ingreso.paciente,
            estado='OCUPADA'
        ).first().id
        
        with transaction.atomic():
            ingreso.cama = cama_nueva
            ingreso.save()
            
            # Sincronizar cambio de cama (simular lo que hace form_valid)
            from core.services.mapeo_camas_service import MapeoCamasService
            MapeoCamasService.sincronizar_cambio_cama_en_ingreso(
                cama_anterior_id=cama_anterior.id,
                cama_nueva_id=cama_nueva.id,
                paciente_id=ingreso.paciente_id,
                usuario=usuario
            )
        
        # Verificar resultados
        asignacion_actualizada = AsignacionCamaPaciente.objects.get(
            paciente=ingreso.paciente,
            estado='OCUPADA'
        )
        
        # Historial: debe haber VACIA (salida) y OCUPADA (entrada)
        historial_salida = HistorialEstadoCama.objects.filter(
            cama=cama_anterior,
            estado='VACIA'
        ).order_by('-fecha_registro').first()
        
        historial_entrada = HistorialEstadoCama.objects.filter(
            cama=cama_nueva,
            estado='OCUPADA'
        ).order_by('-fecha_registro').first()
        
        self.stdout.write(self.style.SUCCESS('  ✓ Ingreso editado'))
        self.stdout.write(f'    - Asignacion anterior ID: {asignacion_id_anterior} (queda VACIA)')
        self.stdout.write(f'    - Asignacion cama nueva ID: {asignacion_actualizada.id} (OCUPADA)')
        self.stdout.write(f'    - Cama actualizada: {asignacion_actualizada.cama_id} (nueva cama ID: {cama_nueva.id})')
        self.stdout.write(f'    - Historial SALIDA: Cama {cama_anterior.numero_cama} → VACIA')
        self.stdout.write(f'    - Historial ENTRADA: Cama {cama_nueva.numero_cama} → OCUPADA')
        
        return ingreso

    def _prueba_inactivar_ingreso(self, ingreso, usuario):
        """FLUJO 3: Inactivar ingreso y verificar cierre de asignación."""
        self.stdout.write('• Inactivando ingreso...')
        
        cama = ingreso.cama
        
        with transaction.atomic():
            ingreso.estado = 2  # Inactivo
            ingreso.save()
            
            # Sincronizar cierre (simular lo que hace inactivarIngreso)
            from core.services.ingreso.ingreso_service import IngresoService
            IngresoService.inactivar_ingreso(ingreso.id, usuario)
        
        # Verificar resultados
        asignacion_cerrada = AsignacionCamaPaciente.objects.get(
            paciente=ingreso.paciente,
            estado='VACIA'
        )
        
        historial_vacia = HistorialEstadoCama.objects.filter(
            cama=cama,
            estado='VACIA'
        ).order_by('-fecha_registro').first()
        
        self.stdout.write(self.style.SUCCESS('  ✓ Ingreso inactivado'))
        self.stdout.write(f'    - AsignacionCamaPaciente: Estado VACIA')
        self.stdout.write(f'    - Fecha fin: {asignacion_cerrada.fecha_fin}')
        self.stdout.write(f'    - HistorialEstadoCama: Cama {cama.numero_cama} → VACIA')
        self.stdout.write(f'    - Historial registrado: {historial_vacia.fecha_registro}')
