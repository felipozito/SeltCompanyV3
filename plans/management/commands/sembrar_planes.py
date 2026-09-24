"""Seed del Cotizador de Planos: catálogo de entregables eléctricos/electrónicos
y parámetros del motor de precios con valores referenciales del mercado
ecuatoriano (2026, USD). Todo es editable desde el CRM/admin.

Uso:
    python manage.py sembrar_planes [--force]
      --force re-aplica valores base sobre los parámetros ya existentes.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from plans.models import Entregable, PlanParametro

# (codigo, categoria, nombre, descripcion, precio_base, unidad)
ENTREGABLES = [
    ('PLAN-LEV-001', 'LEV', 'Levantamiento eléctrico en sitio (as-built)',
     'Relevamiento de instalaciones existentes, medidas y cuadro de cargas real.', Decimal('45.00'), 'VIS'),
    ('PLAN-LEV-002', 'LEV', 'Levantamiento electrónico / comunicaciones en sitio',
     'Puntos de datos, CCTV, alarmas y bandejas/ductos existentes.', Decimal('50.00'), 'VIS'),
    ('PLAN-VFU-001', 'VFU', 'Visita técnica fuera de la ciudad',
     'Jornada completa (2 técnicos) con traslado desde Quito.', Decimal('180.00'), 'VIS'),
    ('PLAN-ANT-001', 'ANT', 'Anteproyecto conceptual eléctrico / electrónico',
     'Esquemas base, matriz de locales y alternativas para validar con el cliente.', Decimal('120.00'), 'UN'),
    ('PLAN-LAM-001', 'LAM', 'Lámina planimétrica de planta con instalaciones',
     'Planta arquitectónica con lay-out de iluminación, tomas y circuitos.', Decimal('25.00'), 'LAM'),
    ('PLAN-LAM-002', 'LAM', 'Lámina de detalle',
     'Detalle de tablero, acometida, medidor, empalmes y bandejas.', Decimal('30.00'), 'LAM'),
    ('PLAN-TAB-001', 'TAB', 'Diseño de tablero de distribución (TD)',
     'Banco de circuitos, carga por circuito y breaker (NEC 210/240).', Decimal('45.00'), 'TBL'),
    ('PLAN-TAB-002', 'TAB', 'Diseño de tablero general (TG)',
     'Esquema de alimentador principal, subalimentadores y protección general.', Decimal('65.00'), 'TBL'),
    ('PLAN-UNI-001', 'UNI', 'Diagrama unifilar',
     'Unifilar general de alimentadores, ramales y contactos con referencia cruzada.', Decimal('85.00'), 'UN'),
    ('PLAN-UNI-002', 'UNI', 'Estudio de cargas y demanda (planilla EEQ / NEC 220)',
     'Planilla de determinación de demandas en formato EEQ e informe de cálculo.', Decimal('90.00'), 'UN'),
    ('PLAN-MEM-001', 'MEM', 'Memoria descriptiva y memoria de cálculo',
     'Justificación técnica, normativa aplicable, cálculos y conclusiones.', Decimal('110.00'), 'UN'),
    ('PLAN-MEM-002', 'MEM', 'Especificaciones técnicas de materiales',
     'Fichas de materiales y equipos conforme NEC y fabricantes.', Decimal('60.00'), 'UN'),
    ('PLAN-FIR-001', 'FIR', 'Firma y sello del profesional responsable',
     'Suscribe planos, memoria y cálculo con registro profesional vigente.', Decimal('60.00'), 'UN'),
    ('PLAN-RED-001', 'RED', 'Diseño de red estructurada (data/voz) por m²',
     'Cableado UTP categoría 6, canalización, patch panels y puntos de red.', Decimal('0.60'), 'M2'),
    ('PLAN-RED-002', 'RED', 'Certificación de canalización / cuarto de telecomunicaciones',
     'Verificación de rutas, largos máximos y diseño del rack/patch panels.', Decimal('40.00'), 'UN'),
    ('PLAN-CCTV-001', 'CCTV', 'Diseño de CCTV por m²',
     'Cobertura, selección de cámaras, alimentación y grabación (NVR).', Decimal('0.50'), 'M2'),
    ('PLAN-ALA-001', 'ALA', 'Diseño de alarma de intrusión / incendio por m²',
     'Zonas de detección, central, dispositivos y planos de evacuación.', Decimal('0.35'), 'M2'),
    ('PLAN-APU-001', 'APU', 'Presupuesto referencial de obra (APU / rubros)',
     'Análisis de precios unitarios, rubros, cantidades y resumen por partidas.', Decimal('400.00'), 'UN'),
    ('PLAN-DIG-001', 'DIG', 'Digitalización e impresión de planos por lámina',
     'Plotter y formato digital de archivo para entrega al cliente/distribuidora.', Decimal('4.00'), 'LAM'),
]

PARAMETROS = [
    ('RECARGO_RES', 'Recargo por tipo de proyecto: residencial', '0.00', '%'),
    ('RECARGO_COM', 'Recargo por tipo de proyecto: comercial', '10.00', '%'),
    ('RECARGO_IND', 'Recargo por tipo de proyecto: industrial', '30.00', '%'),
    ('DESCUENTO_INTEGRAL', 'Descuento a entregables electrónicos en proyecto integral', '10.00', '%'),
    ('IVA_PLANOS', 'Impuesto al valor agregado aplicado en la propuesta', '15.00', '%'),
    ('PORCENTAJE_ANTICIPO', 'Anticipo solicitado para iniciar la elaboración', '60.00', '%'),
    ('VIGENCIA_DIAS', 'Duración de la oferta comercial', '15.00', 'días'),
    ('PAQUETE_EL', 'Paquete recomendado: eléctrico base (códigos de entregables)', (
        'PLAN-LEV-001,PLAN-LAM-001,PLAN-TAB-001,PLAN-UNI-001,PLAN-UNI-002,'
        'PLAN-MEM-001,PLAN-MEM-002,PLAN-FIR-001'), 'códigos'),
    ('PAQUETE_ELEC', 'Paquete recomendado: bloque electrónico data/CCTV/alarma (códigos)', (
        'PLAN-LEV-002,PLAN-RED-001,PLAN-CCTV-001,PLAN-ALA-001'), 'códigos'),
    ('PAQUETE_COM_EXTRA', 'Ítems extra del paquete en proyectos comerciales (códigos)', (
        'PLAN-LAM-002,PLAN-RED-002'), 'códigos'),
    ('PAQUETE_IND_EXTRA', 'Ítems extra del paquete en proyectos industriales (códigos)', (
        'PLAN-TAB-002,PLAN-APU-001,PLAN-VFU-001'), 'códigos'),
    ('M2_POR_LAMINA', 'Área promedio cubierta por cada lámina de planta', '150.00', 'm²'),
]


class Command(BaseCommand):
    help = 'Siembra el catálogo de entregables y parámetros del cotizador de planos.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Re-aplica los valores base sobre parámetros existentes.')

    def handle(self, *args, **opts):
        force = opts.get('force')
        for i, (codigo, cat, nombre, desc, precio, unidad) in enumerate(ENTREGABLES):
            Entregable.objects.update_or_create(
                codigo=codigo,
                defaults=dict(
                    categoria=cat, nombre=nombre, descripcion=desc,
                    precio_base=precio, unidad=unidad, editable=True,
                    activa=True, orden=i,
                ),
            )
        for clave, nombre, valor, unidad in PARAMETROS:
            obj, creado = PlanParametro.objects.get_or_create(
                clave=clave,
                defaults=dict(nombre=nombre, valor=valor, unidad=unidad,
                              fuente='Referencial mercado Ecuador 2026',
                              editable=True),
            )
            if not (creado or force):
                continue
            obj.nombre = nombre
            obj.valor = valor
            obj.unidad = unidad
            obj.fuente = 'Referencial mercado Ecuador 2026 (porcentajes / códigos)'
            obj.editable = True
            obj.save()
        self.stdout.write(self.style.SUCCESS(
            f'Catálogo listo: {Entregable.objects.count()} entregables · '
            f'{PlanParametro.objects.count()} parámetros.'))