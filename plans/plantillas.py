"""Paquetes recomendados (plantillas por defecto) del cotizador de planos.

Agrupan el catálogo en opciones listas para cargar, adaptadas al tipo de
proyecto (RES/COM/IND) y a la opción integral (eléctrico + electrónico).

Todo es configurable desde Parámetros del motor (PlanParametro) — nada queda
quemado en el código:
    PAQUETE_EL       → entregables del paquete eléctrico base
    PAQUETE_ELEC     → bloque electrónico (data/CCTV/alarma)
    PAQUETE_COM_EXTRA→ ítem extra que se suma en proyectos comerciales
    PAQUETE_IND_EXTRA→ ítem extra que se suma en proyectos industriales
    M2_POR_LAMINA    → área promedio cubierta por cada lámina de planta

Las cantidades sugeridas se calculan según los factores del proyecto
(área m², nº tableros y nº circuitos).
"""
from decimal import Decimal
from math import ceil

from .models import Entregable, PlanParametro
from . import pricing

PLANTILLA_BASE = [
    'PLAN-LEV-001',  # Levantamiento eléctrico en sitio
    'PLAN-LAM-001',  # Lámina de planta (cantidad según área)
    'PLAN-TAB-001',  # Diseño de tablero de distribución
    'PLAN-UNI-001',  # Diagrama unifilar
    'PLAN-UNI-002',  # Estudio de cargas y demanda EEQ/NEC 220
    'PLAN-MEM-001',  # Memoria descriptiva y de cálculo
    'PLAN-MEM-002',  # Especificaciones técnicas
    'PLAN-FIR-001',  # Firma y sello profesional
]

PLANTILLA_ELECTRONICA = [
    'PLAN-LEV-002',  # Levantamiento electrónico en sitio
    'PLAN-RED-001',  # Red estructurada por m²
    'PLAN-CCTV-001',  # CCTV por m²
    'PLAN-ALA-001',  # Alarma de intrusión/incendio por m²
]

PLANTILLA_COM_EXTRA = [
    'PLAN-LAM-002',  # Lámina de detalle
    'PLAN-RED-002',  # Certificación cuarto de telecomunicaciones
]

PLANTILLA_IND_EXTRA = [
    'PLAN-TAB-002',  # Diseño de tablero general (TG)
    'PLAN-APU-001',  # Presupuesto referencial de obra (APU)
    'PLAN-VFU-001',  # Visita técnica fuera de la ciudad
]

LAMINAS_POR_M2 = 150  # cada lámina de planta cubre ~150 m² (fallback)


def _lector(clave, fallback):
    """Códigos de un paquete desde PlanParametro (editable), con fallback."""
    fila = PlanParametro.objects.filter(clave=clave).first()
    if not fila or not fila.valor:
        return list(fallback)
    return [c.strip().upper() for c in str(fila.valor).replace(';', ',').split(',')
            if c.strip()]


def _unicos(cods):
    seen, out = set(), []
    for c in cods:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def plantilla_el():
    return _lector('PAQUETE_EL', PLANTILLA_BASE)


def plantilla_elec():
    return _lector('PAQUETE_ELEC', PLANTILLA_ELECTRONICA)


def plantilla_com_extra():
    return _lector('PAQUETE_COM_EXTRA', PLANTILLA_COM_EXTRA)


def plantilla_ind_extra():
    return _lector('PAQUETE_IND_EXTRA', PLANTILLA_IND_EXTRA)


def _codigos(opcion, tipo, integral):
    base = plantilla_el()
    elec = plantilla_elec()
    if opcion == 'elec':
        return _unicos(base + elec)
    if opcion == 'integral':
        return _unicos(base + elec)
    if opcion == 'ind':
        cods = _unicos(base + plantilla_ind_extra())
        if integral:
            cods = _unicos(cods + elec)
        return cods
    # opcion 'el': eléctrico base ajustado al tipo de proyecto
    cods = _unicos(base)
    if tipo == 'COM':
        cods = _unicos(cods + plantilla_com_extra())
    elif tipo == 'IND':
        cods = _unicos(cods + plantilla_ind_extra())
    return cods


def opciones_plantilla():
    return [
        ('el', 'Eléctrico base',
         'Levantamiento, láminas, tablero de distribución, unifilar, estudio de '
         'cargas, memorias, especificaciones y firma. Se ajusta al tipo (comercial '
         'e industrial suman sus ítems extra). Editable con PAQUETE_EL / extras.'),
        ('elec', 'Eléctrico + electrónico (data/CCTV/alarma)',
         'Paquete eléctrico base más el bloque electrónico completo. Editable con '
         'PAQUETE_EL + PAQUETE_ELEC.'),
        ('integral', 'Integral con descuento sobre electrónico',
         'Paquete completo (base + electrónico) aplicando el descuento integral '
         'al bloque data/CCTV/alarma cuando el proyecto es integral. Editable con '
         'PAQUETE_EL / PAQUETE_ELEC.'),
        ('ind', 'Industrial completo',
         'Eléctrico base con tablero general (TG), visita fuera de ciudad y '
         'presupuesto referencial (APU); suma el bloque electrónico si el '
         'proyecto es integral. Editable con PAQUETE_IND_EXTRA.'),
    ]


def recomendada_opcion(tipo, integral):
    """Opción destacada por defecto según tipo de proyecto e integral."""
    if integral:
        return 'integral'
    if tipo == 'IND':
        return 'ind'
    return 'el'


def entregables_plantilla(opcion, tipo='RES', integral=False):
    """Entregables activos de una plantilla, en el orden del paquete."""
    operadas = _codigos(opcion, tipo, integral)
    objetos = {e.codigo: e for e in
               Entregable.objects.filter(codigo__in=operadas, activa=True)}
    return [objetos[c] for c in operadas if c in objetos]


def paquetes_info(tipo='COM', integral=False):
    """Composición actual de cada paquete (para mostrarla en Parámetros)."""
    return [
        {'opcion': key, 'nombre': nombre, 'descripcion': desc,
         'codigos': _codigos(key, tipo, integral)}
        for key, nombre, desc in opciones_plantilla()
    ]


def cantidad_para(entregable, cotizacion):
    """Cantidad recomendada del entregable (m² → láminas estimadas, etc.)."""
    if entregable.codigo == 'PLAN-LAM-001' and getattr(cotizacion, 'area_m2', None):
        area = Decimal(str(cotizacion.area_m2 or 0))
        m2_por_lamina = pricing.param('M2_POR_LAMINA', str(LAMINAS_POR_M2))
        if m2_por_lamina <= 0:
            m2_por_lamina = Decimal(str(LAMINAS_POR_M2))
        if area > 0:
            return Decimal(max(1, ceil(float(area) / float(m2_por_lamina))))
    return pricing.cantidad_sugerida(entregable, cotizacion)