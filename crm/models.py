from decimal import Decimal

from django.db import models
from django.utils import timezone

# Estratos de consumo residencial — EEQ Sección A-11.02 (Tabla A-11.02_2).
ESTRATO_CHOICES = [('A1', 'A1 (501–900 kWh/mes)'), ('A', 'A (351–500)'),
                   ('B', 'B (251–350)'), ('C', 'C (151–250)'),
                   ('D', 'D (101–150)'), ('E', 'E (0–100)')]


class ContactLead(models.Model):
    STATUS_NEW = 'new'
    STATUS_CONTACTED = 'contacted'
    STATUS_CONVERTED = 'converted'
    STATUS_CHOICES = [
        (STATUS_NEW, 'Nuevo'),
        (STATUS_CONTACTED, 'Contactado'),
        (STATUS_CONVERTED, 'Convertido'),
    ]

    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    company = models.CharField(max_length=120, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.full_name} ({self.email})'


class Client(models.Model):
    name = models.CharField(max_length=120)
    ruc = models.CharField('R.U.C. / C.I.', max_length=30, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    company = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=220, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.company or self.name


class Proforma(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Borrador'),
        (STATUS_SENT, 'Enviada'),
        (STATUS_APPROVED, 'Aprobada'),
        (STATUS_REJECTED, 'Rechazada'),
    ]

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='proformas')
    reference = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=120, default='PROPUESTA ECONÓMICA')

    # Snapshot of the client data, so historical proformas stay unchanged.
    client_name = models.CharField(max_length=120, blank=True)
    client_ruc = models.CharField('R.U.C. / C.I.', max_length=30, blank=True)
    client_address = models.CharField(max_length=220, blank=True)
    client_phone = models.CharField(max_length=30, blank=True)
    client_email = models.EmailField(blank=True)

    # Service / content sections.
    service_title = models.CharField(max_length=180, blank=True)
    object_text = models.TextField(blank=True)
    scope_text = models.TextField(blank=True, help_text='Un punto del alcance por línea.')
    terms_text = models.TextField(blank=True, help_text='Un término por línea.')

    place = models.CharField(max_length=80, default='Quito')
    issue_date = models.DateField(default=timezone.localdate)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('15.00'))

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

    @property
    def subtotal(self):
        return sum((item.total for item in self.items.all()), Decimal('0.00'))

    @property
    def tax_amount(self):
        rate = self.tax_rate or Decimal('0.00')
        return (self.subtotal * rate / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def total(self):
        return self.subtotal + self.tax_amount

    @property
    def scope_lines(self):
        return [line.strip() for line in (self.scope_text or '').splitlines() if line.strip()]

    @property
    def terms_lines(self):
        return [line.strip() for line in (self.terms_text or '').splitlines() if line.strip()]


class ProformaItem(models.Model):
    proforma = models.ForeignKey(Proforma, on_delete=models.CASCADE, related_name='items')
    description = models.TextField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.description[:60]

    @property
    def total(self):
        return (self.quantity or Decimal('0.00')) * (self.unit_price or Decimal('0.00'))

# ============================================================================
# CATÁLOGO NORMATIVO DE CARGAS  (NEC / normativa ecuatoriana / distribuidora)
# Fuente = origen de cada valor (catálogo, NEC Art., fabricante, distribuidora)
# ============================================================================

class Norma(models.Model):
    codigo = models.CharField(max_length=20, unique=True)          # NEC-2023
    version = models.CharField(max_length=40)                      # "2023 (NFPA 70)"
    titulo = models.CharField(max_length=180, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['codigo']
        verbose_name_plural = 'Normas'

    def __str__(self):
        return f'{self.codigo} v{self.version}'


class DistribuidoraNEC(models.Model):
    """Empresa eléctrica distribuidora (EEQ, CNEL EP, EEASA...)."""
    nombre = models.CharField(max_length=120, unique=True)         # Empresa Eléctrica Quito
    provincia = models.CharField(max_length=80, blank=True)
    sistema = models.CharField(max_length=60, default='Monofásica')  # Monofásica/Trifásica
    frecuencia_hz = models.CharField(max_length=10, default='60')
    voltaje_suministro = models.CharField(max_length=20, default='120/240 V')
    potencia_max_residencial = models.DecimalField(max_digits=10, decimal_places=2,
                                                   default=Decimal('0.00'), blank=True)
    requisitos_medicion = models.CharField(max_length=220, blank=True)
    norma_acometida = models.CharField(max_length=120, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Distribuidoras eléctricas'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class CargaNormativa(models.Model):
    """Carga predeterminada con criterio normativo (editable por el diseñador)."""
    UNIDAD_CHOICES = [
        ('W', 'W'), ('kW', 'kW'), ('VA', 'VA'), ('kVA', 'kVA'), ('HP', 'HP'),
    ]
    FASES_CHOICES = [('1F', 'Monofásica'), ('2F', 'Bifásica'), ('3F', 'Trifásica')]
    TIPO_CHOICES = [('RES', 'Resistiva'), ('IND', 'Inductiva'), ('MOT', 'Motriz')]
    CATEGORIA_CHOICES = [
        ('ILU', 'Iluminación'), ('TOM', 'Tomacorrientes'), ('ELE', 'Electrodomésticos'),
        ('MOT', 'Motores'), ('HVAC', 'HVAC / Aire acondicionado'), ('COM', 'Comercial'),
        ('IND', 'Industrial'), ('EV', 'Carga de vehículos EV'), ('SOL', 'Solar'),
        ('OTR', 'Otros'),
    ]
    CATEGORIA_COLORES = {
        'ILU': 'text-amber-300', 'TOM': 'text-sky-300', 'ELE': 'text-violet-300',
        'MOT': 'text-red-300', 'HVAC': 'text-emerald-300', 'COM': 'text-cyan-300',
        'IND': 'text-orange-300', 'EV': 'text-fuchsia-300', 'SOL': 'text-yellow-300',
        'OTR': 'text-slate-300',
    }

    codigo = models.CharField(max_length=20, unique=True)          # ILU-RES-001
    categoria = models.CharField(max_length=4, choices=CATEGORIA_CHOICES, default='ELE')
    equipo = models.CharField(max_length=120)                       # Cocina eléctrica
    unidad = models.CharField(max_length=5, choices=UNIDAD_CHOICES, default='W')
    potencia = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1800.00'))
    factor_demanda = models.DecimalField('Factor demanda %', max_digits=6, decimal_places=2, default=Decimal('100.00'))
    factor_potencia = models.DecimalField('Factor potencia', max_digits=5, decimal_places=3, default=Decimal('0.90'))
    voltaje = models.CharField(max_length=20, default='220 V')
    fases = models.CharField(max_length=2, choices=FASES_CHOICES, default='1F')
    tipo_carga = models.CharField(max_length=3, choices=TIPO_CHOICES, default='RES')
    metodo_calculo = models.CharField(max_length=120, blank=True)   # NEC Art. 220
    norma = models.ForeignKey(Norma, on_delete=models.PROTECT, related_name='cargas')
    distribuidora = models.ForeignKey(DistribuidoraNEC, on_delete=models.PROTECT,
                                      related_name='cargas', null=True, blank=True)
    editable = models.BooleanField('Editable por diseñador', default=True)
    obs_tecnica = models.CharField('Observación técnica', max_length=220, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['categoria', 'codigo']
        verbose_name_plural = 'Catálogo de cargas normativas'

    def __str__(self):
        return f'[{self.codigo}] {self.equipo} ({self.potencia} {self.unidad})'

    @property
    def color_clase(self):
        """Clase de color Tailwind de la categoría (para filas del catálogo)."""
        return self.CATEGORIA_COLORES.get(self.categoria, 'text-slate-300')


class HistorialCarga(models.Model):
    """Auditoría de cambios sobre los valores del catálogo (trazabilidad)."""
    carga = models.ForeignKey(CargaNormativa, on_delete=models.CASCADE, related_name='historial')
    campo = models.CharField(max_length=40)           # potencia / factor_demanda...
    valor_antes = models.CharField(max_length=60, blank=True)
    valor_despues = models.CharField(max_length=60, blank=True)
    motivo = models.CharField(max_length=180, blank=True)
    usuario = models.CharField(max_length=120, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name_plural = 'Historial de cambios de carga'

    def __str__(self):
        return f'{self.carga.codigo} · {self.campo} → {self.valor_despues}'


class ParametroNorma(models.Model):
    """Parámetro normativo parametrizable (fuente + versión) — nunca valores quemados."""
    clave = models.CharField(max_length=40, unique=True)        # CAIDA_TENSION_MAX
    nombre = models.CharField(max_length=120)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    unidad = models.CharField(max_length=20, blank=True)        # % · A · mm²
    fuente = models.CharField('Fuente normativa', max_length=120)   # NEC-2023
    referencia = models.CharField('Referencia', max_length=120, blank=True)  # Art. 215.2
    version = models.CharField(max_length=20, default='2025')
    editable = models.BooleanField(default=True)

    class Meta:
        ordering = ['clave']
        verbose_name_plural = 'Parámetros normativos'

    def __str__(self):
        return f'{self.clave} = {self.valor} {self.unidad} ({self.fuente} {self.version})'


class DMDResidencial(models.Model):
    """Tabla A-11.03_1 — Demanda Máxima Diversificada (DMD) en kW según estrato
    de consumo (A1..E) y número de usuarios (Fuente: EEQ Sección A-11, v08).
    Para 1–4 usuarios la DMD = n × FCn × DMU (Apéndice A-11-B1); la fila de
    n=1 equivale a la DMU del estrato. Para n≥5 la DMD = M(n) × N(estrato)."""
    numero_usuarios = models.PositiveIntegerField('Nº usuarios')
    estrato = models.CharField('Estrato', max_length=2, choices=ESTRATO_CHOICES)
    dmd_kw = models.DecimalField('DMD (kW)', max_digits=9, decimal_places=3)

    class Meta:
        ordering = ['estrato', 'numero_usuarios']
        unique_together = ('numero_usuarios', 'estrato')
        verbose_name_plural = 'Demandas máximas diversificadas residenciales (A-11.03_1)'

    def __str__(self):
        return f'DMD {self.estrato} · {self.numero_usuarios} usuarios = {self.dmd_kw} kW'


class FactorDiversidad(models.Model):
    """Apéndice A-11-D1 — Factor de diversidad (FD) para demandas máximas
    diversificadas de usuarios comerciales, dependiente de N (1→1.00 … 50+→3.10)."""
    numero_usuarios = models.PositiveIntegerField('Nº abonados (N)')
    factor = models.DecimalField('Factor de diversidad (FD)', max_digits=5, decimal_places=3)

    class Meta:
        ordering = ['numero_usuarios']
        verbose_name_plural = 'Factores de diversidad comerciales (A-11-D1)'

    def __str__(self):
        return f'FD(N={self.numero_usuarios}) = {self.factor}'


class EstudioCarga(models.Model):
    """Estudio de cargas persistente (inventario + motor de demanda)."""
    nombre = models.CharField(max_length=120)
    cliente = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='estudios')
    descripcion = models.CharField(max_length=220, blank=True)
    creado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    voltaje_fase = models.DecimalField('Voltaje fase–neutro (V)', max_digits=6, decimal_places=1, default=Decimal('120.0'))
    servicio = models.CharField('Servicio', max_length=20,
                          choices=[('1F', 'Monofásico'), ('2F', 'Bifásico'), ('3F', 'Trifásico')],
                          default='1F')

    @property
    def voltaje_linea(self):
        """Voltaje entre líneas según sistema: 1F→fase, 2F→2·fase, 3F→√3·fase."""
        vf = self.voltaje_fase
        if self.servicio == '3F':
            return (vf * Decimal('1.732')).quantize(Decimal('0.1'))
        if self.servicio == '2F':
            return vf * Decimal('2')
        return vf
    caida_tension_max = models.DecimalField('Caída de tensión máx %', max_digits=4, decimal_places=2, null=True, blank=True)
    conductor_material = models.CharField('Material conductor', max_length=6,
                                           choices=[('Cu', 'Cobre'), ('Al', 'Aluminio')], default='Cu')
    longitud_linea = models.DecimalField('Longitud de línea (m)', max_digits=7,
                                          decimal_places=1, null=True, blank=True)
    # Metadatos del formato EEQ "Planilla para la determinación de demandas"
    actividad_tipo = models.CharField('Actividad tipo', max_length=60, blank=True)          # COMERCIAL
    localizacion = models.CharField('Localización', max_length=180, blank=True)             # Av. Shyris Edif. Iqon
    numero_usuarios = models.PositiveIntegerField('Número de usuarios', default=1)
    fecha_estudio = models.DateField('Fecha del estudio', default=timezone.localdate)
    ingeniero_responsable = models.CharField('Ingeniero responsable', max_length=120, blank=True)  # ING. ...
    registro_lp = models.CharField('Registro LP', max_length=60, blank=True)                # LP: 1034-2021-...
    expediente_eeq = models.CharField('Nº expediente EEQ', max_length=60, blank=True)      # EEQ-2022-I.2163
    # ===== Metodología EEQ Sección A-11 (v08) =====
    # A-11.03: tipo de determinación de demanda (residencial por DMD / comercial por DMU·N/FD)
    tipo_estudio = models.CharField('Tipo de estudio', max_length=3,
                    choices=[('RES', 'Residencial (DMD por estrato)'),
                             ('COM', 'Comercial/Industrial (DMU × N / FD)')],
                    default='COM')
    estrato = models.CharField('Estrato de consumo', max_length=2,
                    choices=ESTRATO_CHOICES, blank=True, null=True)          # A-11.02 Tabla A-11.02_2
    # A-11.06: zona + usuarios proyectados para el período de diseño
    zona_urbano_rural = models.CharField('Zona', max_length=3,
                    choices=[('URB', 'Urbano'), ('RUR', 'Rural')], default='URB')
    usuarios_proyectados = models.PositiveIntegerField('Usuarios proyectados (período diseño)', default=0)
    # A-11.04: componentes de la Demanda de Diseño
    dap_kw = models.DecimalField('DAP — Alumbrado público (kW)', max_digits=8, decimal_places=3,
                                 default=Decimal('0.000'))
    es_camara_transformacion = models.BooleanField('Cámara de transformación (DPT 1.0 %)', default=False)
    # A-11.03 b) / Ec. (3): N abonados y factor de diversidad FD del punto de red
    n_abonados_comercial = models.PositiveIntegerField('N — Abonados que inciden en el punto', default=1)
    fd_factor_diversidad = models.DecimalField('FD factor de diversidad (auto si vacío)',
                                               max_digits=5, decimal_places=3, null=True, blank=True)
    # A-11.07: S/E con cambiador de taps bajo carga (define límites de caída)
    subestacion_taps = models.BooleanField('Subestación con taps bajo carga', default=False)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado']
        verbose_name_plural = 'Estudios de carga'

    def __str__(self):
        return self.nombre


class Zona(models.Model):
    """Zona / circuito / tablero de un estudio (cada zona genera su planilla EEQ)."""
    estudio = models.ForeignKey(EstudioCarga, on_delete=models.CASCADE, related_name='zonas')
    nombre = models.CharField('Zona', max_length=120)        # COCINA · BAR · RECEPCION...
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name_plural = 'Zonas del estudio'

    def __str__(self):
        return f'{self.estudio.nombre} · {self.nombre}'


class ItemEstudio(models.Model):
    """Ítem del inventario de cargas (asociado al catálogo normativo, ajustable)."""
    estudio = models.ForeignKey(EstudioCarga, on_delete=models.CASCADE, related_name='items')
    carga = models.ForeignKey(CargaNormativa, on_delete=models.PROTECT, related_name='en_estudios')
    zona = models.ForeignKey(Zona, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='items')
    cantidad = models.PositiveIntegerField(default=1)
    potencia_kw = models.DecimalField('Potencia kW', max_digits=8, decimal_places=3)
    factor_demanda = models.DecimalField('FD %', max_digits=6, decimal_places=2)
    factor_potencia = models.DecimalField('FP', max_digits=5, decimal_places=3)
    # Factores EEQ: FFUn (funcionamiento unitario) y FSn (servicio/simultaneidad)
    ffun = models.DecimalField('FFUn % (funcionamiento unitario)', max_digits=6, decimal_places=2, default=Decimal('100.00'))
    fsn = models.DecimalField('FSn % (servicio/simultaneidad)', max_digits=6, decimal_places=2, default=Decimal('100.00'))
    fase = models.CharField('Fase destino', max_length=1, blank=True,
                       choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('', 'Auto')], default='')

    class Meta:
        ordering = ['id']
        verbose_name_plural = 'Ítems del estudio'

    def save(self, *args, **kwargs):
        # FD% (total) se mantiene sincronizado = FFUn × FSn / 100 (compatibilidad)
        self.factor_demanda = self.ffun * self.fsn / Decimal('100')
        self.factor_demanda = self.factor_demanda.quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.carga.codigo} × {self.cantidad}'


class PerfilHorario(models.Model):
    """Perfil de demanda horaria (% de la demanda máximo) por tipo de uso."""
    TIPO_CHOICES = [('RES', 'Residencial'), ('COM', 'Comercial'), ('OFI', 'Oficinas')]
    tipo = models.CharField(max_length=3, choices=TIPO_CHOICES)
    hora = models.PositiveSmallIntegerField('Hora (0-23)')
    factor = models.DecimalField('Factor demanda %', max_digits=5, decimal_places=1)

    class Meta:
        ordering = ['tipo', 'hora']
        unique_together = ('tipo', 'hora')
        verbose_name_plural = 'Perfiles horarios de demanda'

    def __str__(self):
        return f'{self.tipo} {self.hora:02d}:00 = {self.factor}%'
