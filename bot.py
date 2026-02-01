import asyncio
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import Config
from database import Database
from games import GameEngine

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Проверяем настройки
Config.validate()

# Инициализация бота и БД
bot = Bot(token=Config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()

# Состояния для FSM
class GameStates(StatesGroup):
    choosing_game = State()
    choosing_bet = State()
    playing_flip = State()
    playing_dice = State()

class WithdrawState(StatesGroup):
    choosing_amount = State()

class AdminStates(StatesGroup):
    adding_sponsor = State()
    broadcasting = State()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def format_balance(balance: float) -> str:
    return f"{balance:.2f}"

def format_time(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        return f"{seconds // 60} мин {seconds % 60} сек"
    else:
        return f"{seconds // 3600} ч {(seconds % 3600) // 60} мин"

def create_main_menu(user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="🐵 Заработать звезды", callback_data="earn")],
        [InlineKeyboardButton(text="🎮 Играть в игры", callback_data="play_games")],
        [InlineKeyboardButton(text="📊 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="referral")],
    ]
    
    # Добавляем админ панель для администратора
    if user_id == Config.ADMIN_ID:
        keyboard.append([InlineKeyboardButton(text="👑 Админ панель", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def check_subscriptions(user_id: int) -> bool:
    """Проверить подписки пользователя на спонсоров"""
    try:
        sponsors_status = db.get_user_sponsors_status(user_id)
        if not sponsors_status:  # Если нет спонсоров
            return True
        
        for sponsor in sponsors_status:
            if not sponsor.get('is_subscribed', False):
                return False
        return True
    except Exception as e:
        logger.error(f"Error checking subscriptions for {user_id}: {e}")
        return False

# ========== ОБРАБОТЧИКИ КОМАНД ==========

@dp.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject = None):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    logger.info(f"User {user_id} ({username}) started bot")
    
    # Обработка реферальной ссылки
    referrer_id = None
    if command and command.args:
        try:
            referrer_id = int(command.args)
            if referrer_id == user_id:  # Нельзя самому себя пригласить
                referrer_id = None
        except ValueError:
            referrer_id = None
    
    # Создаем/обновляем пользователя
    db.create_user(user_id, username, referrer_id)
    
    # Проверяем подписки
    if not await check_subscriptions(user_id):
        await show_sponsors_message(message, user_id)
        return
    
    # Показываем главное меню
    await show_main_menu(message)

async def show_sponsors_message(message: Message, user_id: int):
    """Показать сообщение о необходимости подписки"""
    sponsors = db.get_sponsors()
    
    if not sponsors:
        await show_main_menu(message)
        return
    
    keyboard = []
    for sponsor in sponsors:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📢 {sponsor.get('channel_username', 'Канал')}",
                url=sponsor.get('channel_url', 'https://t.me')
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="✅ Я подписался",
            callback_data="check_subscriptions"
        )
    ])
    
    await message.answer(
        "📢 *Чтобы начать, подпишитесь на наших спонсоров!*\n\n"
        "После подписки нажмите кнопку ниже:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

async def show_main_menu(message: Message, text: str = None):
    """Показать главное меню"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    balance = user['balance'] if user else 0.0
    
    welcome_text = text or (
        "🐵 *Monkey Stars*\n\n"
        f"💰 Баланс: *{format_balance(balance)} STAR*\n\n"
        "Выберите действие:"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=create_main_menu(user_id),
        parse_mode="Markdown"
    )

# ========== CALLBACK ОБРАБОТЧИКИ ==========

@dp.callback_query(F.data == "check_subscriptions")
async def handle_check_subscriptions(callback: CallbackQuery):
    """Проверка подписок после нажатия кнопки"""
    user_id = callback.from_user.id
    
    # Имитируем успешную подписку (в реальности нужно проверять через getChatMember)
    sponsors = db.get_sponsors()
    for sponsor in sponsors:
        db.update_user_sponsor_status(user_id, sponsor['id'], True)
    
    await callback.answer("✅ Отлично! Доступ открыт!")
    await callback.message.delete()
    await show_main_menu(callback.message)

@dp.callback_query(F.data == "earn")
async def handle_earn(callback: CallbackQuery):
    """Меню заработка"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        await show_sponsors_message(callback.message, user_id)
        return
    
    keyboard = [
        [InlineKeyboardButton(text="🎯 Кликнуть (+0.2 STAR)", callback_data="click")],
        [InlineKeyboardButton(text="💸 Вывод средств", callback_data="withdraw_menu")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ]
    
    await callback.message.edit_text(
        "🐵 *Заработать звезды*\n\n"
        "Выберите способ заработка:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "click")
async def handle_click(callback: CallbackQuery):
    """Обработка кликера"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    current_time = int(datetime.now().timestamp())
    last_click = user.get('last_click')
    
    # Проверка кулдауна
    if last_click and (current_time - last_click) < Config.CLICK_COOLDOWN:
        remaining = Config.CLICK_COOLDOWN - (current_time - last_click)
        await callback.answer(f"⏳ Подождите {format_time(remaining)}")
        return
    
    # Начисление клика
    reward = Config.CLICK_REWARD
    db.update_balance(user_id, reward)
    db.update_last_click(user_id, current_time)
    db.add_transaction(user_id, reward, "click", "Кликер")
    
    # Реферальный бонус (10%)
    referrer_id = user.get('referrer_id')
    if referrer_id:
        referral_bonus = reward * (Config.CLICK_REFERRAL_PERCENT / 100)
        db.update_balance(referrer_id, referral_bonus)
        db.add_transaction(
            referrer_id,
            referral_bonus,
            "referral_income",
            f"10% от клика пользователя {callback.from_user.username or user_id}"
        )
    
    # Обновляем сообщение
    user = db.get_user(user_id)
    await callback.message.edit_text(
        f"✅ *Вы получили {reward} STAR!*\n\n"
        f"💰 Баланс: *{format_balance(user['balance'])} STAR*\n\n"
        f"⏰ Следующий клик через 1 час",
        parse_mode="Markdown",
        reply_markup=callback.message.reply_markup
    )
    
    await callback.answer(f"+{reward} STAR")

# ========== ИГРЫ ==========

@dp.callback_query(F.data == "play_games")
async def handle_play_games(callback: CallbackQuery):
    """Выбор игры"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton(text=Config.GAMES['flip']['name'], callback_data="game_flip")],
        [InlineKeyboardButton(text=Config.GAMES['crash']['name'], callback_data="game_crash")],
        [InlineKeyboardButton(text=Config.GAMES['slot']['name'], callback_data="game_slot")],
        [InlineKeyboardButton(text=Config.GAMES['dice']['name'], callback_data="game_dice")],
        [InlineKeyboardButton(text=Config.GAMES['jackpot']['name'], callback_data="game_jackpot")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ]
    
    await callback.message.edit_text(
        "🎮 *Выберите игру:*\n\n"
        "💎 *Monkey Flip* - Подбрось банан и угадай сторону\n"
        "🚀 *Banana Crash* - Забери деньги до краша\n"
        "🎰 *Банановый слот* - Крути барабаны\n"
        "🎲 *Банановые кости* - Угадай число\n"
        "💰 *Джекпот* - Выиграй x100",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "game_flip")
async def handle_game_flip(callback: CallbackQuery, state: FSMContext):
    """Игра Monkey Flip"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    await state.set_state(GameStates.playing_flip)
    await state.update_data(game_type="flip")
    
    keyboard = [
        [InlineKeyboardButton(text="🍌 Banana", callback_data="flip_heads")],
        [InlineKeyboardButton(text="🐵 Monkey", callback_data="flip_tails")],
        [InlineKeyboardButton(text="◀️ Назад к играм", callback_data="play_games")]
    ]
    
    await callback.message.edit_text(
        f"🎯 *Monkey Flip*\n\n"
        f"💰 Ваш баланс: *{format_balance(user['balance'])} STAR*\n"
        f"📈 Шанс выигрыша: *49%*\n"
        f"🎲 Множитель: *x2.0*\n\n"
        f"Выберите сторону:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("flip_"))
async def handle_flip_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора в игре Flip"""
    user_id = callback.from_user.id
    choice = callback.data.split("_")[1]  # heads или tails
    
    # Запрашиваем ставку
    await callback.message.edit_text(
        f"🎯 Вы выбрали: {'🍌 Banana' if choice == 'heads' else '🐵 Monkey'}\n\n"
        f"💰 Введите сумму ставки (минимум {Config.MIN_BETS['flip']} STAR):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="game_flip")]
        ])
    )
    
    await state.update_data(flip_choice=choice)
    await state.set_state(GameStates.choosing_bet)

@dp.message(GameStates.choosing_bet)
async def handle_bet_input(message: Message, state: FSMContext):
    """Обработка ввода ставки"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Ошибка, попробуйте /start")
        await state.clear()
        return
    
    try:
        bet = float(message.text)
        
        # Проверка минимальной ставки
        min_bet = Config.MIN_BETS['flip']
        if bet < min_bet:
            await message.answer(f"❌ Минимальная ставка: {min_bet} STAR")
            return
        
        # Проверка баланса
        if user['balance'] < bet:
            await message.answer(f"❌ Недостаточно STAR. Ваш баланс: {format_balance(user['balance'])}")
            return
        
        # Получаем данные о выборе
        data = await state.get_data()
        choice = data.get('flip_choice')
        game_type = data.get('game_type')
        
        if game_type == "flip":
            # Играем в Flip
            win, amount, result_text = GameEngine.play_flip(bet, choice)
            
            # Обновляем баланс и статистику
            if win:
                db.update_balance(user_id, amount - bet)
                db.add_transaction(user_id, amount - bet, "game_win", f"Monkey Flip выигрыш x2.0")
                db.update_game_stats(user_id, bet, True)
            else:
                db.update_balance(user_id, -bet)
                db.add_transaction(user_id, -bet, "game_lose", "Monkey Flip проигрыш")
                db.update_game_stats(user_id, bet, False)
            
            # Получаем обновленный баланс
            user = db.get_user(user_id)
            
            await message.answer(
                f"🎯 *Monkey Flip*\n\n"
                f"{result_text}\n\n"
                f"💰 Новый баланс: *{format_balance(user['balance'])} STAR*\n\n"
                f"🎮 Сыграть ещё?",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎯 Играть снова", callback_data="game_flip")],
                    [InlineKeyboardButton(text="🎮 Все игры", callback_data="play_games")],
                    [InlineKeyboardButton(text="🐵 Главное меню", callback_data="main_menu")]
                ]),
                parse_mode="Markdown"
            )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число!")
    except Exception as e:
        logger.error(f"Error in handle_bet_input: {e}")
        await message.answer("❌ Произошла ошибка")
        await state.clear()

@dp.callback_query(F.data == "game_crash")
async def handle_game_crash(callback: CallbackQuery, state: FSMContext):
    """Игра Banana Crash"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    await state.update_data(game_type="crash")
    
    keyboard = [
        [InlineKeyboardButton(text="🚀 Играть (ставка 1 STAR)", callback_data="crash_play_1")],
        [InlineKeyboardButton(text="🚀 Играть (ставка 5 STAR)", callback_data="crash_play_5")],
        [InlineKeyboardButton(text="🚀 Играть (ставка 10 STAR)", callback_data="crash_play_10")],
        [InlineKeyboardButton(text="◀️ Назад к играм", callback_data="play_games")]
    ]
    
    await callback.message.edit_text(
        f"🚀 *Banana Crash*\n\n"
        f"💰 Ваш баланс: *{format_balance(user['balance'])} STAR*\n"
        f"📈 Множитель растет от x1.00\n"
        f"💥 60% шанс мгновенного краша\n"
        f"🎰 2% шанс на высокий множитель\n\n"
        f"Выберите ставку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("crash_play_"))
async def handle_crash_play(callback: CallbackQuery, state: FSMContext):
    """Играем в Crash"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    try:
        bet = float(callback.data.split("_")[2])
        
        # Проверка баланса
        if user['balance'] < bet:
            await callback.answer(f"❌ Недостаточно STAR. Баланс: {format_balance(user['balance'])}")
            return
        
        # Играем в Crash
        win, amount, result_text = GameEngine.play_crash(bet)
        
        # Обновляем баланс и статистику
        if win:
            db.update_balance(user_id, amount - bet)
            db.add_transaction(user_id, amount - bet, "game_win", f"Banana Crash выигрыш x{amount/bet:.2f}")
            db.update_game_stats(user_id, bet, True)
        else:
            db.update_balance(user_id, -bet)
            db.add_transaction(user_id, -bet, "game_lose", "Banana Crash проигрыш")
            db.update_game_stats(user_id, bet, False)
        
        # Получаем обновленный баланс
        user = db.get_user(user_id)
        
        await callback.message.edit_text(
            f"🚀 *Banana Crash*\n\n"
            f"💰 Ставка: *{bet} STAR*\n"
            f"{result_text}\n\n"
            f"💰 Новый баланс: *{format_balance(user['balance'])} STAR*\n\n"
            f"🎮 Сыграть ещё?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Играть снова", callback_data="game_crash")],
                [InlineKeyboardButton(text="🎮 Все игры", callback_data="play_games")],
                [InlineKeyboardButton(text="🐵 Главное меню", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in handle_crash_play: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.callback_query(F.data == "game_slot")
async def handle_game_slot(callback: CallbackQuery):
    """Игра Слот-машина"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    keyboard = [
        [InlineKeyboardButton(text="🎰 Крутить (1 STAR)", callback_data="slot_play_1")],
        [InlineKeyboardButton(text="🎰 Крутить (5 STAR)", callback_data="slot_play_5")],
        [InlineKeyboardButton(text="🎰 Крутить (10 STAR)", callback_data="slot_play_10")],
        [InlineKeyboardButton(text="◀️ Назад к играм", callback_data="play_games")]
    ]
    
    await callback.message.edit_text(
        f"🎰 *Банановый слот*\n\n"
        f"💰 Ваш баланс: *{format_balance(user['balance'])} STAR*\n"
        f"🎯 3 одинаковых символа = x20\n"
        f"🍌 3 банана = ДЖЕКПОТ x50!\n"
        f"📊 Шанс выигрыша: 1/27\n\n"
        f"Выберите ставку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("slot_play_"))
async def handle_slot_play(callback: CallbackQuery):
    """Играем в слоты"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    try:
        bet = float(callback.data.split("_")[2])
        
        # Проверка баланса
        if user['balance'] < bet:
            await callback.answer(f"❌ Недостаточно STAR. Баланс: {format_balance(user['balance'])}")
            return
        
        # Играем в слоты
        win, amount, result_text, reels = GameEngine.play_slot(bet)
        
        # Обновляем баланс и статистику
        if win:
            db.update_balance(user_id, amount - bet)
            db.add_transaction(user_id, amount - bet, "game_win", f"Слоты выигрыш x{amount/bet:.2f}")
            db.update_game_stats(user_id, bet, True)
        else:
            db.update_balance(user_id, -bet)
            db.add_transaction(user_id, -bet, "game_lose", "Слоты проигрыш")
            db.update_game_stats(user_id, bet, False)
        
        # Получаем обновленный баланс
        user = db.get_user(user_id)
        
        await callback.message.edit_text(
            f"🎰 *Банановый слот*\n\n"
            f"💰 Ставка: *{bet} STAR*\n"
            f"🎰 Результат: *{reels}*\n"
            f"{result_text}\n\n"
            f"💰 Новый баланс: *{format_balance(user['balance'])} STAR*\n\n"
            f"🎮 Сыграть ещё?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎰 Крутить снова", callback_data="game_slot")],
                [InlineKeyboardButton(text="🎮 Все игры", callback_data="play_games")],
                [InlineKeyboardButton(text="🐵 Главное меню", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in handle_slot_play: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.callback_query(F.data == "game_dice")
async def handle_game_dice(callback: CallbackQuery, state: FSMContext):
    """Игра Банановые кости"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    await state.set_state(GameStates.playing_dice)
    
    # Создаем клавиатуру с числами 1-6
    keyboard = []
    for i in range(1, 7):
        keyboard.append([InlineKeyboardButton(text=f"🎲 {i}", callback_data=f"dice_{i}")])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад к играм", callback_data="play_games")])
    
    await callback.message.edit_text(
        f"🎲 *Банановые кости*\n\n"
        f"💰 Ваш баланс: *{format_balance(user['balance'])} STAR*\n"
        f"🎯 Угадайте число от 1 до 6\n"
        f"📈 Шанс выигрыша: 1/6 (16.6%)\n"
        f"💰 Множитель: x3.0\n\n"
        f"Выберите число:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("dice_"))
async def handle_dice_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора числа в Dice"""
    user_id = callback.from_user.id
    user_number = int(callback.data.split("_")[1])
    
    # Запрашиваем ставку
    await callback.message.edit_text(
        f"🎲 Вы выбрали число: *{user_number}*\n\n"
        f"💰 Введите сумму ставки (минимум {Config.MIN_BETS['dice']} STAR):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="game_dice")]
        ])
    )
    
    await state.update_data(dice_number=user_number)
    await state.set_state(GameStates.choosing_bet)

@dp.message(GameStates.choosing_bet)
async def handle_dice_bet(message: Message, state: FSMContext):
    """Обработка ставки для Dice"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Ошибка, попробуйте /start")
        await state.clear()
        return
    
    try:
        bet = float(message.text)
        
        # Проверка минимальной ставки
        min_bet = Config.MIN_BETS['dice']
        if bet < min_bet:
            await message.answer(f"❌ Минимальная ставка: {min_bet} STAR")
            return
        
        # Проверка баланса
        if user['balance'] < bet:
            await message.answer(f"❌ Недостаточно STAR. Ваш баланс: {format_balance(user['balance'])}")
            return
        
        # Получаем данные о выборе числа
        data = await state.get_data()
        user_number = data.get('dice_number')
        
        # Играем в Dice
        win, amount, result_text = GameEngine.play_dice(bet, user_number)
        
        # Обновляем баланс и статистику
        if win:
            db.update_balance(user_id, amount - bet)
            db.add_transaction(user_id, amount - bet, "game_win", f"Кости выигрыш x3.0")
            db.update_game_stats(user_id, bet, True)
        else:
            db.update_balance(user_id, -bet)
            db.add_transaction(user_id, -bet, "game_lose", "Кости проигрыш")
            db.update_game_stats(user_id, bet, False)
        
        # Получаем обновленный баланс
        user = db.get_user(user_id)
        
        await message.answer(
            f"🎲 *Банановые кости*\n\n"
            f"💰 Ставка: *{bet} STAR*\n"
            f"🎲 Вы загадали: *{user_number}*\n"
            f"{result_text}\n\n"
            f"💰 Новый баланс: *{format_balance(user['balance'])} STAR*\n\n"
            f"🎮 Сыграть ещё?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎲 Играть снова", callback_data="game_dice")],
                [InlineKeyboardButton(text="🎮 Все игры", callback_data="play_games")],
                [InlineKeyboardButton(text="🐵 Главное меню", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число!")
    except Exception as e:
        logger.error(f"Error in handle_dice_bet: {e}")
        await message.answer("❌ Произошла ошибка")
        await state.clear()

@dp.callback_query(F.data == "game_jackpot")
async def handle_game_jackpot(callback: CallbackQuery):
    """Игра Джекпот"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    keyboard = [
        [InlineKeyboardButton(text="💰 Купить билет (1 STAR)", callback_data="jackpot_play_1")],
        [InlineKeyboardButton(text="💰 Купить 5 билетов (5 STAR)", callback_data="jackpot_play_5")],
        [InlineKeyboardButton(text="💰 Купить 10 билетов (10 STAR)", callback_data="jackpot_play_10")],
        [InlineKeyboardButton(text="◀️ Назад к играм", callback_data="play_games")]
    ]
    
    await callback.message.edit_text(
        f"💰 *Джекпот*\n\n"
        f"💰 Ваш баланс: *{format_balance(user['balance'])} STAR*\n"
        f"🎰 1% шанс выигрыша\n"
        f"💰 Множитель: x100\n"
        f"🏆 Текущий джекпот: *{(db.get_stats()['total_wagered'] * 0.1):.2f} STAR*\n\n"
        f"Купить билеты:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("jackpot_play_"))
async def handle_jackpot_play(callback: CallbackQuery):
    """Играем в Джекпот"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    try:
        bet = float(callback.data.split("_")[2])
        tickets = int(bet)  # 1 билет за 1 STAR
        
        # Проверка баланса
        if user['balance'] < bet:
            await callback.answer(f"❌ Недостаточно STAR. Баланс: {format_balance(user['balance'])}")
            return
        
        # Сначала списываем деньги за билеты
        db.update_balance(user_id, -bet)
        db.add_transaction(user_id, -bet, "game_lose", f"Покупка {tickets} билетов джекпота")
        db.update_game_stats(user_id, bet, False)
        
        # Играем для каждого билета
        total_win = 0
        win_tickets = 0
        
        for i in range(tickets):
            win, amount, _ = GameEngine.play_jackpot(1.0)
            if win:
                total_win += amount
                win_tickets += 1
        
        # Если есть выигрыш - начисляем
        if total_win > 0:
            db.update_balance(user_id, total_win)
            db.add_transaction(user_id, total_win, "game_win", f"Джекпот выигрыш x{total_win:.0f}")
            db.update_game_stats(user_id, 0, True)  # Обновляем статистику побед
        
        # Получаем обновленный баланс
        user = db.get_user(user_id)
        
        result_text = ""
        if win_tickets > 0:
            result_text = f"🎉 Вы выиграли с {win_tickets} билетов! Выигрыш: {total_win:.2f} STAR!"
        else:
            result_text = f"😢 Ни один билет не выиграл. Попробуйте еще раз!"
        
        await callback.message.edit_text(
            f"💰 *Джекпот*\n\n"
            f"🎫 Куплено билетов: *{tickets}*\n"
            f"💰 Потрачено: *{bet} STAR*\n"
            f"{result_text}\n\n"
            f"💰 Новый баланс: *{format_balance(user['balance'])} STAR*\n\n"
            f"🎮 Купить ещё билетов?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Купить билеты", callback_data="game_jackpot")],
                [InlineKeyboardButton(text="🎮 Все игры", callback_data="play_games")],
                [InlineKeyboardButton(text="🐵 Главное меню", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in handle_jackpot_play: {e}")
        await callback.answer("❌ Произошла ошибка")

# ========== ВЫВОД СРЕДСТВ ==========

@dp.callback_query(F.data == "withdraw_menu")
async def handle_withdraw_menu(callback: CallbackQuery):
    """Меню вывода средств"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    keyboard = []
    for amount in Config.WITHDRAWAL_AMOUNTS:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{amount} STAR",
                callback_data=f"withdraw_{amount}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="earn")])
    
    await callback.message.edit_text(
        "💸 *Вывод средств*\n\n"
        "📋 Требования для вывода:\n"
        "1. Баланс ≥ выбранной суммы\n"
        "2. 3 активных реферала (подписанных на спонсоров)\n\n"
        "Выберите сумму:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("withdraw_"))
async def handle_withdraw(callback: CallbackQuery):
    """Обработка вывода"""
    user_id = callback.from_user.id
    
    try:
        amount = float(callback.data.split("_")[1])
    except:
        await callback.answer("❌ Ошибка суммы")
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    # Проверка баланса
    if user['balance'] < amount:
        await callback.answer(f"❌ Недостаточно STAR. Ваш баланс: {format_balance(user['balance'])}")
        return
    
    # Проверка активных рефералов
    total_ref, active_ref = db.get_user_referrals(user_id)
    if active_ref < 3:
        await callback.answer(f"❌ Нужно 3 активных реферала. У вас: {active_ref}")
        return
    
    # Создание заявки на вывод
    withdrawal = db.create_withdrawal(user_id, amount)
    if not withdrawal:
        await callback.answer("❌ Ошибка при создании заявки")
        return
    
    # Списание баланса
    db.update_balance(user_id, -amount)
    db.add_transaction(user_id, -amount, "withdrawal", f"Вывод #{withdrawal['id']}")
    
    # Отправляем сообщение об успехе
    await callback.message.edit_text(
        f"✅ *Заявка на вывод одобрена!*\n\n"
        f"💰 Сумма: *{amount} STAR*\n"
        f"📝 ID заявки: *#{withdrawal['id']}*\n\n"
        f"Для получения средств свяжитесь с поддержкой: @MonkeyStarsov\n"
        f"Укажите ваш ID: `{user_id}` и сумму: `{amount} STAR`",
        parse_mode="Markdown"
    )
    
    # Уведомляем админа
    try:
        await bot.send_message(
            Config.ADMIN_ID,
            f"📥 Новая заявка на вывод!\n"
            f"👤 Пользователь: @{callback.from_user.username or user_id}\n"
            f"💰 Сумма: {amount} STAR\n"
            f"📝 ID: {withdrawal['id']}\n"
            f"🆔 User ID: {user_id}"
        )
    except:
        pass

# ========== ПРОФИЛЬ И РЕФЕРАЛКА ==========

@dp.callback_query(F.data == "profile")
async def handle_profile(callback: CallbackQuery):
    """Профиль пользователя"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.answer("❌ Ошибка, попробуйте /start")
        return
    
    total_ref, active_ref = db.get_user_referrals(user_id)
    
    # Статистика игр
    games_played = user.get('games_played', 0)
    games_won = user.get('games_won', 0)
    total_wagered = user.get('total_wagered', 0.0)
    
    win_rate = (games_won / games_played * 100) if games_played > 0 else 0
    
    # Время до следующего клика
    last_click = user.get('last_click')
    current_time = int(datetime.now().timestamp())
    
    if last_click:
        time_passed = current_time - last_click
        if time_passed < Config.CLICK_COOLDOWN:
            remaining = Config.CLICK_COOLDOWN - time_passed
            next_click = f"через {format_time(remaining)}"
        else:
            next_click = "сейчас"
    else:
        next_click = "сейчас"
    
    text = (
        f"📊 *Профиль*\n\n"
        f"👤 ID: `{user_id}`\n"
        f"👤 Имя: {callback.from_user.full_name}\n"
        f"💰 Баланс: *{format_balance(user['balance'])} STAR*\n"
        f"👥 Рефералов: *{active_ref}* / {total_ref}\n\n"
        f"🎮 *Статистика игр:*\n"
        f"• Сыграно игр: {games_played}\n"
        f"• Побед: {games_won}\n"
        f"• Процент побед: {win_rate:.1f}%\n"
        f"• Всего поставлено: {format_balance(total_wagered)} STAR\n\n"
        f"⏰ Кликер доступен: {next_click}"
    )
    
    keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "referral")
async def handle_referral(callback: CallbackQuery):
    """Реферальная система"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    total_ref, active_ref = db.get_user_referrals(user_id)
    
    text = (
        f"👥 *Реферальная система*\n\n"
        f"🔗 Ваша реферальная ссылка:\n"
        f"`https://t.me/MonkeyStarsBot?start={user_id}`\n\n"
        f"📊 Статистика:\n"
        f"• Приглашено: *{total_ref}*\n"
        f"• Активных: *{active_ref}*\n\n"
        f"🎁 *Правила:*\n"
        f"• Вы получаете *3 STAR*, а друг *2 STAR* после подписки на спонсоров\n"
        f"• Вы получаете *10%* от всех кликов реферала\n"
        f"• Для вывода нужно *3 активных реферала*"
    )
    
    keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

# ========== АДМИН ПАНЕЛЬ ==========

@dp.callback_query(F.data == "admin_panel")
async def handle_admin_panel(callback: CallbackQuery):
    """Админ панель"""
    if callback.from_user.id != Config.ADMIN_ID:
        await callback.answer("❌ Доступ запрещен")
        return
    
    stats = db.get_stats()
    
    keyboard = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="📢 Добавить спонсора", callback_data="admin_add_sponsor")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ]
    
    text = (
        f"👑 *Админ панель*\n\n"
        f"📊 Краткая статистика:\n"
        f"• Пользователей: {stats['total_users']}\n"
        f"• Общий баланс: {format_balance(stats['total_balance'])} STAR\n"
        f"• Всего поставлено: {format_balance(stats['total_wagered'])} STAR\n"
        f"• Заявок на вывод: {stats['pending_withdrawals']}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "admin_stats")
async def handle_admin_stats(callback: CallbackQuery):
    """Детальная статистика"""
    if callback.from_user.id != Config.ADMIN_ID:
        return
    
    stats = db.get_stats()
    users = db.get_all_users()
    
    # Топ-10 по балансу
    top_users = sorted(users, key=lambda x: x['balance'], reverse=True)[:10]
    
    top_text = "🏆 Топ-10 по балансу:\n"
    for i, user in enumerate(top_users, 1):
        username = f"@{user['username']}" if user['username'] else f"user_{user['user_id']}"
        top_text += f"{i}. {username}: {format_balance(user['balance'])} STAR\n"
    
    text = (
        f"📈 *Детальная статистика*\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"💰 Общий баланс: {format_balance(stats['total_balance'])} STAR\n"
        f"🎮 Всего поставлено: {format_balance(stats['total_wagered'])} STAR\n"
        f"📥 Заявок на вывод: {stats['pending_withdrawals']}\n\n"
        f"{top_text}"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="◀️ В админ панель", callback_data="admin_panel")]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """Команда /admin"""
    if message.from_user.id != Config.ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    await handle_admin_panel(message)

# ========== ГЛАВНОЕ МЕНЮ ==========

@dp.callback_query(F.data == "main_menu")
async def handle_back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.delete()
    await show_main_menu(callback.message)

# ========== ЗАПУСК БОТА ==========

async def main():
    """Основная функция запуска"""
    logger.info("🚀 Запуск бота Monkey Stars...")
    logger.info(f"👑 Админ ID: {Config.ADMIN_ID}")
    
    try:
        # Проверяем подключение к БД
        stats = db.get_stats()
        logger.info(f"✅ База данных подключена. Пользователей: {stats['total_users']}")
        
        # Запускаем бота
        logger.info("✅ Бот успешно запущен!")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
