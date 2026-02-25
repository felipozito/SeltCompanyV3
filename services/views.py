import json
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ServiceCreateForm, ServiceForm, ServiceImageBulkForm, ServiceImageForm
from .models import Service, ServiceFeature, ServiceImage


def gallery(request):
    services = Service.objects.filter(is_active=True).prefetch_related('images', 'features')
    return render(request, 'services/gallery.html', {'services': services})


def service_detail(request, slug):
    service = get_object_or_404(
        Service.objects.filter(is_active=True).prefetch_related('images', 'features'),
        slug=slug,
    )
    return render(request, 'services/detail.html', {'service': service})


@login_required
def manage_services(request):
    if request.method == 'POST':
        form = ServiceCreateForm(request.POST, request.FILES)
        files = request.FILES.getlist('images')

        if form.is_valid():
            service = Service.objects.create(
                title=form.cleaned_data['title'],
                short_description=form.cleaned_data['short_description'],
                description=form.cleaned_data['description'],
                detailed_information=form.cleaned_data['detailed_information'],
                price=form.cleaned_data['price'],
                is_active=form.cleaned_data['is_active'],
            )
            _create_service_images(service, files, form.cleaned_data.get('image_title_prefix', ''), form.cleaned_data.get('image_detail', ''), form.cleaned_data.get('order_start') or 0)
            _create_service_features(
                service,
                [
                    form.cleaned_data.get('feature_1', ''),
                    form.cleaned_data.get('feature_2', ''),
                    form.cleaned_data.get('feature_3', ''),
                    form.cleaned_data.get('feature_4', ''),
                ],
            )
            messages.success(request, f'Servicio "{service.title}" creado con {len(files)} foto(s).')
            return redirect('services:manage')

        messages.error(request, 'No se pudo guardar el servicio. Revisa los campos marcados.')
    else:
        form = ServiceCreateForm()

    services = Service.objects.prefetch_related('images', 'features').all()
    return render(request, 'services/manage_services.html', {'form': form, 'services': services})


@login_required
def edit_service(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, 'Servicio actualizado.')
            return redirect('services:manage')
    else:
        form = ServiceForm(instance=service)
    return render(request, 'services/edit_service.html', {'form': form, 'service': service})


@login_required
def delete_service(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    if request.method == 'POST':
        service.delete()
        messages.success(request, 'Servicio eliminado.')
    return redirect('services:manage')


@login_required
def add_service_image(request, service_id):
    service = get_object_or_404(Service, id=service_id)

    if request.method == 'POST':
        form = ServiceImageBulkForm(request.POST, request.FILES)
        files = request.FILES.getlist('images')

        if form.is_valid() and files:
            _create_service_images(service, files, form.cleaned_data.get('title', ''), form.cleaned_data.get('detail', ''), form.cleaned_data.get('order_start') or 0)
            messages.success(request, f'Se subieron {len(files)} imagen(es) al servicio.')
            return redirect('services:manage_images', service_id=service.id)

        messages.error(request, 'No se pudieron subir las imágenes. Revisa el formulario.')
    else:
        form = ServiceImageBulkForm()

    return render(request, 'services/add_service_image.html', {'form': form, 'service': service})


@login_required
def manage_service_images(request, service_id):
    service = get_object_or_404(Service.objects.prefetch_related('images'), id=service_id)
    return render(request, 'services/manage_images.html', {'service': service})


@login_required
def edit_service_image(request, image_id):
    image = get_object_or_404(ServiceImage.objects.select_related('service'), id=image_id)
    if request.method == 'POST':
        form = ServiceImageForm(request.POST, instance=image)
        if form.is_valid():
            form.save()
            messages.success(request, 'Imagen actualizada.')
            return redirect('services:manage_images', service_id=image.service_id)
    else:
        form = ServiceImageForm(instance=image)
    return render(request, 'services/edit_image.html', {'form': form, 'image': image, 'service': image.service})


@login_required
def delete_service_image(request, image_id):
    image = get_object_or_404(ServiceImage.objects.select_related('service'), id=image_id)
    service_id = image.service_id
    if request.method == 'POST':
        image.delete()
        messages.success(request, 'Imagen eliminada.')
    return redirect('services:manage_images', service_id=service_id)


@login_required
@require_POST
def reorder_service_images(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    try:
        payload = json.loads(request.body.decode('utf-8'))
        image_ids = payload.get('image_ids', [])
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    images_by_id = {img.id: img for img in ServiceImage.objects.filter(service=service, id__in=image_ids)}
    for order, image_id in enumerate(image_ids):
        img = images_by_id.get(image_id)
        if img:
            img.order = order
            img.save(update_fields=['order'])

    return JsonResponse({'ok': True})


def _create_service_images(service, files, title_prefix, detail, order_start):
    title_prefix = (title_prefix or '').strip()
    detail = (detail or '').strip()
    for index, uploaded in enumerate(files, start=1):
        filename = Path(uploaded.name).stem.replace('_', ' ').replace('-', ' ').title()
        title = f'{title_prefix} {index}'.strip() if title_prefix and len(files) > 1 else (title_prefix or filename)
        ServiceImage.objects.create(
            service=service,
            title=title,
            detail=detail,
            image=uploaded,
            order=order_start + index - 1,
        )


def _create_service_features(service, features):
    for index, feature in enumerate(features, start=1):
        text = (feature or '').strip()
        if not text:
            continue
        ServiceFeature.objects.create(service=service, text=text, order=index - 1)
