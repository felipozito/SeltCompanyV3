from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from core.imageutils import delete_thumbnails

from .models import BlogPost, BlogPostImage


def _remove_file(file_field):
    if not file_field or not file_field.name:
        return
    delete_thumbnails(file_field)
    file_field.delete(save=False)


@receiver(post_delete, sender=BlogPostImage)
def delete_blog_image_file(sender, instance, **kwargs):
    _remove_file(instance.image)


@receiver(post_delete, sender=BlogPost)
def delete_blog_cover_file(sender, instance, **kwargs):
    _remove_file(instance.cover_image)


@receiver(pre_save, sender=BlogPost)
def replace_blog_cover_file(sender, instance, **kwargs):
    if not instance.pk:
        return
    old = BlogPost.objects.filter(pk=instance.pk).first()
    if old and old.cover_image and old.cover_image.name != instance.cover_image.name:
        _remove_file(old.cover_image)
