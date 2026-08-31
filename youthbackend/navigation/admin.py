from django.contrib import admin

from .models import NavigationItem


@admin.register(NavigationItem)
class NavigationItemAdmin(admin.ModelAdmin):
    list_display = ['label', 'destination_type', 'status', 'sort_order', 'is_protected']
    list_filter = ['status', 'destination_type', 'is_protected']
    search_fields = ['label']
    filter_horizontal = ['audience_groups']
