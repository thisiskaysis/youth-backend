from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'status', 'is_provisional']
    list_filter = ['role', 'status', 'is_provisional', 'school_year']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    readonly_fields = ('qr_token', 'last_login', 'date_joined')
    fieldsets = UserAdmin.fieldsets + (
        ('Ministry profile', {
            'fields': (
                'role', 'status', 'date_of_birth', 'school_year', 'phone_number',
                'profile_image', 'is_provisional', 'qr_token',
            ),
        }),
        ('Guardian / emergency contact', {
            'fields': (
                'guardian_name', 'guardian_phone', 'guardian_email',
                'emergency_contact_name', 'emergency_contact_phone',
            ),
        }),
    )
