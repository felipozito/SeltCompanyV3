from django.contrib import admin

from .models import Client, ContactLead, Proforma


@admin.register(ContactLead)
class ContactLeadAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('full_name', 'email', 'company')


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'email', 'phone', 'created_at')
    search_fields = ('name', 'company', 'email')


@admin.register(Proforma)
class ProformaAdmin(admin.ModelAdmin):
    list_display = ('reference', 'client', 'total', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('reference', 'client__name', 'client__company')
