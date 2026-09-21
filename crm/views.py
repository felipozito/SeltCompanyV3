from decimal import Decimal
import decimal
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from blog.models import BlogPost
from services.models import Service

from . import defaults
from .forms import ClientForm, ProformaForm, ProformaItemFormSet
from .models import (CargaNormativa, Client, ContactLead, DistribuidoraNEC,
                     EstudioCarga, HistorialCarga, ItemEstudio, Norma, ParametroNorma,
                     PerfilHorario,
                     Proforma)

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
        tipo = request.POST.get('tipo_carga', 'RES')
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
        return Decimal(fallback)


def _param(clave, fallback):
    row = ParametroNorma.objects.filter(clave=clave).first()
    return _dec(row.valor, fallback) if row else Decimal(fallback)


def _kw_catalogo(c):
    """kW por defecto desde el catálogo (conversión W/VA/HP → kW)."""
    if c.unidad in ('W', 'VA'):
        return c.potencia / Decimal('1000')
    if c.unidad == 'HP':
        return c.potencia * Decimal('0.746')
    return c.potencia  # kW / kVA ya son kW


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
    """Diseño del tablero eléctrico (TD-01): cada ítem es un circuito con su
    breaker estandarizado, y el principal protege la corriente de servicio."""
    srv = estudio.servicio
    comp = Decimal('1.732') if srv == '3F' else (Decimal('2') if srv == '2F' else Decimal('1'))
    circuitos, kva = [], Decimal('0')
    for f in estado['filas']:
        amp = f['kva'] * Decimal('1000') / (estudio.voltaje_linea * (comp or Decimal('1')))
        circuitos.append({
            'n': len(circuitos) + 1,
            'codigo': f['codigo'], 'equipo': f['equipo'], 'fase': f['fase'],
            'kva': f['kva'], 'amp': amp, 'breaker': _breaker_estandar(amp),
        })
        kva += f['kva']
    # principal: 125 % de la corriente (NEC 215.3) → breaker estándar
    i_srv = estado['corriente']
    principal = _breaker_estandar(i_srv * Decimal('1.25')) if i_srv else _breaker_estandar(kva * Decimal('1000') / (estudio.voltaje_linea))
    return {'circuitos': circuitos, 'principal': principal, 'kva_total': kva, 'n': len(circuitos)}


def _motor_estado(estudio):
    """Deriva el estado calculado de un estudio (carga instalada, demanda,
    kVA, corrientes, balance de fases). No escribe en BD.

    Asignación de fases: los ítems con fase='' se auto-balancean server-side
    (se asignan a la fase menos cargada de servicio 2F/3F). Los ítems con
    fase manual se respetan.
    """
    servicio = estudio.servicio
    v_ln = estudio.voltaje_linea
    fases_validas = ['A', 'B', 'C'] if servicio == '3F' else (['A', 'B'] if servicio == '2F' else [])
    filas = []
    p_inst = p_dem = kva_total = Decimal('0.00')
    suma_pha = {f: Decimal('0.00') for f in fases_validas}
    # factor por fases en la corriente: 3F→1/√3 · 2F→1/2 · 1F→1
    comp = Decimal('1.732') if servicio == '3F' else (Decimal('2') if servicio == '2F' else Decimal('1'))

    # 1) procesamos todos los ítems y separamos los de fase pendiente (auto)
    pendientes = []
    for it in estudio.items.select_related('carga'):
        inst_kw = it.potencia_kw * it.cantidad                    # kW instalados
        dem_kw = inst_kw * it.factor_demanda / Decimal('100')     # kW demandados
        kva = dem_kw / it.factor_potencia if it.factor_potencia else dem_kw
        amp = (dem_kw * Decimal('1000')) / (comp * v_ln * it.factor_potencia) if dem_kw else Decimal('0')
        p_inst += inst_kw
        p_dem += dem_kw
        kva_total += kva
        if it.fase in suma_pha:
            suma_pha[it.fase] += dem_kw
        fila = {
            'id': it.id,
            'codigo': it.carga.codigo,
            'equipo': it.carga.equipo,
            'categoria': it.carga.get_categoria_display(),
            'cantidad': it.cantidad,
            'kw': it.potencia_kw,
            'fd': it.factor_demanda,
            'fp': it.factor_potencia,
            'fase': it.fase or '.',
            'fase_auto': not it.fase,
            'inst': inst_kw,
            'dem': dem_kw,
            'kva': kva,
            'amp': amp,
        }
        if it.fase:
            filas.append(fila)
        else:
            pendientes.append(fila)

    # 2) auto-asignación: repartir los pendientes en la fase menos cargada.
    # En servicio 1F no hay fases (suma_pha vacío): el ítem queda en línea "L".
    for fila in sorted(pendientes, key=lambda x: -x['dem']):
        if suma_pha:
            fase_objetivo = min(suma_pha, key=suma_pha.get)
            fila['fase'] = fase_objetivo
            fila['fase_auto'] = True
            suma_pha[fase_objetivo] += fila['dem']
        else:
            fila['fase'] = 'L'
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

    kva_srv = kva_total
    corriente_srv = Decimal('0.00')
    if p_dem:
        fp = _param('FP_PROYECTO', '0.9')
        corriente_srv = (p_dem * Decimal('1000')) / (comp * v_ln * fp)

    # dimensionamiento de conductor (aproximación NEC 310.15): con cobre 75 °C
    conductor_req = None
    if p_dem and estudio.conductor_material and estudio.longitud_linea:
        rho = _param('RESISTIVIDAD_COBRE', '0.0217') if estudio.conductor_material == 'Cu' \
              else _param('RESISTIVIDAD_ALUMINIO', '0.0353')
        i_amp = corriente_srv
        L = _dec(estudio.longitud_linea, '30')
        # sección mínima por caída de tensión Ed = (2·I·L·ρ)/S → S = 2·I·L·ρ/ΔV
        dv_max = _dec(estudio.caida_tension_max, '3') or _param('CAIDA_TENSION_MAX', '3')
        S = (Decimal('2') * i_amp * L * rho) / dv_max if dv_max else Decimal('0')
        secc = max(S, _param('SECCION_MINIMA_MM2', '2.5'))
        conductor_req = {
            'secc': secc,
            'material': estudio.conductor_material,
            'dv_real': (Decimal('2') * i_amp * L * rho) / secc if secc else Decimal('0'),
            'dv_max': dv_max,
            'cumple': True,
        }

    return {
        'filas': filas,
        'p_inst': p_inst, 'p_dem': p_dem, 'kva': kva_srv,
        'corriente': corriente_srv,
        'fases': fases, 'alerta': alerta, 'suma_pha': suma_pha,
        'conductor': conductor_req,
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
                voltaje_linea=_dec(request.POST.get('voltaje', '220'), '220'),
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
        if accion == 'agregar':
            carga = CargaNormativa.objects.filter(pk=request.POST.get('carga')).first()
            if carga:
                kw_input = request.POST.get('kw', '').strip()
                ItemEstudio.objects.create(
                    estudio=estudio,
                    carga=carga,
                    cantidad=max(1, int(_dec(request.POST.get('cantidad', '1'), '1'))),
                    potencia_kw=_dec(kw_input, str(_kw_catalogo(carga))) if kw_input else _kw_catalogo(carga),
                    factor_demanda=_dec(request.POST.get('fd') or str(carga.factor_demanda), '100'),
                    factor_potencia=_dec(request.POST.get('fp') or str(carga.factor_potencia), '0.90'),
                    fase=request.POST.get('fase', ''),
                )
                messages.success(request, f'{carga.codigo} agregado al inventario.')
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
                    factor_demanda=_dec(request.POST.get('fd') or '100', '100'),
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
                estudio=estudio, carga=carga, cantidad=max(1, int(_dec(request.POST.get('cantidad', '1'), '1'))),
                potencia_kw=_dec(request.POST.get('kw') or str(kw_default), '0'),
                factor_demanda=_dec(request.POST.get('fd') or '100', '100'),
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
                it.factor_demanda = _dec(request.POST.get('fd') or str(it.factor_demanda), '100')
                it.factor_potencia = _dec(request.POST.get('fp') or str(it.factor_potencia), '0.90')
                it.fase = request.POST.get('fase', it.fase)
                it.save()
                messages.success(request, f'{it.carga.codigo} actualizado en el inventario.')
            return redirect('crm:estudio_detail', estudio_id=estudio.id)
        if accion == 'guardar_ficha':
            estudio.nombre = request.POST.get('nombre', estudio.nombre).strip() or estudio.nombre
            estudio.servicio = request.POST.get('servicio', estudio.servicio)
            estudio.voltaje_linea = _dec(request.POST.get('voltaje', '220'), '220')
            estudio.conductor_material = request.POST.get('conductor_material', '')
            estudio.longitud_linea = _dec(request.POST.get('longitud', '0'), '0') or None
            estudio.caida_tension_max = _dec(request.POST.get('caida_max', ''), '') or None
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
        'param_fp': _param('FP_PROYECTO', '0.90'),
        'param_dv': _param('CAIDA_TENSION_MAX', '3'),
        'simulacion': _simulacion_horaria(estado, perfil_activo),
        'perfiles': PerfilHorario.TIPO_CHOICES,
        'perfil_activo': perfil_activo,
        'tablero': _tablero(estado, estudio),
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
        'param_fp': _param('FP_PROYECTO', '0.90'),
        'param_dv': _param('CAIDA_TENSION_MAX', '3'),
        'simulacion': _simulacion_horaria(estado, perfil_activo),
        'perfil_activo': perfil_activo,
        'tablero': _tablero(estado, estudio),
        'auto_print': True,
    })
