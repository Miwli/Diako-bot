from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from asgiref.sync import async_to_sync
from shared_lib.db import delete_server, get_extra_volume_plans
from .models import (
    Servers, Plans, Orders, Users,
    DiscountCodes, TopUpRequests, Transactions,
    Referrals, Tickets, Tutorials, Faqs, Settings,
    ExtraVolumePlans, ExtraVolumeRequests,
    ExtraTimePlans, ExtraTimeRequests, LocationChangeRequests,
    KeyboardButtons, KeyboardActions, PaymentCards, RequiredChannels,
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


@admin.register(KeyboardButtons)
class KeyboardButtonsAdmin(admin.ModelAdmin):
    list_display  = ("keyboard_name", "label", "callback_data", "row_index", "col_index", "is_active", "admin_only")
    list_filter   = ("keyboard_name", "is_active", "admin_only")
    search_fields = ("label", "callback_data")
    list_editable = ("row_index", "col_index", "is_active")
    ordering      = ("keyboard_name", "row_index", "col_index")


@admin.register(KeyboardActions)
class KeyboardActionsAdmin(admin.ModelAdmin):
    list_display = ("label", "callback_data", "grp", "action_name")
    list_filter  = ("grp",)
    search_fields = ("label", "callback_data", "action_name")


@admin.register(ExtraVolumePlans)
class ExtraVolumePlansAdmin(admin.ModelAdmin):
    list_display  = ("name", "traffic_gb", "price", "is_active", "order_index")
    list_filter   = ("is_active",)
    ordering      = ("order_index", "price")
    list_editable = ("is_active", "order_index")


@admin.register(PaymentCards)
class PaymentCardsAdmin(admin.ModelAdmin):
    list_display = ("number", "owner", "is_active", "order_index")
    list_filter  = ("is_active",)
    ordering     = ("order_index", "id")


@admin.register(RequiredChannels)
class RequiredChannelsAdmin(admin.ModelAdmin):
    list_display = ("title", "chat_id", "is_active", "order_index")
    list_filter  = ("is_active",)
    ordering     = ("order_index", "id")


def _approve_ev_request(request, req_obj):
    """تایید درخواست افزودن حجم از پنل — اتصال به Rebecca و افزودن حجم"""
    import asyncio
    from shared_lib.db import get_extra_volume_request, update_extra_volume_request, get_plan_with_server
    from shared_lib.rebecca_api import RebeccaAPI
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bot"))

    req = async_to_sync(get_extra_volume_request)(req_obj.id)
    if not req:
        messages.error(request, "درخواست یافت نشد.")
        return
    if req["status"] == "approved":
        messages.warning(request, "این درخواست قبلاً تایید شده.")
        return
    plan_data = async_to_sync(get_plan_with_server)(req["vpn_plan_id"])
    if not plan_data:
        messages.error(request, "سرور VPN مرتبط یافت نشد.")
        return
    api = RebeccaAPI(plan_data["panel_url"], plan_data["panel_token"])
    try:
        async_to_sync(api.add_volume)(req["vpn_username"], req["traffic_gb"])
    except Exception as e:
        messages.error(request, f"خطای API: {e}")
        return
    async_to_sync(update_extra_volume_request)(req_obj.id, "approved")
    messages.success(request, f"✅ {req['traffic_gb']}GB به سرویس {req['vpn_username']} اضافه شد.")


@admin.register(ExtraVolumeRequests)
class ExtraVolumeRequestsAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "order_id", "plan_id", "status", "created_at")
    list_filter  = ("status",)
    actions      = ["approve_requests", "reject_requests"]

    @admin.action(description="✅ تایید و افزودن حجم به سرویس")
    def approve_requests(self, request, queryset):
        for req_obj in queryset:
            _approve_ev_request(request, req_obj)

    @admin.action(description="❌ رد کردن درخواست‌ها")
    def reject_requests(self, request, queryset):
        from shared_lib.db import update_extra_volume_request
        for req_obj in queryset:
            if req_obj.status not in ("approved", "rejected"):
                async_to_sync(update_extra_volume_request)(req_obj.id, "rejected")
        messages.success(request, f"{queryset.count()} درخواست رد شد.")


@admin.register(ExtraTimePlans)
class ExtraTimePlansAdmin(admin.ModelAdmin):
    list_display  = ("name", "days", "price", "is_active", "order_index")
    list_filter   = ("is_active",)
    ordering      = ("order_index", "days")
    list_editable = ("is_active", "order_index")


def _approve_et_request(request, req_obj):
    """تایید درخواست افزودن زمان از پنل — اتصال به Rebecca و افزودن زمان"""
    import sys, os
    from shared_lib.db import get_extra_time_request, update_extra_time_request, get_plan_with_server
    from shared_lib.rebecca_api import RebeccaAPI
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bot"))

    req = async_to_sync(get_extra_time_request)(req_obj.id)
    if not req:
        messages.error(request, "درخواست یافت نشد.")
        return
    if req["status"] == "approved":
        messages.warning(request, "این درخواست قبلاً تایید شده.")
        return
    plan_data = async_to_sync(get_plan_with_server)(req["vpn_plan_id"])
    if not plan_data:
        messages.error(request, "سرور VPN مرتبط یافت نشد.")
        return
    api = RebeccaAPI(plan_data["panel_url"], plan_data["panel_token"])
    try:
        async_to_sync(api.add_time)(req["vpn_username"], req["days"])
    except Exception as e:
        messages.error(request, f"خطای API: {e}")
        return
    async_to_sync(update_extra_time_request)(req_obj.id, "approved")
    messages.success(request, f"✅ {req['days']} روز به سرویس {req['vpn_username']} اضافه شد.")


@admin.register(ExtraTimeRequests)
class ExtraTimeRequestsAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "order_id", "plan_id", "status", "created_at")
    list_filter  = ("status",)
    actions      = ["approve_requests", "reject_requests"]

    @admin.action(description="✅ تایید و افزودن زمان به سرویس")
    def approve_requests(self, request, queryset):
        for req_obj in queryset:
            _approve_et_request(request, req_obj)

    @admin.action(description="❌ رد کردن درخواست‌ها")
    def reject_requests(self, request, queryset):
        from shared_lib.db import update_extra_time_request
        for req_obj in queryset:
            if req_obj.status not in ("approved", "rejected"):
                async_to_sync(update_extra_time_request)(req_obj.id, "rejected")
        messages.success(request, f"{queryset.count()} درخواست رد شد.")


@admin.register(LocationChangeRequests)
class LocationChangeRequestsAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "order_id", "from_server_id", "to_server_id", "status", "created_at")
    list_filter  = ("status",)
    actions      = ["approve_requests", "reject_requests"]

    @admin.action(description="✅ تایید و انتقال سرویس")
    def approve_requests(self, request, queryset):
        from shared_lib.db import perform_location_change, update_location_change_request
        for req_obj in queryset:
            if req_obj.status in ("approved", "rejected"):
                messages.warning(request, f"درخواست #{req_obj.id} قبلاً پردازش شده.")
                continue
            try:
                async_to_sync(perform_location_change)(req_obj.order_id, req_obj.to_server_id)
            except Exception as e:
                messages.error(request, f"درخواست #{req_obj.id} — خطا: {e}")
                continue
            async_to_sync(update_location_change_request)(req_obj.id, "approved")
            messages.success(request, f"✅ سرویس سفارش #{req_obj.order_id} منتقل شد.")

    @admin.action(description="❌ رد کردن درخواست‌ها")
    def reject_requests(self, request, queryset):
        from shared_lib.db import update_location_change_request
        for req_obj in queryset:
            if req_obj.status not in ("approved", "rejected"):
                async_to_sync(update_location_change_request)(req_obj.id, "rejected")
        messages.success(request, f"{queryset.count()} درخواست رد شد.")
