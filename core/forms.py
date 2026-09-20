from django.contrib.auth.forms import AuthenticationForm


class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base = 'w-full rounded-lg border-slate-300 focus:border-[#D4AF37] focus:ring-[#D4AF37]'
        self.fields['username'].widget.attrs.update({'class': base, 'placeholder': 'Usuario'})
        self.fields['password'].widget.attrs.update({'class': base, 'placeholder': 'Contraseña'})
