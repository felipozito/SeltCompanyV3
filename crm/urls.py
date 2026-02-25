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
]
