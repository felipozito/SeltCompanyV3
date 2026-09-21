"""Seed del catálogo normativo de cargas desde la base informativa xlsx.

Uso:
    python manage.py sembrar_catalogo --xlsx Catalogo_Cargas_Ecuador_V2_250_Cargas_Base.xlsx \
        [--reset] [--dry-run]

Mapeo (xlsx CATALOGO_DE_CARGAS -> CargaNormativa):
  0 Codigo          -> codigo
  1 Categoria       -> categoria   (Iluminación->ILU, Tomacorrientes->TOM,
                                    Electrodomésticos->ELE, Motores->MOT,
                                    HVAC->HVAC, Comercial->COM, Industrial->IND,
                                    Especiales->COM, EV->EV, Solar->SOL)
  2 Equipo          -> equipo
  3 Unidad          -> unidad      (W / VA / kW / HP)
  4 Potencia        -> potencia
  5 Factor_Demanda  -> factor_demanda  (decimal 0-1 -> %  x100)
  6 Factor_Potencia -> factor_potencia
  7 Voltaje         -> voltaje     ("120V" -> "120 V")
  8 Fases           -> fases       (1F / 3F)
  9 Tipo_Carga      -> tipo_carga  (Electronica->RES, Inductiva->IND, Motor->MOT)
 10 Circuito_Rec.   -> obs_tecnica ("Circuito recomendado: ...")
 11 Referencia_NEC  -> metodo_calculo  (NEC 220, NEC 430...)
 12 Fuente          -> obs_tecnica (añadido como "Fuente: ...")
 13 Editable        -> editable    (SI -> True)
 14 Observaciones   -> obs_tecnica

Sin categoría mapeada -> 'COM' (Comercial) con advertencia.
"""
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from crm.models import CargaNormativa, DistribuidoraNEC, Norma

CATEGORIA_MAP = {
    'Iluminacion': 'ILU', 'Iluminación': 'ILU',
    'Tomacorrientes': 'TOM',
    'Residencial': 'ELE', 'Electrodomesticos': 'ELE', 'Electrodomésticos': 'ELE',
    'Cocina y calentamiento': 'ELE',
    'Motores': 'MOT', 'Motores y bombas': 'MOT',
    'HVAC': 'HVAC', 'Aire acondicionado': 'HVAC', 'Climatizacion': 'HVAC',
    'Comercial': 'COM', 'Oficina': 'COM', 'Especiales': 'COM',
    'Industrial': 'IND', 'Industria': 'IND',
    'EV': 'EV', 'Carga EV': 'EV', 'Solar': 'SOL', 'Residencial-Solar': 'SOL',
}
TIPO_MAP = {
    'Electronica': 'RES', 'Electrónica': 'RES', 'Electronico': 'RES',
    'Inductiva': 'IND', 'Inductivo': 'IND',
    'Motor': 'MOT', 'Motriz': 'MOT',
}
UNIDAD_MAP = {'W': 'W', 'kW': 'kW', 'VA': 'VA', 'kVA': 'kVA', 'HP': 'HP'}
VOLT_MAP = {'120V': '120 V', '220V': '220 V', '240V': '240 V', '440V': '440 V',
            '120/240': '120/240 V', '120/208': '120/208 V', '208V': '208 V'}


def _dec(v, fallback):
    try:
        return Decimal(str(v).strip())
    except (TypeError, ValueError):
        return fallback


class Command(BaseCommand):
    help = 'Siembra el catálogo normativo de cargas (base informativa xlsx).'

    def add_arguments(self, parser):
        parser.add_argument('--xlsx', default='Catalogo_Cargas_Ecuador_V2_250_Cargas_Base.xlsx')
        parser.add_argument('--reset', action='store_true', help='Borra cargas previas.')
        parser.add_argument('--dry-run', action='store_true', help='Solo muestra el mapeo.')

    def handle(self, *args, **opts):
        try:
            import openpyxl
        except ImportError:
            raise CommandError('openpyxl no está instalado (instálalo en venv).')

        xlsx = Path(settings.BASE_DIR) / opts['xlsx']
        if not xlsx.exists():
            raise CommandError(f'No se encuentra la base: {xlsx}')
        wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
        ws = wb['CATALOGO_CARGAS'] if 'CATALOGO_CARGAS' in wb.sheetnames else wb[wb.sheetnames[0]]
        rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[0]]

        norma, _ = Norma.objects.get_or_create(
            codigo='NEC-2023',
            defaults=dict(version='2023 (NFPA 70)', titulo='Código Eléctrico Nacional',
                          activa=True))
        dist, _ = DistribuidoraNEC.objects.get_or_create(
            nombre='Empresa Eléctrica Quito',
            defaults=dict(provincia='Pichincha', sistema='Monofásica',
                          voltaje_suministro='120/240 V', activa=True))

        if opts['reset'] and not opts['dry_run']:
            CargaNormativa.objects.all().delete()
            self.stdout.write('Catálogo anterior eliminado.')

        total = creadas = 0
        sin_categoria = set()
        for r in rows:
            codigo = str(r[0]).strip()
            categoria = str(r[1]).strip()
            equipo = str(r[2] or '').strip()
            unidad = UNIDAD_MAP.get(str(r[3]).strip(), 'W')
            potencia = _dec(r[4], Decimal('0'))
            fd_dec = _dec(r[5], Decimal('1'))          # 0.75 -> 75 %
            fp_coef = _dec(r[6], Decimal('0.90'))
            volt = VOLT_MAP.get(str(r[7]).strip(), '120 V')
            fases = '3F' if '3' in str(r[8]) else '1F'
            tipo = TIPO_MAP.get(str(r[9]).strip(), 'RES')
            circuito = str(r[10] or '').strip()
            nec = str(r[11] or '').strip()
            fuente = str(r[12] or '').strip()
            editable = str(r[13]).upper().startswith('S')
            obs = str(r[14] or '').strip()

            categoria_cod = CATEGORIA_MAP.get(categoria, 'COM')
            if categoria_cod == 'COM' and categoria not in CATEGORIA_MAP:
                sin_categoria.add(categoria)

            obs_tec = parts = [x for x in (
                f'Circuito recomendado: {circuito}' if circuito else '',
                f'Fuente: {fuente}' if fuente else '',
                obs,
            ) if x]
            obs_tec = ' · '.join(parts)

            defaults = dict(
                categoria=categoria_cod, equipo=equipo or f'Carga {codigo}',
                unidad=unidad, potencia=potencia,
                factor_demanda=(fd_dec * 100).quantize(Decimal('0.01')),
                factor_potencia=fp_coef, voltaje=volt, fases=fases,
                tipo_carga=tipo, metodo_calculo=nec, obs_tecnica=obs_tec,
                editable=editable, activa=True, norma=norma, distribuidora=dist,
            )

            if opts['dry_run']:
                if total < 8:
                    self.stdout.write(
                        f'  [{codigo}] {categoria_cod:4} {equipo[:28]:28} '
                        f'{potencia:>9} {unidad:2} | FD {defaults["factor_demanda"]:>6}% '
                        f'| {volt} {fases} | NEC {nec}')
                total += 1
                continue

            _, creada = CargaNormativa.objects.update_or_create(codigo=codigo, defaults=defaults)
            creadas += int(creada)
            total += 1

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(f'\n[DRY-RUN] {total} cargas mapeadas (no guardadas).'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nCatálogo sembrado: {total} cargas ({creadas} nuevas).'))
        if sin_categoria:
            self.stdout.write(self.style.WARNING(
                f'Categorías sin mapeo (usaron COM): {sorted(sin_categoria)}'))
