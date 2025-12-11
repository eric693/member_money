import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from datetime import datetime
import os
from typing import Optional
from dotenv import load_dotenv
import calendar

# ============ 導入安全系統 ============
from security_system import SecurityManager

# 載入 .env 文件
load_dotenv()

# ============ 儲值方案配置 ============
DEPOSIT_PLANS = {
    300: 300,
    500: 520,
    1000: 1100,
    3000: 3400
}

# 轉帳資訊（請修改成你的實際資訊）
BANK_INFO = {
    "銀行名稱": "台灣銀行",
    "銀行代碼": "004",
    "帳號": "123-456-789012",
    "戶名": "你的名字"
}

# ============ 商城商品配置 ============
SHOP_ITEMS = {
    "陪玩1小時": {
        "price": 200,
        "description": "專業陪玩1小時，提供語音服務",
        "category": "陪玩服務",
        "stock": -1,
        "emoji": "🎮",
        "commission_rate": 0.70
    },
    "傳說上分1星": {
        "price": 150,
        "description": "專業代練，保證上分到傳說",
        "category": "代練服務",
        "stock": -1,
        "emoji": "⭐",
        "commission_rate": 0.70
    },
    "代儲1000鑽": {
        "price": 280,
        "description": "遊戲內代儲1000鑽石",
        "category": "代儲服務",
        "stock": -1,
        "emoji": "💎",
        "commission_rate": 0.70
    },
    "客製服務": {
        "price": 500,
        "description": "客製化服務，請在購買後說明需求",
        "category": "客製服務",
        "stock": -1,
        "emoji": "✨",
        "commission_rate": 0.70
    },
    "VIP會員月卡": {
        "price": 1000,
        "description": "VIP會員30天，享有專屬優惠",
        "category": "會員服務",
        "stock": -1,
        "emoji": "👑",
        "commission_rate": 0.00
    }
}

# 工作人員角色 ID
STAFF_ROLES = {
    "陪玩服務": 1041668052909035612,
    "代練服務": 1041668052909035612,
    "代儲服務": 1041668052909035612,
    "客製服務": 1041668052909035612,
    "會員服務": 1041668052909035612
}

# 通知頻道 ID
NOTIFICATION_CHANNEL_ID = 1448290873031917701

# 初始化 Bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

# ============ 初始化安全系統 ============
security_manager = SecurityManager()

# ============ 安全檢查裝飾器 ============
async def check_blacklist(interaction: discord.Interaction) -> bool:
    """檢查用戶是否在黑名單"""
    user_id = interaction.user.id
    is_banned, reason = security_manager.is_blacklisted(user_id)
    
    if is_banned:
        embed = discord.Embed(
            title="🚫 帳號已被封禁",
            description=f"你的帳號因以下原因被封禁：\n**{reason}**",
            color=discord.Color.red()
        )
        embed.add_field(
            name="申訴方式",
            value="如有疑問，請聯繫管理員",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False
    
    return True

# 資料庫初始化
def init_database():
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallets (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            balance REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES wallets (user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            method TEXT,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES wallets (user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposit_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            amount REAL NOT NULL,
            bonus_points REAL NOT NULL,
            screenshot_url TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            processed_by INTEGER,
            reject_reason TEXT,
            FOREIGN KEY (user_id) REFERENCES wallets (user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            category TEXT,
            stock INTEGER DEFAULT -1,
            emoji TEXT,
            enabled INTEGER DEFAULT 1,
            commission_rate REAL DEFAULT 0.70,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            item_name TEXT NOT NULL,
            item_price REAL NOT NULL,
            quantity INTEGER DEFAULT 1,
            total_price REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            staff_id INTEGER,
            commission_rate REAL DEFAULT 0.70,
            staff_earning REAL DEFAULT 0,
            platform_fee REAL DEFAULT 0,
            commission_paid INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES wallets (user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT NOT NULL,
            staff_id INTEGER NOT NULL,
            staff_name TEXT NOT NULL,
            order_amount REAL NOT NULL,
            commission_rate REAL NOT NULL,
            staff_earning REAL NOT NULL,
            platform_fee REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_number) REFERENCES orders (order_number)
        )
    ''')
    
    cursor.execute('SELECT COUNT(*) FROM shop_items')
    if cursor.fetchone()[0] == 0:
        for name, info in SHOP_ITEMS.items():
            cursor.execute('''
                INSERT INTO shop_items (name, price, description, category, stock, emoji, commission_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, info["price"], info["description"], info["category"], 
                  info["stock"], info["emoji"], info["commission_rate"]))
    
    conn.commit()
    conn.close()

def create_wallet(user_id: int, username: str):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO wallets (user_id, username) VALUES (?, ?)', 
                      (user_id, username))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_balance(user_id: int) -> Optional[float]:
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM wallets WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def update_balance(user_id: int, amount: float, transaction_type: str, description: str = ""):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE wallets SET balance = balance + ? WHERE user_id = ?', 
                      (amount, user_id))
        
        cursor.execute('''
            INSERT INTO transactions (user_id, amount, type, description)
            VALUES (?, ?, ?, ?)
        ''', (user_id, amount, transaction_type, description))
        
        if transaction_type == '儲值':
            cursor.execute('''
                INSERT INTO deposits (user_id, amount, method)
                VALUES (?, ?, ?)
            ''', (user_id, abs(amount), description))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"更新餘額錯誤: {e}")
        return False
    finally:
        conn.close()

def get_shop_items(enabled_only=True):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    if enabled_only:
        cursor.execute('SELECT name, price, description, category, stock, emoji, commission_rate FROM shop_items WHERE enabled = 1')
    else:
        cursor.execute('SELECT name, price, description, category, stock, emoji, commission_rate FROM shop_items')
    results = cursor.fetchall()
    conn.close()
    return results

def get_shop_item(item_name: str):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, price, description, category, stock, emoji, commission_rate FROM shop_items WHERE name = ? AND enabled = 1', (item_name,))
    result = cursor.fetchone()
    conn.close()
    return result

def create_order(user_id: int, username: str, item_name: str, item_price: float, quantity: int, commission_rate: float, note: str = ""):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    try:
        order_number = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{user_id % 1000:03d}"
        total_price = item_price * quantity
        staff_earning = total_price * commission_rate
        platform_fee = total_price - staff_earning
        
        cursor.execute('''
            INSERT INTO orders (order_number, user_id, username, item_name, item_price, quantity, 
                               total_price, note, commission_rate, staff_earning, platform_fee)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_number, user_id, username, item_name, item_price, quantity, 
              total_price, note, commission_rate, staff_earning, platform_fee))
        
        conn.commit()
        return order_number
    except Exception as e:
        conn.rollback()
        print(f"創建訂單錯誤: {e}")
        return None
    finally:
        conn.close()

def get_order(order_number: str):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT order_number, user_id, username, item_name, item_price, quantity, total_price, 
               status, note, created_at, staff_id, commission_rate, staff_earning, platform_fee, commission_paid
        FROM orders WHERE order_number = ?
    ''', (order_number,))
    result = cursor.fetchone()
    conn.close()
    return result

def complete_order_with_commission(order_number: str, staff_id: int, staff_name: str):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT total_price, commission_rate, staff_earning, platform_fee, commission_paid
            FROM orders WHERE order_number = ?
        ''', (order_number,))
        result = cursor.fetchone()
        
        if not result:
            return False, "訂單不存在"
        
        total_price, commission_rate, staff_earning, platform_fee, commission_paid = result
        
        if commission_paid:
            return False, "分潤已發放"
        
        cursor.execute('''
            UPDATE orders 
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP, 
                staff_id = ?, commission_paid = 1
            WHERE order_number = ?
        ''', (staff_id, order_number))
        
        cursor.execute('''
            INSERT INTO commissions (order_number, staff_id, staff_name, order_amount, 
                                    commission_rate, staff_earning, platform_fee)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (order_number, staff_id, staff_name, total_price, commission_rate, 
              staff_earning, platform_fee))
        
        conn.commit()
        return True, {
            'staff_earning': staff_earning,
            'platform_fee': platform_fee,
            'total_price': total_price,
            'commission_rate': commission_rate
        }
    except Exception as e:
        conn.rollback()
        print(f"完成訂單錯誤: {e}")
        return False, f"系統錯誤: {e}"
    finally:
        conn.close()

def get_pending_orders():
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT order_number, user_id, username, item_name, item_price, quantity, 
               total_price, note, created_at, staff_earning, platform_fee
        FROM orders WHERE status = 'pending'
        ORDER BY created_at DESC
    ''')
    results = cursor.fetchall()
    conn.close()
    return results

def get_user_orders(user_id: int, limit: int = 10):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT order_number, item_name, total_price, status, created_at
        FROM orders WHERE user_id = ?
        ORDER BY created_at DESC LIMIT ?
    ''', (user_id, limit))
    results = cursor.fetchall()
    conn.close()
    return results

def get_staff_commissions(staff_id: int, limit: int = 10):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT order_number, order_amount, commission_rate, staff_earning, platform_fee, created_at
        FROM commissions WHERE staff_id = ?
        ORDER BY created_at DESC LIMIT ?
    ''', (staff_id, limit))
    results = cursor.fetchall()
    conn.close()
    return results

def get_staff_total_earnings(staff_id: int):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT SUM(staff_earning), COUNT(*)
        FROM commissions WHERE staff_id = ?
    ''', (staff_id,))
    result = cursor.fetchone()
    conn.close()
    return result if result else (0, 0)

def get_platform_stats():
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*), SUM(total_price) FROM orders WHERE status = "completed"')
    total_orders, total_revenue = cursor.fetchone()
    
    cursor.execute('SELECT SUM(staff_earning), SUM(platform_fee) FROM commissions')
    total_paid_out, total_platform_fee = cursor.fetchone()
    
    conn.close()
    
    return {
        'total_orders': total_orders or 0,
        'total_revenue': total_revenue or 0,
        'total_paid_out': total_paid_out or 0,
        'total_platform_fee': total_platform_fee or 0
    }

def get_monthly_platform_stats(year: int, month: int):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02d}-01"
    
    cursor.execute('''
        SELECT COUNT(*), SUM(total_price) 
        FROM orders 
        WHERE status = "completed" AND completed_at >= ? AND completed_at < ?
    ''', (start_date, end_date))
    monthly_orders, monthly_revenue = cursor.fetchone()
    
    cursor.execute('''
        SELECT SUM(staff_earning), SUM(platform_fee) 
        FROM commissions 
        WHERE created_at >= ? AND created_at < ?
    ''', (start_date, end_date))
    monthly_paid_out, monthly_platform_fee = cursor.fetchone()
    
    conn.close()
    
    return {
        'monthly_orders': monthly_orders or 0,
        'monthly_revenue': monthly_revenue or 0,
        'monthly_paid_out': monthly_paid_out or 0,
        'monthly_platform_fee': monthly_platform_fee or 0
    }

def get_top_earners(limit: int = 10):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT staff_name, staff_id, SUM(staff_earning) as total_earning, COUNT(*) as order_count
        FROM commissions
        GROUP BY staff_id
        ORDER BY total_earning DESC
        LIMIT ?
    ''', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

def create_deposit_request(user_id: int, username: str, amount: float, bonus_points: float, screenshot_url: str):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO deposit_requests (user_id, username, amount, bonus_points, screenshot_url)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, amount, bonus_points, screenshot_url))
        conn.commit()
        request_id = cursor.lastrowid
        return request_id
    except Exception as e:
        print(f"創建儲值申請錯誤: {e}")
        return None
    finally:
        conn.close()

def get_pending_requests():
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, username, amount, bonus_points, screenshot_url, created_at
        FROM deposit_requests
        WHERE status = 'pending'
        ORDER BY created_at ASC
    ''')
    results = cursor.fetchall()
    conn.close()
    return results

def get_deposit_request(request_id: int):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, username, amount, bonus_points, screenshot_url, status
        FROM deposit_requests
        WHERE id = ?
    ''', (request_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def approve_deposit_request(request_id: int, admin_id: int):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT user_id, amount, bonus_points FROM deposit_requests WHERE id = ?', (request_id,))
        result = cursor.fetchone()
        if not result:
            return False, "找不到此申請"
        
        user_id, amount, bonus_points = result
        
        cursor.execute('''
            UPDATE deposit_requests 
            SET status = 'approved', processed_at = CURRENT_TIMESTAMP, processed_by = ?
            WHERE id = ?
        ''', (admin_id, request_id))
        
        cursor.execute('UPDATE wallets SET balance = balance + ? WHERE user_id = ?', 
                      (bonus_points, user_id))
        
        cursor.execute('''
            INSERT INTO transactions (user_id, amount, type, description)
            VALUES (?, ?, ?, ?)
        ''', (user_id, bonus_points, "儲值", f"台灣轉帳 ${amount} → {bonus_points} 點"))
        
        cursor.execute('''
            INSERT INTO deposits (user_id, amount, method)
            VALUES (?, ?, ?)
        ''', (user_id, amount, "台灣轉帳"))
        
        conn.commit()
        return True, "審核通過"
    except Exception as e:
        conn.rollback()
        print(f"批准儲值錯誤: {e}")
        return False, f"系統錯誤: {e}"
    finally:
        conn.close()

def reject_deposit_request(request_id: int, admin_id: int, reason: str):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE deposit_requests 
            SET status = 'rejected', processed_at = CURRENT_TIMESTAMP, 
                processed_by = ?, reject_reason = ?
            WHERE id = ?
        ''', (admin_id, reason, request_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"拒絕儲值錯誤: {e}")
        return False
    finally:
        conn.close()

def get_transactions(user_id: int, limit: int = 10):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT amount, type, description, created_at 
        FROM transactions 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (user_id, limit))
    results = cursor.fetchall()
    conn.close()
    return results

def get_deposits(user_id: int, limit: int = 10):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT amount, method, status, created_at 
        FROM deposits 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (user_id, limit))
    results = cursor.fetchall()
    conn.close()
    return results

def get_leaderboard(limit: int = 10):
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT username, balance 
        FROM wallets 
        ORDER BY balance DESC 
        LIMIT ?
    ''', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

@bot.event
async def on_ready():
    init_database()
    print(f'{bot.user} 已上線！')
    try:
        synced = await bot.tree.sync()
        print(f'同步了 {len(synced)} 個指令')
    except Exception as e:
        print(f'同步指令失敗: {e}')

@bot.tree.command(name="註冊", description="創建你的個人錢包")
async def register(interaction: discord.Interaction):
    # 檢查黑名單
    if not await check_blacklist(interaction):
        return
    
    user_id = interaction.user.id
    username = interaction.user.name
    
    if create_wallet(user_id, username):
        embed = discord.Embed(
            title="✅ 註冊成功！",
            description=f"歡迎 {username}！\n你的個人錢包已創建",
            color=discord.Color.green()
        )
        embed.add_field(name="初始餘額", value="$0", inline=False)
        embed.set_footer(text="使用 /商城 查看商品 | /我要儲值 開始儲值")
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="⚠️ 已註冊",
            description="你已經有錢包了！",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="我的餘額", description="查詢你的當前餘額")
async def balance(interaction: discord.Interaction):
    user_id = interaction.user.id
    balance_amount = get_balance(user_id)
    
    if balance_amount is None:
        embed = discord.Embed(
            title="❌ 尚未註冊",
            description="請先使用 /註冊 創建錢包",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title="💰 我的錢包",
            color=discord.Color.blue()
        )
        embed.add_field(name="當前餘額", value=f"${balance_amount:.2f}", inline=False)
        embed.set_footer(text=f"用戶: {interaction.user.name}")
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="商城", description="查看商城商品列表")
async def shop(interaction: discord.Interaction):
    # 檢查黑名單
    if not await check_blacklist(interaction):
        return
    
    user_id = interaction.user.id
    username = interaction.user.name
    balance = get_balance(user_id)
    
    if balance is None:
        embed = discord.Embed(
            title="❌ 尚未註冊",
            description="請先使用 /註冊 創建錢包",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # 檢測可疑操作
    warnings = security_manager.detect_suspicious_activity(user_id, username)
    
    if warnings:
        # 有可疑操作，發送警告給管理員
        if NOTIFICATION_CHANNEL_ID:
            try:
                channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
                if channel:
                    alert_embed = discord.Embed(
                        title="⚠️ 可疑操作警報",
                        description=f"用戶 {username} (ID: {user_id}) 行為異常",
                        color=discord.Color.orange()
                    )
                    alert_embed.add_field(
                        name="異常行為",
                        value="\n".join([f"• {w}" for w in warnings]),
                        inline=False
                    )
                    await channel.send(embed=alert_embed)
            except:
                pass
    
    items = get_shop_items()
    
    if not items:
        embed = discord.Embed(
            title="🏪 商城",
            description="目前沒有可用商品",
            color=discord.Color.grey()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title="🏪 商城",
        description=f"你的餘額: **${balance:.2f}**\n請選擇想要購買的商品",
        color=discord.Color.gold()
    )
    
    categories = {}
    for name, price, description, category, stock, emoji, commission_rate in items:
        if category not in categories:
            categories[category] = []
        categories[category].append((name, price, description, stock, emoji, commission_rate))
    
    for category, products in categories.items():
        product_list = ""
        for name, price, description, stock, emoji, commission_rate in products:
            stock_text = f"（剩餘 {stock}）" if stock > 0 else ""
            product_list += f"{emoji} **{name}** - ${price}\n{description}{stock_text}\n\n"
        embed.add_field(name=f"【{category}】", value=product_list, inline=False)
    
    embed.set_footer(text="點擊下方按鈕購買商品")
    
    view = ShopView(items[:25])
    await interaction.response.send_message(embed=embed, view=view)

class ShopView(discord.ui.View):
    def __init__(self, items):
        super().__init__(timeout=300)
        
        for name, price, description, category, stock, emoji, commission_rate in items:
            button = discord.ui.Button(
                label=f"{emoji} {name} - ${price}",
                style=discord.ButtonStyle.primary,
                custom_id=f"buy_{name}"
            )
            button.callback = self.create_callback(name, price, description, category, emoji, commission_rate)
            self.add_item(button)
    
    def create_callback(self, item_name: str, price: float, description: str, category: str, emoji: str, commission_rate: float):
        async def button_callback(interaction: discord.Interaction):
            user_id = interaction.user.id
            username = interaction.user.name
            balance = get_balance(user_id)
            
            if balance is None:
                await interaction.response.send_message("❌ 請先註冊錢包", ephemeral=True)
                return
            
            if balance < price:
                embed = discord.Embed(
                    title="❌ 餘額不足",
                    description=f"此商品需要 ${price}，你的餘額只有 ${balance:.2f}",
                    color=discord.Color.red()
                )
                embed.add_field(name="💡 提示", value="使用 /我要儲值 進行儲值", inline=False)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            confirm_embed = discord.Embed(
                title=f"{emoji} 確認購買",
                description=f"**{item_name}**\n{description}",
                color=discord.Color.blue()
            )
            confirm_embed.add_field(name="💰 價格", value=f"${price}", inline=True)
            confirm_embed.add_field(name="💳 你的餘額", value=f"${balance:.2f}", inline=True)
            confirm_embed.add_field(name="💵 購買後餘額", value=f"${balance - price:.2f}", inline=True)
            
            confirm_view = ConfirmPurchaseView(item_name, price, category, commission_rate)
            await interaction.response.send_message(embed=confirm_embed, view=confirm_view, ephemeral=True)
        
        return button_callback

class ConfirmPurchaseView(discord.ui.View):
    def __init__(self, item_name: str, price: float, category: str, commission_rate: float):
        super().__init__(timeout=60)
        self.item_name = item_name
        self.price = price
        self.category = category
        self.commission_rate = commission_rate
    
    @discord.ui.button(label="✅ 確認購買", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        username = interaction.user.name
        balance = get_balance(user_id)
        
        if balance < self.price:
            await interaction.response.send_message("❌ 餘額不足", ephemeral=True)
            return
        
        modal = PurchaseNoteModal(self.item_name, self.price, self.category, self.commission_rate)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="❌ 取消", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ 已取消",
            description="購買已取消",
            color=discord.Color.grey()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class PurchaseNoteModal(discord.ui.Modal, title="購買資訊"):
    def __init__(self, item_name: str, price: float, category: str, commission_rate: float):
        super().__init__()
        self.item_name = item_name
        self.price = price
        self.category = category
        self.commission_rate = commission_rate
    
    note = discord.ui.TextInput(
        label="備註說明（選填）",
        placeholder="請輸入遊戲ID、伺服器、聯絡方式等資訊",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        username = interaction.user.name
        note_text = self.note.value or "無"
        
        success = update_balance(user_id, -self.price, "消費", f"購買: {self.item_name}")
        
        if not success:
            await interaction.response.send_message("❌ 購買失敗，請稍後再試", ephemeral=True)
            return
        
        order_number = create_order(user_id, username, self.item_name, self.price, 1, self.commission_rate, note_text)
        
        if not order_number:
            update_balance(user_id, self.price, "退款", f"訂單創建失敗退款: {self.item_name}")
            await interaction.response.send_message("❌ 訂單創建失敗，已退款", ephemeral=True)
            return
        
        new_balance = get_balance(user_id)
        
        user_embed = discord.Embed(
            title="✅ 購買成功！",
            description=f"感謝你的購買！",
            color=discord.Color.green()
        )
        user_embed.add_field(name="📦 商品", value=self.item_name, inline=True)
        user_embed.add_field(name="💰 金額", value=f"${self.price}", inline=True)
        user_embed.add_field(name="📋 訂單號", value=order_number, inline=True)
        user_embed.add_field(name="💳 剩餘餘額", value=f"${new_balance:.2f}", inline=True)
        user_embed.add_field(name="📝 備註", value=note_text, inline=False)
        user_embed.set_footer(text="工作人員會盡快為你服務，請耐心等待")
        
        await interaction.response.send_message(embed=user_embed, ephemeral=True)
        
        await self.notify_staff(interaction, order_number, user_id, username, note_text)
    
    async def notify_staff(self, interaction: discord.Interaction, order_number: str, user_id: int, username: str, note: str):
        staff_earning = self.price * self.commission_rate
        platform_fee = self.price - staff_earning
        
        staff_embed = discord.Embed(
            title="🔔 新訂單通知",
            description=f"用戶 **{username}** 購買了商品",
            color=discord.Color.orange()
        )
        staff_embed.add_field(name="📋 訂單號", value=order_number, inline=True)
        staff_embed.add_field(name="👤 用戶", value=f"<@{user_id}>", inline=True)
        staff_embed.add_field(name="📦 商品", value=self.item_name, inline=True)
        staff_embed.add_field(name="💰 訂單金額", value=f"${self.price}", inline=True)
        staff_embed.add_field(name="💵 工作人員可得", value=f"${staff_earning:.2f} ({self.commission_rate*100}%)", inline=True)
        staff_embed.add_field(name="🏢 平台抽成", value=f"${platform_fee:.2f}", inline=True)
        staff_embed.add_field(name="📁 分類", value=self.category, inline=True)
        staff_embed.add_field(name="⏰ 時間", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        staff_embed.add_field(name="📝 用戶備註", value=note, inline=False)
        staff_embed.set_footer(text=f"使用 /完成訂單 {order_number} 標記完成並發放分潤")
        
        if NOTIFICATION_CHANNEL_ID:
            try:
                channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
                if channel:
                    role_id = STAFF_ROLES.get(self.category)
                    mention = f"<@&{role_id}>" if role_id else "@工作人員"
                    await channel.send(content=mention, embed=staff_embed)
                    return
            except Exception as e:
                print(f"發送通知失敗: {e}")
        
        try:
            await interaction.channel.send(embed=staff_embed)
        except:
            pass

@bot.tree.command(name="我的訂單", description="查看你的購買紀錄")
async def my_orders(interaction: discord.Interaction):
    user_id = interaction.user.id
    orders = get_user_orders(user_id, 10)
    
    if not orders:
        embed = discord.Embed(
            title="📦 我的訂單",
            description="你還沒有任何訂單",
            color=discord.Color.grey()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title="📦 我的訂單（最近10筆）",
        color=discord.Color.blue()
    )
    
    for order_number, item_name, total_price, status, created_at in orders:
        status_emoji = "✅" if status == "completed" else "⏳"
        status_text = "已完成" if status == "completed" else "處理中"
        
        embed.add_field(
            name=f"{status_emoji} {order_number}",
            value=f"商品: {item_name}\n金額: ${total_price}\n狀態: {status_text}\n時間: {created_at}",
            inline=False
        )
    
    embed.set_footer(text=f"用戶: {interaction.user.name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="我要儲值", description="申請儲值並查看轉帳資訊")
async def deposit_request(interaction: discord.Interaction):
    user_id = interaction.user.id
    username = interaction.user.name
    
    # 檢查黑名單
    if not await check_blacklist(interaction):
        return
    
    # 檢查儲值限制
    can_deposit, count, amount = security_manager.check_deposit_limit(user_id)
    
    if not can_deposit:
        is_new = security_manager._is_new_account(user_id)
        
        embed = discord.Embed(
            title="❌ 儲值限制",
            description="你今日已達儲值上限",
            color=discord.Color.red()
        )
        
        if is_new:
            embed.add_field(
                name="新帳號保護",
                value="新註冊帳號每天限制儲值 **1次**\n這是為了保護你的帳號安全",
                inline=False
            )
        else:
            embed.add_field(
                name="今日儲值記錄",
                value=f"次數: {count}/3\n金額: ${amount}/10000",
                inline=False
            )
        
        embed.add_field(
            name="💡 提示",
            value="請明天再試，或聯繫管理員",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # 記錄可疑操作
        security_manager.log_suspicious_action(
            user_id, username,
            'DEPOSIT_LIMIT_EXCEEDED',
            f"嘗試超限儲值（今日第{count+1}次）",
            ""
        )
        return
    
    balance = get_balance(user_id)
    
    if balance is None:
        embed = discord.Embed(
            title="❌ 尚未註冊",
            description="請先使用 /註冊 創建錢包",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="💳 儲值系統",
        description="請選擇儲值方案",
        color=discord.Color.gold()
    )
    
    for amount, points in DEPOSIT_PLANS.items():
        bonus = points - amount
        bonus_text = f" 🎁 **送 {bonus} 點**" if bonus > 0 else ""
        embed.add_field(
            name=f"方案 ${amount}",
            value=f"實際獲得: **{points} 點**{bonus_text}",
            inline=True
        )
    
    embed.add_field(
        name="\n📋 儲值流程",
        value=(
            "1️⃣ 選擇下方按鈕選擇方案\n"
            "2️⃣ 查看轉帳資訊並完成轉帳\n"
            "3️⃣ 上傳付款截圖\n"
            "4️⃣ 等待管理員審核\n"
            "5️⃣ 審核通過後自動入帳"
        ),
        inline=False
    )
    
    view = DepositView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class DepositView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        
        for amount, points in DEPOSIT_PLANS.items():
            button = discord.ui.Button(
                label=f"${amount} → {points}點",
                style=discord.ButtonStyle.primary,
                custom_id=f"deposit_{amount}"
            )
            button.callback = self.create_callback(amount, points)
            self.add_item(button)
    
    def create_callback(self, amount: int, points: int):
        async def button_callback(interaction: discord.Interaction):
            embed = discord.Embed(
                title="💰 轉帳資訊",
                description=f"請轉帳 **${amount}** 到以下帳戶",
                color=discord.Color.green()
            )
            
            embed.add_field(name="🏦 銀行名稱", value=BANK_INFO["銀行名稱"], inline=True)
            embed.add_field(name="🔢 銀行代碼", value=BANK_INFO["銀行代碼"], inline=True)
            embed.add_field(name="💳 帳號", value=BANK_INFO["帳號"], inline=False)
            embed.add_field(name="👤 戶名", value=BANK_INFO["戶名"], inline=False)
            embed.add_field(name="💵 轉帳金額", value=f"**${amount}**", inline=True)
            embed.add_field(name="🎁 獲得點數", value=f"**{points} 點**", inline=True)
            
            embed.add_field(
                name="\n📸 下一步",
                value="完成轉帳後，請點擊下方按鈕上傳付款截圖",
                inline=False
            )
            
            embed.set_footer(text="請在30分鐘內完成轉帳並上傳截圖")
            
            upload_view = UploadView(amount, points)
            await interaction.response.edit_message(embed=embed, view=upload_view)
        
        return button_callback

class UploadView(discord.ui.View):
    def __init__(self, amount: int, points: int):
        super().__init__(timeout=1800)
        self.amount = amount
        self.points = points
    
    @discord.ui.button(label="📸 上傳付款截圖", style=discord.ButtonStyle.success)
    async def upload_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ScreenshotModal(self.amount, self.points)
        await interaction.response.send_modal(modal)

class ScreenshotModal(discord.ui.Modal, title="上傳付款截圖"):
    def __init__(self, amount: int, points: int):
        super().__init__()
        self.amount = amount
        self.points = points
    
    screenshot_url = discord.ui.TextInput(
        label="付款截圖網址",
        placeholder="請上傳截圖到 Imgur 或其他圖床，然後貼上網址",
        style=discord.TextStyle.short,
        required=True,
        max_length=500
    )
    
    note = discord.ui.TextInput(
        label="備註（選填）",
        placeholder="可以填寫轉帳後五碼或其他備註",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=200
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        username = interaction.user.name
        screenshot = self.screenshot_url.value
        
        # 檢查盜刷
        if security_manager.check_stolen_card(user_id, username, self.amount):
            # 發送警告給管理員
            if NOTIFICATION_CHANNEL_ID:
                try:
                    channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
                    if channel:
                        alert_embed = discord.Embed(
                            title="🚨 疑似盜刷警報",
                            description=f"用戶 {username} (ID: {user_id}) 的儲值行為異常",
                            color=discord.Color.red()
                        )
                        alert_embed.add_field(name="儲值金額", value=f"${self.amount}", inline=True)
                        alert_embed.add_field(name="風險等級", value="🚨 高", inline=True)
                        alert_embed.add_field(
                            name="建議操作",
                            value="1. 仔細審核此儲值申請\n2. 查看用戶歷史紀錄\n3. 必要時聯繫用戶確認",
                            inline=False
                        )
                        await channel.send(content="@管理員", embed=alert_embed)
                except:
                    pass
        
        # 記錄儲值嘗試
        security_manager.record_deposit_attempt(user_id, self.amount)
        
        request_id = create_deposit_request(
            user_id, username, self.amount, self.points, screenshot
        )
        
        if request_id:
            user_embed = discord.Embed(
                title="✅ 儲值申請已提交",
                description="你的儲值申請已送出，請等待管理員審核",
                color=discord.Color.green()
            )
            user_embed.add_field(name="申請編號", value=f"#{request_id}", inline=True)
            user_embed.add_field(name="轉帳金額", value=f"${self.amount}", inline=True)
            user_embed.add_field(name="獲得點數", value=f"{self.points} 點", inline=True)
            user_embed.set_footer(text="通常在 1-24 小時內完成審核")
            
            await interaction.response.send_message(embed=user_embed, ephemeral=True)
        else:
            error_embed = discord.Embed(
                title="❌ 提交失敗",
                description="系統錯誤，請稍後再試或聯繫管理員",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="消費紀錄", description="查看你的消費紀錄")
async def transactions_cmd(interaction: discord.Interaction):
    user_id = interaction.user.id
    records = get_transactions(user_id, 10)
    
    if not records:
        embed = discord.Embed(
            title="📊 消費紀錄",
            description="目前沒有任何交易紀錄",
            color=discord.Color.grey()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title="📊 消費紀錄（最近10筆）",
        color=discord.Color.purple()
    )
    
    for amount, trans_type, description, created_at in records:
        sign = "+" if amount > 0 else ""
        embed.add_field(
            name=f"{trans_type} - {created_at}",
            value=f"{sign}${amount:.2f} - {description or '無說明'}",
            inline=False
        )
    
    embed.set_footer(text=f"用戶: {interaction.user.name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="儲值紀錄", description="查看你的儲值紀錄")
async def deposits_history(interaction: discord.Interaction):
    user_id = interaction.user.id
    records = get_deposits(user_id, 10)
    
    if not records:
        embed = discord.Embed(
            title="💳 儲值紀錄",
            description="目前沒有任何儲值紀錄",
            color=discord.Color.grey()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title="💳 儲值紀錄（最近10筆）",
        color=discord.Color.gold()
    )
    
    total = 0
    for amount, method, status, created_at in records:
        total += amount
        status_emoji = "✅" if status == "completed" else "⏳"
        embed.add_field(
            name=f"{status_emoji} {created_at}",
            value=f"金額: ${amount:.2f}\n方式: {method or '未指定'}",
            inline=False
        )
    
    embed.add_field(name="累計儲值", value=f"${total:.2f}", inline=False)
    embed.set_footer(text=f"用戶: {interaction.user.name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="我的收入", description="查看你的分潤收入")
async def my_earnings(interaction: discord.Interaction):
    staff_id = interaction.user.id
    
    total_earning, order_count = get_staff_total_earnings(staff_id)
    commissions = get_staff_commissions(staff_id, 10)
    
    embed = discord.Embed(
        title="💰 我的收入",
        description=f"工作人員: {interaction.user.name}",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="📊 總收入", value=f"${total_earning:.2f}", inline=True)
    embed.add_field(name="📦 完成訂單", value=f"{order_count} 筆", inline=True)
    embed.add_field(name="💵 平均單價", value=f"${(total_earning/order_count if order_count > 0 else 0):.2f}", inline=True)
    
    if commissions:
        embed.add_field(
            name="\n📋 最近10筆分潤",
            value="━━━━━━━━━━━━━━━━",
            inline=False
        )
        
        for order_num, order_amount, comm_rate, earning, platform_fee, created_at in commissions:
            embed.add_field(
                name=f"訂單 {order_num}",
                value=(
                    f"訂單金額: ${order_amount:.2f}\n"
                    f"你的收入: ${earning:.2f} ({comm_rate*100}%)\n"
                    f"平台抽成: ${platform_fee:.2f}\n"
                    f"時間: {created_at}"
                ),
                inline=False
            )
    else:
        embed.add_field(
            name="📋 分潤紀錄",
            value="尚無分潤紀錄",
            inline=False
        )
    
    embed.set_footer(text="完成更多訂單來增加收入！")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="本月收入", description="查看本月分潤收入")
async def monthly_earnings(interaction: discord.Interaction):
    staff_id = interaction.user.id
    now = datetime.now()
    
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    
    start_date = f"{now.year}-{now.month:02d}-01"
    if now.month == 12:
        end_date = f"{now.year+1}-01-01"
    else:
        end_date = f"{now.year}-{now.month+1:02d}-01"
    
    cursor.execute('''
        SELECT COUNT(*), SUM(staff_earning), SUM(order_amount)
        FROM commissions
        WHERE staff_id = ? AND created_at >= ? AND created_at < ?
    ''', (staff_id, start_date, end_date))
    
    result = cursor.fetchone()
    conn.close()
    
    if not result or result[0] == 0:
        embed = discord.Embed(
            title=f"📅 本月收入 ({now.year}/{now.month})",
            description="本月尚無收入紀錄",
            color=discord.Color.grey()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    order_count, total_earning, total_order_amount = result
    avg_earning = total_earning / order_count if order_count > 0 else 0
    
    embed = discord.Embed(
        title=f"📅 本月收入 ({now.year}/{now.month})",
        description=f"工作人員: {interaction.user.name}",
        color=discord.Color.green()
    )
    
    embed.add_field(name="💰 本月總收入", value=f"${total_earning:.2f}", inline=True)
    embed.add_field(name="📦 完成訂單", value=f"{order_count} 筆", inline=True)
    embed.add_field(name="💵 平均單價", value=f"${avg_earning:.2f}", inline=True)
    embed.add_field(name="📊 訂單總額", value=f"${total_order_amount:.2f}", inline=True)
    
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    days_passed = now.day
    days_left = days_in_month - days_passed
    
    embed.add_field(
        name="⏰ 本月進度",
        value=f"已過 {days_passed} 天，剩餘 {days_left} 天",
        inline=False
    )
    
    embed.set_footer(text="繼續努力，衝刺本月目標！")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="收入排行", description="查看工作人員收入排行榜")
async def earnings_leaderboard(interaction: discord.Interaction):
    rankings = get_top_earners(10)
    
    if not rankings:
        embed = discord.Embed(
            title="🏆 收入排行榜",
            description="目前沒有任何分潤紀錄",
            color=discord.Color.grey()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title="🏆 工作人員收入排行榜 (TOP 10)",
        description="根據累計收入排名",
        color=discord.Color.gold()
    )
    
    medals = ["🥇", "🥈", "🥉"]
    for i, (staff_name, staff_id, total_earning, order_count) in enumerate(rankings, 1):
        medal = medals[i-1] if i <= 3 else f"#{i}"
        avg_earning = total_earning / order_count if order_count > 0 else 0
        
        embed.add_field(
            name=f"{medal} {staff_name}",
            value=(
                f"💰 總收入: ${total_earning:.2f}\n"
                f"📦 完成訂單: {order_count} 筆\n"
                f"💵 平均單價: ${avg_earning:.2f}"
            ),
            inline=False
        )
    
    embed.set_footer(text="使用 /我的收入 查看個人詳細數據")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="查看訂單", description="[管理員] 查看所有待處理訂單")
async def view_orders(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    orders = get_pending_orders()
    
    if not orders:
        embed = discord.Embed(
            title="📦 待處理訂單",
            description="目前沒有待處理的訂單",
            color=discord.Color.grey()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📦 待處理訂單",
        description=f"共有 {len(orders)} 筆待處理訂單",
        color=discord.Color.orange()
    )
    
    for (order_number, user_id, username, item_name, item_price, quantity, 
         total_price, note, created_at, staff_earning, platform_fee) in orders:
        embed.add_field(
            name=f"訂單 {order_number}",
            value=(
                f"👤 用戶: <@{user_id}> ({username})\n"
                f"📦 商品: {item_name}\n"
                f"💰 金額: ${total_price}\n"
                f"💵 工作人員可得: ${staff_earning:.2f}\n"
                f"🏢 平台抽成: ${platform_fee:.2f}\n"
                f"📝 備註: {note}\n"
                f"⏰ 時間: {created_at}\n"
                f"━━━━━━━━━━━━━━━━"
            ),
            inline=False
        )
    
    embed.set_footer(text="使用 /完成訂單 [訂單號] [@工作人員] 標記完成並發放分潤")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="完成訂單", description="[管理員] 標記訂單為已完成並發放分潤")
@app_commands.describe(
    訂單號="要完成的訂單號",
    工作人員="負責此訂單的工作人員（可選，預設為執行者）"
)
async def complete_order_cmd(interaction: discord.Interaction, 訂單號: str, 工作人員: Optional[discord.Member] = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    order_info = get_order(訂單號)
    if not order_info:
        await interaction.response.send_message("❌ 找不到此訂單", ephemeral=True)
        return
    
    (order_number, user_id, username, item_name, item_price, quantity, total_price, 
     status, note, created_at, old_staff_id, commission_rate, staff_earning, 
     platform_fee, commission_paid) = order_info
    
    if status == 'completed':
        await interaction.response.send_message("⚠️ 此訂單已完成", ephemeral=True)
        return
    
    staff = 工作人員 if 工作人員 else interaction.user
    staff_id = staff.id
    staff_name = staff.name
    
    success, result = complete_order_with_commission(訂單號, staff_id, staff_name)
    
    if success:
        earnings_info = result
        
        embed = discord.Embed(
            title="✅ 訂單已完成",
            description="分潤已自動發放",
            color=discord.Color.green()
        )
        embed.add_field(name="📋 訂單號", value=訂單號, inline=True)
        embed.add_field(name="👤 客戶", value=f"<@{user_id}>", inline=True)
        embed.add_field(name="📦 商品", value=item_name, inline=True)
        embed.add_field(name="💰 訂單金額", value=f"${earnings_info['total_price']:.2f}", inline=True)
        embed.add_field(name="👨‍💼 工作人員", value=staff.mention, inline=True)
        embed.add_field(name="💵 工作人員收入", value=f"${earnings_info['staff_earning']:.2f} ({earnings_info['commission_rate']*100}%)", inline=True)
        embed.add_field(name="🏢 平台抽成", value=f"${earnings_info['platform_fee']:.2f} ({(1-earnings_info['commission_rate'])*100}%)", inline=True)
        embed.set_footer(text=f"完成者: {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)
        
        try:
            user = await bot.fetch_user(user_id)
            user_embed = discord.Embed(
                title="✅ 訂單已完成",
                description=f"你的訂單 {訂單號} 已經完成！",
                color=discord.Color.green()
            )
            user_embed.add_field(name="商品", value=item_name, inline=True)
            user_embed.add_field(name="金額", value=f"${total_price}", inline=True)
            user_embed.set_footer(text="感謝你的購買！")
            
            await user.send(embed=user_embed)
        except:
            pass
        
        if staff_id != interaction.user.id:
            try:
                staff_user = await bot.fetch_user(staff_id)
                staff_embed = discord.Embed(
                    title="💰 收入到帳",
                    description=f"訂單 {訂單號} 已完成",
                    color=discord.Color.gold()
                )
                staff_embed.add_field(name="你的收入", value=f"${earnings_info['staff_earning']:.2f}", inline=True)
                staff_embed.add_field(name="訂單金額", value=f"${earnings_info['total_price']:.2f}", inline=True)
                staff_embed.add_field(name="抽成比例", value=f"{earnings_info['commission_rate']*100}%", inline=True)
                staff_embed.set_footer(text="繼續加油！")
                
                await staff_user.send(embed=staff_embed)
            except:
                pass
    else:
        await interaction.response.send_message(f"❌ 處理失敗: {result}", ephemeral=True)

@bot.tree.command(name="平台統計", description="[管理員] 查看平台營收統計")
async def platform_stats(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    stats = get_platform_stats()
    now = datetime.now()
    monthly_stats = get_monthly_platform_stats(now.year, now.month)
    
    embed = discord.Embed(
        title="📊 平台統計",
        description="整體營運數據",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🏆 總體數據",
        value=(
            f"總訂單數: {stats['total_orders']} 筆\n"
            f"總營收: ${stats['total_revenue']:.2f}\n"
            f"已付出分潤: ${stats['total_paid_out']:.2f}\n"
            f"平台總收益: ${stats['total_platform_fee']:.2f}"
        ),
        inline=False
    )
    
    embed.add_field(
        name=f"📅 本月數據 ({now.year}/{now.month})",
        value=(
            f"本月訂單: {monthly_stats['monthly_orders']} 筆\n"
            f"本月營收: ${monthly_stats['monthly_revenue']:.2f}\n"
            f"本月分潤: ${monthly_stats['monthly_paid_out']:.2f}\n"
            f"本月平台收益: ${monthly_stats['monthly_platform_fee']:.2f}"
        ),
        inline=False
    )
    
    avg_order_value = stats['total_revenue'] / stats['total_orders'] if stats['total_orders'] > 0 else 0
    platform_margin = (stats['total_platform_fee'] / stats['total_revenue'] * 100) if stats['total_revenue'] > 0 else 0
    
    embed.add_field(
        name="📈 營運指標",
        value=(
            f"平均訂單金額: ${avg_order_value:.2f}\n"
            f"平台利潤率: {platform_margin:.1f}%"
        ),
        inline=False
    )
    
    embed.set_footer(text=f"統計時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="審核儲值", description="[管理員] 查看所有待審核的儲值申請")
async def review_deposits(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    requests = get_pending_requests()
    
    if not requests:
        embed = discord.Embed(
            title="📋 待審核儲值申請",
            description="目前沒有待審核的申請",
            color=discord.Color.grey()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📋 待審核儲值申請",
        description=f"共有 {len(requests)} 筆待審核",
        color=discord.Color.orange()
    )
    
    for req_id, user_id, username, amount, points, screenshot, created_at in requests:
        embed.add_field(
            name=f"申請 #{req_id} - {username}",
            value=(
                f"👤 用戶: <@{user_id}>\n"
                f"💰 金額: ${amount}\n"
                f"🎁 點數: {points} 點\n"
                f"📸 截圖: [查看]({screenshot})\n"
                f"⏰ 時間: {created_at}\n"
                f"━━━━━━━━━━━━━━━━"
            ),
            inline=False
        )
    
    embed.set_footer(text="使用 /通過儲值 或 /拒絕儲值 處理申請")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="通過儲值", description="[管理員] 通過儲值申請")
@app_commands.describe(申請編號="要通過的申請編號")
async def approve_deposit(interaction: discord.Interaction, 申請編號: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    request_info = get_deposit_request(申請編號)
    if not request_info:
        await interaction.response.send_message("❌ 找不到此申請", ephemeral=True)
        return
    
    req_id, user_id, username, amount, points, screenshot, status = request_info
    
    if status != 'pending':
        await interaction.response.send_message(f"❌ 此申請已處理（狀態: {status}）", ephemeral=True)
        return
    
    success, message = approve_deposit_request(申請編號, interaction.user.id)
    
    if success:
        admin_embed = discord.Embed(
            title="✅ 儲值已通過",
            color=discord.Color.green()
        )
        admin_embed.add_field(name="申請編號", value=f"#{申請編號}", inline=True)
        admin_embed.add_field(name="用戶", value=f"<@{user_id}>", inline=True)
        admin_embed.add_field(name="入帳點數", value=f"{points} 點", inline=True)
        admin_embed.set_footer(text=f"審核者: {interaction.user.name}")
        
        await interaction.response.send_message(embed=admin_embed)
        
        try:
            user = await bot.fetch_user(user_id)
            user_embed = discord.Embed(
                title="🎉 儲值審核通過！",
                description=f"你的儲值申請已通過，{points} 點已入帳",
                color=discord.Color.green()
            )
            user_embed.add_field(name="申請編號", value=f"#{申請編號}", inline=True)
            user_embed.add_field(name="轉帳金額", value=f"${amount}", inline=True)
            user_embed.add_field(name="入帳點數", value=f"{points} 點", inline=True)
            user_embed.set_footer(text="感謝你的儲值！")
            
            await user.send(embed=user_embed)
        except:
            pass
    else:
        await interaction.response.send_message(f"❌ 處理失敗: {message}", ephemeral=True)

@bot.tree.command(name="拒絕儲值", description="[管理員] 拒絕儲值申請")
@app_commands.describe(申請編號="要拒絕的申請編號", 原因="拒絕原因")
async def reject_deposit(interaction: discord.Interaction, 申請編號: int, 原因: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    request_info = get_deposit_request(申請編號)
    if not request_info:
        await interaction.response.send_message("❌ 找不到此申請", ephemeral=True)
        return
    
    req_id, user_id, username, amount, points, screenshot, status = request_info
    
    if status != 'pending':
        await interaction.response.send_message(f"❌ 此申請已處理（狀態: {status}）", ephemeral=True)
        return
    
    success = reject_deposit_request(申請編號, interaction.user.id, 原因)
    
    if success:
        admin_embed = discord.Embed(
            title="❌ 儲值已拒絕",
            color=discord.Color.red()
        )
        admin_embed.add_field(name="申請編號", value=f"#{申請編號}", inline=True)
        admin_embed.add_field(name="用戶", value=f"<@{user_id}>", inline=True)
        admin_embed.add_field(name="拒絕原因", value=原因, inline=False)
        admin_embed.set_footer(text=f"審核者: {interaction.user.name}")
        
        await interaction.response.send_message(embed=admin_embed)
        
        try:
            user = await bot.fetch_user(user_id)
            user_embed = discord.Embed(
                title="❌ 儲值申請被拒絕",
                description="你的儲值申請未通過審核",
                color=discord.Color.red()
            )
            user_embed.add_field(name="申請編號", value=f"#{申請編號}", inline=True)
            user_embed.add_field(name="拒絕原因", value=原因, inline=False)
            user_embed.set_footer(text="如有疑問請聯繫管理員")
            
            await user.send(embed=user_embed)
        except:
            pass
    else:
        await interaction.response.send_message("❌ 處理失敗", ephemeral=True)

@bot.tree.command(name="加錢", description="[管理員] 為用戶增加餘額")
@app_commands.describe(用戶="要增加餘額的用戶", 金額="要增加的金額", 說明="說明原因")
async def add_money(interaction: discord.Interaction, 用戶: discord.Member, 金額: float, 說明: str = "管理員加錢"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額必須大於 0", ephemeral=True)
        return
    
    balance = get_balance(用戶.id)
    if balance is None:
        await interaction.response.send_message(f"❌ {用戶.mention} 尚未註冊錢包", ephemeral=True)
        return
    
    if update_balance(用戶.id, 金額, "儲值", 說明):
        new_balance = get_balance(用戶.id)
        embed = discord.Embed(
            title="✅ 加錢成功",
            color=discord.Color.green()
        )
        embed.add_field(name="用戶", value=用戶.mention, inline=True)
        embed.add_field(name="增加金額", value=f"+${金額:.2f}", inline=True)
        embed.add_field(name="新餘額", value=f"${new_balance:.2f}", inline=True)
        embed.add_field(name="說明", value=說明, inline=False)
        embed.set_footer(text=f"操作者: {interaction.user.name}")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ 操作失敗", ephemeral=True)

@bot.tree.command(name="扣錢", description="[管理員] 扣除用戶餘額")
@app_commands.describe(用戶="要扣除餘額的用戶", 金額="要扣除的金額", 說明="說明原因")
async def deduct_money(interaction: discord.Interaction, 用戶: discord.Member, 金額: float, 說明: str = "管理員扣錢"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    if 金額 <= 0:
        await interaction.response.send_message("❌ 金額必須大於 0", ephemeral=True)
        return
    
    balance = get_balance(用戶.id)
    if balance is None:
        await interaction.response.send_message(f"❌ {用戶.mention} 尚未註冊錢包", ephemeral=True)
        return
    
    if update_balance(用戶.id, -金額, "消費", 說明):
        new_balance = get_balance(用戶.id)
        embed = discord.Embed(
            title="✅ 扣錢成功",
            color=discord.Color.orange()
        )
        embed.add_field(name="用戶", value=用戶.mention, inline=True)
        embed.add_field(name="扣除金額", value=f"-${金額:.2f}", inline=True)
        embed.add_field(name="新餘額", value=f"${new_balance:.2f}", inline=True)
        embed.add_field(name="說明", value=說明, inline=False)
        embed.set_footer(text=f"操作者: {interaction.user.name}")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ 操作失敗", ephemeral=True)

@bot.tree.command(name="清零", description="[管理員] 將用戶餘額清零")
@app_commands.describe(用戶="要清零的用戶")
async def reset_balance(interaction: discord.Interaction, 用戶: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    balance = get_balance(用戶.id)
    if balance is None:
        await interaction.response.send_message(f"❌ {用戶.mention} 尚未註冊錢包", ephemeral=True)
        return
    
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE wallets SET balance = 0 WHERE user_id = ?', (用戶.id,))
    cursor.execute('''
        INSERT INTO transactions (user_id, amount, type, description)
        VALUES (?, ?, ?, ?)
    ''', (用戶.id, -balance, "系統", "管理員清零"))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(
        title="✅ 清零成功",
        description=f"{用戶.mention} 的餘額已清零",
        color=discord.Color.red()
    )
    embed.add_field(name="原餘額", value=f"${balance:.2f}", inline=True)
    embed.add_field(name="新餘額", value="$0.00", inline=True)
    embed.set_footer(text=f"操作者: {interaction.user.name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="全服餘額排行", description="查看全服務器餘額排行榜")
async def leaderboard(interaction: discord.Interaction):
    rankings = get_leaderboard(10)
    
    if not rankings:
        embed = discord.Embed(
            title="🏆 全服餘額排行榜",
            description="目前沒有任何用戶",
            color=discord.Color.grey()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title="🏆 全服餘額排行榜 (TOP 10)",
        color=discord.Color.gold()
    )
    
    medals = ["🥇", "🥈", "🥉"]
    for i, (username, balance) in enumerate(rankings, 1):
        medal = medals[i-1] if i <= 3 else f"#{i}"
        embed.add_field(
            name=f"{medal} {username}",
            value=f"${balance:.2f}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

# ============ 安全管理指令 ============

@bot.tree.command(name="封禁用戶", description="[管理員] 將用戶加入黑名單")
@app_commands.describe(
    用戶="要封禁的用戶",
    原因="封禁原因",
    天數="封禁天數（留空=永久）",
    備註="備註說明（選填）"
)
async def ban_user(interaction: discord.Interaction, 用戶: discord.Member, 
                   原因: str, 天數: Optional[int] = None, 備註: str = ""):
    """封禁用戶指令"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    success = security_manager.add_to_blacklist(
        用戶.id, 用戶.name, 原因, interaction.user.id, 天數, 備註
    )
    
    if success:
        duration_text = f"{天數} 天" if 天數 else "永久"
        
        embed = discord.Embed(
            title="✅ 封禁成功",
            description=f"{用戶.mention} 已被加入黑名單",
            color=discord.Color.red()
        )
        embed.add_field(name="封禁原因", value=原因, inline=False)
        embed.add_field(name="封禁期限", value=duration_text, inline=True)
        embed.add_field(name="執行者", value=interaction.user.mention, inline=True)
        if 備註:
            embed.add_field(name="備註", value=備註, inline=False)
        
        await interaction.response.send_message(embed=embed)
        
        # 通知被封禁的用戶
        try:
            user_embed = discord.Embed(
                title="🚫 帳號已被封禁",
                description=f"你的帳號已被封禁 {duration_text}",
                color=discord.Color.red()
            )
            user_embed.add_field(name="封禁原因", value=原因, inline=False)
            user_embed.add_field(name="申訴方式", value="請聯繫伺服器管理員", inline=False)
            
            await 用戶.send(embed=user_embed)
        except:
            pass
    else:
        await interaction.response.send_message("❌ 封禁失敗", ephemeral=True)

@bot.tree.command(name="解封用戶", description="[管理員] 將用戶移出黑名單")
@app_commands.describe(用戶="要解封的用戶")
async def unban_user(interaction: discord.Interaction, 用戶: discord.Member):
    """解封用戶指令"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    success = security_manager.remove_from_blacklist(用戶.id)
    
    if success:
        embed = discord.Embed(
            title="✅ 解封成功",
            description=f"{用戶.mention} 已被移出黑名單",
            color=discord.Color.green()
        )
        embed.add_field(name="執行者", value=interaction.user.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
        
        # 通知被解封的用戶
        try:
            user_embed = discord.Embed(
                title="✅ 帳號已解封",
                description="你的帳號已被解除封禁，現在可以正常使用了",
                color=discord.Color.green()
            )
            await 用戶.send(embed=user_embed)
        except:
            pass
    else:
        await interaction.response.send_message("❌ 解封失敗或該用戶不在黑名單中", ephemeral=True)

@bot.tree.command(name="檢查用戶", description="[管理員] 檢查用戶狀態和可疑操作")
@app_commands.describe(用戶="要檢查的用戶")
async def check_user_security(interaction: discord.Interaction, 用戶: discord.Member):
    """檢查用戶安全狀態"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    # 檢查黑名單
    is_banned, ban_reason = security_manager.is_blacklisted(用戶.id)
    
    # 檢查可疑操作
    warnings = security_manager.detect_suspicious_activity(用戶.id, 用戶.name)
    
    # 檢查儲值限制
    can_deposit, deposit_count, deposit_amount = security_manager.check_deposit_limit(用戶.id)
    
    # 檢查是否為新帳號
    is_new = security_manager._is_new_account(用戶.id)
    
    embed = discord.Embed(
        title=f"🔍 用戶安全檢查 - {用戶.name}",
        color=discord.Color.red() if (is_banned or warnings) else discord.Color.green()
    )
    
    # 基本資訊
    embed.add_field(name="用戶ID", value=用戶.id, inline=True)
    embed.add_field(name="帳號類型", value="🆕 新帳號" if is_new else "✅ 正常帳號", inline=True)
    embed.add_field(name="黑名單狀態", value="🚫 已封禁" if is_banned else "✅ 正常", inline=True)
    
    if is_banned:
        embed.add_field(name="封禁原因", value=ban_reason, inline=False)
    
    # 今日儲值
    embed.add_field(name="今日儲值次數", value=f"{deposit_count} 次", inline=True)
    embed.add_field(name="今日儲值金額", value=f"${deposit_amount:.2f}", inline=True)
    embed.add_field(name="可否儲值", value="✅ 是" if can_deposit else "❌ 否", inline=True)
    
    # 可疑操作
    if warnings:
        embed.add_field(
            name="⚠️ 可疑操作",
            value="\n".join([f"• {w}" for w in warnings]),
            inline=False
        )
        embed.color = discord.Color.orange()
    else:
        embed.add_field(name="可疑操作", value="✅ 無異常", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="查看黑名單", description="[管理員] 查看所有黑名單用戶")
async def view_blacklist(interaction: discord.Interaction):
    """查看黑名單指令"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    blacklist = security_manager.get_blacklist(20)
    
    if not blacklist:
        embed = discord.Embed(
            title="📋 黑名單",
            description="目前沒有被封禁的用戶",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📋 黑名單列表",
        description=f"共 {len(blacklist)} 位用戶被封禁",
        color=discord.Color.red()
    )
    
    for i, user in enumerate(blacklist[:10], 1):  # 只顯示前10個
        embed.add_field(
            name=f"{i}. {user['用戶名']} (ID: {user['用戶ID']})",
            value=(
                f"原因: {user['封禁原因']}\n"
                f"時間: {user['封禁時間']}\n"
                f"期限: {user['解封時間']}"
            ),
            inline=False
        )
    
    if len(blacklist) > 10:
        embed.set_footer(text=f"僅顯示前10位，共 {len(blacklist)} 位")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="查看風險事件", description="[管理員] 查看未處理的風險事件")
async def view_risk_events(interaction: discord.Interaction):
    """查看風險事件指令"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    events = security_manager.get_risk_events(handled=False, limit=20)
    
    if not events:
        embed = discord.Embed(
            title="✅ 風險事件",
            description="目前沒有未處理的風險事件",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="⚠️ 未處理風險事件",
        description=f"共 {len(events)} 件待處理",
        color=discord.Color.orange()
    )
    
    for i, event in enumerate(events[:10], 1):
        severity_emoji = {
            'LOW': '🟢',
            'MEDIUM': '🟡',
            'HIGH': '🟠',
            'CRITICAL': '🔴'
        }.get(event['嚴重程度'], '⚪')
        
        embed.add_field(
            name=f"{i}. {event['用戶名']} (ID: {event['用戶ID']})",
            value=(
                f"{severity_emoji} {event['嚴重程度']}\n"
                f"類型: {event['事件類型']}\n"
                f"描述: {event['描述']}\n"
                f"時間: {event['發生時間']}"
            ),
            inline=False
        )
    
    if len(events) > 10:
        embed.set_footer(text=f"僅顯示前10件，共 {len(events)} 件")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="自動風控", description="[管理員] 執行自動風險處理")
async def auto_risk_control(interaction: discord.Interaction):
    """自動風控指令"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    results = security_manager.auto_handle_risks()
    
    embed = discord.Embed(
        title="🤖 自動風控執行完成",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="檢測事件", value=f"{results['events_logged']} 件", inline=True)
    embed.add_field(name="自動封禁", value=f"{len(results['auto_banned'])} 人", inline=True)
    
    if results['auto_banned']:
        ban_list = "\n".join([
            f"• {b['username']} (ID: {b['user_id']})\n  原因: {b['reason']}"
            for b in results['auto_banned'][:5]
        ])
        embed.add_field(name="封禁列表", value=ban_list, inline=False)
    
    embed.set_footer(text=f"執行者: {interaction.user.name}")
    
    await interaction.followup.send(embed=embed, ephemeral=True)

if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("錯誤: 請設置 DISCORD_TOKEN 環境變數")
    else:
        bot.run(TOKEN)