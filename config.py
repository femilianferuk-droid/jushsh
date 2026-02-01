import os

class Config:
    # Токен бота (из переменных окружения)
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # ID администратора
    ADMIN_ID = 7973988177
    
    # Supabase (используем ту же базу)
    SUPABASE_URL = "https://lzmvkp5wrkoms.hv.qb2usq.supabase.co"
    SUPABASE_KEY = "sb_publishable_lZmVKp5wrkoOMsHvQB2UsQ_jkmn1gul"
    
    # Настройки игры
    CLICK_REWARD = 0.2
    CLICK_COOLDOWN = 3600  # 1 час
    REFERRAL_REWARD_REFERRER = 3.0
    REFERRAL_REWARD_REFEREE = 2.0
    CLICK_REFERRAL_PERCENT = 10
    
    # Суммы для вывода
    WITHDRAWAL_AMOUNTS = [15, 25, 50, 100]
    
    # Настройки игр
    GAMES = {
        'flip': {
            'name': '🎯 Monkey Flip',
            'win_chance': 0.49,
            'multiplier': 2.0,
            'special_event_chance': 0.015,
        },
        'crash': {
            'name': '🚀 Banana Crash',
            'instant_crash_chance': 0.6,
            'low_multiplier_range': (1.0, 1.1),
            'high_multiplier_chance': 0.02,
            'min_high_multiplier': 1.5,
        },
        'slot': {
            'name': '🎰 Банановый слот',
            'winning_combinations': 1,
            'total_combinations': 27,
            'win_multiplier': 20,
        },
        'dice': {
            'name': '🎲 Банановые кости',
            'win_chance': 0.33,
            'multiplier': 3.0,
        },
        'jackpot': {
            'name': '💰 Джекпот',
            'ticket_price': 1.0,
            'win_chance': 0.01,
            'multiplier': 100.0,
        }
    }
    
    # Минимальные ставки
    MIN_BETS = {
        'flip': 1.0,
        'crash': 1.0,
        'slot': 1.0,
        'dice': 1.0,
        'jackpot': 1.0,
    }
    
    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError(
                "❌ Установите токен бота!\n"
                "Создайте файл .env с BOT_TOKEN=ваш_токен\n"
                "Или установите в системе: export BOT_TOKEN='ваш_токен'"
            )
        return True
