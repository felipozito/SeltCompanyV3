import random
from datetime import timedelta
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw

from blog.models import BlogPost
from services.models import Service, ServiceFeature, ServiceImage
from crm import defaults
from crm.models import Client, ContactLead, Proforma

BRAND = {
    'primary': (3, 43, 61),
    'accent': (232, 201, 133),
    'surface': (15, 58, 82),
}

PALETTES = [
    [(7, 59, 97), (11, 93, 137), (232, 201, 133)],
    [(3, 43, 61), (15, 58, 82), (232, 201, 133)],
    [(31, 76, 105), (64, 124, 162), (240, 226, 190)],
]


class Command(BaseCommand):
    help = 'Carga datos de prueba: 1 guia de blog y 3 servicios con imagenes de ejemplo.'

    def handle(self, *args, **options):
        self._run()

    def _run(self):
        for model in (Proforma, Client, ContactLead, ServiceImage, ServiceFeature, Service, BlogPost):
            model.objects.all().delete()

        self._seed_service(
            title='Mantenimiento Eléctrico Industrial',
            short_description='Preventivo y correctivo de instalaciones industriales de media y baja tensión.',
            description='Diagnóstico, corrección y mantenimiento de tableros, motores, transformadores y sistemas de fuerza.',
            detailed_information=(
                'Cobertura:\n'
                '- Inspección termográfica de tableros eléctricos\n'
                '- Prueba y reconexión de protecciones (guardamotores, termomagnéticos)\n'
                '- Mantenimiento de motores y variadores de frecuencia\n'
                '- Informe técnico con mediciones y recomendaciones\n\n'
                'Proceso: levantamiento del estado actual, plan de trabajo, ejecución con protocolos de seguridad y entrega de reporte.'
            ),
            price=150.00,
            features=['Inspección termográfica', 'Cumplimiento normativo', 'Informe técnico detallado', 'Protocolos de seguridad'],
        )
        self._seed_service(
            title='Instalaciones Eléctricas Residenciales',
            short_description='Instalación, ampliación y remodelación del sistema eléctrico de tu hogar.',
            description='Diseño e instalación de circuitos, iluminación, tomacorrientes y sistemas de protección para viviendas.',
            detailed_information=(
                'Incluye:\n'
                '- Diseño del plano eléctrico bajo norma\n'
                '- Tablero general y circuitos ramales\n'
                '- Iluminación interior y exterior (LED)\n'
                '- Puesta a tierra y protecciones diferenciales\n\n'
                'Garantía por escrito sobre los trabajos realizados.'
            ),
            price=80.00,
            features=['Certificación del instalador', 'Materiales de primera', 'Plano eléctrico incluido', 'Garantía por escrito'],
        )
        self._seed_service(
            title='Sistemas de Energía Solar Fotovoltaica',
            short_description='Diseño e instalación de paneles solares para reducir tu consumo eléctrico.',
            description='Soluciones aisladas y conectadas a red, dimensionadas según tu consumo y presupuesto.',
            detailed_information=(
                'Incluye:\n'
                '- Estudio de consumo y dimensionamiento\n'
                '- Instalación de paneles e inversores\n'
                '- Trámites de conexión a la red\n'
                '- Monitoreo remoto del rendimiento\n\n'
                'Financiamiento disponible para proyectos residenciales.'
            ),
            price=250.00,
            features=['Ahorro en planilla', 'Monitoreo remoto', 'Garantía de paneles 25 años', 'Trámites de conexión'],
        )

        self._seed_blog(
            title='Guía: Cómo prevenir fallas eléctricas en tu hogar',
            excerpt='Recomendaciones prácticas de nuestros ingenieros para detectar señales de riesgo y evitar cortocircuitos.',
            content=(
                '<h2>Señales de alerta</h2>\n'
                '<p>Un tablero que zumba, enchufes calientes o luces que parpadean son señales de que la instalación '
                'podría estar sobrecargada. No las ignores: detectarlas a tiempo evita accidentes mayores.</p>\n'
                '<h2>Revisión periódica</h2>\n'
                '<p>Recomendamos una inspección profesional al menos una vez al año, y con mayor frecuencia en '
                'inmuebles con más de 15 años de antigüedad. La termografía permite detectar puntos calientes '
                'sin interrumpir el servicio.</p>\n'
                '<h2>Buenas prácticas diarias</h2>\n'
                '<ul>\n'
                '  <li>Evita triples y conexiones en serie de alta demanda.</li>\n'
                '  <li>Instala protectores de sobretensión para equipos sensibles.</li>\n'
                '  <li>Reemplaza cables pelados o con aislante deteriorado.</li>\n'
                '</ul>\n'
                '<h2>¿Cuándo llamar a un ingeniero?</h2>\n'
                '<p>Si percibes olor a quemado, disparos frecuentes del breaker o caídas de tensión inexplicables, '
                'desconecta el circuito y contacta a un profesional certificado: tu seguridad primero.</p>'
            ),
        )

        self._seed_crm()

        self.stdout.write(self.style.SUCCESS(
            'Listo. Se cargaron: 3 servicios, 1 guia de blog y datos de CRM de ejemplo.'
        ))

    def _make_image_bytes(self, label, sublabel='', palette=None, width=960, height=640):
        palette = palette or random.choice(PALETTES)
        img = Image.new('RGB', (width, height), palette[0])
        draw = ImageDraw.Draw(img)
        for i in range(0, height, 40):
            shade = tuple(int(a * (0.98 - i * 0.02 / height)) for a in palette[1])
            draw.rectangle([0, i, width, min(i + 40, height)], fill=shade)
        draw.rectangle([width // 2 - 190, height // 2 - 130, width // 2 + 190, height // 2 + 130], outline=palette[2], width=10)
        draw.ellipse([width // 2 - 60, height // 2 - 60, width // 2 + 60, height // 2 + 60], fill=palette[2])
        draw.text((width // 2 - 150, height // 2 + 80), label, fill=palette[2])
        if sublabel:
            draw.text((width // 2 - 150, height // 2 + 110), sublabel, fill=palette[1])
        buf = __import__('io').BytesIO()
        img.save(buf, format='JPEG', quality=82)
        return buf.getvalue()

    def _seed_service(self, title, short_description, description, detailed_information, price, features):
        service = Service.objects.create(
            title=title,
            short_description=short_description,
            description=description,
            detailed_information=detailed_information,
            price=price,
            is_active=True,
        )
        for i, text in enumerate(features):
            ServiceFeature.objects.create(service=service, text=text, order=i)

        photo_labels = [
            'SELT COMPANY',
            title,
            'Servicio profesional',
            'Calidad garantizada',
        ]
        for i, label in enumerate(photo_labels):
            bytes_ = self._make_image_bytes(label, sublabel=self._short(title))
            image = ServiceImage.objects.create(service=service, title=f'{title} - Foto {i + 1}', detail=self._short(description), order=i)
            image.image.save(f'service_{service.id}_{i + 1}.jpg', ContentFile(bytes_), save=True)
        self.stdout.write(f'  + Servicio: {title}')

    def _seed_blog(self, title, excerpt, content):
        now = timezone.now()
        post = BlogPost.objects.create(
            title=title,
            excerpt=excerpt,
            content=content,
            is_featured=True,
            is_published=True,
            created_at=now,
            published_at=now,
        )
        cover = self._make_image_bytes(post.title, sublabel='Blog guía', palette=PALETTES[1], width=1200, height=680)
        post.cover_image.save('blog_cover_guide.jpg', ContentFile(cover), save=True)
        self.stdout.write(f'  + Blog: {post.title}')

    def _seed_crm(self):
        client = Client.objects.create(name='Empresa Ejemplo S.A.', ruc='1790012345001', email='contacto@ejemplo.com', phone='0991234567', company='Empresa Ejemplo S.A.', address='Av. Principal 123', notes='Cliente de demostración.')
        ContactLead.objects.create(full_name='Juan Pérez', email='juan@correo.com', phone='0990001111', company='Pyme Local', message='Necesito mantenimiento eléctrico en mi taller.')
        ContactLead.objects.create(full_name='María Gómez', email='maria@correo.com', phone='0992223333', message='Quiero cotización para paneles solares en mi casa.')

        proforma = Proforma.objects.create(
            client=client,
            reference='PF-0001',
            title=defaults.DEFAULT_TITLE,
            client_name='Empresa Ejemplo S.A.',
            client_ruc='1790012345001',
            client_address='Av. Principal 123',
            client_phone='0991234567',
            client_email='contacto@ejemplo.com',
            service_title=defaults.DEFAULT_SERVICE_TITLE,
            object_text=defaults.DEFAULT_OBJECT,
            scope_text=defaults.DEFAULT_SCOPE,
            terms_text=defaults.DEFAULT_TERMS,
            place=defaults.COMPANY['city'],
            tax_rate=15,
            status=Proforma.STATUS_SENT,
        )
        proforma.items.create(description='Visita técnica en sitio (2 técnicos, 1 jornada).', quantity=1, unit_price=450.00, order=0)

        proforma2 = Proforma.objects.create(
            client=client,
            reference='PF-0002',
            title=defaults.DEFAULT_TITLE,
            client_name='Empresa Ejemplo S.A.',
            client_ruc='1790012345001',
            client_address='Av. Principal 123',
            client_phone='0991234567',
            client_email='contacto@ejemplo.com',
            service_title='INSTALACIÓN DE SISTEMA SOLAR 3 kWp',
            object_text=defaults.DEFAULT_OBJECT,
            scope_text=defaults.DEFAULT_SCOPE,
            terms_text=defaults.DEFAULT_TERMS,
            place=defaults.COMPANY['city'],
            tax_rate=15,
            status=Proforma.STATUS_DRAFT,
        )
        proforma2.items.create(description='Panel solar 550 W', quantity=6, unit_price=320.00, order=0)
        proforma2.items.create(description='Inversor híbrido 3 kW', quantity=1, unit_price=980.00, order=1)
        proforma2.items.create(description='Estructura de montaje e instalación', quantity=1, unit_price=600.00, order=2)

        self.stdout.write('  + CRM: 1 cliente, 2 leads, 2 proformas')

    def _short(self, text):
        return text if len(text) <= 60 else text[:57] + '...'