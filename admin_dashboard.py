"""
Discord Bot 管理後台系統
功能：訂單查詢、紀錄匯出、對帳、防詐騙追蹤、黑名單管理
與 main_complete.py 共用 wallet.db 資料庫
"""

import sqlite3
from datetime import datetime, timedelta
import csv
import json
from typing import List, Dict, Optional
import os

# 導入安全系統
from security_system import SecurityManager

class OrderManager:
    """訂單管理系統"""
    
    def __init__(self, db_path='wallet.db'):
        self.db_path = db_path
    
    def get_connection(self):
        """獲取資料庫連接"""
        return sqlite3.connect(self.db_path)
    
    # ============ 訂單查詢功能 ============
    
    def get_order_detail(self, order_number: str) -> Optional[Dict]:
        """獲取訂單完整資訊（防糾紛用）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                order_number, user_id, username, item_name, item_price,
                quantity, total_price, status, note, created_at,
                completed_at, staff_id, commission_rate, staff_earning,
                platform_fee, commission_paid
            FROM orders
            WHERE order_number = ?
        ''', (order_number,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
        
        return {
            '訂單號': result[0],
            '用戶ID': result[1],
            '用戶名': result[2],
            '商品名稱': result[3],
            '商品單價': result[4],
            '數量': result[5],
            '總金額': result[6],
            '訂單狀態': result[7],
            '用戶備註': result[8],
            '下單時間': result[9],
            '完成時間': result[10],
            '工作人員ID': result[11],
            '分潤比例': result[12],
            '工作人員收入': result[13],
            '平台抽成': result[14],
            '分潤已發放': result[15]
        }
    
    def get_orders_by_user(self, user_id: int, limit: int = 100) -> List[Dict]:
        """查詢某用戶的所有訂單（防詐騙用）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                order_number, item_name, total_price, status,
                created_at, completed_at, staff_id
            FROM orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (user_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        orders = []
        for r in results:
            orders.append({
                '訂單號': r[0],
                '商品': r[1],
                '金額': r[2],
                '狀態': r[3],
                '下單時間': r[4],
                '完成時間': r[5],
                '工作人員ID': r[6]
            })
        
        return orders
    
    def get_orders_by_staff(self, staff_id: int, limit: int = 100) -> List[Dict]:
        """查詢某工作人員的所有訂單（防跑路用）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                o.order_number, o.user_id, o.username, o.item_name,
                o.total_price, o.status, o.created_at, o.completed_at,
                c.staff_earning, c.platform_fee
            FROM orders o
            LEFT JOIN commissions c ON o.order_number = c.order_number
            WHERE o.staff_id = ?
            ORDER BY o.created_at DESC
            LIMIT ?
        ''', (staff_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        orders = []
        for r in results:
            orders.append({
                '訂單號': r[0],
                '客戶ID': r[1],
                '客戶名': r[2],
                '商品': r[3],
                '訂單金額': r[4],
                '狀態': r[5],
                '下單時間': r[6],
                '完成時間': r[7],
                '工作人員收入': r[8] if r[8] else 0,
                '平台抽成': r[9] if r[9] else 0
            })
        
        return orders
    
    def get_orders_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """查詢時間區間內的所有訂單（對帳用）
        
        Args:
            start_date: 開始日期 (格式: YYYY-MM-DD)
            end_date: 結束日期 (格式: YYYY-MM-DD)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                o.order_number, o.user_id, o.username, o.item_name,
                o.total_price, o.status, o.created_at, o.completed_at,
                o.staff_id, c.staff_name, c.staff_earning, c.platform_fee
            FROM orders o
            LEFT JOIN commissions c ON o.order_number = c.order_number
            WHERE DATE(o.created_at) >= ? AND DATE(o.created_at) <= ?
            ORDER BY o.created_at DESC
        ''', (start_date, end_date))
        
        results = cursor.fetchall()
        conn.close()
        
        orders = []
        for r in results:
            orders.append({
                '訂單號': r[0],
                '客戶ID': r[1],
                '客戶名': r[2],
                '商品': r[3],
                '訂單金額': r[4],
                '狀態': r[5],
                '下單時間': r[6],
                '完成時間': r[7],
                '工作人員ID': r[8],
                '工作人員名': r[9] if r[9] else '未分配',
                '工作人員收入': r[10] if r[10] else 0,
                '平台抽成': r[11] if r[11] else 0
            })
        
        return orders
    
    def get_pending_orders_detail(self) -> List[Dict]:
        """獲取所有待處理訂單的詳細資訊"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                order_number, user_id, username, item_name, total_price,
                note, created_at, staff_earning, platform_fee
            FROM orders
            WHERE status = 'pending'
            ORDER BY created_at ASC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        orders = []
        for r in results:
            # 計算等待時間
            created_time = datetime.strptime(r[6], '%Y-%m-%d %H:%M:%S')
            wait_time = datetime.now() - created_time
            wait_hours = int(wait_time.total_seconds() / 3600)
            
            orders.append({
                '訂單號': r[0],
                '客戶ID': r[1],
                '客戶名': r[2],
                '商品': r[3],
                '金額': r[4],
                '備註': r[5],
                '下單時間': r[6],
                '等待時長': f'{wait_hours} 小時',
                '工作人員可得': r[7],
                '平台抽成': r[8]
            })
        
        return orders
    
    # ============ 統計分析功能 ============
    
    def get_user_statistics(self, user_id: int) -> Dict:
        """獲取用戶統計資料（防詐騙分析）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 基本統計
        cursor.execute('''
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_orders,
                SUM(total_price) as total_spent,
                AVG(total_price) as avg_order_value
            FROM orders
            WHERE user_id = ?
        ''', (user_id,))
        
        stats = cursor.fetchone()
        
        # 最近訂單
        cursor.execute('''
            SELECT created_at, completed_at, status
            FROM orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (user_id,))
        
        last_order = cursor.fetchone()
        
        # 餘額資訊
        cursor.execute('SELECT balance FROM wallets WHERE user_id = ?', (user_id,))
        balance = cursor.fetchone()
        
        conn.close()
        
        return {
            '總訂單數': stats[0],
            '已完成訂單': stats[1],
            '待處理訂單': stats[2],
            '總消費金額': stats[3] if stats[3] else 0,
            '平均訂單金額': stats[4] if stats[4] else 0,
            '當前餘額': balance[0] if balance else 0,
            '最後下單時間': last_order[0] if last_order else '無',
            '最後訂單狀態': last_order[2] if last_order else '無'
        }
    
    def get_staff_statistics(self, staff_id: int) -> Dict:
        """獲取工作人員統計資料（防跑路監控）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 訂單統計
        cursor.execute('''
            SELECT 
                COUNT(*) as total_orders,
                SUM(staff_earning) as total_earning,
                AVG(staff_earning) as avg_earning,
                MIN(created_at) as first_order,
                MAX(created_at) as last_order
            FROM commissions
            WHERE staff_id = ?
        ''', (staff_id,))
        
        stats = cursor.fetchone()
        
        # 本月統計
        now = datetime.now()
        start_of_month = f"{now.year}-{now.month:02d}-01"
        cursor.execute('''
            SELECT COUNT(*), SUM(staff_earning)
            FROM commissions
            WHERE staff_id = ? AND created_at >= ?
        ''', (staff_id, start_of_month))
        
        monthly = cursor.fetchone()
        
        # 待處理訂單
        cursor.execute('''
            SELECT COUNT(*)
            FROM orders
            WHERE staff_id = ? AND status = 'pending'
        ''', (staff_id,))
        
        pending = cursor.fetchone()
        
        conn.close()
        
        return {
            '總完成訂單': stats[0] if stats[0] else 0,
            '總收入': stats[1] if stats[1] else 0,
            '平均單價': stats[2] if stats[2] else 0,
            '首次接單': stats[3] if stats[3] else '無',
            '最後接單': stats[4] if stats[4] else '無',
            '本月訂單': monthly[0] if monthly[0] else 0,
            '本月收入': monthly[1] if monthly[1] else 0,
            '待處理訂單': pending[0] if pending[0] else 0
        }
    
    def get_daily_summary(self, date: str) -> Dict:
        """獲取每日營運摘要（對帳用）
        
        Args:
            date: 日期 (格式: YYYY-MM-DD)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 訂單統計
        cursor.execute('''
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(total_price) as total_revenue
            FROM orders
            WHERE DATE(created_at) = ?
        ''', (date,))
        
        order_stats = cursor.fetchone()
        
        # 分潤統計
        cursor.execute('''
            SELECT 
                SUM(staff_earning) as total_paid_out,
                SUM(platform_fee) as total_platform_fee,
                COUNT(DISTINCT staff_id) as active_staff
            FROM commissions
            WHERE DATE(created_at) = ?
        ''', (date,))
        
        commission_stats = cursor.fetchone()
        
        # 儲值統計
        cursor.execute('''
            SELECT 
                COUNT(*) as deposit_count,
                SUM(amount) as total_deposits
            FROM deposits
            WHERE DATE(created_at) = ?
        ''', (date,))
        
        deposit_stats = cursor.fetchone()
        
        conn.close()
        
        return {
            '日期': date,
            '總訂單數': order_stats[0],
            '已完成': order_stats[1],
            '待處理': order_stats[2],
            '訂單總額': order_stats[3] if order_stats[3] else 0,
            '已付出分潤': commission_stats[0] if commission_stats[0] else 0,
            '平台收益': commission_stats[1] if commission_stats[1] else 0,
            '活躍工作人員': commission_stats[2] if commission_stats[2] else 0,
            '儲值筆數': deposit_stats[0],
            '儲值總額': deposit_stats[1] if deposit_stats[1] else 0
        }
    
    # ============ 異常檢測功能（防詐騙）============
    
    def detect_suspicious_users(self) -> List[Dict]:
        """檢測可疑用戶"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        suspicious_users = []
        
        # 1. 大量未完成訂單的用戶
        cursor.execute('''
            SELECT user_id, username, COUNT(*) as pending_count, SUM(total_price) as total_amount
            FROM orders
            WHERE status = 'pending'
            GROUP BY user_id
            HAVING COUNT(*) >= 3
            ORDER BY pending_count DESC
        ''')
        
        for r in cursor.fetchall():
            suspicious_users.append({
                '用戶ID': r[0],
                '用戶名': r[1],
                '異常類型': '大量未完成訂單',
                '待處理訂單數': r[2],
                '涉及金額': r[3],
                '風險等級': '⚠️ 中'
            })
        
        # 2. 短時間內大量下單的用戶
        one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            SELECT user_id, username, COUNT(*) as order_count, SUM(total_price) as total
            FROM orders
            WHERE created_at >= ?
            GROUP BY user_id
            HAVING COUNT(*) >= 5
        ''', (one_hour_ago,))
        
        for r in cursor.fetchall():
            suspicious_users.append({
                '用戶ID': r[0],
                '用戶名': r[1],
                '異常類型': '1小時內大量下單',
                '訂單數': r[2],
                '涉及金額': r[3],
                '風險等級': '🚨 高'
            })
        
        # 3. 餘額異常（負數或極高）
        cursor.execute('''
            SELECT user_id, username, balance
            FROM wallets
            WHERE balance < 0 OR balance > 10000
        ''')
        
        for r in cursor.fetchall():
            risk = '🚨 高' if r[2] < 0 else '⚠️ 中'
            suspicious_users.append({
                '用戶ID': r[0],
                '用戶名': r[1],
                '異常類型': '餘額異常',
                '當前餘額': r[2],
                '風險等級': risk
            })
        
        conn.close()
        return suspicious_users
    
    def detect_suspicious_staff(self) -> List[Dict]:
        """檢測可疑工作人員（防跑路）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        suspicious_staff = []
        
        # 1. 有未完成訂單但長時間未活動
        two_days_ago = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            SELECT o.staff_id, c.staff_name, COUNT(*) as pending_count
            FROM orders o
            LEFT JOIN commissions c ON o.staff_id = c.staff_id
            WHERE o.status = 'pending' 
              AND o.staff_id IS NOT NULL
              AND o.created_at < ?
            GROUP BY o.staff_id
            HAVING COUNT(*) > 0
        ''', (two_days_ago,))
        
        for r in cursor.fetchall():
            suspicious_staff.append({
                '工作人員ID': r[0],
                '工作人員名': r[1] if r[1] else '未知',
                '異常類型': '長時間未完成訂單',
                '待處理訂單': r[2],
                '風險等級': '🚨 高（疑似跑路）'
            })
        
        # 2. 突然停止接單的活躍人員
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            SELECT c.staff_id, c.staff_name, 
                   COUNT(*) as past_orders,
                   MAX(c.created_at) as last_order
            FROM commissions c
            WHERE c.created_at < ?
            GROUP BY c.staff_id
            HAVING COUNT(*) >= 10
        ''', (seven_days_ago,))
        
        for r in cursor.fetchall():
            # 檢查最近是否有接單
            cursor.execute('''
                SELECT COUNT(*) FROM commissions
                WHERE staff_id = ? AND created_at >= ?
            ''', (r[0], seven_days_ago))
            
            recent_orders = cursor.fetchone()[0]
            
            if recent_orders == 0:
                suspicious_staff.append({
                    '工作人員ID': r[0],
                    '工作人員名': r[1],
                    '異常類型': '活躍人員突然消失',
                    '歷史訂單數': r[2],
                    '最後接單': r[3],
                    '風險等級': '⚠️ 中'
                })
        
        conn.close()
        return suspicious_staff
    
    # ============ 匯出功能 ============
    
    def export_to_csv(self, data: List[Dict], filename: str):
        """匯出資料為 CSV 檔案"""
        if not data:
            print("沒有資料可匯出")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        
        print(f"✅ 資料已匯出到 {filename}")
    
    def export_to_json(self, data: List[Dict], filename: str):
        """匯出資料為 JSON 檔案"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 資料已匯出到 {filename}")
    
    # ============ 對帳報表功能 ============
    
    def generate_reconciliation_report(self, start_date: str, end_date: str) -> Dict:
        """生成對帳報表
        
        Args:
            start_date: 開始日期 (YYYY-MM-DD)
            end_date: 結束日期 (YYYY-MM-DD)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 訂單營收
        cursor.execute('''
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN status = 'completed' THEN total_price ELSE 0 END) as completed_revenue,
                SUM(CASE WHEN status = 'pending' THEN total_price ELSE 0 END) as pending_revenue
            FROM orders
            WHERE DATE(created_at) >= ? AND DATE(created_at) <= ?
        ''', (start_date, end_date))
        
        order_stats = cursor.fetchone()
        
        # 分潤支出
        cursor.execute('''
            SELECT 
                SUM(staff_earning) as total_commission,
                SUM(platform_fee) as total_platform_fee
            FROM commissions
            WHERE DATE(created_at) >= ? AND DATE(created_at) <= ?
        ''', (start_date, end_date))
        
        commission_stats = cursor.fetchone()
        
        # 儲值收入
        cursor.execute('''
            SELECT 
                COUNT(*) as deposit_count,
                SUM(amount) as total_deposits
            FROM deposits
            WHERE DATE(created_at) >= ? AND DATE(created_at) <= ?
        ''', (start_date, end_date))
        
        deposit_stats = cursor.fetchone()
        
        # 交易紀錄
        cursor.execute('''
            SELECT 
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_income,
                SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) as total_expense
            FROM transactions
            WHERE DATE(created_at) >= ? AND DATE(created_at) <= ?
        ''', (start_date, end_date))
        
        transaction_stats = cursor.fetchone()
        
        conn.close()
        
        completed_revenue = order_stats[1] if order_stats[1] else 0
        total_commission = commission_stats[0] if commission_stats[0] else 0
        total_platform_fee = commission_stats[1] if commission_stats[1] else 0
        total_deposits = deposit_stats[1] if deposit_stats[1] else 0
        
        return {
            '對帳期間': f'{start_date} 至 {end_date}',
            '總訂單數': order_stats[0],
            '已完成訂單營收': completed_revenue,
            '待處理訂單金額': order_stats[2] if order_stats[2] else 0,
            '已付出分潤': total_commission,
            '平台實際收益': total_platform_fee,
            '儲值筆數': deposit_stats[0],
            '儲值總額': total_deposits,
            '系統記錄收入': transaction_stats[0] if transaction_stats[0] else 0,
            '系統記錄支出': abs(transaction_stats[1]) if transaction_stats[1] else 0,
            '淨利潤': total_platform_fee,
            '營收確認': '✅ 正常' if completed_revenue == (total_commission + total_platform_fee) else '❌ 異常'
        }


# ============ 命令行工具 ============

def print_dict(data: Dict, title: str = ""):
    """美化輸出字典"""
    if title:
        print(f"\n{'='*50}")
        print(f"  {title}")
        print('='*50)
    
    for key, value in data.items():
        if isinstance(value, float):
            print(f"{key}: ${value:.2f}")
        else:
            print(f"{key}: {value}")
    print()

def print_list(data: List[Dict], title: str = ""):
    """美化輸出列表"""
    if not data:
        print(f"\n{title} - 無資料")
        return
    
    if title:
        print(f"\n{'='*50}")
        print(f"  {title}")
        print('='*50)
    
    for i, item in enumerate(data, 1):
        print(f"\n[{i}]")
        for key, value in item.items():
            if isinstance(value, float):
                print(f"  {key}: ${value:.2f}")
            else:
                print(f"  {key}: {value}")
    print()


def main():
    """主程式 - 命令行介面"""
    manager = OrderManager()
    security = SecurityManager()  # 初始化安全系統
    
    print("""
╔═══════════════════════════════════════════╗
║     Discord Bot 訂單管理後台系統           ║
║     防詐騙 | 防糾紛 | 對帳工具 | 安全管理   ║
╚═══════════════════════════════════════════╝
""")
    
    while True:
        print("""
請選擇功能：

【訂單管理】
1. 查詢訂單詳情
2. 查詢用戶所有訂單
3. 查詢工作人員所有訂單
4. 查詢時間區間訂單
5. 查看待處理訂單

【統計分析】
6. 用戶統計分析
7. 工作人員統計分析
8. 每日營運摘要
9. 檢測可疑用戶
10. 檢測可疑工作人員

【財務報表】
11. 生成對帳報表
12. 匯出資料

【安全管理】⭐ 新增
13. 查看黑名單
14. 加入黑名單
15. 移除黑名單
16. 檢查用戶黑名單狀態
17. 查看風險事件
18. 查看儲值限制記錄
19. 自動風控處理

0. 退出
""")
        
        choice = input("請輸入選項: ").strip()
        
        if choice == '1':
            order_number = input("請輸入訂單號: ").strip()
            detail = manager.get_order_detail(order_number)
            if detail:
                print_dict(detail, f"訂單 {order_number} 詳情")
            else:
                print("❌ 找不到此訂單")
        
        elif choice == '2':
            user_id = input("請輸入用戶ID: ").strip()
            try:
                orders = manager.get_orders_by_user(int(user_id))
                print_list(orders, f"用戶 {user_id} 的訂單")
                
                export = input("\n是否匯出? (y/n): ").strip().lower()
                if export == 'y':
                    manager.export_to_csv(orders, f'user_{user_id}_orders.csv')
            except ValueError:
                print("❌ 無效的用戶ID")
        
        elif choice == '3':
            staff_id = input("請輸入工作人員ID: ").strip()
            try:
                orders = manager.get_orders_by_staff(int(staff_id))
                print_list(orders, f"工作人員 {staff_id} 的訂單")
                
                export = input("\n是否匯出? (y/n): ").strip().lower()
                if export == 'y':
                    manager.export_to_csv(orders, f'staff_{staff_id}_orders.csv')
            except ValueError:
                print("❌ 無效的工作人員ID")
        
        elif choice == '4':
            start_date = input("請輸入開始日期 (YYYY-MM-DD): ").strip()
            end_date = input("請輸入結束日期 (YYYY-MM-DD): ").strip()
            orders = manager.get_orders_by_date_range(start_date, end_date)
            print_list(orders, f"{start_date} 至 {end_date} 的訂單")
            
            export = input("\n是否匯出? (y/n): ").strip().lower()
            if export == 'y':
                manager.export_to_csv(orders, f'orders_{start_date}_to_{end_date}.csv')
        
        elif choice == '5':
            orders = manager.get_pending_orders_detail()
            print_list(orders, "待處理訂單")
        
        elif choice == '6':
            user_id = input("請輸入用戶ID: ").strip()
            try:
                stats = manager.get_user_statistics(int(user_id))
                print_dict(stats, f"用戶 {user_id} 統計資料")
            except ValueError:
                print("❌ 無效的用戶ID")
        
        elif choice == '7':
            staff_id = input("請輸入工作人員ID: ").strip()
            try:
                stats = manager.get_staff_statistics(int(staff_id))
                print_dict(stats, f"工作人員 {staff_id} 統計資料")
            except ValueError:
                print("❌ 無效的工作人員ID")
        
        elif choice == '8':
            date = input("請輸入日期 (YYYY-MM-DD，留空=今天): ").strip()
            if not date:
                date = datetime.now().strftime('%Y-%m-%d')
            summary = manager.get_daily_summary(date)
            print_dict(summary, f"{date} 營運摘要")
        
        elif choice == '9':
            suspicious = manager.detect_suspicious_users()
            print_list(suspicious, "可疑用戶列表")
            
            if suspicious:
                export = input("\n是否匯出? (y/n): ").strip().lower()
                if export == 'y':
                    manager.export_to_csv(suspicious, 'suspicious_users.csv')
        
        elif choice == '10':
            suspicious = manager.detect_suspicious_staff()
            print_list(suspicious, "可疑工作人員列表")
            
            if suspicious:
                export = input("\n是否匯出? (y/n): ").strip().lower()
                if export == 'y':
                    manager.export_to_csv(suspicious, 'suspicious_staff.csv')
        
        elif choice == '11':
            start_date = input("請輸入開始日期 (YYYY-MM-DD): ").strip()
            end_date = input("請輸入結束日期 (YYYY-MM-DD): ").strip()
            report = manager.generate_reconciliation_report(start_date, end_date)
            print_dict(report, "對帳報表")
            
            export = input("\n是否匯出? (y/n): ").strip().lower()
            if export == 'y':
                with open(f'reconciliation_{start_date}_to_{end_date}.json', 'w', encoding='utf-8') as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
                print(f"✅ 報表已匯出")
        
        elif choice == '12':
            print("""
匯出選項：
1. 所有訂單
2. 所有分潤紀錄
3. 所有用戶
4. 所有儲值紀錄
""")
            export_choice = input("請選擇: ").strip()
            
            if export_choice == '1':
                orders = manager.get_orders_by_date_range('2020-01-01', '2099-12-31')
                manager.export_to_csv(orders, 'all_orders.csv')
        
        # ============ 安全管理功能 ============
        
        elif choice == '13':
            # 查看黑名單
            blacklist = security.get_blacklist()
            if blacklist:
                print(f"\n{'='*80}")
                print(f"  📋 黑名單列表（共 {len(blacklist)} 人）")
                print('='*80)
                for i, user in enumerate(blacklist, 1):
                    print(f"\n[{i}]")
                    for key, value in user.items():
                        print(f"  {key}: {value}")
                
                export = input("\n是否匯出? (y/n): ").strip().lower()
                if export == 'y':
                    manager.export_to_csv(blacklist, 'blacklist.csv')
            else:
                print("\n✅ 黑名單為空")
        
        elif choice == '14':
            # 加入黑名單
            print("\n=== 加入黑名單 ===")
            try:
                user_id = int(input("用戶ID: "))
                username = input("用戶名: ")
                reason = input("封禁原因: ")
                duration = input("封禁天數（留空=永久）: ").strip()
                notes = input("備註（選填）: ")
                
                days = int(duration) if duration else None
                
                if security.add_to_blacklist(user_id, username, reason, 0, days, notes):
                    duration_text = f"{days}天" if days else "永久"
                    print(f"\n✅ 已加入黑名單（{duration_text}）")
                else:
                    print("\n❌ 操作失敗")
            except ValueError:
                print("❌ 輸入格式錯誤")
        
        elif choice == '15':
            # 移除黑名單
            try:
                user_id = int(input("用戶ID: "))
                if security.remove_from_blacklist(user_id):
                    print("\n✅ 已移除黑名單")
                else:
                    print("\n❌ 操作失敗或該用戶不在黑名單中")
            except ValueError:
                print("❌ 無效的用戶ID")
        
        elif choice == '16':
            # 檢查黑名單狀態
            try:
                user_id = int(input("用戶ID: "))
                is_banned, reason = security.is_blacklisted(user_id)
                
                print(f"\n{'='*60}")
                print(f"  用戶 {user_id} 黑名單狀態")
                print('='*60)
                
                if is_banned:
                    print(f"\n🚫 該用戶已被封禁")
                    print(f"原因: {reason}")
                else:
                    print(f"\n✅ 該用戶未被封禁")
                
                # 顯示更多資訊
                warnings = security.detect_suspicious_activity(user_id, "查詢用戶")
                if warnings:
                    print(f"\n⚠️  可疑操作：")
                    for w in warnings:
                        print(f"  • {w}")
                
                can_deposit, count, amount = security.check_deposit_limit(user_id)
                print(f"\n今日儲值記錄：")
                print(f"  次數: {count}")
                print(f"  金額: ${amount:.2f}")
                print(f"  可否儲值: {'✅ 是' if can_deposit else '❌ 否'}")
                
            except ValueError:
                print("❌ 無效的用戶ID")
        
        elif choice == '17':
            # 查看風險事件
            print("""
查看選項：
1. 未處理事件
2. 所有事件
""")
            event_choice = input("請選擇: ").strip()
            
            if event_choice == '1':
                events = security.get_risk_events(handled=False)
                title = "未處理風險事件"
            else:
                events = security.get_risk_events()
                title = "所有風險事件"
            
            if events:
                print(f"\n{'='*80}")
                print(f"  ⚠️  {title}（共 {len(events)} 件）")
                print('='*80)
                for i, event in enumerate(events[:20], 1):  # 只顯示前20個
                    print(f"\n[{i}]")
                    for key, value in event.items():
                        print(f"  {key}: {value}")
                
                if len(events) > 20:
                    print(f"\n僅顯示前20件，共 {len(events)} 件")
                
                export = input("\n是否匯出? (y/n): ").strip().lower()
                if export == 'y':
                    manager.export_to_csv(events, f'risk_events_{datetime.now().strftime("%Y%m%d")}.csv')
            else:
                print("\n✅ 無風險事件")
        
        elif choice == '18':
            # 查看儲值限制記錄
            try:
                user_id = int(input("用戶ID: "))
                can_deposit, count, amount = security.check_deposit_limit(user_id)
                
                print(f"\n{'='*60}")
                print(f"  📊 儲值限制檢查 - 用戶 {user_id}")
                print('='*60)
                print(f"\n今日已儲值: {count} 次")
                print(f"今日總額: ${amount:.2f}")
                print(f"是否可儲值: {'✅ 是' if can_deposit else '❌ 否'}")
                
                if not can_deposit:
                    if security._is_new_account(user_id):
                        print(f"\n⚠️  新帳號每天限制1次儲值")
                    else:
                        print(f"\n⚠️  達到每日儲值上限（3次或$10000）")
                
                is_new = security._is_new_account(user_id)
                print(f"\n帳號類型: {'🆕 新帳號（7天內註冊）' if is_new else '✅ 正常帳號'}")
                
            except ValueError:
                print("❌ 無效的用戶ID")
        
        elif choice == '19':
            # 自動風控處理
            print("\n🔄 正在執行自動風控處理...")
            results = security.auto_handle_risks()
            
            print(f"\n{'='*60}")
            print(f"  📊 處理結果")
            print('='*60)
            print(f"\n檢測事件: {results['events_logged']} 件")
            print(f"自動封禁: {len(results['auto_banned'])} 人")
            
            if results['auto_banned']:
                print("\n封禁列表：")
                for ban in results['auto_banned']:
                    print(f"\n  • {ban['username']} (ID: {ban['user_id']})")
                    print(f"    原因: {ban['reason']}")
            
            if results['auto_banned']:
                export = input("\n是否匯出封禁記錄? (y/n): ").strip().lower()
                if export == 'y':
                    filename = f'auto_banned_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)
                    print(f"✅ 已匯出到 {filename}")
        
        elif choice == '0':
            print("\n再見！")
            break
        
        else:
            print("❌ 無效的選項")
        
        input("\n按 Enter 繼續...")


if __name__ == '__main__':
    main()