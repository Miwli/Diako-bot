from django.contrib import admin
from asgiref.sync import async_to_sync
from shared_lib.db import delete_server
from .models import Servers, Plans, Orders, Users


@admin.register(Servers)
class ServersAdmin(admin.ModelAdmin):
    list_display = ("name", "panel_url", "is_active")

    def delete_queryset(self, request, queryset):
        for server in queryset:
            async_to_sync(delete_server)(server.id)

    def delete_model(self, request, obj):
        async_to_sync(delete_server)(obj.id)


@admin.register(Plans)
class PlansAdmin(admin.ModelAdmin):
    list_display = ("name", "server", "price", "duration", "traffic", "is_active")


@admin.register(Orders)
class OrdersAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "plan", "status", "created_at")


@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ("user_id", "first_name", "username", "balance", "is_banned")
