from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.conf import settings

from blog.models import BlogPost
from crm.forms import ContactLeadForm
from services.models import Service


def home(request):
    if request.method == 'POST':
        form = ContactLeadForm(request.POST)
        if form.is_valid():
            lead = form.save()
            notification_target = settings.CONTACT_NOTIFICATION_EMAIL
            if notification_target:
                subject = f'Nuevo contacto web - {lead.full_name}'
                body = (
                    f'Se registró un nuevo contacto desde la landing.\n\n'
                    f'Nombre: {lead.full_name}\n'
                    f'Email: {lead.email}\n'
                    f'Teléfono: {lead.phone}\n'
                    f'Empresa: {lead.company}\n'
                    f'Mensaje:\n{lead.message}\n'
                )
                try:
                    send_mail(
                        subject=subject,
                        message=body,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[notification_target],
                        fail_silently=False,
                    )
                    messages.success(request, 'Tu mensaje fue enviado y notificado por correo. Te contactaremos pronto.')
                except Exception:
                    messages.warning(request, 'Tu mensaje se guardó, pero no se pudo enviar la notificación por correo.')
            else:
                messages.success(request, 'Tu mensaje fue enviado. Te contactaremos pronto.')
            return redirect('home')
    else:
        form = ContactLeadForm()

    context = {
        'services': Service.objects.filter(is_active=True)[:6],
        'featured_posts': BlogPost.objects.filter(is_published=True)[:3],
        'contact_form': form,
        'google_maps_embed_src': settings.GOOGLE_MAPS_EMBED_SRC,
    }
    return render(request, 'core/home.html', context)
