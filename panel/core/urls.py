from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from dashboard import views as v
from dashboard import api_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('diako/', RedirectView.as_view(url='/diako/login/', permanent=False)),
    path('diako/login/', v.login_view, name='diako_login'),
    path('diako/logout/', v.logout_view, name='diako_logout'),
    path('diako/dashboard/', v.dashboard_view, name='diako_dashboard'),
    path('diako/keyboard-editor/', v.keyboard_editor_view, name='diako_keyboard_editor'),
    path('diako/api/pending-orders/', api_views.pending_orders, name='diako_pending_orders'),
    path('diako/api/chart-data/', api_views.chart_data, name='diako_chart_data'),
    path('diako/api/save-keyboard/', api_views.save_keyboard, name='diako_save_keyboard'),
    path('diako/api/keyboard/<str:keyboard_name>/', api_views.keyboard_data, name='diako_keyboard_data'),
]
