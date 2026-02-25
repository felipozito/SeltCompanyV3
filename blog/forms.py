from django import forms

from .models import BlogPost, BlogPostImage


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        if data:
            return [single_clean(data, initial)]
        return []


class BlogPostForm(forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = ['title', 'excerpt', 'content', 'cover_image', 'is_featured', 'is_published']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'h-4 w-4 rounded border-slate-300 text-primary focus:ring-[#D4AF37]'
            else:
                field.widget.attrs['class'] = 'w-full rounded-lg border-slate-300 focus:border-[#D4AF37] focus:ring-[#D4AF37]'
            if name == 'content':
                field.widget.attrs['rows'] = 12
        self.fields['title'].label = 'Post Title'
        self.fields['excerpt'].label = 'Excerpt'
        self.fields['content'].label = 'Content'
        self.fields['cover_image'].label = 'Cover Image'
        self.fields['title'].widget.attrs['placeholder'] = 'e.g., The Future of Industrial Grid Management'
        self.fields['excerpt'].widget.attrs['placeholder'] = 'Short summary of the article'


class BlogPostImageBulkForm(forms.Form):
    caption = forms.CharField(required=False, max_length=140)
    order_start = forms.IntegerField(required=False, min_value=0, initial=0)
    images = MultipleImageField(widget=MultiFileInput(attrs={'multiple': True}), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['caption'].label = 'Gallery Caption Prefix'
        self.fields['order_start'].label = 'Initial Order'
        self.fields['images'].label = 'Gallery Images'
        self.fields['caption'].widget.attrs['placeholder'] = 'e.g., Installation Progress'
        for field in self.fields.values():
            field.widget.attrs['class'] = 'w-full rounded-lg border-slate-300 focus:border-[#D4AF37] focus:ring-[#D4AF37]'


class BlogPostImageForm(forms.ModelForm):
    class Meta:
        model = BlogPostImage
        fields = ['caption', 'order']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'w-full rounded-lg border-slate-300 focus:border-[#D4AF37] focus:ring-[#D4AF37]'
