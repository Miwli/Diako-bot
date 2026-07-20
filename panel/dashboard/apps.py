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
        self._start_restart_watcher()

    def _start_restart_watcher(self):
        import os
        # only self-exit in environments wired for it (Docker/systemd), never in dev
        if os.environ.get('ENABLE_SELF_RESTART') != '1':
            return
        import time
        import signal
        import threading

        def watch():
            from shared_lib.db import get_setting_sync
            start = time.time()
            while True:
                time.sleep(5)
                try:
                    val = get_setting_sync('restart_panel_requested')
                    if val and float(val) > start:
                        # signal the gunicorn master (our parent) to shut down;
                        # the restart policy brings the panel back up
                        os.kill(os.getppid(), signal.SIGTERM)
                        return
                except Exception:
                    pass

        threading.Thread(target=watch, daemon=True).start()
