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