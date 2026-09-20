from django import template

from core.imageutils import thumbnail_url

register = template.Library()


@register.simple_tag
def thumb(file_field, preset='card'):
    return thumbnail_url(file_field, preset)
