from django.db.models.signals import post_delete
from django.dispatch import receiver

from core.imageutils import delete_thumbnails

from .models import ServiceImage


@receiver(post_delete, sender=ServiceImage)
def delete_service_image_file(sender, instance, **kwargs):
    if not instance.image or not instance.image.name:
        return
    delete_thumbnails(instance.image)
    instance.image.delete(save=False)
