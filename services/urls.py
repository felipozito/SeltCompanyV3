from django.urls import path

from . import views

app_name = 'services'

urlpatterns = [
    path('', views.gallery, name='gallery'),
    path('manage/', views.manage_services, name='manage'),
    path('manage/<int:service_id>/edit/', views.edit_service, name='edit'),
    path('manage/<int:service_id>/delete/', views.delete_service, name='delete'),
    path('manage/<int:service_id>/images/', views.manage_service_images, name='manage_images'),
    path('manage/<int:service_id>/images/reorder/', views.reorder_service_images, name='reorder_images'),
    path('manage/<int:service_id>/images/new/', views.add_service_image, name='add_image'),
    path('manage/images/<int:image_id>/edit/', views.edit_service_image, name='edit_image'),
    path('manage/images/<int:image_id>/delete/', views.delete_service_image, name='delete_image'),
    path('<slug:slug>/', views.service_detail, name='detail'),
]
