from django import forms

from .models import Client, ContactLead, Proforma


class ContactLeadForm(forms.ModelForm):
    class Meta:
        model = ContactLead
        fields = ['full_name', 'email', 'phone', 'company', 'message']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base = 'w-full rounded-lg border-slate-300 focus:border-[#D4AF37] focus:ring-[#D4AF37]'
        placeholders = {
            'full_name': 'Nombre completo',
            'email': 'Correo electrónico',
            'phone': 'Teléfono',
            'company': 'Empresa (opcional)',
            'message': 'Cuéntanos qué necesitas',
        }
        for name, field in self.fields.items():
            field.widget.attrs['class'] = base
            field.widget.attrs['placeholder'] = placeholders.get(name, '')


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'email', 'phone', 'company', 'address', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'w-full rounded-lg border-slate-300 focus:border-[#D4AF37] focus:ring-[#D4AF37]'


class ProformaForm(forms.ModelForm):
    class Meta:
        model = Proforma
        fields = ['client', 'reference', 'description', 'total', 'status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'w-full rounded-lg border-slate-300 focus:border-[#D4AF37] focus:ring-[#D4AF37]'
