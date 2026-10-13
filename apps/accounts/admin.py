from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_producer', 'is_staff', 'is_active')
    list_filter = ('is_producer', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Perfil de productor', {'fields': ('is_producer', 'phone', 'document_number')}),
    )