from decimal import Decimal
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from crm.models import Client, Proforma, ProformaItem

from . import plantillas, pricing
from .models import CotizacionPlanos, Entregable, PlanParametro, RubroCotizacion


def _dec(value, fallback='0'):
    return pricing._dec(value, fallback)


def _pk(value):
    """Id de un form a entero, o None si viene vacío/inválido
    (evita el ValueError de filter(pk=''))."""
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _cantidad_proforma(value):
    """Cantidad de un rubro para ProformaItem (evita ceros invisibles)."""
    from decimal import ROUND_DOWN
    try:
        cantidad = Decimal(str(value))
    except Exception:
        cantidad = Decimal('1')
    return cantidad.quantize(Decimal('0.01'), rounding=ROUND_DOWN)


# ============================================================================
# RESUMEN ECONÓMICO — desglose por rubro + impuestos (mismo esquema que Proforma)
# ============================================================================

def _resumen(cotizacion):
    """Filas enriquecidas, subtotales (eléctrico/electrónico), descuento por
    proyecto integral, IVA y total. No escribe en BD."""
    filas = []
    subtotal = subtotal_elec = Decimal('0.00')
    for rubro in cotizacion.rubros.select_related('entregable').order_by('orden', 'id'):
        e = rubro.entregable
        filas.append({
            'rubro': rubro,
            'codigo': e.codigo,
            'nombre': e.nombre,
            'categoria': e.get_categoria_display(),
            'es_electronico': e.es_electronico,
            'unidad': e.get_unidad_display(),
            'recargo': pricing.recargo_tipo(cotizacion.tipo_proyecto),
            'descuento_integral': cotizacion.integral and e.es_electronico,
        })
        subtotal += rubro.total
        if e.es_electronico:
            subtotal_elec += rubro.total

    desc_factor = Decimal('1.00')
    desc_teorico = Decimal('0.00')
    if cotizacion.integral and subtotal_elec:
        desc_factor = pricing.descuento_factor()
        desc_teorico = (subtotal_elec * (Decimal('1') - desc_factor)).quantize(Decimal('0.01'))

    # Los precios unitarios de los rubros YA incluyen el descuento integral
    # (base × recargo × 0,90), así que el subtotal es el valor neto final.
    gravado = subtotal
    iva = (gravado * pricing.param('IVA_PLANOS', '15.00') / Decimal('100')).quantize(Decimal('0.01'))
    total = gravado + iva

    return {
        'filas': filas,
        'subtotal': subtotal,
        'subtotal_sin_desc': (subtotal + desc_teorico).quantize(Decimal('0.01')),
        'subtotal_elec': subtotal_elec,
        'desc_factor': desc_factor,
        'desc_importe': desc_teorico,
        'gravado': gravado,
        'iva': iva,
        'total': total,
        'recargo': pricing.recargo_tipo(cotizacion.tipo_proyecto),
    }


# ============================================================================
# ESTIMACIÓN RÁPIDA + PLANTILLAS RECOMENDADAS
# ============================================================================

def _estimacion(opcion, tipo, area, n_tableros, n_circuitos, integral,
                cotizacion=None):
    """Desglose aproximado de una plantilla SIN escribir en la base.
    Si se pasa una cotización, los entregables ya presentes en el desglose se
    valoran con SU cantidad y precio reales (solo se estima lo que falta), de
    modo que el paquete recomendado se actualiza al cambiar el desglose.
    Reutiliza el motor de precios (recargos, descuento integral e IVA en %)."""
    pseudo = SimpleNamespace(
        tipo_proyecto=tipo,
        area_m2=_dec(area, '0'),
        n_tableros=max(0, int(_dec(n_tableros, '1'))),
        n_circuitos=max(0, int(_dec(n_circuitos, '1'))),
        integral=integral,
    )
    presentes = {}
    if cotizacion is not None:
        presentes = {r.entregable_id: r for r in
                     cotizacion.rubros.select_related('entregable')}

    lineas, subtotal, elect, subtotal_faltante = \
        [], Decimal('0.00'), Decimal('0.00'), Decimal('0.00')
    for e in plantillas.entregables_plantilla(opcion, tipo, integral):
        rubro = presentes.get(e.id)
        en_desglose = rubro is not None
        if en_desglose:
            cantidad = rubro.cantidad
            unitario = rubro.precio_unitario
        else:
            cantidad = plantillas.cantidad_para(e, pseudo)
            unitario = pricing.precio_unitario(e, pseudo)
        total = (cantidad * unitario).quantize(Decimal('0.01'))
        subtotal += total
        if e.es_electronico:
            elect += total
        if not en_desglose:
            subtotal_faltante += total
        lineas.append({
            'codigo': e.codigo,
            'nombre': e.nombre,
            'categoria': e.get_categoria_display(),
            'unidad': e.get_unidad_display(),
            'cantidad': cantidad,
            'unitario': unitario,
            'total': total,
            'es_electronico': e.es_electronico,
            'en_desglose': en_desglose,
        })

    desc_importe = Decimal('0.00')
    if integral and elect:
        desc_importe = (elect * (Decimal('1') - pricing.descuento_factor()))\
            .quantize(Decimal('0.01'))
    iva_pct = pricing.param('IVA_PLANOS', '15.00')
    iva = (subtotal * iva_pct / Decimal('100')).quantize(Decimal('0.01'))
    n_faltantes = sum(1 for l in lineas if not l['en_desglose'])
    return {
        'opcion': opcion,
        'lineas': lineas,
        'n_items': len(lineas),
        'n_faltantes': n_faltantes,
        'n_en_desglose': len(lineas) - n_faltantes,
        'subtotal': subtotal,
        'subtotal_faltante': subtotal_faltante,
        'subtotal_sin_desc': (subtotal + desc_importe).quantize(Decimal('0.01')),
        'desc_importe': desc_importe,
        'gravado': subtotal,
        'iva': iva,
        'iva_pct': iva_pct,
        'total': subtotal + iva,
        'recargo': pricing.recargo_tipo(tipo),
    }


def _cargar_plantilla(cotizacion, opcion):
    """Añade a la cotización los entregables de la plantilla que falten.
    Devuelve los códigos agregados (lista vacía si ya estaban todos)."""
    agregados = []
    existentes = set(cotizacion.rubros.values_list('entregable_id', flat=True))
    for e in plantillas.entregables_plantilla(opcion, cotizacion.tipo_proyecto,
                                              cotizacion.integral):
        if e.id in existentes:
            continue
        cantidad = plantillas.cantidad_para(e, cotizacion)
        RubroCotizacion.objects.create(
            cotizacion=cotizacion, entregable=e,
            descripcion=pricing.descripcion_rubro(e, cantidad),
            cantidad=cantidad,
            precio_unitario=pricing.precio_unitario(e, cotizacion),
            orden=cotizacion.rubros.count(),
        )
        existentes.add(e.id)
        agregados.append(e.codigo)
    return agregados


# ============================================================================
# COTIZACIONES
# ============================================================================

@login_required
def cotizaciones_list(request):
    cotizaciones = CotizacionPlanos.objects.select_related('cliente', 'creado_por')\
        .order_by('-creado')
    return render(request, 'plans/cotizaciones_list.html', {'cotizaciones': cotizaciones})


@login_required
def cotizacion_create(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        if not nombre:
            messages.error(request, 'Indica el nombre del proyecto.')
            clientes = Client.objects.order_by('name')
            return render(request, 'plans/cotizacion_form.html',
                          {'clientes': clientes, 'tipos': CotizacionPlanos.TIPO_CHOICES})
        cotizacion = CotizacionPlanos.objects.create(
            nombre=nombre,
            cliente=Client.objects.filter(pk=_pk(request.POST.get('cliente'))).first(),
            descripcion=request.POST.get('descripcion', '').strip(),
            tipo_proyecto=request.POST.get('tipo_proyecto', 'RES'),
            area_m2=_dec(request.POST.get('area_m2'), '0') or Decimal('0.0'),
            n_tableros=max(0, int(_dec(request.POST.get('n_tableros'), '1'))),
            n_circuitos=max(0, int(_dec(request.POST.get('n_circuitos'), '1'))),
            integral=request.POST.get('integral') == 'on',
            notas=request.POST.get('notas', ''),
            creado_por=request.user,
        )

        plantilla_pedida = request.POST.get('plantilla', 'none')
        if plantilla_pedida != 'none':
            if plantilla_pedida == 'recomendada':
                plantilla_pedida = plantillas.recomendada_opcion(
                    cotizacion.tipo_proyecto, cotizacion.integral)
            agregados = _cargar_plantilla(cotizacion, plantilla_pedida)
            if agregados:
                messages.success(request,
                                 f'Cotización creada con la plantilla '
                                 f'({len(agregados)} entregables cargados).')
            else:
                messages.success(request, 'Cotización creada.')
                messages.info(request, 'Todos los entregables de la plantilla ya estaban.')
            return redirect('plans:detail', cotizacion_id=cotizacion.id)

        messages.success(request, f'Cotización «{cotizacion.nombre}» creada. '
                                  'Agrega los entregables del desglose.')
        return redirect('plans:detail', cotizacion_id=cotizacion.id)

    est = None
    if request.GET.get('est_opcion'):
        tipo = request.GET.get('est_tipo', 'RES')
        integral = request.GET.get('est_integral') == 'on'
        opcion = request.GET.get('est_opcion', 'recomendada')
        if opcion == 'recomendada':
            opcion = plantillas.recomendada_opcion(tipo, integral)
        est = _estimacion(
            opcion, tipo,
            request.GET.get('est_area', '0'),
            request.GET.get('est_tableros', '1'),
            request.GET.get('est_circuitos', '1'),
            integral,
        )
        est['opcion_label'] = dict(
            (k, nombre) for k, nombre, _ in plantillas.opciones_plantilla()
        ).get(opcion, opcion)

    clientes = Client.objects.order_by('name')
    context = {
        'clientes': clientes,
        'tipos': CotizacionPlanos.TIPO_CHOICES,
        'tipos_recargo': [(t, n, pricing.param(f'RECARGO_{t}', '1.00'))
                          for t, n in CotizacionPlanos.TIPO_CHOICES],
        'param_integral': pricing.param('DESCUENTO_INTEGRAL', '10'),
        'opciones_plantilla': plantillas.opciones_plantilla(),
        'recomendada_opcion': plantillas.recomendada_opcion(
            request.GET.get('est_tipo', 'RES'),
            request.GET.get('est_integral') == 'on'),
        'est': est,
        'est_values': {k: request.GET.get(k, '') for k in
                       ('est_tipo', 'est_area', 'est_tableros', 'est_circuitos',
                        'est_integral', 'est_opcion')},
    }
    return render(request, 'plans/cotizacion_form.html', context)


@login_required
def cotizacion_detail(request, cotizacion_id):
    cotizacion = get_object_or_404(CotizacionPlanos.objects.select_related('cliente'),
                                   id=cotizacion_id)
    resumen = _resumen(cotizacion)

    if request.method == 'POST':
        accion = request.POST.get('accion', '')

        if accion == 'agregar':
            e = Entregable.objects.filter(pk=_pk(request.POST.get('entregable'))).first()
            if e:
                cant_txt = request.POST.get('cantidad', '').strip()
                cantidad = _dec(cant_txt, '0') if cant_txt else pricing.cantidad_sugerida(e, cotizacion)
                if cantidad <= Decimal('0'):
                    cantidad = pricing.cantidad_sugerida(e, cotizacion)
                RubroCotizacion.objects.create(
                    cotizacion=cotizacion, entregable=e,
                    descripcion=pricing.descripcion_rubro(e, cantidad),
                    cantidad=cantidad,
                    precio_unitario=pricing.precio_unitario(e, cotizacion),
                    orden=cotizacion.rubros.count(),
                )
                messages.success(request, f'{e.codigo} agregado al desglose.')
            return redirect('plans:detail', cotizacion_id=cotizacion.id)

        if accion == 'actualizar':
            rubro = RubroCotizacion.objects.filter(pk=_pk(request.POST.get('rubro')),
                                                   cotizacion=cotizacion).first()
            if rubro:
                cant_txt = request.POST.get('cantidad', '').strip()
                if cant_txt:
                    rubro.cantidad = _dec(cant_txt, '0') or rubro.cantidad
                precio_txt = request.POST.get('precio_unitario', '').strip()
                if precio_txt:
                    rubro.precio_unitario = (_dec(precio_txt, '0')
                                             .quantize(Decimal('0.01')))
                rubro.descripcion = pricing.descripcion_rubro(
                    rubro.entregable, rubro.cantidad)
                rubro.save()
                messages.success(request, f'{rubro.entregable.codigo} actualizado.')
            return redirect('plans:detail', cotizacion_id=cotizacion.id)

        if accion == 'eliminar':
            RubroCotizacion.objects.filter(pk=_pk(request.POST.get('rubro')),
                                           cotizacion=cotizacion).delete()
            messages.success(request, 'Rubro eliminado del desglose.')
            return redirect('plans:detail', cotizacion_id=cotizacion.id)

        if accion == 'recalcular':
            for rubro in cotizacion.rubros.select_related('entregable').all():
                e = rubro.entregable
                if e.unidad in ('M2', 'TBL', 'CIR'):
                    rubro.cantidad = pricing.cantidad_sugerida(e, cotizacion)
                rubro.precio_unitario = pricing.precio_unitario(e, cotizacion)
                rubro.descripcion = pricing.descripcion_rubro(e, rubro.cantidad)
                rubro.save()
            messages.success(request, 'Cantidades y precios recalculados según factores.')
            return redirect('plans:detail', cotizacion_id=cotizacion.id)

        if accion == 'cargar_plantilla':
            opcion = request.POST.get('opcion', '')
            if not opcion or opcion not in dict((k, _) for k, _, _ in plantillas.opciones_plantilla()):
                messages.error(request, 'Selecciona una plantilla válida.')
                return redirect('plans:detail', cotizacion_id=cotizacion.id)
            agregados = _cargar_plantilla(cotizacion, opcion)
            if agregados:
                messages.success(request, f'Plantilla cargada: {len(agregados)} '
                                          'entregables añadidos al desglose.')
            else:
                messages.info(request, 'Todos los entregables de la plantilla ya estaban en el desglose.')
            return redirect('plans:detail', cotizacion_id=cotizacion.id)

        if accion == 'guardar_ficha':
            cotizacion.nombre = request.POST.get('nombre', cotizacion.nombre).strip() or cotizacion.nombre
            cotizacion.descripcion = request.POST.get('descripcion', '').strip()
            cotizacion.cliente = Client.objects.filter(pk=_pk(request.POST.get('cliente'))).first()
            cotizacion.tipo_proyecto = request.POST.get('tipo_proyecto', cotizacion.tipo_proyecto)
            cotizacion.area_m2 = _dec(request.POST.get('area_m2'), '0') or Decimal('0.0')
            cotizacion.n_tableros = max(0, int(_dec(request.POST.get('n_tableros'), '1')))
            cotizacion.n_circuitos = max(0, int(_dec(request.POST.get('n_circuitos'), '1')))
            cotizacion.integral = request.POST.get('integral') == 'on'
            cotizacion.notas = request.POST.get('notas', '')
            cotizacion.save()
            messages.success(request, 'Ficha de la cotización actualizada.')
            return redirect('plans:detail', cotizacion_id=cotizacion.id)

        if accion == 'generar_proforma':
            return _generar_proforma(request, cotizacion)

    cargas_cat = Entregable.objects.filter(activa=True)
    clientes = Client.objects.order_by('name')

    recom = plantillas.recomendada_opcion(cotizacion.tipo_proyecto,
                                          cotizacion.integral)
    plantilla_cards = []
    for key, nombre, descripcion in plantillas.opciones_plantilla():
        est = _estimacion(key, cotizacion.tipo_proyecto, cotizacion.area_m2,
                          cotizacion.n_tableros, cotizacion.n_circuitos,
                          cotizacion.integral, cotizacion=cotizacion)
        est['nombre'] = nombre
        est['descripcion'] = descripcion
        est['recomendada'] = key == recom
        plantilla_cards.append(est)

    return render(request, 'plans/cotizacion_detail.html', {
        'cp': cotizacion,
        'resumen': resumen,
        'categorias': Entregable.CATEGORIA_CHOICES,
        'entregables': cargas_cat,
        'clientes': clientes,
        'tipos': CotizacionPlanos.TIPO_CHOICES,
        'param_integral': pricing.param('DESCUENTO_INTEGRAL', '10'),
        'param_iva': pricing.param('IVA_PLANOS', '15.00'),
        'plantilla_cards': plantilla_cards,
        'plantilla_recomendada': recom,
    })


@login_required
@require_POST
def cotizacion_delete(request, cotizacion_id):
    cotizacion = get_object_or_404(CotizacionPlanos, id=cotizacion_id)
    nombre = cotizacion.nombre
    cotizacion.rubros.all().delete()
    cotizacion.delete()
    messages.success(request, f'Cotización «{nombre}» eliminada.')
    return redirect('plans:list')


# ============================================================================
# GENERAR PROFORMA (reutiliza crm.Proforma + ProformaItem)
# ============================================================================

def _proforma_reference():
    last = Proforma.objects.order_by('-id').first()
    numero = 1
    if last and last.reference.upper().startswith('CPL-'):
        try:
            numero = int(last.reference.split('-', 1)[1]) + 1
        except (IndexError, ValueError):
            numero = Proforma.objects.count() + 1
    return f'CPL-{numero:04d}'


def _generar_proforma(request, cotizacion):
    if not cotizacion.cliente:
        messages.error(request, 'Asigna un cliente a la cotización para generar la propuesta.')
        return redirect('plans:detail', cotizacion_id=cotizacion.id)
    if cotizacion.proforma:
        messages.info(request, 'La propuesta ya fue generada para esta cotización.')
        return redirect('crm:proforma_detail', proforma_id=cotizacion.proforma_id)

    total_rubros = cotizacion.rubros.count()
    if not total_rubros:
        messages.error(request, 'Agrega al menos un entregable antes de generar la propuesta.')
        return redirect('plans:detail', cotizacion_id=cotizacion.id)

    anticipo = pricing.param('PORCENTAJE_ANTICIPO', '60')
    vigencia = pricing.param('VIGENCIA_DIAS', '15')

    entregables_txt = ', '.join(
        r.entregable.nombre for r in cotizacion.rubros.select_related('entregable'))
    scope = '\n'.join([
        'Levantamiento de información en sitio (cuando aplique según el alcance).',
        'Elaboración de planos eléctricos y electrónicos conforme a la NEC-2023 '
        'y la normativa de la distribuidora local (EEQ / CNEL).',
        f'Entrega de: {entregables_txt}.',
        'Memoria descriptiva y memoria de cálculo del proyecto.',
        'Firmas del profesional responsable.',
    ])
    terms = '\n'.join([
        'El valor considera la elaboración de planos, memorias y firmas indicadas en el alcance.',
        'Se incluyen hasta dos (2) rondas de observaciones; revisiones adicionales se cotizarán por separado.',
        'La entrega final se realiza en formato digital (PDF/DWG) con una (1) copia impresa.',
        f'Forma de pago: {anticipo}% de anticipo y {100 - int(anticipo)}% contra entrega.',
        f'Duración de la oferta: {vigencia} días.',
    ])

    proforma = Proforma.objects.create(
        client=cotizacion.cliente,
        reference=_proforma_reference(),
        client_name=cotizacion.cliente.company or cotizacion.cliente.name,
        client_ruc=cotizacion.cliente.ruc or '',
        client_address=cotizacion.cliente.address or '',
        client_phone=cotizacion.cliente.phone or '',
        client_email=cotizacion.cliente.email or '',
        service_title='ELABORACIÓN DE PLANOS ELÉCTRICOS Y ELECTRÓNICOS',
        object_text=(
            f'Realizar la elaboración de los planos eléctricos y electrónicos del proyecto '
            f'«{cotizacion.nombre}» del cliente {cotizacion.cliente.company or cotizacion.cliente.name}, '
            'en sus instalaciones y conforme a los entregables detallados en el alcance.'
        ),
        scope_text=scope,
        terms_text=terms,
        tax_rate=pricing.param('IVA_PLANOS', '15.00'),
    )

    for orden, rubro in enumerate(cotizacion.rubros.select_related('entregable')):
        ProformaItem.objects.create(
            proforma=proforma,
            description=rubro.descripcion,
            quantity=_cantidad_proforma(rubro.cantidad),
            unit_price=rubro.precio_unitario,
            order=orden,
        )

    cotizacion.proforma = proforma
    cotizacion.save(update_fields=['proforma'])
    messages.success(request, f'Propuesta {proforma.reference} generada desde la cotización.')
    return redirect('crm:proforma_detail', proforma_id=proforma.id)


# ============================================================================
# CATÁLOGO DE ENTREGABLES (100% server-side)
# ============================================================================

@login_required
def entregables_list(request):
    qs = Entregable.objects.all()
    cat = request.GET.get('categoria', '')
    if cat:
        qs = qs.filter(categoria=cat)
    return render(request, 'plans/entregables_list.html', {
        'entregables': qs,
        'categorias': Entregable.CATEGORIA_CHOICES,
        'cat_sel': cat,
        'total': qs.count(),
    })


@login_required
def entregable_form(request, entregable_id=None):
    e = Entregable.objects.filter(pk=entregable_id).first()
    es_editar = e is not None
    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip().upper()
        nombre = request.POST.get('nombre', '').strip()
        if not (codigo and nombre):
            messages.error(request, 'Código y nombre son obligatorios.')
            return render(request, 'plans/entregable_form.html', {
                'e': e, 'es_editar': es_editar,
                'categorias': Entregable.CATEGORIA_CHOICES,
                'unidades': Entregable.UNIDAD_CHOICES,
                'electronica': Entregable.CATEGORIA_ELECTRONICA,
            })
        defaults = dict(
            categoria=request.POST.get('categoria', 'LAM'),
            nombre=nombre,
            descripcion=request.POST.get('descripcion', '').strip(),
            precio_base=(_dec(request.POST.get('precio_base'), '0')
                         .quantize(Decimal('0.01'))),
            unidad=request.POST.get('unidad', 'UN'),
            editable=request.POST.get('editable') == 'on',
            activa=request.POST.get('activa') == 'on',
        )
        if es_editar:
            for k, v in defaults.items():
                setattr(e, k, v)
            e.save()
            messages.success(request, f'{e.codigo} actualizado en el catálogo.')
        else:
            _, creada = Entregable.objects.get_or_create(codigo=codigo, defaults=defaults)
            messages.success(request, 'Entregable creado.' if creada
                             else f'{codigo} ya existía (no se duplicó).')
        return redirect('plans:entregables')

    return render(request, 'plans/entregable_form.html', {
        'e': e, 'es_editar': es_editar,
        'categorias': Entregable.CATEGORIA_CHOICES,
        'unidades': Entregable.UNIDAD_CHOICES,
        'electronica': Entregable.CATEGORIA_ELECTRONICA,
    })


@login_required
@require_POST
def entregable_delete(request, entregable_id):
    e = get_object_or_404(Entregable, id=entregable_id)
    codigo = e.codigo
    if e.rubros.exists():
        messages.error(request, f'{codigo} está en uso por cotizaciones; inactívalo en su lugar.')
        return redirect('plans:entregables')
    e.delete()
    messages.success(request, f'{codigo} eliminado del catálogo.')
    return redirect('plans:entregables')


# ============================================================================
# PARÁMETROS DEL MOTOR (editable, como ParametroNorma)
# ============================================================================

@login_required
def parametros_list(request):
    if request.method == 'POST':
        for p in PlanParametro.objects.filter(editable=True):
            valor = request.POST.get(p.clave, '').strip()
            if valor == '':
                continue
            if p.unidad in ('códigos', 'texto'):
                p.valor = ','.join(
                    c.strip().upper() for c in valor.replace(';', ',').split(',')
                    if c.strip())
            else:
                p.valor = _dec(valor, '0')
            p.save()
        messages.success(request, 'Parámetros del cotizador actualizados.')
        return redirect('plans:parametros')

    parametros = PlanParametro.objects.all().order_by('id')
    return render(request, 'plans/parametros_list.html', {
        'parametros': parametros,
        'paquetes': plantillas.paquetes_info(),
    })