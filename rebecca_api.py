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
                          duration_hours: float = 0) -> dict:
        """ساخت یوزر — duration_days یا duration_hours (0 = بی‌نهایت) | data_limit_gb=0 = نامحدود"""
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

    def _random_username(self) -> str:
        chars = string.ascii_lowercase + string.digits
        return "bp_" + "".join(random.choices(chars, k=8))
