from decimal import Decimal

from django.db import models


# ============================================================================
# COTIZADOR DE PLANOS ELÉCTRICOS Y ELECTRÓNICOS — SELT COMPANY (Ecuador)
#
# Modelo de costos: precio base por ENTREGABLE × recargo por tipo de proyecto
# (Residencial/Comercial/Industrial) × descuento por proyecto integral.
# Los parámetros del motor viven en PlanParametro (nunca valores quemados),
# igual que ParametroNorma del estudio de cargas.
# ============================================================================

class Entregable(models.Model):
    """Catálogo de entregables de elaboración de planos (precio base editable)."""
    CATEGORIA_CHOICES = [
        ('LEV', 'Levantamiento en sitio'),
        ('VFU', 'Visita fuera de ciudad'),
        ('ANT', 'Anteproyecto'),
        ('LAM', 'Lámina planimétrica'),
        ('TAB', 'Diseño de tableros'),
        ('UNI', 'Unifilar / cuadro de cargas'),
        ('MEM', 'Memoria técnica y de cálculo'),
        ('FIR', 'Firma profesional'),
        ('RED', 'Red estructurada (data/voz)'),
        ('CCTV', 'CCTV / seguridad electrónica'),
        ('ALA', 'Alarma (intrusión / incendio)'),
        ('APU', 'Presupuesto referencial (APU)'),
        ('DIG', 'Digitalización / impresión'),
    ]
    # Categorías electrónicas (reciben descuento en proyecto integral).
    CATEGORIA_ELECTRONICA = {'RED', 'CCTV', 'ALA'}

    UNIDAD_CHOICES = [
        ('UN', 'Unidad'),
        ('M2', 'Metro cuadrado (m²)'),
        ('LAM', 'Lámina planimétrica'),
        ('VIS', 'Visita'),
        ('TBL', 'Tablero'),
        ('CIR', 'Circuito'),
    ]

    codigo = models.CharField(max_length=20, unique=True)          # PLAN-LEV-001
    categoria = models.CharField(max_length=4, choices=CATEGORIA_CHOICES, default='LAM')
    nombre = models.CharField(max_length=160)
    descripcion = models.CharField(max_length=220, blank=True)
    precio_base = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    unidad = models.CharField(max_length=3, choices=UNIDAD_CHOICES, default='UN')
    editable = models.BooleanField(default=True)
    activa = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['categoria', 'orden', 'codigo']
        verbose_name = 'Entregable de planos'
        verbose_name_plural = 'Catálogo de entregables de planos'

    def __str__(self):
        return f'{self.codigo} · {self.nombre}'

    @property
    def es_electronico(self):
        """True si la categoría pertenece al bloque electrónico (integral)."""
        return self.categoria in self.CATEGORIA_ELECTRONICA


class PlanParametro(models.Model):
    """Parámetro del motor de precios (editable) — nunca valores quemados.
    `valor` guarda el contenido como texto: numérico («10.00») para porcentajes
    o lista de códigos («PLAN-LEV-001,PLAN-LAM-001,…») para paquetes."""
    clave = models.CharField(max_length=40, unique=True)            # RECARGO_COM
    nombre = models.CharField(max_length=120)
    valor = models.CharField(max_length=300)
    unidad = models.CharField(max_length=24, blank=True)            # % · $ · códigos
    fuente = models.CharField(max_length=120, blank=True)
    editable = models.BooleanField(default=True)

    class Meta:
        ordering = ['clave']
        verbose_name = 'Parámetro del cotizador de planos'
        verbose_name_plural = 'Parámetros del cotizador de planos'

    def __str__(self):
        return f'{self.clave} = {self.valor} {self.unidad}'


class CotizacionPlanos(models.Model):
    """Cotización de elaboración de planos eléctricos/electrónicos.
    Genera una Proforma (crm) reutilizando el pipeline de propuestas existente."""
    TIPO_CHOICES = [
        ('RES', 'Residencial'),
        ('COM', 'Comercial'),
        ('IND', 'Industrial'),
    ]

    cliente = models.ForeignKey('crm.Client', on_delete=models.SET_NULL,
                                null=True, blank=True,
                                related_name='cotizaciones_planos')
    nombre = models.CharField(max_length=160)
    descripcion = models.CharField(max_length=220, blank=True)
    tipo_proyecto = models.CharField(max_length=3, choices=TIPO_CHOICES, default='RES')
    area_m2 = models.DecimalField('Área (m²)', max_digits=9, decimal_places=1,
                                  default=Decimal('0.0'))
    n_tableros = models.PositiveIntegerField('Nº tableros', default=1)
    n_circuitos = models.PositiveIntegerField('Nº circuitos', default=1)
    integral = models.BooleanField('Proyecto integral (eléctrico + electrónico)',
                                   default=False)
    plano_arquitectonico = models.BooleanField(
        'Dispone de plano arquitectónico (ej. CAD del arquitecto)', default=True)
    notas = models.TextField(blank=True)
    proforma = models.ForeignKey('crm.Proforma', on_delete=models.SET_NULL,
                                 null=True, blank=True,
                                 related_name='cotizaciones_planos')
    creado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado']
        verbose_name = 'Cotización de planos'
        verbose_name_plural = 'Cotizaciones de planos'

    def __str__(self):
        return f'{self.nombre} ({self.get_tipo_proyecto_display()})'

    @property
    def subtotal(self):
        return sum((r.total for r in self.rubros.all()), Decimal('0.00'))

    @staticmethod
    def _param(clave, fallback):
        row = PlanParametro.objects.filter(clave=clave).first()
        try:
            return Decimal(str(row.valor)) if row else Decimal(str(fallback))
        except Exception:
            return Decimal(str(fallback))

    @property
    def gravado(self):
        return self.subtotal.quantize(Decimal('0.01'))

    @property
    def iva(self):
        rate = self._param('IVA_PLANOS', '15.00')
        return (self.gravado * rate / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def total(self):
        return self.gravado + self.iva


class RubroCotizacion(models.Model):
    """Ítem de una cotización: snapshot de entregable + cantidad + precio congelado.
    El precio unitario ya incluye recargo (tipo) y descuento integral aplicados."""
    cotizacion = models.ForeignKey(CotizacionPlanos, on_delete=models.CASCADE,
                                   related_name='rubros')
    entregable = models.ForeignKey(Entregable, on_delete=models.PROTECT,
                                   related_name='rubros')
    descripcion = models.CharField(max_length=220, blank=True)
    cantidad = models.DecimalField(max_digits=9, decimal_places=2, default=Decimal('1.00'))
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2,
                                          default=Decimal('0.00'))
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = 'Rubro de la cotización'
        verbose_name_plural = 'Rubros de la cotización'

    def __str__(self):
        return f'{self.entregable.codigo} × {self.cantidad}'

    @property
    def total(self):
        return (self.cantidad or Decimal('0.00')) * (self.precio_unitario or Decimal('0.00'))