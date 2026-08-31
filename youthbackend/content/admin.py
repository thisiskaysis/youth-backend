from django.contrib import admin

from .models import ContentItem


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'publish_at', 'expire_at', 'audience_everyone']
    list_filter = ['status', 'audience_everyone']
    search_fields = ['title']
    filter_horizontal = ['audience_groups']
