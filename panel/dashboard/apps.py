from django.apps import AppConfig


class DashboardConfig(AppConfig):
    name = 'dashboard'

    def ready(self):
        from asgiref.sync import async_to_sync
        from shared_lib.db import init_db
        try:
            async_to_sync(init_db)()
        except Exception:
            pass
