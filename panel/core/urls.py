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
    path('diako/api/pending-orders/', api_views.pending_orders, name='diako_pending_orders'),
]
