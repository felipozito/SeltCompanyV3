from decimal import Decimal

from django.db import models
from django.utils import timezone


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
