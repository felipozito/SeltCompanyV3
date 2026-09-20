from django import forms
from django.forms import inlineformset_factory

from . import defaults
from .models import Client, ContactLead, Proforma, ProformaItem

INPUT_CLASS = 'w-full rounded-lg border-slate-300 focus:border-[#D4AF37] focus:ring-[#D4AF37]'


class ClientSelect(forms.Select):
    client_data = {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        raw = getattr(value, 'value', value)
        try:
            key = int(raw) if raw not in (None, '') else None
        except (TypeError, ValueError):
            key = None
        if key is not None:
            data = self.client_data.get(key)
            if data:
                option['attrs'].update({f'data-{field}': val for field, val in data.items()})
        return option


class ContactLeadForm(forms.ModelForm):
    class Meta:
        model = ContactLead
        fields = ['full_name', 'email', 'phone', 'company', 'message']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'full_name': 'Nombre completo',
            'email': 'Correo electrónico',
            'phone': 'Teléfono',
            'company': 'Empresa (opcional)',
            'message': 'Cuéntanos qué necesitas',
        }
        for name, field in self.fields.items():
            field.widget.attrs['class'] = INPUT_CLASS
            field.widget.attrs['placeholder'] = placeholders.get(name, '')


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'ruc', 'email', 'phone', 'company', 'address', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT_CLASS


class ProformaForm(forms.ModelForm):
    class Meta:
        model = Proforma
        fields = [
            'client', 'reference', 'title',
            'client_name', 'client_ruc', 'client_address', 'client_phone', 'client_email',
            'service_title', 'object_text', 'scope_text', 'terms_text',
            'place', 'issue_date', 'tax_rate', 'status',
        ]
        widgets = {
            'client': ClientSelect,
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'object_text': forms.Textarea(attrs={'rows': 4}),
            'scope_text': forms.Textarea(attrs={'rows': 6}),
            'terms_text': forms.Textarea(attrs={'rows': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'h-4 w-4 rounded border-slate-300 text-primary focus:ring-[#D4AF37]'
            else:
                field.widget.attrs['class'] = INPUT_CLASS
        self.fields['client'].widget.attrs['class'] = INPUT_CLASS
        self.fields['client'].widget.client_data = {
            client.id: {
                'name': client.name,
                'ruc': client.ruc or '',
                'address': client.address or '',
                'phone': client.phone or '',
                'email': client.email or '',
            }
            for client in Client.objects.all()
        }

        help_texts = {
            'client_name': 'Se completa al elegir el cliente; puedes editarlo para esta proforma.',
            'reference': 'Código único de la proforma (ej. PF-0001).',
            'title': 'Título principal que aparece en el documento.',
            'service_title': 'Nombre del servicio; se muestra en mayúsculas en el PDF.',
            'object_text': 'Describe el objetivo del servicio. Se muestra como párrafo.',
            'scope_text': 'Un punto del alcance por línea. Se listan como viñetas.',
            'terms_text': 'Un término por línea. Se listan como viñetas.',
            'place': 'Ciudad que aparece junto a la fecha.',
            'issue_date': 'Fecha de emisión de la propuesta.',
            'tax_rate': 'Porcentaje de IVA aplicado al subtotal.',
            'status': 'Estado interno de la proforma.',
        }
        for name, text in help_texts.items():
            self.fields[name].help_text = text

        self.fields['client'].widget.client_data = {
            client.id: {
                'name': client.name,
                'ruc': client.ruc or '',
                'address': client.address or '',
                'phone': client.phone or '',
                'email': client.email or '',
            }
            for client in Client.objects.all()
        }

        if not self.instance.pk:
            self.fields['title'].initial = self.fields['title'].initial or defaults.DEFAULT_TITLE
            self.fields['reference'].initial = self.fields['reference'].initial or _next_reference()
            self.fields['service_title'].initial = self.fields['service_title'].initial or defaults.DEFAULT_SERVICE_TITLE
            self.fields['object_text'].initial = self.fields['object_text'].initial or defaults.DEFAULT_OBJECT
            self.fields['scope_text'].initial = self.fields['scope_text'].initial or defaults.DEFAULT_SCOPE
            self.fields['terms_text'].initial = self.fields['terms_text'].initial or defaults.DEFAULT_TERMS
            self.fields['place'].initial = self.fields['place'].initial or defaults.COMPANY['city']


def _next_reference():
    last = Proforma.objects.order_by('-id').first()
    number = 1
    if last and last.reference.upper().startswith('PF-'):
        try:
            number = int(last.reference.split('-', 1)[1]) + 1
        except (IndexError, ValueError):
            number = Proforma.objects.count() + 1
    return f'PF-{number:04d}'


class ProformaItemForm(forms.ModelForm):
    class Meta:
        model = ProformaItem
        fields = ['description', 'quantity', 'unit_price']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Descripción del ítem'}),
            'quantity': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'unit_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        compact = INPUT_CLASS + ' px-2.5 py-1.5 text-sm'
        for field in self.fields.values():
            field.widget.attrs['class'] = compact


ProformaItemFormSet = inlineformset_factory(
    Proforma,
    ProformaItem,
    form=ProformaItemForm,
    fields=['description', 'quantity', 'unit_price'],
    extra=1,
    can_delete=True,
)

