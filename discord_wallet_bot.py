import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from datetime import datetime
import os
from typing import Optional
from dotenv import load_dotenv

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

# 初始化 Bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

# 資料庫初始化
def init_database():
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    
    # 用戶錢包表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallets (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            balance REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 消費紀錄表
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
    
    # 儲值紀錄表（已完成的儲值）
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
    
    # 儲值申請表（待審核的儲值）
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
    
    conn.commit()
    conn.close()

# 資料庫操作函數
def create_wallet(user_id: int, username: str):
    """創建用戶錢包"""
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
    """獲取用戶餘額"""
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM wallets WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def update_balance(user_id: int, amount: float, transaction_type: str, description: str = ""):
    """更新用戶餘額並記錄交易"""
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    
    try:
        # 更新餘額
        cursor.execute('UPDATE wallets SET balance = balance + ? WHERE user_id = ?', 
                      (amount, user_id))
        
        # 記錄交易
        cursor.execute('''
            INSERT INTO transactions (user_id, amount, type, description)
            VALUES (?, ?, ?, ?)
        ''', (user_id, amount, transaction_type, description))
        
        # 如果是儲值，記錄到儲值表
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

def create_deposit_request(user_id: int, username: str, amount: float, bonus_points: float, screenshot_url: str):
    """創建儲值申請"""
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
    """獲取所有待審核的儲值申請"""
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
    """獲取特定儲值申請"""
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
    """批准儲值申請"""
    conn = sqlite3.connect('wallet.db')
    cursor = conn.cursor()
    try:
        # 獲取申請資訊
        cursor.execute('SELECT user_id, amount, bonus_points FROM deposit_requests WHERE id = ?', (request_id,))
        result = cursor.fetchone()
        if not result:
            return False, "找不到此申請"
        
        user_id, amount, bonus_points = result
        
        # 更新申請狀態
        cursor.execute('''
            UPDATE deposit_requests 
            SET status = 'approved', processed_at = CURRENT_TIMESTAMP, processed_by = ?
            WHERE id = ?
        ''', (admin_id, request_id))
        
        # 增加用戶餘額
        cursor.execute('UPDATE wallets SET balance = balance + ? WHERE user_id = ?', 
                      (bonus_points, user_id))
        
        # 記錄交易
        cursor.execute('''
            INSERT INTO transactions (user_id, amount, type, description)
            VALUES (?, ?, ?, ?)
        ''', (user_id, bonus_points, "儲值", f"台灣轉帳 ${amount} → {bonus_points} 點"))
        
        # 記錄到儲值表
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
    """拒絕儲值申請"""
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
    """獲取用戶交易紀錄"""
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
    """獲取用戶儲值紀錄"""
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
    """獲取餘額排行榜"""
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

# Bot 事件
@bot.event
async def on_ready():
    init_database()
    print(f'{bot.user} 已上線！')
    try:
        synced = await bot.tree.sync()
        print(f'同步了 {len(synced)} 個指令')
    except Exception as e:
        print(f'同步指令失敗: {e}')

# ============ 用戶指令 ============

@bot.tree.command(name="註冊", description="創建你的個人錢包")
async def register(interaction: discord.Interaction):
    """註冊指令"""
    user_id = interaction.user.id
    username = interaction.user.name
    
    if create_wallet(user_id, username):
        embed = discord.Embed(
            title="✅ 註冊成功！",
            description=f"歡迎 {username}！\n你的個人錢包已創建",
            color=discord.Color.green()
        )
        embed.add_field(name="初始餘額", value="$0", inline=False)
        embed.set_footer(text="使用 /我的餘額 查看餘額 | /我要儲值 開始儲值")
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
    """查詢餘額指令"""
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

@bot.tree.command(name="我要儲值", description="申請儲值並查看轉帳資訊")
async def deposit_request(interaction: discord.Interaction):
    """儲值申請指令"""
    user_id = interaction.user.id
    balance = get_balance(user_id)
    
    if balance is None:
        embed = discord.Embed(
            title="❌ 尚未註冊",
            description="請先使用 /註冊 創建錢包",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # 創建儲值方案選單
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
    
    # 創建按鈕
    view = DepositView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# 儲值選擇按鈕視圖
class DepositView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)  # 5分鐘超時
        
        # 為每個儲值方案創建按鈕
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
            # 顯示轉帳資訊
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
            
            # 創建上傳截圖按鈕
            upload_view = UploadView(amount, points)
            await interaction.response.edit_message(embed=embed, view=upload_view)
        
        return button_callback

# 上傳截圖視圖
class UploadView(discord.ui.View):
    def __init__(self, amount: int, points: int):
        super().__init__(timeout=1800)  # 30分鐘超時
        self.amount = amount
        self.points = points
    
    @discord.ui.button(label="📸 上傳付款截圖", style=discord.ButtonStyle.success)
    async def upload_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 創建模態對話框請求截圖
        modal = ScreenshotModal(self.amount, self.points)
        await interaction.response.send_modal(modal)

# 截圖上傳模態框
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
        
        # 創建儲值申請
        request_id = create_deposit_request(
            user_id, username, self.amount, self.points, screenshot
        )
        
        if request_id:
            # 通知用戶
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
            
            # 通知管理員頻道（可選）
            # 找到有管理員權限的頻道發送通知
            for channel in interaction.guild.text_channels:
                if channel.permissions_for(interaction.guild.me).send_messages:
                    admin_embed = discord.Embed(
                        title="🔔 新的儲值申請",
                        description=f"用戶 {username} 提交了儲值申請",
                        color=discord.Color.orange()
                    )
                    admin_embed.add_field(name="申請編號", value=f"#{request_id}", inline=True)
                    admin_embed.add_field(name="用戶", value=f"<@{user_id}>", inline=True)
                    admin_embed.add_field(name="金額", value=f"${self.amount}", inline=True)
                    admin_embed.add_field(name="點數", value=f"{self.points} 點", inline=True)
                    admin_embed.add_field(name="截圖", value=screenshot, inline=False)
                    
                    if self.note.value:
                        admin_embed.add_field(name="備註", value=self.note.value, inline=False)
                    
                    admin_embed.set_footer(text="使用 /審核儲值 查看所有待審核申請")
                    
                    try:
                        await channel.send(embed=admin_embed)
                        break  # 只發送到第一個可用頻道
                    except:
                        continue
        else:
            error_embed = discord.Embed(
                title="❌ 提交失敗",
                description="系統錯誤，請稍後再試或聯繫管理員",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="消費紀錄", description="查看你的消費紀錄")
async def transactions(interaction: discord.Interaction):
    """消費紀錄指令"""
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
    """儲值紀錄指令"""
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

# ============ 管理員指令 ============

@bot.tree.command(name="審核儲值", description="[管理員] 查看所有待審核的儲值申請")
async def review_deposits(interaction: discord.Interaction):
    """審核儲值指令"""
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
    """通過儲值指令"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    # 獲取申請資訊
    request_info = get_deposit_request(申請編號)
    if not request_info:
        await interaction.response.send_message("❌ 找不到此申請", ephemeral=True)
        return
    
    req_id, user_id, username, amount, points, screenshot, status = request_info
    
    if status != 'pending':
        await interaction.response.send_message(f"❌ 此申請已處理（狀態: {status}）", ephemeral=True)
        return
    
    # 批准申請
    success, message = approve_deposit_request(申請編號, interaction.user.id)
    
    if success:
        # 通知管理員
        admin_embed = discord.Embed(
            title="✅ 儲值已通過",
            color=discord.Color.green()
        )
        admin_embed.add_field(name="申請編號", value=f"#{申請編號}", inline=True)
        admin_embed.add_field(name="用戶", value=f"<@{user_id}>", inline=True)
        admin_embed.add_field(name="入帳點數", value=f"{points} 點", inline=True)
        admin_embed.set_footer(text=f"審核者: {interaction.user.name}")
        
        await interaction.response.send_message(embed=admin_embed)
        
        # 通知用戶（嘗試發送私訊）
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
            pass  # 如果無法發送私訊就忽略
    else:
        await interaction.response.send_message(f"❌ 處理失敗: {message}", ephemeral=True)

@bot.tree.command(name="拒絕儲值", description="[管理員] 拒絕儲值申請")
@app_commands.describe(申請編號="要拒絕的申請編號", 原因="拒絕原因")
async def reject_deposit(interaction: discord.Interaction, 申請編號: int, 原因: str):
    """拒絕儲值指令"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 此指令僅限管理員使用", ephemeral=True)
        return
    
    # 獲取申請資訊
    request_info = get_deposit_request(申請編號)
    if not request_info:
        await interaction.response.send_message("❌ 找不到此申請", ephemeral=True)
        return
    
    req_id, user_id, username, amount, points, screenshot, status = request_info
    
    if status != 'pending':
        await interaction.response.send_message(f"❌ 此申請已處理（狀態: {status}）", ephemeral=True)
        return
    
    # 拒絕申請
    success = reject_deposit_request(申請編號, interaction.user.id, 原因)
    
    if success:
        # 通知管理員
        admin_embed = discord.Embed(
            title="❌ 儲值已拒絕",
            color=discord.Color.red()
        )
        admin_embed.add_field(name="申請編號", value=f"#{申請編號}", inline=True)
        admin_embed.add_field(name="用戶", value=f"<@{user_id}>", inline=True)
        admin_embed.add_field(name="拒絕原因", value=原因, inline=False)
        admin_embed.set_footer(text=f"審核者: {interaction.user.name}")
        
        await interaction.response.send_message(embed=admin_embed)
        
        # 通知用戶
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
    """管理員加錢指令"""
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
    """管理員扣錢指令"""
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
    """管理員清零指令"""
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
    """排行榜指令"""
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

# 啟動 Bot
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("錯誤: 請設置 DISCORD_TOKEN 環境變數")
    else:
        bot.run(TOKEN)