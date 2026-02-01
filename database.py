from supabase import create_client, Client
from datetime import datetime
from config import Config
import logging
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        try:
            logger.info("🔄 Подключаемся к Supabase...")
            self.supabase: Client = create_client(
                Config.SUPABASE_URL,
                Config.SUPABASE_KEY
            )
            logger.info("✅ Подключение к Supabase успешно")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Supabase: {e}")
            raise
    
    # === ПОЛЬЗОВАТЕЛИ ===
    def get_user(self, user_id: int) -> Optional[Dict]:
        try:
            response = self.supabase.table("users")\
                .select("*")\
                .eq("user_id", user_id)\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Ошибка получения пользователя {user_id}: {e}")
            return None
    
    def create_user(self, user_id: int, username: str, referrer_id: int = None) -> bool:
        try:
            user_data = {
                "user_id": user_id,
                "username": username or f"user_{user_id}",
                "referrer_id": referrer_id,
                "created_at": int(datetime.now().timestamp()),
                "balance": 0.0,
                "last_click": None,
                "total_wagered": 0.0,
                "games_played": 0,
                "games_won": 0
            }
            
            response = self.supabase.table("users")\
                .upsert(user_data, on_conflict="user_id")\
                .execute()
            
            # Начисляем реферальные бонусы
            if referrer_id and response.data:
                referrer = self.get_user(referrer_id)
                if referrer:
                    # Бонус рефереру
                    self.update_balance(referrer_id, Config.REFERRAL_REWARD_REFERRER)
                    self.add_transaction(
                        referrer_id,
                        Config.REFERRAL_REWARD_REFERRER,
                        "referral_bonus",
                        f"За приглашение {username}"
                    )
                    
                    # Бонус рефералу
                    self.update_balance(user_id, Config.REFERRAL_REWARD_REFEREE)
                    self.add_transaction(
                        user_id,
                        Config.REFERRAL_REWARD_REFEREE,
                        "referral_bonus",
                        "За регистрацию по реферальной ссылке"
                    )
            
            return bool(response.data)
        except Exception as e:
            logger.error(f"Ошибка создания пользователя {user_id}: {e}")
            return False
    
    def update_balance(self, user_id: int, amount: float) -> bool:
        try:
            user = self.get_user(user_id)
            if not user:
                return False
            
            new_balance = user["balance"] + amount
            
            response = self.supabase.table("users")\
                .update({"balance": new_balance})\
                .eq("user_id", user_id)\
                .execute()
            
            return bool(response.data)
        except Exception as e:
            logger.error(f"Ошибка обновления баланса {user_id}: {e}")
            return False
    
    def update_last_click(self, user_id: int, timestamp: int) -> bool:
        try:
            response = self.supabase.table("users")\
                .update({"last_click": timestamp})\
                .eq("user_id", user_id)\
                .execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Ошибка обновления last_click {user_id}: {e}")
            return False
    
    def update_game_stats(self, user_id: int, wagered: float, won: bool) -> bool:
        try:
            user = self.get_user(user_id)
            if not user:
                return False
            
            updates = {
                "total_wagered": user.get("total_wagered", 0.0) + wagered,
                "games_played": user.get("games_played", 0) + 1
            }
            
            if won:
                updates["games_won"] = user.get("games_won", 0) + 1
            
            response = self.supabase.table("users")\
                .update(updates)\
                .eq("user_id", user_id)\
                .execute()
            
            return bool(response.data)
        except Exception as e:
            logger.error(f"Ошибка обновления статистики игр {user_id}: {e}")
            return False
    
    # === СПОНСОРЫ ===
    def get_sponsors(self) -> List[Dict]:
        try:
            response = self.supabase.table("sponsors")\
                .select("*")\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Ошибка получения спонсоров: {e}")
            return []
    
    def get_user_sponsors_status(self, user_id: int) -> List[Dict]:
        try:
            # Получаем всех спонсоров
            sponsors = self.get_sponsors()
            if not sponsors:
                return []
            
            # Получаем статусы подписки
            response = self.supabase.table("user_sponsors")\
                .select("sponsor_id, is_subscribed")\
                .eq("user_id", user_id)\
                .execute()
            
            subscribed_ids = {row['sponsor_id']: row['is_subscribed'] for row in response.data}
            
            # Формируем результат
            result = []
            for sponsor in sponsors:
                result.append({
                    **sponsor,
                    'is_subscribed': subscribed_ids.get(sponsor['id'], False)
                })
            
            return result
        except Exception as e:
            logger.error(f"Ошибка получения статуса подписок {user_id}: {e}")
            return []
    
    def update_user_sponsor_status(self, user_id: int, sponsor_id: int, is_subscribed: bool) -> bool:
        try:
            response = self.supabase.table("user_sponsors")\
                .upsert({
                    "user_id": user_id,
                    "sponsor_id": sponsor_id,
                    "is_subscribed": is_subscribed,
                    "last_check": int(datetime.now().timestamp())
                }, on_conflict="user_id,sponsor_id")\
                .execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Ошибка обновления статуса подписки: {e}")
            return False
    
    # === РЕФЕРАЛЫ ===
    def get_user_referrals(self, user_id: int) -> Tuple[int, int]:
        try:
            # Все рефералы
            response = self.supabase.table("users")\
                .select("user_id")\
                .eq("referrer_id", user_id)\
                .execute()
            total = len(response.data) if response.data else 0
            
            # Активные рефералы (которые подписаны на хотя бы одного спонсора)
            active = 0
            for referral in response.data:
                referral_status = self.get_user_sponsors_status(referral['user_id'])
                if any(s['is_subscribed'] for s in referral_status):
                    active += 1
            
            return total, active
        except Exception as e:
            logger.error(f"Ошибка получения рефералов {user_id}: {e}")
            return 0, 0
    
    # === ТРАНЗАКЦИИ ===
    def add_transaction(self, user_id: int, amount: float, type: str, description: str = "") -> bool:
        try:
            response = self.supabase.table("transactions")\
                .insert({
                    "user_id": user_id,
                    "amount": amount,
                    "type": type,
                    "description": description,
                    "created_at": int(datetime.now().timestamp())
                })\
                .execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Ошибка добавления транзакции: {e}")
            return False
    
    # === ВЫВОД СРЕДСТВ ===
    def create_withdrawal(self, user_id: int, amount: float) -> Optional[Dict]:
        try:
            response = self.supabase.table("withdrawals")\
                .insert({
                    "user_id": user_id,
                    "amount": amount,
                    "status": "pending",
                    "created_at": int(datetime.now().timestamp())
                })\
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Ошибка создания вывода: {e}")
            return None
    
    # === АДМИН ФУНКЦИИ ===
    def get_all_users(self) -> List[Dict]:
        try:
            response = self.supabase.table("users")\
                .select("*")\
                .order("created_at", desc=True)\
                .execute()
            return response.data
        except Exception as e:
            logger.error(f"Ошибка получения всех пользователей: {e}")
            return []
    
    def get_stats(self) -> Dict:
        try:
            # Количество пользователей
            users_resp = self.supabase.table("users")\
                .select("user_id", count="exact")\
                .execute()
            
            # Общий баланс
            balance_resp = self.supabase.table("users")\
                .select("balance")\
                .execute()
            total_balance = sum(user['balance'] for user in balance_resp.data) if balance_resp.data else 0
            
            # Общая сумма ставок
            wagered_resp = self.supabase.table("users")\
                .select("total_wagered")\
                .execute()
            total_wagered = sum(user['total_wagered'] for user in wagered_resp.data) if wagered_resp.data else 0
            
            # Заявки на вывод
            withdrawals_resp = self.supabase.table("withdrawals")\
                .select("id", count="exact")\
                .eq("status", "pending")\
                .execute()
            
            return {
                "total_users": users_resp.count or 0,
                "total_balance": total_balance,
                "total_wagered": total_wagered,
                "pending_withdrawals": withdrawals_resp.count or 0
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {"total_users": 0, "total_balance": 0, "total_wagered": 0, "pending_withdrawals": 0}
    
    def add_sponsor(self, channel_username: str, channel_id: str, channel_url: str) -> bool:
        try:
            response = self.supabase.table("sponsors")\
                .insert({
                    "channel_username": channel_username,
                    "channel_id": channel_id,
                    "channel_url": channel_url
                })\
                .execute()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Ошибка добавления спонсора: {e}")
            return False
