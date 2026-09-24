"""Genera un estudio de carga realista de una CASA UNIFAMILIAR (120 V, 1F):
3 dormitorios, cocina, sala, comedor, lavandería y baños, cada uno como zona
(planilla EEQ) con sus cargas típicas. Idempotente."""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from crm.models import CargaNormativa, Client, EstudioCarga, ItemEstudio, Zona

NOMBRE = 'DEMO · Casa Unifamiliar 120 V'

# (codigo, cantidad) por zona. Los códigos que no existan se crean al vuelo.
CASAS = [
    ('DORMITORIO 1', [
        ('RES011', 1),    # Televisor 32"
        ('ILU004', 2),    # Foco LED 15 W
        ('TOM-RES', 4),   # Tomacorriente 180 VA
        ('HVAC001', 1),   # Ventilador de techo
    ]),
    ('DORMITORIO 2', [
        ('RES011', 1),
        ('ILU004', 2),
        ('TOM-RES', 4),
        ('HVAC001', 1),
    ]),
    ('DORMITORIO 3', [
        ('RES012', 1),    # Televisor 55"
        ('ILU004', 2),
        ('TOM-RES', 4),
        ('HVAC001', 1),
    ]),
    ('COCINA', [
        ('RES004', 1),    # Microondas 1200 W
        ('COC003', 1),    # Cocina eléctrica
        ('COC004', 1),    # Horno eléctrico
        ('COC007', 1),    # Campana extractora / extractor de olor
        ('RES002', 1),    # Refrigeradora grande
        ('TOM-RES', 4),
        ('ILU004', 2),
    ]),
    ('SALA', [
        ('ILU004', 5),
        ('TOM-RES', 4),
        ('HVAC004', 1),   # Aire acondicionado 12000 BTU
    ]),
    ('COMEDOR', [
        ('ILU004', 5),
        ('TOM-RES', 5),
    ]),
    ('LAVANDERÍA', [
        ('RES007', 1),    # Lavadora
        ('RES008', 1),    # Secadora de ropa
        ('TOM-RES', 2),
        ('ILU004', 2),
    ]),
    ('BAÑOS', [
        ('COC005', 1),    # Calentador eléctrico de ducha
        ('HVAC002', 1),   # Extractor de baño
        ('ILU004', 1),
    ]),
]

CREAR_NORMA = {
    'TOM-RES': ('Tomacorriente residencial (180 VA)', Decimal('180.0'),
                Decimal('40.0'), Decimal('0.950'), 'RES', 'ELE'),
}


def _carga(codigo):
    carga = CargaNormativa.objects.filter(codigo=codigo).first()
    if carga:
        return carga
    if codigo in CREAR_NORMA:
        equipo, potencia, fd, fp, tipo, cat = CREAR_NORMA[codigo]
        norma = None
        from crm.models import Norma
        norma = Norma.objects.first()
        if not norma:
            norma = Norma.objects.create(
                codigo='NEC-2023', version='2023', titulo='Norma base', activa=True)
        return CargaNormativa.objects.create(
            codigo=codigo, equipo=equipo, potencia=potencia, unidad='W',
            factor_demanda=fd, factor_potencia=fp, tipo_carga=tipo,
            categoria=cat, norma=norma, activa=True)
    return None


class Command(BaseCommand):
    help = 'Crea un estudio de una casa unifamiliar completa (zona por habitación).'

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(is_superuser=True).first()
        cliente, _ = Client.objects.get_or_create(name='Cliente Casa Demo')

        EstudioCarga.objects.filter(nombre=NOMBRE).delete()

        estudio = EstudioCarga.objects.create(
            nombre=NOMBRE,
            cliente=cliente,
            servicio='1F',
            voltaje_fase=Decimal('120.0'),
            creado_por=user,
            actividad_tipo='RESIDENCIAL',
            localizacion='Quito, Ecuador — casa unifamiliar 2 pisos',
            tipo_estudio='RES',
            estrato='A',
            numero_usuarios=4,
            fecha_estudio=datetime.date.today(),
            ingeniero_responsable='Ing. EJEMPLO',
            registro_lp='LP-DEMO-002',
            expediente_eeq='EEQ-DEMO-2026',
        )

        total_items = 0
        for zona_nombre, equipos in CASAS:
            zona = Zona.objects.create(estudio=estudio, nombre=zona_nombre)
            for codigo, cantidad in equipos:
                carga = _carga(codigo)
                if not carga:
                    self.stdout.write(self.style.WARNING(f'  ⚠ omitida: {codigo}'))
                    continue
                ItemEstudio.objects.create(
                    estudio=estudio,
                    zona=zona,
                    carga=carga,
                    cantidad=cantidad,
                    potencia_kw=carga.potencia / Decimal('1000'),
                    ffun=Decimal('100'),
                    fsn=carga.factor_demanda,
                    factor_potencia=carga.factor_potencia,
                )
                total_items += 1
            self.stdout.write(self.style.SUCCESS(f'  ✔ {zona_nombre}: {len(equipos)} equipos'))

        self.stdout.write(self.style.SUCCESS(
            f'Estudio «{NOMBRE}»: {estudio.zonas.count()} zonas, {estudio.items.count()} ítems. '
            f'Ábrelo en el detalle para ver planillas, RESUMEN, tablero y esquema TD-01.'))