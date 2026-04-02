from aiogram.fsm.state import State, StatesGroup


class AdminAddProduct(StatesGroup):
    category = State()
    name = State()
    price = State()
    description = State()
    stock = State()
    photo = State()


class AdminEditProduct(StatesGroup):
    price = State()
    stock = State()
    photo = State()


class CheckoutForm(StatesGroup):
    delivery_method = State()
    first_name = State()
    last_name = State()
    middle_name = State()
    phone = State()
    city = State()
    branch = State()
    payment = State()
    bonus_confirm = State()
    # City delivery flow
    city_recip_name = State()
    city_recip_address = State()
    city_recip_phone = State()


class OrderReceiptForm(StatesGroup):
    file = State()


class ProfileForm(StatesGroup):
    first_name = State()
    last_name = State()
    middle_name = State()
    phone = State()
    city = State()
    branch = State()


class AdminBroadcast(StatesGroup):
    text = State()


class SearchForm(StatesGroup):
    query = State()


class AdminWelcome(StatesGroup):
    text = State()
    photo = State()


class AdminNotifications(StatesGroup):
    admin_new_order_template = State()
    user_status_template = State()
    notify_chat_id = State()


class AdminUsers(StatesGroup):
    add_admin_id = State()
    message_text = State()
    bonus_amount = State()


class AdminCategory(StatesGroup):
    name = State()


class AdminCatalogImport(StatesGroup):
    file = State()


class AdminPayments(StatesGroup):
    card = State()
    applepay = State()
    googlepay = State()


class SupportDialog(StatesGroup):
    user_message = State()
    admin_reply = State()
