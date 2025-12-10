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
    
    # 儲值紀錄表
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

# 用戶指令
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
        embed.set_footer(text="使用 /我的餘額 查看餘額")
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

# 管理員指令
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