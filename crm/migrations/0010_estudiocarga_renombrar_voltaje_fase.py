from decimal import Decimal

from django.db import migrations, models


def convertir_voltaje(apps, schema_editor):
    """El campo se interpretaba como 'voltaje de línea'. Para no alterar las
    corrientes calculadas, la tensión fase–neutro se deriva de vuelta:
    - 1F y 2F: tenían como almacenado el valor fase–neutro (se conserva).
    - 3F: tenían el valor fase–fase (línea), se divide entre √3."""
    Estudio = apps.get_model('crm', 'EstudioCarga')
    for e in Estudio.objects.all():
        if e.servicio == '3F' and e.voltaje_fase:
            e.voltaje_fase = (e.voltaje_fase / Decimal('1.732')).quantize(Decimal('0.1'))
            e.save(update_fields=['voltaje_fase'])


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0009_estudiocarga_actividad_tipo_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='estudiocarga',
            old_name='voltaje_linea',
            new_name='voltaje_fase',
        ),
        migrations.AlterField(
            model_name='estudiocarga',
            name='voltaje_fase',
            field=models.DecimalField(decimal_places=1, default=Decimal('120.0'), max_digits=6, verbose_name='Voltaje fase–neutro (V)'),
        ),
        migrations.RunPython(convertir_voltaje, migrations.RunPython.noop),
    ]