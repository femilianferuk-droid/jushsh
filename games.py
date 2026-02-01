import random
from typing import Dict, Any, Tuple
from config import Config

class GameEngine:
    @staticmethod
    def play_flip(bet: float, choice: str) -> Tuple[bool, float, str]:
        """Игра Monkey Flip"""
        game_config = Config.GAMES['flip']
        
        # Специальное событие (1.5% шанс проигрыша)
        if random.random() < game_config['special_event_chance']:
            return False, 0.0, "🍌🌀 Специальное событие! Банан улетел в космос!"
        
        # Основная логика
        win = random.random() < game_config['win_chance']
        
        if win:
            win_amount = bet * game_config['multiplier']
            result_text = f"🎉 {choice} выпало! Вы выиграли {win_amount:.2f} STAR!"
            return True, win_amount, result_text
        else:
            lose_choices = {
                'heads': 'решка',
                'tails': 'орел'
            }
            result_text = f"😢 Выпало {lose_choices.get(choice, 'другая сторона')}. Вы проиграли {bet:.2f} STAR"
            return False, 0.0, result_text
    
    @staticmethod
    def play_crash(bet: float) -> Tuple[bool, float, str]:
        """Игра Banana Crash"""
        game_config = Config.GAMES['crash']
        
        # 60% шанс мгновенного краша
        if random.random() < game_config['instant_crash_chance']:
            return False, 0.0, "💥 Мгновенный краш! x1.00"
        
        # 2% шанс на высокий множитель
        if random.random() < game_config['high_multiplier_chance']:
            multiplier = random.uniform(game_config['min_high_multiplier'], 5.0)
            win_amount = bet * multiplier
            return True, win_amount, f"🚀 Улетный множитель! x{multiplier:.2f}"
        
        # Обычный низкий множитель
        multiplier = random.uniform(*game_config['low_multiplier_range'])
        
        # Игрок забирает в 80% случаев, когда множитель > 1.0
        if multiplier > 1.0 and random.random() < 0.8:
            win_amount = bet * multiplier
            return True, win_amount, f"✅ Вы забрали на x{multiplier:.2f}"
        else:
            return False, 0.0, f"💥 Краш на x{multiplier:.2f}"
    
    @staticmethod
    def play_slot(bet: float) -> Tuple[bool, float, str, str]:
        """Игра Слот-машина"""
        game_config = Config.GAMES['slot']
        
        # Генерируем 3 барабана
        symbols = ['🍌', '🐵', '⭐', '💎', '🎯', '💰', '🎰', '🍀']
        reels = [
            random.choice(symbols),
            random.choice(symbols),
            random.choice(symbols)
        ]
        
        # Проверяем выигрышную комбинацию (3 одинаковых символа)
        if reels[0] == reels[1] == reels[2]:
            if reels[0] == '🍌':  # Джекпот за 3 банана
                win_amount = bet * 50.0
                result_text = f"🎰 ДЖЕКПОТ! 3x{reels[0]}! Выигрыш: {win_amount:.2f} STAR!"
                return True, win_amount, result_text, " | ".join(reels)
            
            win_amount = bet * game_config['win_multiplier']
            result_text = f"🎰 Выигрыш! 3x{reels[0]}! Выигрыш: {win_amount:.2f} STAR!"
            return True, win_amount, result_text, " | ".join(reels)
        else:
            result_text = f"🎰 {reels[0]} | {reels[1]} | {reels[2]}\nПовезет в следующий раз!"
            return False, 0.0, result_text, " | ".join(reels)
    
    @staticmethod
    def play_dice(bet: float, user_number: int) -> Tuple[bool, float, str]:
        """Игра Банановые кости"""
        game_config = Config.GAMES['dice']
        
        # Бросаем кубик (1-6)
        dice_roll = random.randint(1, 6)
        
        # Игрок выигрывает, если угадал число
        if user_number == dice_roll:
            win_amount = bet * game_config['multiplier']
            result_text = f"🎲 Выпало {dice_roll}! Вы угадали! Выигрыш: {win_amount:.2f} STAR!"
            return True, win_amount, result_text
        else:
            result_text = f"🎲 Выпало {dice_roll}, а вы загадали {user_number}. Проигрыш: {bet:.2f} STAR"
            return False, 0.0, result_text
    
    @staticmethod
    def play_jackpot(bet: float) -> Tuple[bool, float, str]:
        """Игра Джекпот"""
        game_config = Config.GAMES['jackpot']
        
        # 1% шанс выигрыша джекпота
        if random.random() < game_config['win_chance']:
            win_amount = bet * game_config['multiplier']
            result_text = f"💰 ДЖЕКПОТ!!! Вы выиграли {win_amount:.2f} STAR!"
            return True, win_amount, result_text
        else:
            result_text = f"💰 Билет не выиграл. Попробуйте еще!"
            return False, 0.0, result_text
