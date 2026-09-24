from decimal import Decimal, ROUND_CEILING
import decimal
import re
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from blog.models import BlogPost
from services.models import Service

from . import defaults
from .forms import ClientForm, ProformaForm, ProformaItemFormSet
from .models import (CargaNormativa, Client, ContactLead, DMDResidencial,
                     DistribuidoraNEC, EstudioCarga, FactorDiversidad, HistorialCarga,
                     ItemEstudio, Norma, ParametroNorma, PerfilHorario,
                     Proforma, Zona)

# Mapeo de fases según sistema de servicio (distribución correcta en Ecuador).
DISTRIBUCION_FASES = {
    '1F': {'nombre': 'Monofásico', 'fases': ['A'], 'distribucion': 'A'},
    '2F': {'nombre': 'Bifásico', 'fases': ['A', 'B'], 'distribucion': 'A / B'},
    '3F': {'nombre': 'Trifásico', 'fases': ['A', 'B', 'C'], 'distribucion': 'A / B / C'},
}

# Glosario del formato EEQ (se muestra como leyenda en vista e informe).
GLOSARIO = [
    ('Cant', 'Cantidad de equipos iguales instalados en la zona.'),
    ('Pn (W)', 'Potencia nominal unitaria del equipo, en vatios.'),
    ('FFUn (%)', 'Factor de Funcionamiento Unitario: % de tiempo que opera cada unidad (suele ser 100 %).'),
    ('CIR (W)', 'Carga Instalada Resultante = Pn × Cant × FFUn.'),
    ('FSn (%)', 'Factor de Servicio o simultaneidad: uso esperado de cada tipo de carga (15-70 % típico).'),
    ('DMU (W)', 'Demanda Máxima Unitaria de diseño = CIR × FSn.'),
    ('FDM', 'Factor de Demanda Máxima del tablero = ΣDMU / ΣCIR.'),
    ('DMU (kW)', 'Demanda en kW = ΣDMU(W) / 1000.'),
    ('DMU (kVA)', 'Demanda en kVA = DMU(kW) / FP.'),
    ('FP', 'Factor de Potencia del proyecto (0.90).'),
    ('Demanda Requerida', 'kVA a solicitar a la distribuidora (EEQ) = DMU(kVA).'),
    ('kVA Servicio', 'Demanda requerida redondeada al alza para dimensionar acometida/transformador.'),
    ('Fase', 'Fase de conexión (A en monofásico · A/B bifásico · A/B/C trifásico) — balance de cargas.'),
]

PROFORMA_CONTEXT = {'company': defaults.COMPANY}


@login_required
def dashboard(request):
    context = {
        'contacts_count': ContactLead.objects.count(),
        'clients_count': Client.objects.count(),
        'proformas_count': Proforma.objects.count(),
        'blog_count': BlogPost.objects.count(),
        'services_count': Service.objects.count(),
        'estudios_count': EstudioCarga.objects.count(),
        'latest_contacts': ContactLead.objects.all()[:6],
        'latest_proformas': Proforma.objects.select_related('client').prefetch_related('items')[:6],
    }
    return render(request, 'crm/dashboard.html', context)


@login_required
def leads_list(request):
    leads = ContactLead.objects.all()
    return render(request, 'crm/leads_list.html', {'leads': leads})


@login_required
def clients_list(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente creado correctamente.')
            return redirect('crm:clients')
    else:
        form = ClientForm()

    clients = Client.objects.all()
    return render(request, 'crm/clients_list.html', {'clients': clients, 'form': form})


@login_required
def edit_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente actualizado.')
            return redirect('crm:clients')
    else:
        form = ClientForm(instance=client)
    return render(request, 'crm/edit_client.html', {'form': form, 'client': client})


@login_required
def delete_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        client.delete()
        messages.success(request, 'Cliente eliminado.')
    return redirect('crm:clients')


@login_required
def proformas_list(request):
    proformas = Proforma.objects.select_related('client').prefetch_related('items')
    return render(request, 'crm/proformas_list.html', {'proformas': proformas})


@login_required
def proforma_create(request):
    if request.method == 'POST':
        form = ProformaForm(request.POST)
        formset = ProformaItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            proforma = form.save()
            _save_items(formset, proforma)
            messages.success(request, f'Proforma {proforma.reference} creada.')
            return redirect('crm:proforma_detail', proforma_id=proforma.id)
        messages.error(request, 'Revisa los errores del formulario antes de guardar.')
    else:
        form = ProformaForm()
        formset = ProformaItemFormSet()

    return render(request, 'crm/proforma_form.html', {
        **PROFORMA_CONTEXT,
        'form': form,
        'formset': formset,
        'proforma': None,
    })


@login_required
def proforma_edit(request, proforma_id):
    proforma = get_object_or_404(Proforma, id=proforma_id)
    if request.method == 'POST':
        form = ProformaForm(request.POST, instance=proforma)
        formset = ProformaItemFormSet(request.POST, instance=proforma)
        if form.is_valid() and formset.is_valid():
            form.save()
            _save_items(formset, proforma)
            messages.success(request, 'Proforma actualizada.')
            return redirect('crm:proforma_detail', proforma_id=proforma.id)
        messages.error(request, 'Revisa los errores del formulario antes de guardar.')
    else:
        form = ProformaForm(instance=proforma)
        formset = ProformaItemFormSet(instance=proforma)

    return render(request, 'crm/proforma_form.html', {
        **PROFORMA_CONTEXT,
        'form': form,
        'formset': formset,
        'proforma': proforma,
    })


def _get_proforma(proforma_id):
    return get_object_or_404(
        Proforma.objects.select_related('client').prefetch_related('items'),
        id=proforma_id,
    )


@login_required
def proforma_detail(request, proforma_id):
    return render(request, 'crm/proforma_detail.html', {
        **PROFORMA_CONTEXT,
        'proforma': _get_proforma(proforma_id),
        'auto_print': False,
    })


@login_required
def proforma_print(request, proforma_id):
    return render(request, 'crm/proforma_detail.html', {
        **PROFORMA_CONTEXT,
        'proforma': _get_proforma(proforma_id),
        'auto_print': True,
    })


@login_required
def proforma_delete(request, proforma_id):
    proforma = get_object_or_404(Proforma, id=proforma_id)
    if request.method == 'POST':
        reference = proforma.reference
        proforma.delete()
        messages.success(request, f'Proforma {reference} eliminada.')
    return redirect('crm:proformas')


def _save_items(formset, proforma):
    instances = formset.save(commit=False)
    for deleted in formset.deleted_objects:
        deleted.delete()
    for order, item in enumerate(instances):
        item.proforma = proforma
        item.order = order
        item.save()
    formset.save_m2m()


@login_required
def catalogo_list(request):
    """Catálogo normativo de cargas — 100% server-side (GET + querystring, sin AJAX)."""
    qs = CargaNormativa.objects.select_related('norma', 'distribuidora').all()
    cat = request.GET.get('categoria', '')
    if cat:
        qs = qs.filter(categoria=cat)
    nec = request.GET.get('nec', '')
    if nec:
        qs = qs.filter(metodo_calculo__icontains=nec)
    orden = request.GET.get('orden', 'codigo')
    if orden in ('categoria', 'potencia', 'equipo'):
        qs = qs.order_by(orden, 'codigo')
    else:
        qs = qs.order_by('codigo')
    context = {
        'cargas': qs,
        'categorias': CargaNormativa.CATEGORIA_CHOICES,
        'cat_sel': cat,
        'nec_sel': nec,
        'total': qs.count(),
    }
    return render(request, 'crm/catalogo_list.html', context)


# ============================================================================
# CRUD de CargaNormativa — 100% server-side (POST normal + redirect, sin AJAX).
# Cada cambio crea HistorialCarga (motivo · usuario · fecha) para auditoría.
# ============================================================================


@login_required
def carga_create(request):
    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip()
        equipo = request.POST.get('equipo', '').strip()
        cat = request.POST.get('categoria', 'COM')
        unidad = request.POST.get('unidad', 'W')
        potencia = request.POST.get('potencia', '1800')
        fd = request.POST.get('factor_demanda', '100')
        fp = request.POST.get('factor_potencia', '0.90')
        voltaje = request.POST.get('voltaje', '220 V')
        fases = request.POST.get('fases', '1F')
        nec = request.POST.get('metodo_calculo', '')
        obs = request.POST.get('obs_tecnica', '')

        if codigo and equipo:
            obj, creado = CargaNormativa.objects.get_or_create(
                codigo=codigo,
                defaults=dict(
                    equipo=equipo, categoria=cat, unidad=unidad,
                    potencia=potencia, factor_demanda=fd, factor_potencia=fp,
                    voltaje=voltaje, fases=fases, metodo_calculo=nec,
                    obs_tecnica=obs, editable=True, activa=True,
                    norma=Norma.objects.filter(activa=True).first(),
                    distribuidora=DistribuidoraNEC.objects.filter(activa=True).first(),
                ),
            )
            if creado:
                HistorialCarga.objects.create(
                    carga=obj, campo='creacion', valor_antes='', valor_despues='Nuevo',
                    motivo=request.POST.get('motivo', 'Alta manual del diseñador'),
                    usuario=request.user.get_full_name() or request.user.username,
                )
                messages.success(request, f'Carga {obj.codigo} creada y auditada.')
            else:
                messages.warning(request, f'{obj.codigo} ya existía (no se duplicó).')
        else:
            messages.error(request, 'Código y equipo son obligatorios.')
        return redirect('crm:catalogo')

    context = {
        'form_titulo': 'Agregar carga normalizada',
        'es_editar': False,
        'categorias': CargaNormativa.CATEGORIA_CHOICES,
        'unidades': CargaNormativa.UNIDAD_CHOICES,
        'fases': CargaNormativa.FASES_CHOICES,
        'tipos': CargaNormativa.TIPO_CHOICES,
    }
    return render(request, 'crm/carga_form.html', context)


@login_required
def carga_edit(request, carga_id):
    obj = get_object_or_404(CargaNormativa, id=carga_id)

    if request.method == 'POST':
        antiguo = dict(potencia=str(obj.potencia or ''),
                       factor_demanda=str(obj.factor_demanda or ''),
                       factor_potencia=str(obj.factor_potencia or ''))
        nuevos = dict(
            potencia=request.POST.get('potencia', obj.potencia),
            factor_demanda=request.POST.get('factor_demanda', obj.factor_demanda),
            factor_potencia=request.POST.get('factor_potencia', obj.factor_potencia),
        )
        for campo, valor in nuevos.items():
            setattr(obj, campo, valor)
            if str(valor) != antiguo[campo]:
                HistorialCarga.objects.create(
                    carga=obj, campo=campo,
                    valor_antes=antiguo[campo], valor_despues=str(valor),
                    motivo=request.POST.get('motivo', 'Ajuste de diseño'),
                    usuario=request.user.get_full_name() or request.user.username,
                )
        obj.obs_tecnica = request.POST.get('obs_tecnica', obj.obs_tecnica)
        obj.save()
        messages.success(request, f'{obj.codigo} actualizado (cambios auditados).')
        return redirect('crm:catalogo')

    context = {
        'form_titulo': f'Editar {obj.codigo} · {obj.equipo}',
        'es_editar': True,
        'c': obj,
        'categorias': CargaNormativa.CATEGORIA_CHOICES,
        'unidades': CargaNormativa.UNIDAD_CHOICES,
        'fases': CargaNormativa.FASES_CHOICES,
        'tipos': CargaNormativa.TIPO_CHOICES,
    }
    return render(request, 'crm/carga_form.html', context)


@login_required
@require_POST
def carga_delete(request, carga_id):
    obj = get_object_or_404(CargaNormativa, id=carga_id)
    HistorialCarga.objects.create(
        carga=obj, campo='eliminacion', valor_antes=str(obj.codigo), valor_despues='',
        motivo=request.POST.get('motivo', 'Baja del catálogo'),
        usuario=request.user.get_full_name() or request.user.username,
    )
    obj.delete()
    messages.success(request, f'{obj.codigo} eliminada (baja auditada).')
    return redirect('crm:catalogo')


# ============================================================================
# SIMULADOR DE ESTUDIO DE CARGAS — persistente (EstudioCarga + ItemEstudio)
# Motor NEC Art. 220 server-side (sin AJAX). Los valores del catálogo normativo
# son INMUTABLES; el motor deriva: instalada, demanda (FD), kVA (FP),
# balance de fases y caída de tensión con base normativa parametrizable.
# ============================================================================

def _dec(v, fallback='0'):
    try:
        return Decimal(str(v).strip())
    except (TypeError, ValueError, decimal.InvalidOperation):
        try:
            return Decimal(str(fallback).strip())
        except (TypeError, ValueError, decimal.InvalidOperation):
            return Decimal('0')


def _param(clave, fallback):
    row = ParametroNorma.objects.filter(clave=clave).first()
    return _dec(row.valor, fallback) if row else Decimal(fallback)


def _kw_catalogo(c):
    """kW por defecto desde el catálogo (conversión W/VA/HP → kW, kVA → kW×FP)."""
    if c.unidad == 'kVA':
        return c.potencia * (c.factor_potencia or Decimal('0.90'))
    if c.unidad in ('W', 'VA'):
        return c.potencia / Decimal('1000')
    if c.unidad == 'HP':
        return c.potencia * Decimal('0.746')
    return c.potencia  # kW ya es kW


def _breaker_estandar(amp):
    """Redondea la corriente al breaker comercial estándar inmediato superior
    (NEC 240.6 / EN 60898): 6,10,16,20,25,32,40,50,63,80,100,125,160,200,250,315,400."""
    serie = [6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400]
    for b in serie:
        if Decimal(b) >= amp:
            return b
    return 600


def _simulacion_horaria(estado, perfil_tipo='RES'):
    """Simulación horaria de demanda: aplica el perfil (% de la máxima) a la
    demanda pico por fase. Devuelve curva (24 h), pico, energía diaria y
    factor de carga. La máx del perfil se normaliza a la demanda pico."""
    perfiles = {}
    for p in PerfilHorario.objects.filter(tipo=perfil_tipo):
        perfiles[p.hora] = p.factor
    max_f = max(perfiles.values()) or Decimal('100')
    pico = estado['p_dem']
    curva, energia = [], Decimal('0')
    for h in range(24):
        kw = pico * (_dec(perfiles.get(h, 0), '0') / max_f)
        curva.append({'h': h, 'kw': kw, 'pct': (kw / pico * Decimal('100')) if pico else 0})
        energia += kw
    prom = energia / Decimal('24') if energia else Decimal('0')
    fc = (prom / pico) if pico else Decimal('0')
    return {
        'perfil': perfil_tipo,
        'curva': curva,
        'pico': pico,
        'energia': energia,          # kWh/día (demanda)
        'promedio': prom,
        'factor_carga': fc,
    }


def _tablero(estado, estudio):
    """Diseño del tablero eléctrico (TD-01), un circuito por ítem:
    - Ramal: breaker por la CORRIENTE CONECTADA (S instalada / V_f), con factor
      de protección configurable (NEC 210.20: cargas continuas al 125 %).
    - Principal: protege el alimentador al 125 % de la corriente de SERVICIO
      (demanda DMU, NEC 215.3).
    """
    circuitos, kva_con = [], Decimal('0')
    v_f = estudio.voltaje_fase
    factor_ramal = _param('FACTOR_PROTECCION_RAMAL', '125') / Decimal('100')
    for f in estado['filas']:
        s_inst = (f['inst'] / f['fp']) if f['fp'] else f['inst']    # kVA conectados (placa)
        s_dem = f['kva']                                            # kVA demandados (DMU)
        amp_inst = s_inst * Decimal('1000') / (v_f or Decimal('1'))
        circuitos.append({
            'n': len(circuitos) + 1,
            'codigo': f['codigo'], 'equipo': f['equipo'], 'fase': f['fase'],
            'kva_inst': s_inst, 'kva_dem': s_dem,
            'amp_inst': amp_inst,
            'breaker': _breaker_estandar(amp_inst * factor_ramal),
        })
        kva_con += s_inst
    # principal: 125 % de la corriente de servicio (NEC 215.3) → breaker estándar
    i_srv = estado['corriente']
    principal = _breaker_estandar(i_srv * Decimal('1.25')) if i_srv \
        else _breaker_estandar(kva_con * Decimal('1000') / (v_f or Decimal('1')))
    return {
        'circuitos': circuitos, 'principal': principal, 'kva_total': kva_con,
        'factor_ramal': factor_ramal, 'n': len(circuitos),
    }


def _totales_planilla(filas, servicio, v_f, fp_global):
    """Totales EEQ de una planilla (CIR, DMU, FDM, kVA, corriente).

    La corriente de servicio (por línea) usa el voltaje fase–neutro:
    1F → V_f · bifásico → 2·V_f · trifásico → 3·V_f.
    """
    cir_w = sum(f['cir_w'] for f in filas)
    dmu_w = sum(f['dmu_w'] for f in filas)
    p_inst = sum(f['inst'] for f in filas)
    p_dem = dmu_w / Decimal('1000')
    cir_kw = cir_w / Decimal('1000')
    fdm = (p_dem / cir_kw) if cir_kw else Decimal('0')
    dmu_kva = (p_dem / fp_global) if p_dem else Decimal('0')
    nf = Decimal('3') if servicio == '3F' else (Decimal('2') if servicio == '2F' else Decimal('1'))
    corriente = (p_dem * Decimal('1000')) / (nf * v_f * fp_global) if p_dem else Decimal('0')
    return {
        'cir_w': cir_w, 'dmu_w': dmu_w,
        'p_inst': p_inst, 'p_dem': p_dem, 'cir_kw': cir_kw,
        'fdm': fdm, 'dmu_kw': p_dem, 'dmu_kva': dmu_kva,
        'corriente': corriente,
    }


def _kva_servicio(dmu_kva):
    """Redondea la demanda requerida al alza (paso configurable)."""
    paso = _param('KVA_SERVICIO_REDONDEO', '1')
    if paso <= Decimal('0'):
        paso = Decimal('1')
    return (dmu_kva / paso).to_integral_value(rounding=ROUND_CEILING) * paso


def _cdv_limites(estudio):
    """Caída máxima de voltaje admisible por componente — EEQ A-11.07.
    Devuelve límites de red primaria y secundaria según zona (urbano/rural)
    y S/E con/sin cambiador de taps bajo carga (Tablas A-11.07_1..4)."""
    zona = 'URB'
    if estudio.zona_urbano_rural == 'RUR':
        zona = 'RUR'
    taps = 'CON' if estudio.subestacion_taps else 'SIN'
    prim = _param(f'CDV_PRIMARIA_{zona}_{taps}', '3.0')
    sec = _param(f'CDV_SECUNDARIA_{zona}_{taps}', '2.5')
    return {
        'zona': zona, 'taps': estudio.subestacion_taps,
        'primaria': prim, 'secundaria': sec,
        'total': (prim + sec).quantize(Decimal('0.1')),
    }


def _interpolar(puntos, n):
    """Interpolación lineal sobre {x: y} con extrapolación plana de pendiente."""
    xs = sorted(puntos)
    if not xs:
        return None
    if n <= xs[0]:
        return puntos[xs[0]]
    if n >= xs[-1]:
        if len(xs) >= 2:
            x1, x2 = xs[-2], xs[-1]
            m = (puntos[x2] - puntos[x1]) / Decimal(x2 - x1)
            return puntos[x2] + m * Decimal(n - x2)
        return puntos[xs[-1]]
    for lo, hi in zip(xs, xs[1:]):
        if lo <= n <= hi:
            if hi == lo:
                return puntos[lo]
            y1, y2 = puntos[lo], puntos[hi]
            return y1 + (y2 - y1) * Decimal(n - lo) / Decimal(hi - lo)
    return puntos[xs[-1]]


def _dmd_residencial(estudio):
    """Demanda Máxima Diversificada (kW) — EEQ Tabla A-11.03_1 / Apéndices A-11-B y A-11-B1.

    - 1 a 4 usuarios : DMD = n × FCn × DMU(estrato)      [A-11-B1]
    - n ≥ 5          : DMD = M(n) × N(estrato) → interpolada de la tabla.
    El n usado = usuarios existentes + proyectados (período de diseño A-11.06).
    Devuelve (dmd_kw, detalle) o (None, motivo) si no hay estrato/tabla."""
    estrato = estudio.estrato
    if not estrato:
        return None, 'Sin estrato de consumo definido'
    n = estudio.numero_usuarios + estudio.usuarios_proyectados
    if n < 1:
        n = 1
    filas = {r.numero_usuarios: r.dmd_kw for r in
             DMDResidencial.objects.filter(estrato=estrato).only('numero_usuarios', 'dmd_kw')}
    if not filas:
        return None, f'Sin datos de DMD para estrato {estrato}'
    if n <= 4:
        fc = _param(f'FC_COINCIDENCIA_{n}', '100') / Decimal('100')
        dmu = filas.get(1)
        if dmu is None:
            return None, 'Falta DMU del estrato (fila n=1)'
        dmd = Decimal(n) * fc * dmu
        return dmd.quantize(Decimal('0.001')), (
            f'DMD = n × FCn × DMU = {n} × {fc * 100:.0f}% × {dmu} kW (Apéndice A-11-B1)')
    dmd = _interpolar(filas, n)
    return dmd.quantize(Decimal('0.001')), (
        f'DMD = M(n) × N({estrato}) — interpolada de la Tabla A-11.03_1 para n={n}')


def _fd_comercial(estudio):
    """Factor de diversidad (FD) — EEQ Apéndice A-11-D1. Si el diseñador no lo
    fijó, se toma automático (interpolado) según N; N > 50 → 3,10 (máx)."""
    if estudio.fd_factor_diversidad is not None:
        return estudio.fd_factor_diversidad, False
    n = max(1, estudio.n_abonados_comercial)
    puntos = {r.numero_usuarios: r.factor for r in FactorDiversidad.objects.all()}
    if not puntos:
        return Decimal('1.00'), False
    return _interpolar(puntos, n), True


def _motor_estado(estudio):
    """Deriva el estado calculado de un estudio (carga instalada, demanda,
    CIR/DMU/FSn al formato EEQ, kVA, corrientes, balance de fases, zonas).
    No escribe en BD.

    Asignación de fases: los ítems con fase='' se auto-balancean server-side
    (se asignan a la fase menos cargada de servicio 2F/3F). Los ítems con
    fase manual se respetan.
    """
    servicio = estudio.servicio
    v_f = estudio.voltaje_fase    # tensión fase–neutro (por línea)
    # Distribución de fases: Monofásico→A · Bifásico→A,B · Trifásico→A,B,C
    fases_validas = DISTRIBUCION_FASES[servicio]['fases']
    filas = []
    p_inst = p_dem = kva_total = cir_kw_tot = Decimal('0.00')
    suma_pha = {f: Decimal('0.00') for f in fases_validas}
    fp_global = _param('FP_PROYECTO', '0.85')

    # 0) contenedores por zona (incluye pseudo-zona GENERAL para ítems sin zona)
    zonas = {}
    for z in estudio.zonas.all():
        zonas[z.id] = {'id': z.id, 'nombre': z.nombre, 'filas': []}
    zonas['__general__'] = {'id': None, 'nombre': 'GENERAL', 'filas': []}

    # 1) procesamos todos los ítems y separamos los de fase pendiente (auto)
    pendientes = []
    for it in estudio.items.select_related('carga').order_by('id'):
        ff = it.ffun / Decimal('100')
        fs = it.fsn / Decimal('100')
        pn_w = it.potencia_kw * Decimal('1000')
        cir_w = pn_w * it.cantidad * ff                        # Carga Instalada Resultante
        dmu_w = cir_w * fs                                     # Demanda Máxima Unitaria
        inst_kw = it.potencia_kw * it.cantidad                 # kW instalados
        dem_kw = dmu_w / Decimal('1000')                       # kW demandados
        kva = dem_kw / it.factor_potencia if it.factor_potencia else dem_kw
        amp = (dem_kw * Decimal('1000')) / (v_f * it.factor_potencia) if dem_kw else Decimal('0')
        p_inst += inst_kw
        p_dem += dem_kw
        kva_total += kva
        cir_kw_tot += cir_w / Decimal('1000')
        if it.fase in suma_pha:
            suma_pha[it.fase] += dem_kw
        container = zonas.get(it.zona_id, zonas['__general__'])
        fila = {
            'id': it.id,
            'codigo': it.carga.codigo,
            'equipo': it.carga.equipo,
            'categoria': it.carga.get_categoria_display(),
            'cantidad': it.cantidad,
            'kw': it.potencia_kw,
            'pn_w': pn_w,
            'fd': it.factor_demanda,
            'fp': it.factor_potencia,
            'ff': it.ffun,          # FFUn %
            'fs': it.fsn,           # FSn %
            'fase': it.fase or '.',
            'fase_auto': not it.fase,
            'inst': inst_kw,
            'dem': dem_kw,
            'kva': kva,
            'amp': amp,
            'cir_w': cir_w,
            'dmu_w': dmu_w,
            'zona': container['nombre'],
            'zona_id': it.zona_id,
        }
        container['filas'].append(fila)
        if it.fase:
            filas.append(fila)
        else:
            pendientes.append(fila)

    # 2) auto-asignación: repartir los pendientes en la fase menos cargada.
    # En monofásico solo existe la fase A.
    for fila in sorted(pendientes, key=lambda x: -x['dem']):
        if suma_pha:
            fase_objetivo = min(suma_pha, key=suma_pha.get)
            fila['fase'] = fase_objetivo
            fila['fase_auto'] = True
            suma_pha[fase_objetivo] += fila['dem']
        else:
            fila['fase'] = 'A'
            fila['fase_auto'] = False
        filas.append(fila)

    # 3) balance de fases (2F/3F): diferencia respecto a (total/n_fases)
    alerta = None
    fases = []
    nf = len(fases_validas)
    if nf > 1 and p_dem:
        prom = p_dem / Decimal(nf)
        limite = _param('DESBALANCE_FASES_MAX', '10')  # en % (configurable)
        for f in fases_validas:
            kw = suma_pha.get(f, Decimal('0'))
            desv = (abs(kw - prom) / prom) * Decimal('100') if prom else Decimal('0')
            fases.append({'fase': f, 'kw': kw, 'desv': desv, 'ok': desv <= limite})
        peak = max(suma_pha.values()) if suma_pha else Decimal('0')
        if peak > prom * (Decimal('1') + limite / Decimal('100')):
            alerta = {
                'limite': limite,
                'prom': prom,
                'max': peak,
                'mensaje': 'Desbalance de fases superior al límite configurado. Redistribuye cargas.',
            }

    # 4) totales EEQ por zona y globales
    lista_zonas = []
    for key, z in zonas.items():
        if not z['filas']:
            continue
        z.update(_totales_planilla(z['filas'], servicio, v_f, fp_global))
        lista_zonas.append(z)
    total_gral = _totales_planilla(filas, servicio, v_f, fp_global)

    # ===== Demanda de Diseño (EEQ A-11.03 / A-11.04) =====
    # RES → DMD por estrato + DPT + DAP, Ec. (1)/(2).
    # COM → DD = (DMU × N)/FD, Ec. (3), con FDM ≤ 0,60 (A-11.03).
    fdm = total_gral['fdm']
    dmd_kw = dpt_kw = dap_kw = dd_kw = dd_kva = Decimal('0.000')
    n_abonados = 1
    fd_val = Decimal('1.00')
    fd_auto = False
    fdm_max = _param('FDM_MAX_COMERCIAL', '0.60')
    fdm_ok = (fdm <= fdm_max)
    dd_detalle = ''
    tipo_estudio = estudio.tipo_estudio

    if tipo_estudio == 'RES':
        fp_dd = _param('FP_RESIDENCIAL', '0.95')
        dmd_res, detalle = _dmd_residencial(estudio)
        if dmd_res is None:
            # A-11.02: potestad del diseñador — justificativo por estudio de carga.
            dmd_res = p_dem
            dd_detalle = (f'DMD = demanda por estudio de carga (sin estrato): {p_dem} kW. '
                          f'({detalle})')
        else:
            dd_detalle = detalle
        dmd_kw = dmd_res
        perd_key = 'PERDIDAS_TECNICAS_CAMARA' if estudio.es_camara_transformacion \
            else 'PERDIDAS_TECNICAS_RSD'
        perd = _param(perd_key, '3.6')
        dpt_kw = (dmd_kw * perd / Decimal('100')).quantize(Decimal('0.001'))
        dap_kw = estudio.dap_kw or Decimal('0')
        dd_kw = dmd_kw + dap_kw + dpt_kw
        dd_kva = (dd_kw / fp_dd).quantize(Decimal('0.01'))
        dap_txt = f' + DAP {dap_kw} kW' if dap_kw else ''
        dd_detalle += (f'  ·  DPT = {perd}% × DMD = {dpt_kw} kW{dap_txt}  ·  '
                       f'DD = (DMD+DAP+DPT)/FP = ({dmd_kw}+{dap_kw}+{dpt_kw})/{fp_dd} kVA')
    else:
        fp_dd = _param('FP_COMERCIAL', '0.85')
        n_abonados = max(1, estudio.n_abonados_comercial)
        fd_val, fd_auto = _fd_comercial(estudio)
        dmu_kva = (p_dem / fp_dd) if p_dem else Decimal('0')
        dd_kva = (dmu_kva * Decimal(n_abonados) / fd_val).quantize(Decimal('0.01')) \
            if dmu_kva else Decimal('0')
        dd_kw = p_dem
        dd_detalle = (f'DD = (DMU × N)/FD = ({dmu_kva} kVA × {n_abonados}) / {fd_val}'
                      f'{" (automático A-11-D1)" if fd_auto else ""}')

    kva_servicio = _kva_servicio(dd_kva) if dd_kva else (
        _kva_servicio(total_gral['dmu_kva']) if total_gral['dmu_kva'] else Decimal('0'))

    # dimensionamiento de conductor (aproximación NEC 310.15): con cobre 75 °C.
    # El límite por defecto es la caída máxima de red SECUNDARIA (EEQ A-11.07).
    cdv = _cdv_limites(estudio)
    conductor_req = None
    if p_dem and estudio.conductor_material and estudio.longitud_linea:
        rho = _param('RESISTIVIDAD_COBRE', '0.0217') if estudio.conductor_material == 'Cu' \
              else _param('RESISTIVIDAD_ALUMINIO', '0.0353')
        i_amp = total_gral['corriente']
        L = _dec(estudio.longitud_linea, '30')
        # sección mínima por caída de tensión Ed = (2·I·L·ρ)/S → S = 2·I·L·ρ/ΔV
        dv_max = _dec(estudio.caida_tension_max) or cdv['secundaria'] \
            or _param('CAIDA_TENSION_MAX', '3')
        S = (Decimal('2') * i_amp * L * rho) / dv_max if dv_max else Decimal('0')
        secc = max(S, _param('SECCION_MINIMA_MM2', '2.5'))
        dv_real = (Decimal('2') * i_amp * L * rho) / secc if secc else Decimal('0')
        conductor_req = {
            'secc': secc,
            'material': estudio.conductor_material,
            'dv_real': dv_real,
            'dv_max': dv_max,
            'cumple': dv_real <= dv_max * Decimal('1.01'),
        }

    # ===== Checklist de cumplimiento normativo (cierre del estudio) =====
    checks = []
    checks.append({
        'label': 'Factor de Demanda FDM ≤ 0,60 (A-11.03, comercial)',
        'ok': fdm_ok if tipo_estudio == 'COM' else None,
        'detail': (f'FDM = DMU/CIR = {fdm.quantize(Decimal("0.001"))} (máx {fdm_max}). '
                   f'Baja el FSn (%) de las cargas en la planilla o divide el circuito.'
                   if not fdm_ok and tipo_estudio == 'COM' else
                   f'FDM = DMU/CIR = {fdm.quantize(Decimal("0.001"))} ≤ {fdm_max}. ✔'
                   if tipo_estudio == 'COM' else 'N/A — estudio residencial'),
    })
    checks.append({
        'label': 'Estrato de consumo definido / justificado (A-11.02)',
        'ok': bool(estudio.estrato) if tipo_estudio == 'RES' else None,
        'detail': (f'Estrato {estudio.estrato} · {estudio.numero_usuarios} usuarios'
                   f' (+{estudio.usuarios_proyectados} proy.) '
                   f'= {estudio.numero_usuarios + estudio.usuarios_proyectados} totales'
                   if estudio.estrato else
                   ('Sin estrato — se usa justificativo por estudio de carga.'
                    if tipo_estudio == 'RES' else 'N/A — el estrato aplica a estudios residenciales.')),
    })
    checks.append({
        'label': 'Demanda de Diseño DD calculada (A-11.04)',
        'ok': dd_kva > Decimal('0'),
        'detail': f'DD = {dd_kva} kVA' if dd_kva else 'Sin demanda para calcular DD.',
    })
    checks.append({
        'label': f'Caída de red secundaria ≤ {cdv["secundaria"]} % (A-11.07, {cdv["zona"]})',
        'ok': conductor_req['cumple'] if conductor_req else None,
        'detail': (f'Real {conductor_req["dv_real"].quantize(Decimal("0.01"))} % '
                   f'· límite {conductor_req["dv_max"]} %'
                   if conductor_req else 'Define material y longitud para verificar.'),
    })
    checks.append({
        'label': 'Período de diseño (A-11.06): 15 a. primaria · 10 a. secundaria',
        'ok': True,
        'detail': f'{cdv["primaria"]}% primaria + {cdv["secundaria"]}% secundaria '
                  f'= {cdv["total"]}% total ({"con" if cdv["taps"] else "sin"} taps, zona {cdv["zona"]})',
    })

    return {
        'filas': filas,
        'p_inst': p_inst,
        'p_dem': p_dem,          # DMU inventario (kW)
        'kva': kva_total,
        'dmd_kw': dmd_kw,        # DMD residencial aplicada (kW)
        'dpt_kw': dpt_kw, 'dap_kw': dap_kw, 'dd_kw': dd_kw, 'dd_kva': dd_kva,
        'fp_dd': fp_dd,
        'n_abonados': n_abonados, 'fd': fd_val, 'fd_auto': fd_auto,
        'fdm': fdm, 'fdm_max': fdm_max, 'fdm_ok': fdm_ok,
        'tipo_estudio': tipo_estudio,
        'dd_detalle': dd_detalle,
        'cdv': cdv, 'checks': checks,
        'corriente': total_gral['corriente'],
        'fases': fases, 'alerta': alerta, 'suma_pha': suma_pha,
        'conductor': conductor_req,
        # Totales EEQ (formato GOLDEN)
        'cir_kw': cir_kw_tot,
        'dmu_kva': total_gral['dmu_kva'],
        'kva_servicio': kva_servicio,
        'zonas': lista_zonas,
    }


@login_required
def estudios_list(request):
    """Listado de estudios de carga persistentes."""
    qs = EstudioCarga.objects.select_related('cliente', 'creado_por').order_by('-creado')
    context = {
        'estudios': qs,
        'parametros': ParametroNorma.objects.count(),
        'n_cat': CargaNormativa.objects.count(),
    }
    return render(request, 'crm/estudios_list.html', context)


@login_required
def estudio_create(request):
    """Crea un estudio mínimo (server-side) y va al detalle para llenar inventario."""
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        cliente_id = request.POST.get('cliente', '')
        servicio = request.POST.get('servicio', '1F')
        if not nombre:
            messages.error(request, 'Debes indicar el nombre del estudio.')
        else:
            estudio = EstudioCarga.objects.create(
                nombre=nombre,
                cliente=Client.objects.filter(pk=cliente_id).first() if cliente_id else None,
                servicio=servicio,
                voltaje_fase=_dec(request.POST.get('voltaje', '120'), '120'),
                tipo_estudio=request.POST.get('tipo_estudio', 'COM'),
                zona_urbano_rural='RUR' if request.POST.get('zona_urbano_rural') == 'RUR' else 'URB',
                estrato=request.POST.get('estrato', '').strip() or None,
                creado_por=request.user,
            )
            messages.success(request, f'Estudio «{nombre}» creado. Agrega cargas del catálogo.')
            return redirect('crm:estudio_detail', estudio_id=estudio.id)

    clientes = Client.objects.order_by('name')
    return render(request, 'crm/estudio_form.html', {'clientes': clientes})


@login_required
def estudio_detail(request, estudio_id):
    """Detalle: INVENTARIO DE CARGAS + motor matemático + balance + dimensionamiento."""
    estudio = get_object_or_404(EstudioCarga, id=estudio_id)
    estado = _motor_estado(estudio)

    if request.method == 'POST':
        accion = request.POST.get('accion', '')
        zona_id = _dec(request.POST.get('zona_id'), '0') or 0
        zona_obj = Zona.objects.filter(pk=zona_id, estudio=estudio).first() if int(zona_id) else None
        if accion == 'agregar':
            carga = CargaNormativa.objects.filter(pk=request.POST.get('carga')).first()
            if carga:
                kw_input = request.POST.get('kw', '').strip()
                ff = _dec(request.POST.get('ff') or '100', '100')
                fs = _dec(request.POST.get('fs') or str(carga.factor_demanda), '100')
                ItemEstudio.objects.create(
                    estudio=estudio,
                    carga=carga,
                    zona=zona_obj,
                    cantidad=max(1, int(_dec(request.POST.get('cantidad', '1'), '1'))),
                    potencia_kw=_dec(kw_input, str(_kw_catalogo(carga))) if kw_input else _kw_catalogo(carga),
                    ffun=ff, fsn=fs,
                    factor_potencia=_dec(request.POST.get('fp') or str(carga.factor_potencia), '0.90'),
                    fase=request.POST.get('fase', ''),
                )
                messages.success(request, f'{carga.codigo} agregado al inventario.')
            return redirect('crm:estudio_detail', estudio_id=estudio.id)
        if accion == 'agregar_zona':
            nombre = request.POST.get('zona_nombre', '').strip()
            if nombre:
                estudio.zonas.create(nombre=nombre, orden=estudio.zonas.count())
                messages.success(request, f'Zona «{nombre}» creada. Asigna cargas desde cada fila.')
            else:
                messages.error(request, 'Indica el nombre de la zona (ej.: COCINA, BAR).')
            return redirect('crm:estudio_detail', estudio_id=estudio.id)
        if accion == 'eliminar_zona':
            zona_obj2 = Zona.objects.filter(pk=request.POST.get('zona_id'), estudio=estudio)
            if zona_obj2.exists():
                nombre = zona_obj2.first().nombre
                zona_obj2.first().items.update(zona=None)
                zona_obj2.delete()
                messages.success(request, f'Zona «{nombre}» eliminada (las cargas pasan a GENERAL).')
            return redirect('crm:estudio_detail', estudio_id=estudio.id)
        if accion == 'nuevo_item':
            """Alta libre: crea item desde cero y además guarda la carga en el catálogo
            normativo (CargaNormativa) con auditoría HistorialCarga."""
            equipo = request.POST.get('equipo', '').strip()
            cat = request.POST.get('categoria', 'ELE')
            unidad = request.POST.get('unidad', 'W')
            potencia = _dec(request.POST.get('potencia', '0'), '0')
            kw_default = potencia / Decimal('1000') if unidad in ('W', 'VA') else (
                potencia * Decimal('0.746') if unidad == 'HP' else potencia)
            norma = Norma.objects.first()
            codigo = request.POST.get('codigo', '').strip().upper()
            if not codigo:
                base = f'{cat}-LIB-'
                n = CargaNormativa.objects.filter(codigo__startswith=base).count() + 1
                codigo = f'{base}{n:03d}'
            carga, creada = CargaNormativa.objects.get_or_create(
                codigo=codigo,
                defaults=dict(
                    categoria=cat, equipo=equipo, unidad=unidad, potencia=potencia,
                    factor_demanda=(_dec(request.POST.get('ff') or '100', '100')
                                    * _dec(request.POST.get('fs') or '100', '100')
                                    / Decimal('100')).quantize(Decimal('0.01')),
                    factor_potencia=_dec(request.POST.get('fp') or '0.90', '0.90'),
                    voltaje=request.POST.get('voltaje') or '220 V',
                    fases=request.POST.get('fases', '1F'), norma=norma, editable=True,
                    metodo_calculo='NEC 220 (carga libre)',
                ),
            )
            if not creada:
                messages.warning(request, f'{codigo} ya existía en el catálogo; se reutilizó.')
            else:
                HistorialCarga.objects.create(
                    carga=carga, campo='creacion', valor_despues=codigo,
                    motivo='Alta libre desde estudio de carga', usuario=request.user.get_full_name() or request.user.username,
                )
            ItemEstudio.objects.create(
                estudio=estudio, carga=carga, zona=zona_obj, cantidad=max(1, int(_dec(request.POST.get('cantidad', '1'), '1'))),
                potencia_kw=_dec(request.POST.get('kw') or str(kw_default), '0'),
                ffun=_dec(request.POST.get('ff') or '100', '100'),
                fsn=_dec(request.POST.get('fs') or '100', '100'),
                factor_potencia=_dec(request.POST.get('fp') or '0.90', '0.90'),
                fase=request.POST.get('fase', ''),
            )
            messages.success(request, f'«{equipo}» ({codigo}) agregado y guardado en el catálogo.')
            return redirect('crm:estudio_detail', estudio_id=estudio.id)
        if accion == 'eliminar':
            ItemEstudio.objects.filter(pk=request.POST.get('item')).delete()
            messages.success(request, 'Carga quitada del inventario.')
            return redirect('crm:estudio_detail', estudio_id=estudio.id)
        if accion == 'actualizar_item':
            it = ItemEstudio.objects.filter(pk=request.POST.get('item'), estudio=estudio).first()
            if it:
                kw = request.POST.get('kw', '').strip()
                it.cantidad = max(1, int(_dec(request.POST.get('cantidad', '1'), '1')))
                it.potencia_kw = _dec(kw, str(it.potencia_kw)) if kw else it.potencia_kw
                it.ffun = _dec(request.POST.get('ff') or str(it.ffun), '100')
                it.fsn = _dec(request.POST.get('fs') or str(it.fsn), '100')
                it.factor_potencia = _dec(request.POST.get('fp') or str(it.factor_potencia), '0.90')
                it.fase = request.POST.get('fase', it.fase)
                it.zona = zona_obj
                it.save()
                messages.success(request, f'{it.carga.codigo} actualizado en el inventario.')
            return redirect('crm:estudio_detail', estudio_id=estudio.id)
        if accion == 'guardar_ficha':
            estudio.nombre = request.POST.get('nombre', estudio.nombre).strip() or estudio.nombre
            estudio.servicio = request.POST.get('servicio', estudio.servicio)
            estudio.voltaje_fase = _dec(request.POST.get('voltaje', '120'), '120')
            estudio.conductor_material = request.POST.get('conductor_material', '')
            estudio.longitud_linea = _dec(request.POST.get('longitud', '0'), '0') or None
            estudio.caida_tension_max = _dec(request.POST.get('caida_max', ''), '0') or None
            estudio.localizacion = request.POST.get('localizacion', '').strip()
            estudio.numero_usuarios = max(1, int(_dec(request.POST.get('numero_usuarios', '1'), '1')))
            # Campos EEQ Sección A-11
            tipo_est = request.POST.get('tipo_estudio', 'COM')
            estudio.tipo_estudio = tipo_est if tipo_est in ('RES', 'COM') else 'COM'
            estudio.actividad_tipo = estudio.get_tipo_estudio_display()
            estrato = request.POST.get('estrato', '').strip() or None
            estudio.estrato = estrato if estrato in dict(
                EstudioCarga._meta.get_field('estrato').choices or {}) else None
            estudio.zona_urbano_rural = 'RUR' if request.POST.get('zona_urbano_rural') == 'RUR' else 'URB'
            estudio.subestacion_taps = request.POST.get('subestacion_taps') == 'on'
            estudio.es_camara_transformacion = request.POST.get('es_camara_transformacion') == 'on'
            estudio.usuarios_proyectados = max(0, int(_dec(request.POST.get('usuarios_proyectados', '0'), '0')))
            estudio.dap_kw = _dec(request.POST.get('dap_kw', '0'), '0')
            estudio.n_abonados_comercial = max(1, int(_dec(request.POST.get('n_abonados', '1'), '1')))
            fd_txt = request.POST.get('fd_diversidad', '').strip()
            estudio.fd_factor_diversidad = _dec(fd_txt, '0') or None if fd_txt else None
            estudio.ingeniero_responsable = request.POST.get('ingeniero', '').strip()
            estudio.registro_lp = request.POST.get('registro_lp', '').strip()
            estudio.expediente_eeq = request.POST.get('expediente_eeq', '').strip()
            fecha_txt = request.POST.get('fecha', '').strip()
            if fecha_txt:
                try:
                    estudio.fecha_estudio = datetime.strptime(fecha_txt, '%Y-%m-%d').date()
                except ValueError:
                    pass
            estudio.save()
            messages.success(request, 'Ficha del estudio actualizada.')
            return redirect('crm:estudio_detail', estudio_id=estudio.id)
        if accion == 'simular_curva':
            perfil_tipo = request.POST.get('perfil', 'RES')
            request.session['perfil_activo'] = perfil_tipo
            messages.success(request, f'Curva recalculada con perfil {perfil_tipo}.')
            return redirect('crm:estudio_detail', estudio_id=estudio.id)

    cargas = CargaNormativa.objects.select_related('norma').order_by('categoria', 'codigo')
    perfil_activo = request.session.get('perfil_activo', 'RES')
    if perfil_activo not in dict(PerfilHorario.TIPO_CHOICES):
        perfil_activo = 'RES'
    contexto = {
        'estudio': estudio,
        'estado': estado,
        'zonas': estudio.zonas.all(),
        'fases_disp': DISTRIBUCION_FASES.get(estudio.servicio, DISTRIBUCION_FASES['1F']),
        'cargas': cargas,
        'cargas_meta': {
            c.id: {'kw': _kw_catalogo(c), 'fd': c.factor_demanda, 'fp': c.factor_potencia,
                   'unidad': c.unidad, 'fases': c.get_fases_display(), 'voltaje': c.voltaje,
                   'categoria': c.get_categoria_display()}
            for c in cargas
        },
        'clientes': Client.objects.order_by('name'),
        'cat_choices': dict(CargaNormativa.CATEGORIA_CHOICES),
        'mat_options': [('Cu', 'Cobre'), ('Al', 'Aluminio')],
        'voltajes_posibles': (110, 120, 127, 220),
        'estrato_choices': EstudioCarga._meta.get_field('estrato').choices,
        'tipo_estudio_choices': EstudioCarga._meta.get_field('tipo_estudio').choices,
        'param_fp': _param('FP_PROYECTO', '0.85'),
        'param_dv': _param('CAIDA_TENSION_MAX', '3'),
        'simulacion': _simulacion_horaria(estado, perfil_activo),
        'perfiles': PerfilHorario.TIPO_CHOICES,
        'perfil_activo': perfil_activo,
        'tablero': _tablero(estado, estudio),
        'glosario': GLOSARIO,
    }
    return render(request, 'crm/estudio_detail.html', contexto)


@login_required
@require_POST
def estudio_delete(request, estudio_id):
    """Elimina un estudio de carga (POST, auditoría por mensaje)."""
    estudio = get_object_or_404(EstudioCarga, id=estudio_id)
    nombre = estudio.nombre
    estudio.items.all().delete()
    estudio.delete()
    messages.success(request, f'Estudio «{nombre}» eliminado.')
    return redirect('crm:estudios')


@login_required
def estudio_print(request, estudio_id):
    """Reporte imprimible del estudio (inventario, motor, balance, conductor,
    tablero y simulación horaria) usando el perfil activo de la sesión."""
    estudio = get_object_or_404(EstudioCarga.objects.select_related('cliente', 'creado_por'), id=estudio_id)
    estado = _motor_estado(estudio)
    perfil_activo = request.session.get('perfil_activo', 'RES')
    if perfil_activo not in dict(PerfilHorario.TIPO_CHOICES):
        perfil_activo = 'RES'
    return render(request, 'crm/estudio_print.html', {
        'estudio': estudio,
        'estado': estado,
        'fases_disp': DISTRIBUCION_FASES.get(estudio.servicio, DISTRIBUCION_FASES['1F']),
        'param_fp': _param('FP_PROYECTO', '0.85'),
        'param_dv': _param('CAIDA_TENSION_MAX', '3'),
        'simulacion': _simulacion_horaria(estado, perfil_activo),
        'perfil_activo': perfil_activo,
        'glosario': GLOSARIO,
        'auto_print': True,
    })


@login_required
def estudio_export_excel(request, estudio_id):
    """Exporta el estudio al formato EEQ (GOLDEN): una hoja por zona,
    hoja GENERALTOT, hoja RESUMEN y hoja LEYENDA (glosario de variables)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    estudio = get_object_or_404(EstudioCarga.objects.select_related('cliente', 'creado_por'), id=estudio_id)
    estado = _motor_estado(estudio)
    fp = _param('FP_PROYECTO', '0.85')

    wb = Workbook()
    wb.remove(wb.active)

    negrita = Font(bold=True)
    titulo = Font(bold=True, size=14)
    sub = Font(bold=True, size=11)
    relleno = PatternFill('solid', fgColor='EFEFEF')
    borde = Border(*[Side(style='thin', color='BBBBBB')] * 4)
    ce = Alignment(horizontal='center')
    der = Alignment(horizontal='right')

    def header(ws, hoja_n):
        ws.cell(1, 3, f'hoja {hoja_n} de {len(estado["zonas"]) + 3}')
        ws.cell(2, 3, 'ESTUDIO DE CARGA Y DEMANDA').font = titulo
        ws.cell(3, 3, f'{estudio.nombre}').font = sub
        ws.cell(3, 8, 'FECHA:').font = negrita
        ws.cell(4, 8, estudio.fecha_estudio.strftime('%d/%m/%Y'))
        ws.cell(5, 2, f'NOMBRE DEL PROYECTO:  {estudio.nombre}').font = negrita
        ws.cell(6, 4, f' {estudio.cliente.name if estudio.cliente else ""}')
        ws.cell(7, 2, 'ACTIVIDAD TIPO:').font = negrita
        ws.cell(7, 3, estudio.actividad_tipo or '')
        ws.cell(7, 5, 'LOCALIZACION:').font = negrita
        ws.cell(7, 6, estudio.localizacion or '')
        ws.cell(8, 2, 'ESTRATO (RES):').font = negrita
        ws.cell(8, 3, estudio.estrato or '-')
        ws.cell(9, 2, 'ZONA URB/RUR:').font = negrita
        ws.cell(9, 3, 'URBANA' if estudio.zona_urbano_rural == 'URB' else 'RURAL')
        ws.cell(8, 5, 'NUMERO DE USUARIOS:').font = negrita
        ws.cell(8, 6, float(estudio.numero_usuarios)).alignment = ce

    def planilla(ws, nombre_zona, filas, fila_ini=14):
        """Escribe una planilla EEQ a partir de `fila_ini`. Devuelve fila final."""
        ws.cell(fila_ini, 3, nombre_zona).font = sub
        ws.cell(fila_ini + 2, 1, 'PLANILLA PARA LA DETERMINACION DE DEMANDAS UNITARIAS DE DISEÑO').font = negrita
        encab = fila_ini + 4
        cols = [('RENGLÓN', 0), ('APARATOS ELÉCTRICOS Y DE ALUMBRADO', 1), ('CANT', 2),
                ('Pn (W)', 3), ('FFUn (%)', 4), ('CIR (W)', 5), ('FSn (%)', 6), ('DMU (W)', 7)]
        for texto, c in cols:
            cel = ws.cell(encab, c + 1, texto)
            cel.font = negrita
            cel.fill = relleno
            cel.border = borde
        r = encab + 1
        for i, f in enumerate(filas, 1):
            vals = (i / 1, f['codigo'], f['cantidad'], float(f['pn_w']), float(f['ff']),
                    round(float(f['cir_w']), 1), float(f['fs']), round(float(f['dmu_w']), 1))
            for c, v in enumerate(vals, 1):
                cel = ws.cell(r, c, v)
                cel.alignment = der if c > 2 else None
                cel.border = borde
            ws.cell(r, 2).alignment = Alignment()
            r += 1
        tot = _totales_planilla(filas, estudio.servicio, estudio.voltaje_fase, fp)
        ws.cell(r, 1, 'TOTALES').font = negrita
        ws.cell(r, 6, round(float(tot['cir_w']), 1)).font = negrita
        ws.cell(r, 8, round(float(tot['dmu_w']), 1)).font = negrita
        ws.cell(r + 1, 1, 'Factor de Potencia FP:').font = negrita
        ws.cell(r + 1, 2, float(fp))
        ws.cell(r + 1, 3, 'Factor de Demanda FDM=DMU(w)/CIR(w)').font = negrita
        ws.cell(r + 1, 8, round(float(tot['fdm']), 6))
        ws.cell(r + 2, 1, 'DMU (kW)').font = negrita
        ws.cell(r + 2, 2, round(float(tot['dmu_kw']), 3))
        ws.cell(r + 3, 1, 'DMU (kVA)').font = negrita
        ws.cell(r + 3, 2, round(float(tot['dmu_kva']), 4))
        ws.cell(r + 4, 1, 'Factor de Sobrecarga').font = negrita
        ws.cell(r + 4, 2, float(fp))
        ws.cell(r + 4, 4, 'Demanda Requerida').font = negrita
        ws.cell(r + 4, 6, round(float(tot['dmu_kva']), 4))
        ws.cell(r + 4, 7, 'kVA')
        return r + 5

    def firma(ws, r):
        ws.cell(r, 2, estudio.ingeniero_responsable or 'ING. ______________________')
        ws.cell(r + 1, 2, estudio.registro_lp or 'LP: ____')
        ws.cell(r + 2, 2, estudio.expediente_eeq or 'EEQ-____')

    def recortar(nombre):
        # openpyxl prohíbe  \ / ? * [ ]  y >31 chars en el título de hoja.
        nombre = nombre.upper()
        for c in '\\/?*[]:':
            nombre = nombre.replace(c, '-')
        if len(nombre) > 31:
            nombre = nombre[:31]
        while nombre.endswith(' ') or nombre.endswith('.'):
            nombre = nombre[:-1]
        return nombre or 'ZONA'

    # Hojas por zona
    for idx, z in enumerate(estado['zonas'], 1):
        ws = wb.create_sheet(recortar(z['nombre']))
        header(ws, idx)
        r = planilla(ws, z['nombre'], z['filas'])
        firma(ws, r + 2)

    # GENERALTOT
    ws = wb.create_sheet('GENERALTOT')
    header(ws, len(estado['zonas']) + 1)
    r = planilla(ws, 'GENERAL TOTAL', estado['filas'])
    firma(ws, r + 2)

    # RESUMEN
    ws = wb.create_sheet('RESUMEN')
    header(ws, len(estado['zonas']) + 2)
    ws.cell(14, 1, 'RENGLÓN').font = negrita
    ws.cell(14, 2, 'DESCRIPCION').font = negrita
    ws.cell(14, 8, 'DMU').font = negrita
    ws.cell(15, 2, 'DESCRIPCIÓN').font = negrita
    ws.cell(15, 8, '(kVA)').font = negrita
    r = 16
    for i, z in enumerate(estado['zonas'], 1):
        ws.cell(r, 1, i / 1)
        ws.cell(r, 2, z['nombre'])
        ws.cell(r, 8, round(float(z['dmu_kva']), 4)).alignment = der
        r += 1
    ws.cell(r, 4, 'TOTALES').font = negrita
    ws.cell(r, 8, round(float(estado['dmu_kva']), 4)).font = negrita
    ws.cell(r + 2, 8, f'{int(estado["kva_servicio"])}KVA').font = Font(bold=True, size=14)

    # Bloque Demanda de Diseño (EEQ A-11.04)
    r = r + 5
    ws.cell(r, 4, 'DEMANDA DE DISEÑO (EEQ Sección A-11.04)').font = sub
    r += 1
    if estado['tipo_estudio'] == 'RES':
        ws.cell(r, 2, 'DMD (kW) · Tabla A-11.03_1').font = negrita
        ws.cell(r, 4, round(float(estado['dmd_kw']), 3))
        ws.cell(r + 1, 2, 'DAP · Alumbrado público (kW)').font = negrita
        ws.cell(r + 1, 4, round(float(estado['dap_kw']), 3))
        ws.cell(r + 2, 2, 'DPT · Pérdidas técnicas (kW)').font = negrita
        ws.cell(r + 2, 4, round(float(estado['dpt_kw']), 3))
        ws.cell(r + 3, 2, 'FP (Ec. 1/2)').font = negrita
        ws.cell(r + 3, 4, float(_param('FP_RESIDENCIAL', '0.95')))
    else:
        ws.cell(r, 2, 'N · Abonados que inciden (kN)').font = negrita
        ws.cell(r, 4, int(estado['n_abonados']))
        ws.cell(r + 1, 2, 'FD · Factor de diversidad (A-11-D1)').font = negrita
        ws.cell(r + 1, 4, round(float(estado['fd']), 3))
        ws.cell(r + 2, 2, 'FDM = DMU/CIR (máx 0,60)').font = negrita
        ws.cell(r + 2, 4, round(float(estado['fdm']), 4))
        ws.cell(r + 3, 2, 'FP (Ec. 3)').font = negrita
        ws.cell(r + 3, 4, float(_param('FP_COMERCIAL', '0.85')))
    ws.cell(r + 4, 2, 'DD · Demanda de Diseño (kVA)').font = negrita
    ws.cell(r + 4, 4, round(float(estado['dd_kva']), 2))
    ws.cell(r + 5, 2, 'kVA de Servicio redondeado').font = negrita
    ws.cell(r + 5, 4, round(float(estado['kva_servicio']), 0))
    firma(ws, r + 7)

    # LEYENDA / glosario
    ws = wb.create_sheet('LEYENDA')
    ws.cell(1, 1, 'DEFINICION DE VARIABLES - FORMATO EEQ').font = titulo
    for i, (var, desc) in enumerate(GLOSARIO, 2):
        ws.cell(i, 1, var).font = negrita
        ws.cell(i, 2, desc)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    nombre_archivo = re.sub(r'[^\w]+', '_', estudio.nombre.lower())[:60] or 'estudio'
    response['Content-Disposition'] = f'attachment; filename="estudio_{nombre_archivo}.xlsx"'
    wb.save(response)
    return response
