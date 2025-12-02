from aiogram.dispatcher.filters.state import State, StatesGroup

class Purchase(StatesGroup):
    waiting_confirmation = State()
