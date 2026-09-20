from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from blog.models import BlogPost
from services.models import Service

from . import defaults
from .forms import ClientForm, ProformaForm, ProformaItemFormSet
from .models import Client, ContactLead, Proforma

PROFORMA_CONTEXT = {'company': defaults.COMPANY}


@login_required
def dashboard(request):
    context = {
        'contacts_count': ContactLead.objects.count(),
        'clients_count': Client.objects.count(),
        'proformas_count': Proforma.objects.count(),
        'blog_count': BlogPost.objects.count(),
        'services_count': Service.objects.count(),
        'latest_contacts': ContactLead.objects.all()[:6],
        'latest_proformas': Proforma.objects.select_related('client').prefetch_related('items')[:6],
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
    proformas = Proforma.objects.select_related('client').prefetch_related('items')
    return render(request, 'crm/proformas_list.html', {'proformas': proformas})


@login_required
def proforma_create(request):
    if request.method == 'POST':
        form = ProformaForm(request.POST)
        formset = ProformaItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            proforma = form.save()
            _save_items(formset, proforma)
            messages.success(request, f'Proforma {proforma.reference} creada.')
            return redirect('crm:proforma_detail', proforma_id=proforma.id)
        messages.error(request, 'Revisa los errores del formulario antes de guardar.')
    else:
        form = ProformaForm()
        formset = ProformaItemFormSet()

    return render(request, 'crm/proforma_form.html', {
        **PROFORMA_CONTEXT,
        'form': form,
        'formset': formset,
        'proforma': None,
    })


@login_required
def proforma_edit(request, proforma_id):
    proforma = get_object_or_404(Proforma, id=proforma_id)
    if request.method == 'POST':
        form = ProformaForm(request.POST, instance=proforma)
        formset = ProformaItemFormSet(request.POST, instance=proforma)
        if form.is_valid() and formset.is_valid():
            form.save()
            _save_items(formset, proforma)
            messages.success(request, 'Proforma actualizada.')
            return redirect('crm:proforma_detail', proforma_id=proforma.id)
        messages.error(request, 'Revisa los errores del formulario antes de guardar.')
    else:
        form = ProformaForm(instance=proforma)
        formset = ProformaItemFormSet(instance=proforma)

    return render(request, 'crm/proforma_form.html', {
        **PROFORMA_CONTEXT,
        'form': form,
        'formset': formset,
        'proforma': proforma,
    })


def _get_proforma(proforma_id):
    return get_object_or_404(
        Proforma.objects.select_related('client').prefetch_related('items'),
        id=proforma_id,
    )


@login_required
def proforma_detail(request, proforma_id):
    return render(request, 'crm/proforma_detail.html', {
        **PROFORMA_CONTEXT,
        'proforma': _get_proforma(proforma_id),
        'auto_print': False,
    })


@login_required
def proforma_print(request, proforma_id):
    return render(request, 'crm/proforma_detail.html', {
        **PROFORMA_CONTEXT,
        'proforma': _get_proforma(proforma_id),
        'auto_print': True,
    })


@login_required
def proforma_delete(request, proforma_id):
    proforma = get_object_or_404(Proforma, id=proforma_id)
    if request.method == 'POST':
        reference = proforma.reference
        proforma.delete()
        messages.success(request, f'Proforma {reference} eliminada.')
    return redirect('crm:proformas')


def _save_items(formset, proforma):
    instances = formset.save(commit=False)
    for deleted in formset.deleted_objects:
        deleted.delete()
    for order, item in enumerate(instances):
        item.proforma = proforma
        item.order = order
        item.save()
    formset.save_m2m()
