from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from blog.models import BlogPost
from services.models import Service

from .forms import ClientForm, ProformaForm
from .models import Client, ContactLead, Proforma


@login_required
def dashboard(request):
    context = {
        'contacts_count': ContactLead.objects.count(),
        'clients_count': Client.objects.count(),
        'proformas_count': Proforma.objects.count(),
        'blog_count': BlogPost.objects.count(),
        'services_count': Service.objects.count(),
        'latest_contacts': ContactLead.objects.all()[:6],
        'latest_proformas': Proforma.objects.select_related('client').all()[:6],
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
    if request.method == 'POST':
        form = ProformaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proforma registrada.')
            return redirect('crm:proformas')
    else:
        form = ProformaForm()

    proformas = Proforma.objects.select_related('client').all()
    return render(request, 'crm/proformas_list.html', {'proformas': proformas, 'form': form})
