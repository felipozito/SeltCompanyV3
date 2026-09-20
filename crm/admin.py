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
