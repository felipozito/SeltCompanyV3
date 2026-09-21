from django.core.management.base import BaseCommand
from decimal import Decimal
from crm.models import ParametroNorma

PARAMS = [
    ('CAIDA_TENSION_MAX', 'Caída de tensión máxima en alimentadores y ramales', Decimal('3.00'), '%', 'NEC-2023', 'Art. 215.2(A)(1) 210.19', '2025'),
    ('CAIDA_TENSION_TOTAL_MAX', 'Caída de tensión total a la salida más lejana', Decimal('5.00'), '%', 'NEC-2023', 'Art. 215.2/210.19 FPN', '2025'),
    ('CORRIENTE_BREAKER_NOMINAL', 'Capacidad estándar mínima de interruptor (A)', Decimal('15.00'), 'A', 'NEC-2023', 'Art. 240.6', '2025'),
    ('RESISTIVIDAD_COBRE', 'Resistividad del cobre (ohm mm2/m, 75 C)', Decimal('0.0217'), 'ohm mm2/m', 'IEEE 141 / NEC Table 8', 'Table 8', '2025'),
    ('RESISTIVIDAD_ALUMINIO', 'Resistividad del aluminio (ohm mm2/m, 75 C)', Decimal('0.0353'), 'ohm mm2/m', 'IEEE 141 / NEC Table 8', 'Table 8', '2025'),
    ('SECCION_MINIMA_MM2', 'Sección mínima de conductor (mm2)', Decimal('2.50'), 'mm2', 'NEC-2023', 'Art. 250.122', '2025'),
    ('FP_PROYECTO', 'Factor de potencia del proyecto por defecto', Decimal('0.90'), '-', 'NEC-2023', 'Criterio de diseño', '2025'),
    ('DESBALANCE_FASES_MAX', 'Desbalance máximo permitido entre fases', Decimal('10.00'), '%', 'NEC-2023', 'Art. 220.61', '2025'),
]

class Command(BaseCommand):
    help = "Siembra la base normativa de parametros (NEC-2023 / IEEE)."

    def handle(self, *args, **opts):
        for (clave, nombre, valor, unidad, fuente, ref, version) in PARAMS:
            obj, creado = ParametroNorma.objects.update_or_create(
                clave=clave, defaults=dict(nombre=nombre, valor=valor, unidad=unidad,
                fuente=fuente, referencia=ref, version=version))
            self.stdout.write(('CREADO ' if creado else 'EXISTE ') + clave)