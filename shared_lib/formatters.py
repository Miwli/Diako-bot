# توابع نمایش حجم — زیر ۱ گیگ به مگابایت، بالاتر به گیگابایت
# مشترک بین بات و پنل


def fmt_traffic_gb(gb) -> str:
    """نمایش هوشمند حجم بر حسب گیگابایت ورودی"""
    try:
        gb = float(gb)
    except (TypeError, ValueError):
        gb = 0.0
    if gb <= 0:
        return "۰ مگابایت"
    if gb < 1:
        mb = gb * 1024
        # زیر ۱۰ مگ یک رقم اعشار، بالاتر عدد صحیح
        return (f"{mb:.1f}" if mb < 10 else f"{round(mb)}") + " مگابایت"
    return (f"{int(gb)}" if gb == int(gb) else f"{gb:.1f}") + " گیگابایت"


def fmt_traffic_bytes(b) -> str:
    """همون تابع بالا ولی ورودی بایت (از API ربکا)"""
    try:
        b = float(b or 0)
    except (TypeError, ValueError):
        b = 0.0
    return fmt_traffic_gb(b / (1024 ** 3))
