"""
黑名單與風控系統
功能：黑名單管理、風險控制、安全防護
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

class SecurityManager:
    """安全管理系統"""
    
    def __init__(self, db_path='wallet.db'):
        self.db_path = db_path
        self._init_security_tables()
    
    def _init_security_tables(self):
        """初始化安全相關資料表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 黑名單表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                username TEXT NOT NULL,
                reason TEXT NOT NULL,
                banned_by INTEGER,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                banned_until TIMESTAMP,
                is_permanent INTEGER DEFAULT 1,
                notes TEXT
            )
        ''')
        
        # 風險事件記錄表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS risk_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                handled INTEGER DEFAULT 0,
                handled_by INTEGER,
                handled_at TIMESTAMP
            )
        ''')
        
        # 儲值限制記錄表（防止一天多次儲值）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deposit_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                deposit_date DATE NOT NULL,
                deposit_count INTEGER DEFAULT 0,
                total_amount REAL DEFAULT 0,
                UNIQUE(user_id, deposit_date)
            )
        ''')
        
        # 可疑操作日誌表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS suspicious_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                action_type TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # ============ 黑名單管理 ============
    
    def add_to_blacklist(self, user_id: int, username: str, reason: str, 
                         banned_by: int, days: Optional[int] = None, notes: str = "") -> bool:
        """
        加入黑名單
        
        Args:
            user_id: 用戶ID
            username: 用戶名
            reason: 封禁原因
            banned_by: 執行封禁的管理員ID
            days: 封禁天數（None = 永久）
            notes: 備註
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            is_permanent = 1 if days is None else 0
            banned_until = None
            
            if days is not None:
                banned_until = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT OR REPLACE INTO blacklist 
                (user_id, username, reason, banned_by, banned_until, is_permanent, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, reason, banned_by, banned_until, is_permanent, notes))
            
            # 記錄風險事件
            self._log_risk_event(
                user_id, username, 'BLACKLISTED', 'CRITICAL',
                f"加入黑名單：{reason}"
            )
            
            conn.commit()
            return True
        except Exception as e:
            print(f"加入黑名單錯誤: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def remove_from_blacklist(self, user_id: int) -> bool:
        """移除黑名單"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM blacklist WHERE user_id = ?', (user_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"移除黑名單錯誤: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def is_blacklisted(self, user_id: int) -> tuple[bool, Optional[str]]:
        """
        檢查是否在黑名單
        
        Returns:
            (是否被封禁, 封禁原因)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT reason, banned_until, is_permanent
            FROM blacklist
            WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return False, None
        
        reason, banned_until, is_permanent = result
        
        # 如果是永久封禁
        if is_permanent:
            return True, reason
        
        # 如果是臨時封禁，檢查是否過期
        if banned_until:
            banned_time = datetime.strptime(banned_until, '%Y-%m-%d %H:%M:%S')
            if datetime.now() < banned_time:
                return True, reason
            else:
                # 過期了，自動解除
                self.remove_from_blacklist(user_id)
                return False, None
        
        return False, None
    
    def get_blacklist(self, limit: int = 100) -> List[Dict]:
        """獲取黑名單列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, reason, banned_at, banned_until, 
                   is_permanent, notes
            FROM blacklist
            ORDER BY banned_at DESC
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        blacklist = []
        for r in results:
            blacklist.append({
                '用戶ID': r[0],
                '用戶名': r[1],
                '封禁原因': r[2],
                '封禁時間': r[3],
                '解封時間': r[4] if r[4] else '永久',
                '封禁類型': '永久封禁' if r[5] else '臨時封禁',
                '備註': r[6] if r[6] else '無'
            })
        
        return blacklist
    
    # ============ 風險事件記錄 ============
    
    def _log_risk_event(self, user_id: int, username: str, event_type: str,
                       severity: str, description: str):
        """記錄風險事件"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO risk_events (user_id, username, event_type, severity, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, event_type, severity, description))
            conn.commit()
        except Exception as e:
            print(f"記錄風險事件錯誤: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_risk_events(self, handled: Optional[bool] = None, limit: int = 100) -> List[Dict]:
        """
        獲取風險事件列表
        
        Args:
            handled: None=全部, True=已處理, False=未處理
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if handled is None:
            cursor.execute('''
                SELECT user_id, username, event_type, severity, description, 
                       created_at, handled
                FROM risk_events
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
        else:
            handled_int = 1 if handled else 0
            cursor.execute('''
                SELECT user_id, username, event_type, severity, description, 
                       created_at, handled
                FROM risk_events
                WHERE handled = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (handled_int, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        events = []
        for r in results:
            events.append({
                '用戶ID': r[0],
                '用戶名': r[1],
                '事件類型': r[2],
                '嚴重程度': r[3],
                '描述': r[4],
                '發生時間': r[5],
                '處理狀態': '已處理' if r[6] else '未處理'
            })
        
        return events
    
    def mark_event_handled(self, event_id: int, admin_id: int) -> bool:
        """標記風險事件為已處理"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE risk_events
                SET handled = 1, handled_by = ?, handled_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (admin_id, event_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"標記處理錯誤: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    # ============ 儲值限制檢查 ============
    
    def check_deposit_limit(self, user_id: int) -> tuple[bool, int, float]:
        """
        檢查今日儲值限制
        
        Returns:
            (是否可以儲值, 今日已儲值次數, 今日已儲值金額)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT deposit_count, total_amount
            FROM deposit_limits
            WHERE user_id = ? AND deposit_date = ?
        ''', (user_id, today))
        
        result = cursor.fetchone()
        
        if not result:
            # 今天還沒儲值過
            conn.close()
            return True, 0, 0.0
        
        deposit_count, total_amount = result
        conn.close()
        
        # 新帳號限制：每天只能儲值一次
        # 檢查是否為新帳號（註冊未滿7天）
        is_new_account = self._is_new_account(user_id)
        
        if is_new_account and deposit_count >= 1:
            return False, deposit_count, total_amount
        
        # 一般帳號限制：每天最多3次，或單日超過10000元
        if deposit_count >= 3 or total_amount >= 10000:
            return False, deposit_count, total_amount
        
        return True, deposit_count, total_amount
    
    def record_deposit_attempt(self, user_id: int, amount: float) -> bool:
        """記錄儲值嘗試"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        try:
            cursor.execute('''
                INSERT INTO deposit_limits (user_id, deposit_date, deposit_count, total_amount)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(user_id, deposit_date) 
                DO UPDATE SET 
                    deposit_count = deposit_count + 1,
                    total_amount = total_amount + ?
            ''', (user_id, today, amount, amount))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"記錄儲值錯誤: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def _is_new_account(self, user_id: int) -> bool:
        """檢查是否為新帳號（7天內註冊）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT created_at FROM wallets WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return True  # 沒找到資料，視為新帳號
        
        created_at = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
        days_since_creation = (datetime.now() - created_at).days
        
        return days_since_creation < 7
    
    # ============ 可疑操作檢測 ============
    
    def detect_suspicious_activity(self, user_id: int, username: str) -> List[str]:
        """
        檢測用戶的可疑操作
        
        Returns:
            可疑操作列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        warnings = []
        
        # 1. 檢查短時間大量下單
        one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            SELECT COUNT(*) FROM orders
            WHERE user_id = ? AND created_at >= ?
        ''', (user_id, one_hour_ago))
        
        recent_orders = cursor.fetchone()[0]
        if recent_orders >= 5:
            warnings.append(f"1小時內下單 {recent_orders} 次")
            self._log_risk_event(user_id, username, 'RAPID_ORDERS', 'HIGH',
                               f"1小時內下單 {recent_orders} 次")
        
        # 2. 檢查大量未完成訂單
        cursor.execute('''
            SELECT COUNT(*) FROM orders
            WHERE user_id = ? AND status = 'pending'
        ''', (user_id,))
        
        pending_orders = cursor.fetchone()[0]
        if pending_orders >= 3:
            warnings.append(f"有 {pending_orders} 筆未完成訂單")
            self._log_risk_event(user_id, username, 'MANY_PENDING', 'MEDIUM',
                               f"有 {pending_orders} 筆未完成訂單")
        
        # 3. 檢查餘額異常
        cursor.execute('SELECT balance FROM wallets WHERE user_id = ?', (user_id,))
        balance_result = cursor.fetchone()
        
        if balance_result:
            balance = balance_result[0]
            if balance < 0:
                warnings.append(f"餘額為負數: ${balance}")
                self._log_risk_event(user_id, username, 'NEGATIVE_BALANCE', 'CRITICAL',
                                   f"餘額為負數: ${balance}")
            elif balance > 50000:
                warnings.append(f"餘額異常高: ${balance}")
                self._log_risk_event(user_id, username, 'HIGH_BALANCE', 'MEDIUM',
                                   f"餘額異常高: ${balance}")
        
        # 4. 檢查退款請求
        cursor.execute('''
            SELECT COUNT(*) FROM transactions
            WHERE user_id = ? AND type = '退款' 
              AND created_at >= datetime('now', '-30 days')
        ''', (user_id,))
        
        refund_count = cursor.fetchone()[0]
        if refund_count >= 3:
            warnings.append(f"30天內退款 {refund_count} 次")
            self._log_risk_event(user_id, username, 'FREQUENT_REFUNDS', 'HIGH',
                               f"30天內退款 {refund_count} 次")
        
        # 5. 檢查是否為新帳號大額儲值
        if self._is_new_account(user_id):
            cursor.execute('''
                SELECT SUM(amount) FROM deposits
                WHERE user_id = ?
            ''', (user_id,))
            
            total_deposit = cursor.fetchone()[0]
            if total_deposit and total_deposit > 5000:
                warnings.append(f"新帳號大額儲值: ${total_deposit}")
                self._log_risk_event(user_id, username, 'NEW_ACCOUNT_LARGE_DEPOSIT', 'HIGH',
                                   f"新帳號大額儲值: ${total_deposit}")
        
        conn.close()
        return warnings
    
    def log_suspicious_action(self, user_id: int, username: str, 
                             action_type: str, details: str, ip: str = ""):
        """記錄可疑操作"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO suspicious_logs (user_id, username, action_type, details, ip_address)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, action_type, details, ip))
            conn.commit()
        except Exception as e:
            print(f"記錄可疑操作錯誤: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    # ============ 惡意退款檢測 ============
    
    def check_malicious_refund(self, user_id: int, username: str) -> bool:
        """
        檢查是否為惡意退款
        
        Returns:
            True = 疑似惡意退款，False = 正常
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 檢查30天內退款次數
        cursor.execute('''
            SELECT COUNT(*) FROM transactions
            WHERE user_id = ? AND type = '退款'
              AND created_at >= datetime('now', '-30 days')
        ''', (user_id,))
        
        refund_count = cursor.fetchone()[0]
        
        # 檢查總訂單數
        cursor.execute('''
            SELECT COUNT(*) FROM orders WHERE user_id = ?
        ''', (user_id,))
        
        total_orders = cursor.fetchone()[0]
        conn.close()
        
        # 如果退款次數 >= 3 或 退款率 > 50%
        if refund_count >= 3:
            self._log_risk_event(user_id, username, 'MALICIOUS_REFUND', 'CRITICAL',
                               f"30天內退款 {refund_count} 次")
            return True
        
        if total_orders > 0 and (refund_count / total_orders) > 0.5:
            self._log_risk_event(user_id, username, 'HIGH_REFUND_RATE', 'HIGH',
                               f"退款率 {(refund_count/total_orders)*100:.1f}%")
            return True
        
        return False
    
    # ============ 盜刷檢測 ============
    
    def check_stolen_card(self, user_id: int, username: str, amount: float) -> bool:
        """
        檢查是否疑似盜刷
        
        Returns:
            True = 疑似盜刷，False = 正常
        """
        # 新帳號大額儲值
        if self._is_new_account(user_id) and amount >= 3000:
            self._log_risk_event(user_id, username, 'SUSPECTED_STOLEN_CARD', 'CRITICAL',
                               f"新帳號大額儲值 ${amount}")
            return True
        
        # 檢查短時間內多次儲值
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            SELECT COUNT(*), SUM(amount) FROM deposit_requests
            WHERE user_id = ? AND created_at >= ?
        ''', (user_id, one_hour_ago))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] >= 3:
            self._log_risk_event(user_id, username, 'RAPID_DEPOSITS', 'HIGH',
                               f"1小時內儲值 {result[0]} 次，總額 ${result[1]}")
            return True
        
        return False
    
    # ============ 自動處理 ============
    
    def auto_handle_risks(self) -> Dict:
        """自動處理高風險事件"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 獲取未處理的高危事件
        cursor.execute('''
            SELECT id, user_id, username, event_type, description
            FROM risk_events
            WHERE handled = 0 AND severity = 'CRITICAL'
              AND created_at >= datetime('now', '-24 hours')
        ''')
        
        critical_events = cursor.fetchall()
        
        actions_taken = {
            'auto_banned': [],
            'warnings_sent': [],
            'events_logged': len(critical_events)
        }
        
        for event_id, user_id, username, event_type, description in critical_events:
            # 根據事件類型決定處理方式
            if event_type in ['MALICIOUS_REFUND', 'SUSPECTED_STOLEN_CARD', 'NEGATIVE_BALANCE']:
                # 自動加入黑名單
                success = self.add_to_blacklist(
                    user_id, username,
                    f"自動封禁：{description}",
                    0,  # 系統自動
                    days=7,  # 先封7天
                    notes=f"自動風控系統觸發 - 事件ID: {event_id}"
                )
                
                if success:
                    actions_taken['auto_banned'].append({
                        'user_id': user_id,
                        'username': username,
                        'reason': description
                    })
                    
                    # 標記為已處理
                    self.mark_event_handled(event_id, 0)
        
        conn.close()
        return actions_taken


# ============ 管理介面 ============

def print_security_menu():
    """顯示安全管理選單"""
    print("""
╔═══════════════════════════════════════════╗
║        安全管理與風控系統                  ║
╚═══════════════════════════════════════════╝

1. 查看黑名單
2. 加入黑名單
3. 移除黑名單
4. 檢查用戶是否被封禁
5. 查看風險事件（未處理）
6. 查看風險事件（全部）
7. 檢測用戶可疑操作
8. 自動處理高風險事件
9. 查看儲值限制記錄
0. 返回
""")


def security_management_cli():
    """安全管理命令行介面"""
    security = SecurityManager()
    
    while True:
        print_security_menu()
        choice = input("請選擇功能: ").strip()
        
        if choice == '1':
            blacklist = security.get_blacklist()
            if blacklist:
                print(f"\n📋 黑名單列表（共 {len(blacklist)} 人）")
                print("=" * 80)
                for i, user in enumerate(blacklist, 1):
                    print(f"\n[{i}]")
                    for key, value in user.items():
                        print(f"  {key}: {value}")
            else:
                print("\n✅ 黑名單為空")
        
        elif choice == '2':
            user_id = int(input("用戶ID: "))
            username = input("用戶名: ")
            reason = input("封禁原因: ")
            duration = input("封禁天數（留空=永久）: ").strip()
            notes = input("備註（選填）: ")
            
            days = int(duration) if duration else None
            
            if security.add_to_blacklist(user_id, username, reason, 0, days, notes):
                print("\n✅ 已加入黑名單")
            else:
                print("\n❌ 操作失敗")
        
        elif choice == '3':
            user_id = int(input("用戶ID: "))
            if security.remove_from_blacklist(user_id):
                print("\n✅ 已移除黑名單")
            else:
                print("\n❌ 操作失敗")
        
        elif choice == '4':
            user_id = int(input("用戶ID: "))
            is_banned, reason = security.is_blacklisted(user_id)
            if is_banned:
                print(f"\n🚫 該用戶已被封禁")
                print(f"原因: {reason}")
            else:
                print("\n✅ 該用戶未被封禁")
        
        elif choice == '5':
            events = security.get_risk_events(handled=False)
            if events:
                print(f"\n⚠️ 未處理風險事件（共 {len(events)} 件）")
                print("=" * 80)
                for i, event in enumerate(events, 1):
                    print(f"\n[{i}]")
                    for key, value in event.items():
                        print(f"  {key}: {value}")
            else:
                print("\n✅ 無未處理事件")
        
        elif choice == '6':
            events = security.get_risk_events()
            if events:
                print(f"\n📋 所有風險事件（共 {len(events)} 件）")
                print("=" * 80)
                for i, event in enumerate(events[:20], 1):  # 只顯示前20個
                    print(f"\n[{i}]")
                    for key, value in event.items():
                        print(f"  {key}: {value}")
            else:
                print("\n✅ 無風險事件")
        
        elif choice == '7':
            user_id = int(input("用戶ID: "))
            username = input("用戶名: ")
            warnings = security.detect_suspicious_activity(user_id, username)
            
            if warnings:
                print(f"\n⚠️ 發現可疑操作：")
                for w in warnings:
                    print(f"  • {w}")
            else:
                print("\n✅ 未發現可疑操作")
        
        elif choice == '8':
            print("\n🔄 正在自動處理高風險事件...")
            results = security.auto_handle_risks()
            
            print(f"\n📊 處理結果：")
            print(f"  事件總數: {results['events_logged']}")
            print(f"  自動封禁: {len(results['auto_banned'])}")
            
            if results['auto_banned']:
                print("\n封禁列表：")
                for ban in results['auto_banned']:
                    print(f"  • {ban['username']} (ID: {ban['user_id']})")
                    print(f"    原因: {ban['reason']}")
        
        elif choice == '9':
            user_id = int(input("用戶ID: "))
            can_deposit, count, amount = security.check_deposit_limit(user_id)
            
            print(f"\n📊 儲值限制檢查：")
            print(f"  今日已儲值: {count} 次")
            print(f"  今日總額: ${amount}")
            print(f"  是否可儲值: {'✅ 是' if can_deposit else '❌ 否'}")
            
            if not can_deposit:
                if security._is_new_account(user_id):
                    print(f"  ⚠️ 新帳號每天限制1次儲值")
                else:
                    print(f"  ⚠️ 達到每日儲值上限（3次或$10000）")
        
        elif choice == '0':
            break
        
        else:
            print("❌ 無效的選項")
        
        input("\n按 Enter 繼續...")


if __name__ == '__main__':
    security_management_cli()