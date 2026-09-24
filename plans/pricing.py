"""Motor de precios del cotizador de planos eléctricos/electrónicos (Ecuador).

Precio unitario = precio_base (catálogo) × recargo(tipo proyecto) [× descuento integral].

Parámetros en PORCENTAJE con valores por defecto para Ecuador (PlanParametro):
    RECARGO_RES = 0 %   ·  RECARGO_COM = 10 %  ·  RECARGO_IND = 30 %
    DESCUENTO_INTEGRAL = 10 %  (aplicado al bloque electrónico RED/CCTV/ALA)
    IVA_PLANOS = 15 %   ·  PORCENTAJE_ANTICIPO = 60 %  ·  VIGENCIA_DIAS = 15

Cantidad sugerida según unidad del entregable:
    M2  → área del proyecto · TBL → nº tableros · CIR → nº circuitos · resto → 1.
"""
import decimal
from decimal import Decimal

from .models import PlanParametro


def _dec(value, fallback='0'):
    try:
        return Decimal(str(value).strip())
    except (TypeError, ValueError, decimal.InvalidOperation):
        try:
            return Decimal(str(fallback).strip())
        except (TypeError, ValueError, decimal.InvalidOperation):
            return Decimal('0')


def _q2(value):
    return value.quantize(Decimal('0.01'))


def param(clave, fallback):
    row = PlanParametro.objects.filter(clave=clave).first()
    return _dec(row.valor, fallback) if row else _dec(fallback)


def recargo_tipo(tipo_proyecto):
    """Factor de recargo por tipo de proyecto (%), p. ej. COM 10 % → 1,10."""
    pct = param(f'RECARGO_{tipo_proyecto or "RES"}',
                {'RES': '0', 'COM': '10', 'IND': '30'}.get(tipo_proyecto, '0'))
    return (Decimal('100') + pct) / Decimal('100')


def descuento_pct():
    """Descuento integral (%) sobre el bloque electrónico en proyecto integral."""
    return param('DESCUENTO_INTEGRAL', '10')


def descuento_factor():
    """Factor multiplicador equivalente: 10 % → 0,90."""
    return (Decimal('100') - descuento_pct()) / Decimal('100')


def sa_replanteo_factor(cotizacion):
    """Factor por relevamiento arquitectónico (sin plano del arquitecto).

    Sin plano base, el levantamiento en sitio debe replantear la arquitectura:
    se aplica un recargo (RECARGO_SIN_PLANO, % ) sobre los entregables LEV.
    """
    if getattr(cotizacion, 'plano_arquitectonico', True):
        return Decimal('1.00')
    pct = param('RECARGO_SIN_PLANO', '15')
    return (Decimal('100') + pct) / Decimal('100')


def cantidad_sugerida(entregable, cotizacion):
    """Cantidad que se autoasigna al añadir un entregable (dependiente de factores)."""
    if entregable.unidad == 'M2':
        return _dec(cotizacion.area_m2, '0') or Decimal('0')
    if entregable.unidad == 'TBL':
        return Decimal(cotizacion.n_tableros or 0)
    if entregable.unidad == 'CIR':
        return Decimal(cotizacion.n_circuitos or 0)
    return Decimal('1.00')


def precio_unitario(entregable, cotizacion):
    """Precio unitario congelable: base × recargo (× descuento integral si aplica)
    (× recargo por relevamiento sin plano arquitectónico en entregables LEV)."""
    base = _dec(entregable.precio_base, '0')
    unit = _q2(base * recargo_tipo(cotizacion.tipo_proyecto))
    if cotizacion.integral and entregable.es_electronico:
        unit = _q2(unit * descuento_factor())
    if str(entregable.categoria or '').upper() == 'LEV':
        unit = _q2(unit * sa_replanteo_factor(cotizacion))
    return unit


def descripcion_rubro(entregable, cantidad):
    """Texto snapshot del rubro (entregable + unidad, para informe y proforma)."""
    texto = entregable.nombre
    if entregable.descripcion:
        texto = f'{texto} — {entregable.descripcion}'
    unidad = entregable.get_unidad_display()
    return f'{texto}\nCantidad: {_q2(cantidad).normalize()} {unidad}'