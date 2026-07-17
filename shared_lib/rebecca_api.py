import time
import random
import string
import aiohttp

class RebeccaAPI:
    def __init__(self, panel_url: str, token: str):
        self.base_url = panel_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    async def get_subscription_url(self, sub_path: str) -> str:
        """ساخت URL کامل لینک ساب — اگه URL کامل بود همونو برگردون"""
        if sub_path.startswith("http"):
            return sub_path
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(f"{self.base_url}/api/admin", ssl=False) as resp:
                if resp.status == 200:
                    admin = await resp.json()
                    domain = admin.get("subscription_domain")
                    if domain:
                        if not domain.startswith("http"):
                            domain = f"https://{domain}"
                        return domain.rstrip("/") + sub_path
        return self.base_url + sub_path

    async def get_services(self) -> list:
        """گرفتن لیست سرویس‌های تعریف‌شده در پنل"""
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(
                f"{self.base_url}/api/v2/services",
                ssl=False
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("services", [])

    async def create_user(self, service_id: int, data_limit_gb: float, duration_days: float = 0,
                          duration_hours: float = 0, ip_limit: int = 0) -> dict:
        """ساخت یوزر — duration (0 = بی‌نهایت) | data_limit_gb=0 = نامحدود | ip_limit=0 = نامحدود"""
        username = self._random_username()
        total_hours = duration_hours if duration_hours else duration_days * 24
        expire_ts = 0 if total_hours == 0 else int(time.time()) + int(total_hours * 3600)
        data_limit_bytes = 0 if data_limit_gb == 0 else int(data_limit_gb * 1024 * 1024 * 1024)

        payload = {
            "username": username,
            "service_id": service_id,
            "expire": expire_ts,
            "data_limit": data_limit_bytes,
            "data_limit_reset_strategy": "no_reset",
            "ip_limit": ip_limit,
            "status": "active"
        }

        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(
                f"{self.base_url}/api/v2/users",
                json=payload,
                ssl=False
            ) as resp:
                if not resp.ok:
                    body = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {body}")
                return await resp.json()

    async def delete_user(self, username: str) -> None:
        """حذف یوزر از پنل"""
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.delete(
                f"{self.base_url}/api/user/{username}",
                ssl=False
            ) as resp:
                resp.raise_for_status()

    async def get_user(self, username: str) -> dict:
        """دریافت اطلاعات زنده یوزر از پنل"""
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(
                f"{self.base_url}/api/user/{username}",
                ssl=False
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def add_time(self, username: str, extra_days: int) -> dict:
        """افزودن زمان به یوزر — اگه منقضی شده از الان حساب می‌کنه، وگرنه از انقضای فعلی"""
        import time as _time
        current = await self.get_user(username)
        current_expire = current.get("expire", 0)
        now = int(_time.time())
        base = max(current_expire, now) if current_expire else now
        new_expire = base + extra_days * 86400
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.put(
                f"{self.base_url}/api/user/{username}",
                json={"expire": new_expire},
                ssl=False
            ) as resp:
                if not resp.ok:
                    body = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {body}")
                return await resp.json()

    async def add_volume(self, username: str, extra_gb: float) -> dict:
        """افزودن حجم به یوزر موجود — اگه نامحدود باشد بدون تغییر برمی‌گردد"""
        current = await self.get_user(username)
        current_limit = current.get("data_limit", 0)
        if current_limit == 0:
            return current  # نامحدود — تغییر نمی‌کند
        extra_bytes = int(extra_gb * 1024 * 1024 * 1024)
        new_limit = current_limit + extra_bytes
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.put(
                f"{self.base_url}/api/user/{username}",
                json={"data_limit": new_limit},
                ssl=False
            ) as resp:
                if not resp.ok:
                    body = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {body}")
                return await resp.json()

    async def toggle_status(self, username: str, active: bool) -> dict:
        """فعال یا غیرفعال کردن یوزر"""
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.put(
                f"{self.base_url}/api/user/{username}",
                json={"status": "active" if active else "disabled"},
                ssl=False
            ) as resp:
                if not resp.ok:
                    body = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {body}")
                return await resp.json()

    async def get_nodes(self) -> list:
        """لیست نودهای پنل با وضعیت اتصال هرکدوم"""
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(
                f"{self.base_url}/api/nodes",
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def get_system_stats(self) -> dict:
        """آمار کلی پنل — کاربران، پهنای باند، CPU و RAM"""
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(
                f"{self.base_url}/api/system",
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    def _random_username(self) -> str:
        chars = string.ascii_lowercase + string.digits
        return "bp_" + "".join(random.choices(chars, k=8))
