from django.contrib import admin

from .models import Client, ContactLead, Proforma, ProformaItem


@admin.register(ContactLead)
class ContactLeadAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('full_name', 'email', 'company')


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'ruc', 'company', 'email', 'phone', 'created_at')
    search_fields = ('name', 'ruc', 'company', 'email')


class ProformaItemInline(admin.TabularInline):
    model = ProformaItem
    extra = 1


@admin.register(Proforma)
class ProformaAdmin(admin.ModelAdmin):
    list_display = ('reference', 'client', 'issue_date', 'status', 'total')
    list_filter = ('status',)
    search_fields = ('reference', 'client__name', 'client__company')
    inlines = [ProformaItemInline]


@admin.register(ProformaItem)
class ProformaItemAdmin(admin.ModelAdmin):
    list_display = ('proforma', 'description', 'quantity', 'unit_price', 'order')
    list_filter = ('proforma',)


# ============================================================================
# CATÁLOGO NORMATIVO — admin
# ============================================================================
from .models import CargaNormativa, DistribuidoraNEC, HistorialCarga, Norma


class HistorialCargaInline(admin.TabularInline):
    model = HistorialCarga
    extra = 0
    readonly_fields = ('campo', 'valor_antes', 'valor_despues', 'fecha', 'usuario', 'motivo')
    can_delete = False


@admin.register(Norma)
class NormaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'titulo', 'version', 'activa')
    list_filter = ('activa',)
    search_fields = ('codigo', 'titulo')


@admin.register(DistribuidoraNEC)
class DistribuidoraNECAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'provincia', 'sistema', 'voltaje_suministro', 'activa')
    list_filter = ('activa', 'sistema')
    search_fields = ('nombre', 'provincia')


@admin.register(CargaNormativa)
class CargaNormativaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'categoria', 'equipo', 'potencia', 'unidad',
                    'factor_demanda', 'voltaje', 'editable')
    list_filter = ('categoria', 'editable', 'norma', 'distribuidora')
    search_fields = ('codigo', 'equipo')
    inlines = [HistorialCargaInline]
    list_editable = ('potencia', 'factor_demanda')


# ============================================================================
# ESTUDIOS DE CARGA + BASE NORMATIVA — admin
# ============================================================================
from .models import EstudioCarga, ItemEstudio, ParametroNorma, PerfilHorario


class ItemEstudioInline(admin.TabularInline):
    model = ItemEstudio
    extra = 1
    autocomplete_fields = ('carga',)


@admin.register(EstudioCarga)
class EstudioCargaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cliente', 'servicio', 'voltaje_linea', 'creado')
    list_filter = ('servicio',)
    search_fields = ('nombre', 'cliente__name')
    inlines = [ItemEstudioInline]


@admin.register(ItemEstudio)
class ItemEstudioAdmin(admin.ModelAdmin):
    list_display = ('estudio', 'carga', 'cantidad', 'potencia_kw', 'factor_demanda', 'fase')
    list_filter = ('fase',)


@admin.register(ParametroNorma)
class ParametroNormaAdmin(admin.ModelAdmin):
    list_display = ('clave', 'nombre', 'valor', 'unidad', 'fuente', 'version', 'editable')
    list_editable = ('valor',)
    search_fields = ('clave', 'nombre', 'fuente')


@admin.register(PerfilHorario)
class PerfilHorarioAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'hora', 'factor')
    list_filter = ('tipo',)
    list_editable = ('factor',)
    ordering = ('tipo', 'hora')
