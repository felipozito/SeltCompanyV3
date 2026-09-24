"""Genera un estudio de carga demo completo por cada sistema de servicio:
DEMO · Monofásico 120 V / DEMO · Bifásico 120/240 V / DEMO · Trifásico 120/208 V.
Idempotente: si ya existen con esos nombres, los reconstruye."""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from crm.models import CargaNormativa, Client, EstudioCarga, ItemEstudio, Zona

NOMBRES_DEMO = ('DEMO · Monofásico 120 V', 'DEMO · Bifásico 120/240 V', 'DEMO · Trifásico 120/208 V')

PLANES = [
    {
        'nombre': NOMBRES_DEMO[0],
        'servicio': '1F', 'voltaje_fase': Decimal('120.0'),
        'tipo_estudio': 'RES', 'estrato': 'B',
        'zona_urbano_rural': 'URB', 'subestacion_taps': False,
        'numero_usuarios': 8, 'usuarios_proyectados': 2,
        'dap_kw': Decimal('0.000'),
        'zonas': [('ALUMBRADO', [
            ('ILU002', 24), ('ILU-RES-001', 8)]),
            ('COCINA', [('COC002', 1), ('COC004', 1), ('COC007', 1)]),
            ('AGUA / CONFORT', [('CAL-RES-001', 1), ('HVAC001', 3), ('HVAC002', 2)]),
            ('OFICINA', [('ESP001', 1)])],
    },
    {
        'nombre': NOMBRES_DEMO[1],
        'servicio': '2F', 'voltaje_fase': Decimal('120.0'),
        'tipo_estudio': 'COM', 'n_abonados_comercial': 4,
        'zonas': [('ALUMBRADO', [
            ('ILU-RES-010', 30), ('ILU-LIB-001', 1)]),
            ('COCINA', [('COC004', 2), ('COC001', 2)]),
            ('CONFORT', [('HVAC004', 2), ('HVAC005', 1)]),
            ('OFICINA / EV', [('ESP004', 1), ('EV-001', 1)])],
    },
    {
        'nombre': NOMBRES_DEMO[2],
        'servicio': '3F', 'voltaje_fase': Decimal('120.0'),
        'tipo_estudio': 'COM', 'n_abonados_comercial': 6,
        'zonas': [('ALUMBRADO', [
            ('ILU-RES-010', 40), ('ILU-LIB-001', 2)]),
            ('DATA CENTER', [('ESP003', 1), ('ESP004', 1), ('ESP005', 1), ('ESP006', 1)]),
            ('CONFORT', [('HVAC003', 3), ('HVAC004', 4)]),
            ('EV', [('EV-001', 2)])],
    },
]


class Command(BaseCommand):
    help = 'Genera estudios de carga demo completos (1F/2F/3F) para revisar resultados.'

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(is_superuser=True).first()
        cliente, _ = Client.objects.get_or_create(name='Cliente Demo')

        eliminados, _ = EstudioCarga.objects.filter(nombre__in=NOMBRES_DEMO).delete()
        self.stdout.write(f'Eliminados demos previos: {eliminados} objetos')

        for plan in PLANES:
            estudio = EstudioCarga.objects.create(
                nombre=plan['nombre'],
                cliente=cliente,
                servicio=plan['servicio'],
                voltaje_fase=plan['voltaje_fase'],
                creado_por=user,
                tipo_estudio=plan.get('tipo_estudio', 'COM'),
                estrato=plan.get('estrato'),
                zona_urbano_rural=plan.get('zona_urbano_rural', 'URB'),
                subestacion_taps=plan.get('subestacion_taps', False),
                numero_usuarios=plan.get('numero_usuarios', 12),
                usuarios_proyectados=plan.get('usuarios_proyectados', 0),
                dap_kw=plan.get('dap_kw', Decimal('0.000')),
                n_abonados_comercial=plan.get('n_abonados_comercial', 1),
                actividad_tipo='COMERCIAL',
                localizacion='Quito, Ecuador',
                fecha_estudio=datetime.date.today(),
                ingeniero_responsable='Ing. EJEMPLO',
                registro_lp='LP-DEMO-001',
                expediente_eeq='EEQ-DEMO-2026',
            )
            for nombre, cargas in plan['zonas']:
                zona = Zona.objects.create(estudio=estudio, nombre=nombre)
                for codigo, cantidad in cargas:
                    carga = CargaNormativa.objects.filter(activa=True, codigo=codigo).first()
                    if not carga:
                        self.stdout.write(self.style.WARNING(
                            f'  ⚠ Carga no encontrada: {codigo} (se omite)'))
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
            self.stdout.write(self.style.SUCCESS(
                f'  ✔ {estudio.nombre!r} — servicio {estudio.servicio}, '
                f'voltaje fase-neutro {estudio.voltaje_fase} V (línea {estudio.voltaje_linea} V), '
                f'{estudio.items.count()} cargas en {estudio.zonas.count()} zonas'))

        self.stdout.write(self.style.SUCCESS(
            'Estudios demo listos: ábrelos en el detalle, imprime el informe o exporta Excel.'))