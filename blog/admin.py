from django.contrib import admin

from .models import BlogPost, BlogPostImage


class BlogPostImageInline(admin.TabularInline):
    model = BlogPostImage
    extra = 1


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_featured', 'is_published', 'created_at')
    list_filter = ('is_featured', 'is_published')
    search_fields = ('title', 'excerpt', 'content')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [BlogPostImageInline]


@admin.register(BlogPostImage)
class BlogPostImageAdmin(admin.ModelAdmin):
    list_display = ('post', 'caption', 'order')
    list_filter = ('post',)
