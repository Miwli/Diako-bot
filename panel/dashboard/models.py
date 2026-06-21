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


class Referrals(models.Model):
    referrer_id = models.IntegerField()
    referred_id = models.IntegerField(unique=True)
    first_purchase_rewarded = models.IntegerField(blank=True, null=True)
    total_commission = models.IntegerField(blank=True, null=True)
    created_at = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'referrals'


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


class Settings(models.Model):
    key = models.TextField(primary_key=True)
    value = models.TextField()

    class Meta:
        managed = False
        db_table = 'settings'


class Tickets(models.Model):
    user_id = models.IntegerField()
    topic_id = models.IntegerField(blank=True, null=True)
    group_id = models.IntegerField(blank=True, null=True)
    status = models.TextField(blank=True, null=True)
    created_at = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'tickets'


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


class Transactions(models.Model):
    user = models.ForeignKey('Users', models.DO_NOTHING)
    amount = models.IntegerField()
    type = models.TextField()
    description = models.TextField(blank=True, null=True)
    created_at = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'transactions'


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
