def public_services(request):
    """Make active services available to shared partials (header/footer)."""
    from services.models import Service

    return {
        'footer_services': Service.objects.filter(is_active=True).only('title', 'slug')[:5],
    }
