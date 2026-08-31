from django.contrib import admin

from .models import Group, GroupMembership


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0
    autocomplete_fields = ['person']


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'group_type', 'is_active']
    list_filter = ['group_type', 'is_active']
    search_fields = ['name']
    inlines = [GroupMembershipInline]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ['person', 'group', 'membership_role', 'is_active', 'joined_at']
    list_filter = ['membership_role', 'is_active']
    autocomplete_fields = ['person', 'group']
