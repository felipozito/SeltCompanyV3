from django.core.management.base import BaseCommand

from crm.models import PerfilHorario

# Curvas típicas de demanda horaria (% de la demanda máxima) — perfiles de diseño genéricos.
PERFILES = {
    'RES': [15, 10, 10, 10, 12, 30, 45, 60, 50, 35, 30, 30, 35, 40, 45, 50, 60, 75, 95, 90, 70, 60, 50, 25],
    'COM': [10, 8, 6, 6, 8, 15, 40, 70, 85, 90, 90, 85, 80, 85, 90, 95, 90, 80, 60, 35, 20, 15, 12, 10],
    'OFI': [10, 8, 6, 6, 8, 12, 25, 50, 80, 95, 95, 90, 85, 85, 90, 85, 75, 55, 30, 15, 10, 8, 6, 5],
}


class Command(BaseCommand):
    help = 'Siembra los perfiles horarios de demanda (RES/COM/OFI).'

    def handle(self, *args, **options):
        n = 0
        for tipo, serie in PERFILES.items():
            if len(serie) != 24:
                self.stdout.write(self.style.ERROR(f'{tipo}: debe tener 24 valores'))
                continue
            for h, f in enumerate(serie):
                PerfilHorario.objects.update_or_create(
                    tipo=tipo, hora=h, defaults={'factor': f})
                n += 1
        self.stdout.write(self.style.SUCCESS(f'Perfiles horarios listos: {n}/72'))