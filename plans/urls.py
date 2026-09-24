from django.urls import path

from . import views

app_name = 'plans'

urlpatterns = [
    path('', views.cotizaciones_list, name='list'),
    path('nueva/', views.cotizacion_create, name='create'),
    path('<int:cotizacion_id>/', views.cotizacion_detail, name='detail'),
    path('<int:cotizacion_id>/eliminar/', views.cotizacion_delete, name='delete'),
    path('entregables/', views.entregables_list, name='entregables'),
    path('entregables/nuevo/', views.entregable_form, name='entregable_create'),
    path('entregables/<int:entregable_id>/editar/', views.entregable_form, name='entregable_edit'),
    path('entregables/<int:entregable_id>/eliminar/', views.entregable_delete, name='entregable_delete'),
    path('parametros/', views.parametros_list, name='parametros'),
]