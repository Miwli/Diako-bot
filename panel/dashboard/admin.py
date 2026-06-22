from django.contrib import admin
from asgiref.sync import async_to_sync
from shared_lib.db import delete_server
from .models import (
    Servers, Plans, Orders, Users,
    DiscountCodes, TopUpRequests, Transactions,
    Referrals, Tickets, Tutorials, Faqs, Settings,
)


@admin.register(Servers)
class ServersAdmin(admin.ModelAdmin):
    list_display = ("name", "panel_url", "is_active", "free_test_enabled")
    list_filter = ("is_active",)
    search_fields = ("name", "panel_url")

    def delete_queryset(self, request, queryset):
        for server in queryset:
            async_to_sync(delete_server)(server.id)

    def delete_model(self, request, obj):
        async_to_sync(delete_server)(obj.id)


@admin.register(Plans)
class PlansAdmin(admin.ModelAdmin):
    list_display = ("name", "server", "price", "duration", "traffic", "is_active")
    list_filter = ("is_active", "server")
    search_fields = ("name",)


@admin.register(Orders)
class OrdersAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "plan", "status", "order_type", "created_at")
    list_filter = ("status", "order_type")
    search_fields = ("username", "vpn_username")


@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ("user_id", "first_name", "username", "balance", "is_banned", "created_at")
    list_filter = ("is_banned",)
    search_fields = ("first_name", "username")


@admin.register(DiscountCodes)
class DiscountCodesAdmin(admin.ModelAdmin):
    list_display = ("code", "type", "value", "max_uses", "used_count", "is_active", "expires_at")
    list_filter = ("is_active", "type")
    search_fields = ("code",)


@admin.register(TopUpRequests)
class TopUpRequestsAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "amount", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("username",)


@admin.register(Transactions)
class TransactionsAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "amount", "type", "description", "created_at")
    list_filter = ("type",)


@admin.register(Referrals)
class ReferralsAdmin(admin.ModelAdmin):
    list_display = ("referrer_id", "referred_id", "total_commission", "first_purchase_rewarded", "created_at")


@admin.register(Tickets)
class TicketsAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "status", "created_at")
    list_filter = ("status",)


@admin.register(Tutorials)
class TutorialsAdmin(admin.ModelAdmin):
    list_display = ("title", "content_type", "order_index", "is_active")
    list_filter = ("is_active", "content_type")


@admin.register(Faqs)
class FaqsAdmin(admin.ModelAdmin):
    list_display = ("question", "order_index", "is_active")
    list_filter = ("is_active",)


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ("key", "value")
