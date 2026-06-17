from aiogram.fsm.state import State, StatesGroup

class AddPlan(StatesGroup):
    waiting_for_name     = State()
    waiting_for_price    = State()
    waiting_for_duration = State()
    waiting_for_traffic  = State()

class AddServer(StatesGroup):
    waiting_for_name  = State()
    waiting_for_url   = State()
    waiting_for_token = State()