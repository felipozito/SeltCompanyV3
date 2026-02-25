from django.urls import path

from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.post_list, name='list'),
    path('manage/', views.manage_posts, name='manage'),
    path('manage/<int:post_id>/edit/', views.edit_post, name='edit'),
    path('manage/<int:post_id>/delete/', views.delete_post, name='delete'),
    path('manage/<int:post_id>/images/', views.manage_post_images, name='manage_images'),
    path('manage/<int:post_id>/images/reorder/', views.reorder_post_images, name='reorder_images'),
    path('manage/<int:post_id>/images/new/', views.add_post_images, name='add_images'),
    path('manage/images/<int:image_id>/edit/', views.edit_post_image, name='edit_image'),
    path('manage/images/<int:image_id>/delete/', views.delete_post_image, name='delete_image'),
    path('<slug:slug>/', views.post_detail, name='detail'),
]
