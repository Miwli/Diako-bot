# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class DiscountCodeUses(models.Model):
    pk = models.CompositePrimaryKey('code_id', 'user_id')
    code_id = models.IntegerField()
    user_id = models.IntegerField()
    used_at = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'discount_code_uses'
        verbose_name = 'استفاده از کد تخفیف'
        verbose_name_plural = 'استفاده از کدهای تخفیف'


class DiscountCodes(models.Model):
    code = models.TextField(unique=True)
    type = models.TextField()
    value = models.IntegerField()
    max_uses = models.IntegerField(blank=True, null=True)
    used_count = models.IntegerField(blank=True, null=True)
    is_active = models.IntegerField(blank=True, null=True)
    expires_at = models.TextField(blank=True, null=True)
    created_at = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'discount_codes'
        verbose_name = 'کد تخفیف'
        verbose_name_plural = 'کدهای تخفیف'


class Faqs(models.Model):
    question = models.TextField()
    answer = models.TextField()
    order_index = models.IntegerField(blank=True, null=True)
    is_active = models.IntegerField(blank=True, null=True)
    created_at = models.TextField(blank=True, null=True)  # This field type is a guess.
    answer_entities = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'faqs'
        verbose_name = 'سوال متداول'
        verbose_name_plural = 'سوالات متداول'


class Orders(models.Model):
    user_id = models.IntegerField()
    username = models.TextField(blank=True, null=True)
    plan = models.ForeignKey('Plans', models.DO_NOTHING)
    receipt_file_id = models.TextField()
    status = models.TextField()
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.TextField(blank=True, null=True)  # This field type is a guess.
    vpn_username = models.TextField(blank=True, null=True)
    subscription_url = models.TextField(blank=True, null=True)
    order_type = models.TextField(blank=True, null=True)
    free_test_server_id = models.IntegerField(blank=True, null=True)
    discount_code = models.TextField(blank=True, null=True)
    discount_amount = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'orders'
        verbose_name = 'سفارش'
        verbose_name_plural = 'سفارش‌ها'


class Plans(models.Model):
    server = models.ForeignKey('Servers', models.DO_NOTHING, blank=True, null=True)
    name = models.TextField()
    price = models.IntegerField()
    duration = models.IntegerField()
    traffic = models.IntegerField()
    is_active = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'plans'
        verbose_name = 'پلن'
        verbose_name_plural = 'پلن‌ها'


class Referrals(models.Model):
    referrer_id = models.IntegerField()
    referred_id = models.IntegerField(unique=True)
    first_purchase_rewarded = models.IntegerField(blank=True, null=True)
    total_commission = models.IntegerField(blank=True, null=True)
    created_at = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'referrals'
        verbose_name = 'دعوت'
        verbose_name_plural = 'دعوت دوستان'


class Servers(models.Model):
    name = models.TextField(unique=True)
    panel_url = models.TextField()
    panel_token = models.TextField()
    is_active = models.IntegerField(blank=True, null=True)
    service_id = models.TextField(blank=True, null=True)
    service_ids = models.TextField(blank=True, null=True)
    api_version = models.TextField(blank=True, null=True)
    free_test_enabled = models.IntegerField(blank=True, null=True)
    free_test_duration = models.IntegerField(blank=True, null=True)
    free_test_traffic = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'servers'
        verbose_name = 'سرور'
        verbose_name_plural = 'سرورها'


class Settings(models.Model):
    key = models.TextField(primary_key=True)
    value = models.TextField()

    class Meta:
        managed = False
        db_table = 'settings'
        verbose_name = 'تنظیم'
        verbose_name_plural = 'تنظیمات'


class Tickets(models.Model):
    user_id = models.IntegerField()
    topic_id = models.IntegerField(blank=True, null=True)
    group_id = models.IntegerField(blank=True, null=True)
    status = models.TextField(blank=True, null=True)
    created_at = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'tickets'
        verbose_name = 'تیکت'
        verbose_name_plural = 'تیکت‌ها'


class TopUpRequests(models.Model):
    user_id = models.IntegerField()
    username = models.TextField(blank=True, null=True)
    amount = models.IntegerField()
    receipt_file_id = models.TextField()
    status = models.TextField()
    created_at = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'top_up_requests'
        verbose_name = 'شارژ حساب'
        verbose_name_plural = 'شارژ حساب'


class Transactions(models.Model):
    user = models.ForeignKey('Users', models.DO_NOTHING)
    amount = models.IntegerField()
    type = models.TextField()
    description = models.TextField(blank=True, null=True)
    created_at = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'transactions'
        verbose_name = 'تراکنش'
        verbose_name_plural = 'تراکنش‌ها'


class Tutorials(models.Model):
    title = models.TextField()
    content_type = models.TextField()
    file_id = models.TextField(blank=True, null=True)
    caption = models.TextField(blank=True, null=True)
    order_index = models.IntegerField(blank=True, null=True)
    is_active = models.IntegerField(blank=True, null=True)
    created_at = models.TextField(blank=True, null=True)  # This field type is a guess.
    caption_entities = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tutorials'
        verbose_name = 'آموزش'
        verbose_name_plural = 'آموزش‌ها'


class Users(models.Model):
    user_id = models.AutoField(primary_key=True)
    first_name = models.TextField(blank=True, null=True)
    username = models.TextField(blank=True, null=True)
    balance = models.IntegerField(blank=True, null=True)
    created_at = models.TextField(blank=True, null=True)  # This field type is a guess.
    referral_code = models.TextField(blank=True, null=True)
    free_test_uses = models.IntegerField(blank=True, null=True)
    referral_by = models.TextField(blank=True, null=True)
    is_banned = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'users'
        verbose_name = 'کاربر'


class KeyboardButtons(models.Model):
    keyboard_name     = models.TextField()
    label             = models.TextField()
    callback_data     = models.TextField()
    row_index         = models.IntegerField(default=0)
    col_index         = models.IntegerField(default=0)
    is_active         = models.IntegerField(default=1)
    callback_template = models.TextField(blank=True, null=True)
    admin_only        = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'keyboard_buttons'
        verbose_name = 'دکمه کیبورد'
        verbose_name_plural = 'دکمه‌های کیبورد'

    def __str__(self):
        return f"[{self.keyboard_name}] {self.label} → {self.callback_data}"


class KeyboardActions(models.Model):
    action_name   = models.TextField(unique=True)
    label         = models.TextField()
    callback_data = models.TextField()
    grp           = models.TextField(default='user')

    class Meta:
        managed = False
        db_table = 'keyboard_actions'
        verbose_name = 'اکشن کیبورد'
        verbose_name_plural = 'کاتالوگ اکشن‌ها'

    def __str__(self):
        return f"[{self.grp}] {self.label} — {self.callback_data}"


class ExtraVolumePlans(models.Model):
    name        = models.TextField()
    traffic_gb  = models.FloatField()
    price       = models.IntegerField()
    is_active   = models.IntegerField(default=1)
    order_index = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'extra_volume_plans'
        verbose_name = 'پکیج افزودن حجم'
        verbose_name_plural = 'پکیج‌های افزودن حجم'

    def __str__(self):
        return f"{self.name} — {self.traffic_gb}GB — {self.price:,} تومان"


class ExtraVolumeRequests(models.Model):
    user_id         = models.IntegerField()
    order_id        = models.IntegerField()
    plan_id         = models.IntegerField()
    receipt_file_id = models.TextField(blank=True, null=True)
    status          = models.TextField(default='pending')
    created_at      = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'extra_volume_requests'
        verbose_name = 'درخواست افزودن حجم'
        verbose_name_plural = 'درخواست‌های افزودن حجم'

    def __str__(self):
        return f"درخواست #{self.pk} — کاربر {self.user_id} — وضعیت: {self.status}"


class ExtraTimePlans(models.Model):
    name        = models.TextField()
    days        = models.IntegerField()
    price       = models.IntegerField()
    is_active   = models.IntegerField(default=1)
    order_index = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'extra_time_plans'
        verbose_name = 'پکیج افزودن زمان'
        verbose_name_plural = 'پکیج‌های افزودن زمان'

    def __str__(self):
        return f"{self.name} — {self.days} روز — {self.price:,} تومان"


class ExtraTimeRequests(models.Model):
    user_id         = models.IntegerField()
    order_id        = models.IntegerField()
    plan_id         = models.IntegerField()
    receipt_file_id = models.TextField(blank=True, null=True)
    status          = models.TextField(default='pending')
    created_at      = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'extra_time_requests'
        verbose_name = 'درخواست افزودن زمان'
        verbose_name_plural = 'درخواست‌های افزودن زمان'

    def __str__(self):
        return f"درخواست #{self.pk} — کاربر {self.user_id} — وضعیت: {self.status}"
