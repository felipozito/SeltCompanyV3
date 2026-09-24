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
    ('FP_PROYECTO', 'Factor de potencia de la planilla EEQ A-11-D (carga)', Decimal('0.85'), '-', 'EEQ A-11.03', 'A-11-D (FP carga = 0,85)', '2024'),
    ('FP_RESIDENCIAL', 'Factor de potencia en Demanda de Diseño residencial (Ec. 1/2)', Decimal('0.95'), '-', 'EEQ A-11.04', 'Ec. (1) y (2), FP = 0,95', '2024'),
    ('FP_COMERCIAL', 'Factor de potencia en Demanda de Diseño comercial (Ec. 3)', Decimal('0.85'), '-', 'EEQ A-11.04', 'Ec. (3), FP = 0,85', '2024'),
    ('PERDIDAS_TECNICAS_RSD', 'Pérdidas técnicas resistivas red secundaria (DPT = % DMD)', Decimal('3.60'), '%', 'EEQ A-11.04', 'Ec. (1)', '2024'),
    ('PERDIDAS_TECNICAS_CAMARA', 'Pérdidas técnicas en cámara de transformación (DPT = % DMD)', Decimal('1.00'), '%', 'EEQ A-11.04', 'Ec. (2)', '2024'),
    ('FDM_MAX_COMERCIAL', 'Factor de Demanda máximo del usuario comercial representativo', Decimal('0.60'), '-', 'EEQ A-11.03', 'FDM máx 0,6', '2024'),
    ('DESBALANCE_FASES_MAX', 'Desbalance máximo permitido entre fases', Decimal('10.00'), '%', 'NEC-2023', 'Art. 220.61', '2025'),
    ('FACTOR_PROTECCION_RAMAL', 'Protección de ramales vs corriente conectada (continuas)', Decimal('125.00'), '%', 'NEC-2023', 'Art. 210.20', '2025'),
    # A-11.07 Caída máxima de voltaje admisible por componente (urbano/rural · con/sin taps).
    ('CDV_PRIMARIA_URB_SIN', 'Caída máx red primaria urbano (S/E sin taps)', Decimal('3.00'), '%', 'EEQ A-11.07', 'Tabla A-11.07_1', '2024'),
    ('CDV_PRIMARIA_URB_CON', 'Caída máx red primaria urbano (S/E con taps)', Decimal('3.50'), '%', 'EEQ A-11.07', 'Tabla A-11.07_2', '2024'),
    ('CDV_PRIMARIA_RUR_SIN', 'Caída máx red primaria rural (S/E sin taps)', Decimal('3.50'), '%', 'EEQ A-11.07', 'Tabla A-11.07_1', '2024'),
    ('CDV_PRIMARIA_RUR_CON', 'Caída máx red primaria rural (S/E con taps)', Decimal('4.00'), '%', 'EEQ A-11.07', 'Tabla A-11.07_2', '2024'),
    ('CDV_SECUNDARIA_URB_SIN', 'Caída máx red secundaria urbano (S/E sin taps)', Decimal('2.50'), '%', 'EEQ A-11.07', 'Tabla A-11.07_3', '2024'),
    ('CDV_SECUNDARIA_URB_CON', 'Caída máx red secundaria urbano (S/E con taps)', Decimal('3.00'), '%', 'EEQ A-11.07', 'Tabla A-11.07_4', '2024'),
    ('CDV_SECUNDARIA_RUR_SIN', 'Caída máx red secundaria rural (S/E sin taps)', Decimal('3.00'), '%', 'EEQ A-11.07', 'Tabla A-11.07_3', '2024'),
    ('CDV_SECUNDARIA_RUR_CON', 'Caída máx red secundaria rural (S/E con taps)', Decimal('3.50'), '%', 'EEQ A-11.07', 'Tabla A-11.07_4', '2024'),
    # A-11-B1 Factores de coincidencia FCn (1–4 usuarios).
    ('FC_COINCIDENCIA_1', 'Factor de coincidencia 1 usuario (Apéndice A-11-B1)', Decimal('100.00'), '%', 'EEQ A-11-B1', 'FC1 = 1', '2024'),
    ('FC_COINCIDENCIA_2', 'Factor de coincidencia 2 usuarios (Apéndice A-11-B1)', Decimal('80.00'), '%', 'EEQ A-11-B1', 'FC2 = 0,8', '2024'),
    ('FC_COINCIDENCIA_3', 'Factor de coincidencia 3 usuarios (Apéndice A-11-B1)', Decimal('73.30'), '%', 'EEQ A-11-B1', 'FC3 = 0,733', '2024'),
    ('FC_COINCIDENCIA_4', 'Factor de coincidencia 4 usuarios (Apéndice A-11-B1)', Decimal('70.00'), '%', 'EEQ A-11-B1', 'FC4 = 0,7', '2024'),
]

class Command(BaseCommand):
    help = "Siembra la base normativa de parametros (NEC-2023 / IEEE)."

    def handle(self, *args, **opts):
        for (clave, nombre, valor, unidad, fuente, ref, version) in PARAMS:
            obj, creado = ParametroNorma.objects.update_or_create(
                clave=clave, defaults=dict(nombre=nombre, valor=valor, unidad=unidad,
                fuente=fuente, referencia=ref, version=version))
            self.stdout.write(('CREADO ' if creado else 'EXISTE ') + clave)