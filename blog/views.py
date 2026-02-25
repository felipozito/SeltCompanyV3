import json
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import BlogPostForm, BlogPostImageBulkForm, BlogPostImageForm
from .models import BlogPost, BlogPostImage


def post_list(request):
    query = request.GET.get('q', '').strip()
    posts = BlogPost.objects.filter(is_published=True).prefetch_related('images')
    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(excerpt__icontains=query) | Q(content__icontains=query))

    context = {
        'posts': posts,
        'featured_post': posts.filter(is_featured=True).first() or posts.first(),
        'query': query,
    }
    return render(request, 'blog/post_list.html', context)


def post_detail(request, slug):
    post = get_object_or_404(BlogPost.objects.prefetch_related('images'), slug=slug, is_published=True)
    return render(request, 'blog/post_detail.html', {'post': post})


@login_required
def manage_posts(request):
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES)
        image_form = BlogPostImageBulkForm(request.POST, request.FILES)

        if form.is_valid() and image_form.is_valid():
            post = form.save()
            _create_post_images(post, request.FILES.getlist('images'), image_form.cleaned_data.get('caption', ''), image_form.cleaned_data.get('order_start') or 0)
            messages.success(request, f'Entrada creada correctamente con {post.images.count()} foto(s) de galería.')
            return redirect('blog:manage')

        messages.error(request, 'No se pudo crear la entrada. Revisa los errores del formulario.')
    else:
        form = BlogPostForm()
        image_form = BlogPostImageBulkForm()

    posts = BlogPost.objects.prefetch_related('images').all()
    return render(request, 'blog/manage_posts.html', {'form': form, 'image_form': image_form, 'posts': posts})


@login_required
def edit_post(request, post_id):
    post = get_object_or_404(BlogPost, id=post_id)
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, 'Publicación actualizada.')
            return redirect('blog:manage')
    else:
        form = BlogPostForm(instance=post)
    return render(request, 'blog/edit_post.html', {'form': form, 'post': post})


@login_required
def delete_post(request, post_id):
    post = get_object_or_404(BlogPost, id=post_id)
    if request.method == 'POST':
        post.delete()
        messages.success(request, 'Publicación eliminada.')
    return redirect('blog:manage')


@login_required
def manage_post_images(request, post_id):
    post = get_object_or_404(BlogPost.objects.prefetch_related('images'), id=post_id)
    return render(request, 'blog/manage_images.html', {'post': post})


@login_required
def add_post_images(request, post_id):
    post = get_object_or_404(BlogPost, id=post_id)
    if request.method == 'POST':
        form = BlogPostImageBulkForm(request.POST, request.FILES)
        if form.is_valid():
            files = request.FILES.getlist('images')
            if not files:
                messages.error(request, 'Selecciona al menos una imagen.')
            else:
                _create_post_images(post, files, form.cleaned_data.get('caption', ''), form.cleaned_data.get('order_start') or 0)
                messages.success(request, f'Se agregaron {len(files)} imagen(es).')
                return redirect('blog:manage_images', post_id=post.id)
    else:
        form = BlogPostImageBulkForm()

    return render(request, 'blog/add_images.html', {'form': form, 'post': post})


@login_required
def edit_post_image(request, image_id):
    image = get_object_or_404(BlogPostImage.objects.select_related('post'), id=image_id)
    if request.method == 'POST':
        form = BlogPostImageForm(request.POST, instance=image)
        if form.is_valid():
            form.save()
            messages.success(request, 'Imagen actualizada.')
            return redirect('blog:manage_images', post_id=image.post_id)
    else:
        form = BlogPostImageForm(instance=image)
    return render(request, 'blog/edit_image.html', {'form': form, 'image': image, 'post': image.post})


@login_required
def delete_post_image(request, image_id):
    image = get_object_or_404(BlogPostImage.objects.select_related('post'), id=image_id)
    post_id = image.post_id
    if request.method == 'POST':
        image.delete()
        messages.success(request, 'Imagen eliminada.')
    return redirect('blog:manage_images', post_id=post_id)


@login_required
@require_POST
def reorder_post_images(request, post_id):
    post = get_object_or_404(BlogPost, id=post_id)
    try:
        payload = json.loads(request.body.decode('utf-8'))
        image_ids = payload.get('image_ids', [])
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    images_by_id = {img.id: img for img in BlogPostImage.objects.filter(post=post, id__in=image_ids)}
    for order, image_id in enumerate(image_ids):
        img = images_by_id.get(image_id)
        if img:
            img.order = order
            img.save(update_fields=['order'])

    return JsonResponse({'ok': True})


def _create_post_images(post, files, caption, order_start):
    caption = (caption or '').strip()
    for index, uploaded in enumerate(files, start=1):
        fallback = Path(uploaded.name).stem.replace('_', ' ').replace('-', ' ').title()
        image_caption = f'{caption} {index}'.strip() if caption and len(files) > 1 else (caption or fallback)
        BlogPostImage.objects.create(
            post=post,
            caption=image_caption,
            image=uploaded,
            order=order_start + index - 1,
        )
