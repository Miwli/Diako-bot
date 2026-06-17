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
        """ساخت URL کامل لینک ساب — با دامنه اختصاصی ادمین یا آدرس پنل"""
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

    async def create_user(self, service_id: int, data_limit_gb: int, duration_days: int) -> dict:
        """ساخت یوزر جدید با استفاده از service_id"""
        username = self._random_username()
        expire_ts = int(time.time()) + (duration_days * 86400)
        data_limit_bytes = data_limit_gb * 1024 * 1024 * 1024

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
                f"{self.base_url}/api/user",
                json=payload,
                ssl=False
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    def _random_username(self) -> str:
        chars = string.ascii_lowercase + string.digits
        return "bp_" + "".join(random.choices(chars, k=8))
