from aiogram.fsm.state import State, StatesGroup

class AddPlan(StatesGroup):
    waiting_for_name     = State()
    waiting_for_price    = State()
    waiting_for_duration = State()
    waiting_for_traffic  = State()

class AddServer(StatesGroup):
    waiting_for_name    = State()
    waiting_for_url     = State()
    waiting_for_token   = State()
    waiting_for_service = State()

class EditServer(StatesGroup):
    waiting_for_url   = State()
    waiting_for_token = State()

class BuyVPN(StatesGroup):
    waiting_for_receipt = State()

class AdminAction(StatesGroup):
    waiting_for_rejection_reason = State()

class SetCardInfo(StatesGroup):
    waiting_for_card_number = State()
    waiting_for_card_owner  = State()

class TopUp(StatesGroup):
    waiting_for_amount  = State()
    waiting_for_receipt = State()

class EditPlan(StatesGroup):
    waiting_for_price    = State()
    waiting_for_duration = State()
    waiting_for_traffic  = State()

class GeneralSettings(StatesGroup):
    waiting_for_banner     = State()
    waiting_for_caption    = State()
    waiting_for_emoji_text = State()

class FreeTestSettings(StatesGroup):
    waiting_for_global_duration = State()
    waiting_for_global_traffic  = State()
    waiting_for_max_uses        = State()
    waiting_for_server_duration = State()
    waiting_for_server_traffic  = State()

class Support(StatesGroup):
    waiting_for_first_message = State()
    in_conversation           = State()

class AdminSupportSettings(StatesGroup):
    waiting_for_group_id   = State()
    waiting_for_ticket_msg = State()

class AddTutorial(StatesGroup):
    waiting_for_title   = State()
    waiting_for_content = State()

class EditTutorial(StatesGroup):
    waiting_for_title   = State()
    waiting_for_content = State()

class AddFAQ(StatesGroup):
    waiting_for_question = State()
    waiting_for_answer   = State()

class EditFAQ(StatesGroup):
    waiting_for_question = State()
    waiting_for_answer   = State()

class ReferralSettings(StatesGroup):
    waiting_for_flat_amount    = State()
    waiting_for_percent_value  = State()
    waiting_for_discount_value = State()

class AdminUserManagement(StatesGroup):
    waiting_for_search_query  = State()
    waiting_for_add_amount    = State()
    waiting_for_deduct_amount = State()
    waiting_for_ban_reason    = State()
    waiting_for_direct_msg    = State()

class Broadcast(StatesGroup):
    waiting_for_content = State()
    waiting_for_confirm = State()

class AddDiscountCode(StatesGroup):
    waiting_for_code     = State()
    waiting_for_type     = State()
    waiting_for_value    = State()
    waiting_for_max_uses = State()
    waiting_for_expiry   = State()

class ApplyDiscount(StatesGroup):
    waiting_for_code = State()

