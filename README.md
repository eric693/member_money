# Discord 會員餘額系統機器人 💰

一個功能完整的 Discord 機器人，用於管理會員帳戶和餘額系統。

## 功能特色 ✨

### 用戶功能
- `/註冊` - 創建個人錢包
- `/我的餘額` - 查詢當前餘額
- `/消費紀錄` - 查看最近 10 筆交易紀錄
- `/儲值紀錄` - 查看最近 10 筆儲值紀錄

### 管理員功能
- `/加錢 @用戶 金額 說明` - 為用戶增加餘額
- `/扣錢 @用戶 金額 說明` - 扣除用戶餘額
- `/清零 @用戶` - 將用戶餘額清零
- `/全服餘額排行` - 查看餘額排行榜 (TOP 10)

## 系統架構 🏗️

- **資料庫**: SQLite3
- **框架**: discord.py
- **語言**: Python 3.8+

### 資料庫結構

1. **wallets** - 用戶錢包
   - user_id (主鍵)
   - username
   - balance
   - created_at

2. **transactions** - 交易紀錄
   - id (自增主鍵)
   - user_id
   - amount
   - type (儲值/消費/系統)
   - description
   - created_at

3. **deposits** - 儲值紀錄
   - id (自增主鍵)
   - user_id
   - amount
   - method
   - status
   - created_at

## 快速開始 🚀

### 1. 創建 Discord Bot

1. 前往 [Discord Developer Portal](https://discord.com/developers/applications)
2. 點擊 "New Application"
3. 進入 "Bot" 頁面，點擊 "Add Bot"
4. 複製 Bot Token
5. 啟用以下 Intents:
   - Presence Intent
   - Server Members Intent
   - Message Content Intent
6. 前往 "OAuth2" > "URL Generator"
   - Scopes: 選擇 `bot` 和 `applications.commands`
   - Bot Permissions: 選擇 `Administrator` 或所需權限
   - 複製生成的 URL 並邀請 Bot 到你的伺服器

### 2. 本地測試

```bash
# 克隆專案
git clone https://github.com/your-username/discord-wallet-bot.git
cd discord-wallet-bot

# 安裝依賴
pip install -r requirements.txt

# 設置環境變數
cp .env.example .env
# 編輯 .env 文件，填入你的 DISCORD_TOKEN

# 運行 Bot
python discord_wallet_bot.py
```

## 部署到 Railway 🚂

### 方法一: 通過 GitHub 自動部署

1. **推送代碼到 GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/你的用戶名/你的專案名.git
   git push -u origin main
   ```

2. **在 Railway 創建專案**
   - 前往 [Railway.app](https://railway.app/)
   - 點擊 "New Project"
   - 選擇 "Deploy from GitHub repo"
   - 選擇你的 Discord Bot 專案

3. **設置環境變數**
   - 在 Railway 專案中，點擊 "Variables"
   - 添加 `DISCORD_TOKEN` 變數，填入你的 Bot Token

4. **自動部署**
   - Railway 會自動偵測 `requirements.txt`
   - Bot 會自動啟動並運行

### 方法二: 使用 Railway CLI

```bash
# 安裝 Railway CLI
npm i -g @railway/cli

# 登入
railway login

# 初始化專案
railway init

# 添加環境變數
railway variables set DISCORD_TOKEN=你的token

# 部署
railway up
```

## Railway 設置文件

創建 `railway.json` (可選):

```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python discord_wallet_bot.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

## 資料持久化 💾

Railway 提供的臨時檔案系統會在重新部署時清空。如需永久保存資料：

### 選項 1: 使用 Railway PostgreSQL (推薦)
可以修改代碼使用 PostgreSQL 替代 SQLite

### 選項 2: 使用 Railway Volumes
```bash
railway volume create
railway volume attach
```

## 使用範例 📝

### 用戶註冊與查詢
```
用戶: /註冊
Bot: ✅ 註冊成功！歡迎 UserName！你的個人錢包已創建

用戶: /我的餘額
Bot: 💰 當前餘額: $0.00
```

### 管理員操作
```
管理員: /加錢 @User123 1000 首次儲值
Bot: ✅ 加錢成功
     用戶: @User123
     增加金額: +$1000.00
     新餘額: $1000.00
```

## 安全建議 🔒

1. **絕對不要將 Bot Token 提交到 GitHub**
2. 使用環境變數儲存敏感資訊
3. 定期備份資料庫
4. 限制管理員指令權限
5. 監控異常交易

## 商業模式 💡

這個系統的核心優勢：
- ✅ 客戶儲值後，真實貨幣已進入你的口袋
- ✅ Bot 內的餘額只是「系統內數字」
- ✅ 你可以提供各種服務讓用戶消費餘額
- ✅ 完整的交易紀錄追蹤

### 盈利方式
1. 用戶購買點數/餘額
2. 提供付費服務消耗餘額
3. 會員制度
4. 虛擬商品販售

## 常見問題 ❓

**Q: Bot 離線怎麼辦？**
A: Railway 提供 24/7 運行，如果 Bot 崩潰會自動重啟。

**Q: 資料會遺失嗎？**
A: 使用 SQLite 時，重新部署可能會清空資料。建議使用 Railway Volumes 或 PostgreSQL。

**Q: 可以自訂指令嗎？**
A: 可以！修改代碼中的 `@bot.tree.command()` 裝飾器即可。

**Q: 如何限制只有管理員使用某些指令？**
A: 已內建管理員權限檢查: `interaction.user.guild_permissions.administrator`

## 授權 📄

MIT License

## 支援 💬

如有問題，請在 GitHub 開 Issue 或聯絡開發者。

---

**⚠️ 重要提醒**
- 此系統僅供學習和合法用途
- 請遵守當地法律法規
- 妥善保管 Bot Token 和用戶資料