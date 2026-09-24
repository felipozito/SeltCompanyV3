from django.contrib import admin

from .models import CotizacionPlanos, Entregable, PlanParametro, RubroCotizacion


class RubroInline(admin.TabularInline):
    model = RubroCotizacion
    extra = 1
    autocomplete_fields = ('entregable',)


@admin.register(Entregable)
class EntregableAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'categoria', 'nombre', 'precio_base', 'unidad',
                    'es_electronico', 'activa')
    list_filter = ('categoria', 'unidad', 'activa')
    search_fields = ('codigo', 'nombre')
    list_editable = ('precio_base',)
    ordering = ('categoria', 'orden', 'codigo')


@admin.register(PlanParametro)
class PlanParametroAdmin(admin.ModelAdmin):
    list_display = ('clave', 'nombre', 'valor', 'unidad', 'editable')
    list_editable = ('valor',)
    search_fields = ('clave', 'nombre')


@admin.register(CotizacionPlanos)
class CotizacionPlanosAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cliente', 'tipo_proyecto', 'area_m2', 'integral', 'creado')
    list_filter = ('tipo_proyecto', 'integral')
    search_fields = ('nombre', 'cliente__name')
    inlines = [RubroInline]


@admin.register(RubroCotizacion)
class RubroCotizacionAdmin(admin.ModelAdmin):
    list_display = ('cotizacion', 'entregable', 'cantidad', 'precio_unitario', 'total')
    list_filter = ('entregable__categoria',)
    autocomplete_fields = ('entregable',)