from django.urls import path

from . import views

app_name = 'crm'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('leads/', views.leads_list, name='leads'),
    path('clients/', views.clients_list, name='clients'),
    path('clients/<int:client_id>/edit/', views.edit_client, name='client_edit'),
    path('clients/<int:client_id>/delete/', views.delete_client, name='client_delete'),
    path('proformas/', views.proformas_list, name='proformas'),
    path('proformas/nueva/', views.proforma_create, name='proforma_create'),
    path('proformas/<int:proforma_id>/', views.proforma_detail, name='proforma_detail'),
    path('proformas/<int:proforma_id>/editar/', views.proforma_edit, name='proforma_edit'),
    path('proformas/<int:proforma_id>/imprimir/', views.proforma_print, name='proforma_print'),
    path('proformas/<int:proforma_id>/eliminar/', views.proforma_delete, name='proforma_delete'),
    path('catalogo/', views.catalogo_list, name='catalogo'),
    path('cargas/nueva/', views.carga_create, name='carga_create'),
    path('cargas/<int:carga_id>/editar/', views.carga_edit, name='carga_edit'),
    path('cargas/<int:carga_id>/eliminar/', views.carga_delete, name='carga_delete'),
    path('estudios/', views.estudios_list, name='estudios'),
    path('estudios/nuevo/', views.estudio_create, name='estudio_create'),
    path('estudios/<int:estudio_id>/', views.estudio_detail, name='estudio_detail'),
    path('estudios/<int:estudio_id>/eliminar/', views.estudio_delete, name='estudio_delete'),
    path('estudios/<int:estudio_id>/imprimir/', views.estudio_print, name='estudio_print'),
    path('estudios/<int:estudio_id>/exportar/', views.estudio_export_excel, name='estudio_export_excel'),
]
