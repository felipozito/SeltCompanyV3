from django import forms

from .models import Service, ServiceImage


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        if data:
            return [single_clean(data, initial)]
        return []


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['title', 'short_description', 'description', 'detailed_information', 'price', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'h-4 w-4 rounded border-slate-300 text-primary focus:ring-[#D4AF37]'
            else:
                field.widget.attrs['class'] = 'w-full rounded-lg border-slate-300 focus:border-[#D4AF37] focus:ring-[#D4AF37]'


class ServiceCreateForm(ServiceForm):
    images = MultipleImageField(
        required=False,
        widget=MultiFileInput(attrs={'multiple': True}),
        help_text='Puedes subir varias imágenes a la vez.',
    )
    image_title_prefix = forms.CharField(required=False, max_length=120)
    image_detail = forms.CharField(required=False, max_length=220)
    order_start = forms.IntegerField(required=False, min_value=0, initial=0)
    feature_1 = forms.CharField(required=False, max_length=140)
    feature_2 = forms.CharField(required=False, max_length=140)
    feature_3 = forms.CharField(required=False, max_length=140)
    feature_4 = forms.CharField(required=False, max_length=140)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['images'].label = 'Fotos del servicio'
        self.fields['image_title_prefix'].label = 'Prefijo de título (opcional)'
        self.fields['image_detail'].label = 'Detalle común (opcional)'
        self.fields['order_start'].label = 'Orden inicial'
        self.fields['title'].label = 'Service Name'
        self.fields['short_description'].label = 'Short Summary'
        self.fields['description'].label = 'Description'
        self.fields['detailed_information'].label = 'Specific & Detailed Information'
        self.fields['price'].label = 'Base Price ($)'
        self.fields['title'].widget.attrs['placeholder'] = 'e.g., Residential Solar Setup'
        self.fields['short_description'].widget.attrs['placeholder'] = 'One-line summary for cards and lists'
        self.fields['description'].widget.attrs['placeholder'] = 'Briefly describe what this service covers...'
        self.fields['detailed_information'].widget.attrs['placeholder'] = 'Provide complete technical details, scope, coverage, and process.'
        self.fields['price'].widget.attrs['placeholder'] = '$ 0.00'
        self.fields['description'].widget.attrs['rows'] = 4
        self.fields['detailed_information'].widget.attrs['rows'] = 6
        self.fields['image_title_prefix'].widget.attrs['placeholder'] = 'e.g., Panel Install'
        self.fields['image_detail'].widget.attrs['placeholder'] = 'Common detail text for uploaded images'
        self.fields['feature_1'].label = 'Option 1'
        self.fields['feature_2'].label = 'Option 2'
        self.fields['feature_3'].label = 'Option 3'
        self.fields['feature_4'].label = 'Option 4'
        self.fields['feature_1'].widget.attrs['placeholder'] = 'e.g., Certified safety compliance'
        self.fields['feature_2'].widget.attrs['placeholder'] = 'e.g., Maintenance and support plans'
        self.fields['feature_3'].widget.attrs['placeholder'] = 'e.g., Expert technical team'
        self.fields['feature_4'].widget.attrs['placeholder'] = 'e.g., PLC diagnostics and monitoring'
        for name in ['images', 'image_title_prefix', 'image_detail', 'order_start', 'feature_1', 'feature_2', 'feature_3', 'feature_4']:
            self.fields[name].widget.attrs['class'] = 'w-full rounded-lg border-slate-300 focus:border-[#D4AF37] focus:ring-[#D4AF37]'


class ServiceImageBulkForm(forms.Form):
    title = forms.CharField(required=False, max_length=120)
    detail = forms.CharField(required=False, max_length=220)
    order_start = forms.IntegerField(required=False, min_value=0, initial=0)
    images = MultipleImageField(widget=MultiFileInput(attrs={'multiple': True}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'w-full rounded-lg border-slate-300 focus:border-[#D4AF37] focus:ring-[#D4AF37]'


class ServiceImageForm(forms.ModelForm):
    class Meta:
        model = ServiceImage
        fields = ['title', 'detail', 'order']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'w-full rounded-lg border-slate-300 focus:border-[#D4AF37] focus:ring-[#D4AF37]'
