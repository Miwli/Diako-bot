from django.urls import path, include
from django.views.generic import RedirectView
from dashboard import views as v
from dashboard import api_views


urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('diako/', RedirectView.as_view(url='/diako/login/', permanent=False)),
    path('diako/login/', v.login_view, name='diako_login'),
    path('diako/logout/', v.logout_view, name='diako_logout'),
    path('diako/dashboard/', v.dashboard_view, name='diako_dashboard'),
    path('diako/keyboard-editor/', v.keyboard_editor_view, name='diako_keyboard_editor'),
    path('diako/texts-editor/', v.texts_editor_view, name='diako_texts_editor'),
    path('diako/import-export/', v.import_export_view, name='diako_import_export'),
    path('diako/monitoring/', v.monitoring_view, name='diako_monitoring'),
    path('diako/api/pending-orders/', api_views.pending_orders, name='diako_pending_orders'),
    path('diako/api/chart-data/', api_views.chart_data, name='diako_chart_data'),
    path('diako/api/save-keyboard/', api_views.save_keyboard, name='diako_save_keyboard'),
    path('diako/api/keyboard/<str:keyboard_name>/', api_views.keyboard_data, name='diako_keyboard_data'),
    path('diako/api/bot-info/', api_views.bot_info, name='diako_bot_info'),
    path('diako/api/update-text/', api_views.update_text, name='diako_update_text'),
    path('diako/orders/', v.orders_view, name='diako_orders'),
    path('diako/users/', v.users_view, name='diako_users'),
    path('diako/api/order-action/', api_views.order_action, name='diako_order_action'),
    path('diako/api/user-detail/<int:user_id>/', api_views.user_detail, name='diako_user_detail'),
    path('diako/api/user-action/', api_views.user_action, name='diako_user_action'),
    # New pages
    path('diako/servers/', v.servers_view, name='diako_servers'),
    path('diako/plans/', v.plans_view, name='diako_plans'),
    path('diako/finance/', v.finance_view, name='diako_finance'),
    path('diako/extra-requests/', v.extra_requests_view, name='diako_extra_requests'),
    path('diako/settings/bot/', v.settings_bot_view, name='diako_settings_bot'),
    # مسیرهای قدیمی — این صفحه‌ها داخل مالی/تنظیمات ادغام شدن
    path('diako/discounts/', RedirectView.as_view(url='/diako/finance/', permanent=False)),
    path('diako/tutorials/', RedirectView.as_view(url='/diako/settings/bot/', permanent=False)),
    path('diako/force-join/', RedirectView.as_view(url='/diako/settings/bot/', permanent=False)),
    # New API endpoints
    path('diako/api/server-action/', api_views.server_action, name='diako_server_action'),
    path('diako/api/plan-action/', api_views.plan_action, name='diako_plan_action'),
    path('diako/api/finance-action/', api_views.finance_action, name='diako_finance_action'),
    path('diako/api/discount-action/', api_views.discount_action, name='diako_discount_action'),
    path('diako/api/tutorial-action/', api_views.tutorial_action, name='diako_tutorial_action'),
    path('diako/api/extra-request-action/', api_views.extra_request_action, name='diako_extra_request_action'),
    path('diako/api/service-action/', api_views.service_action, name='diako_service_action'),
    path('diako/api/import-config/', api_views.import_config, name='diako_import_config'),
    path('diako/api/backup-manifest/', api_views.backup_manifest, name='diako_backup_manifest'),
    path('diako/api/export-data/', api_views.export_data, name='diako_export_data'),
    path('diako/api/export-full-db/', api_views.export_full_db, name='diako_export_full_db'),
    path('diako/api/import-data/', api_views.import_data, name='diako_import_data'),
    path('diako/api/import-full-db/', api_views.import_full_db, name='diako_import_full_db'),
    path('diako/api/nodes-status/', api_views.nodes_status, name='diako_nodes_status'),
    path('diako/api/force-join-action/', api_views.force_join_action, name='diako_force_join_action'),
    path('diako/api/bot-status/', api_views.bot_status, name='diako_bot_status'),
    path('diako/api/search/', api_views.global_search, name='diako_global_search'),
]
