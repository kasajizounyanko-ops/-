import discord
from discord import app_commands
import json
import os
import time

CONFIG_FILE = "config.json"
EXECUTION_LOG_FILE = "execution_log.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"log_channel_id": None, "allowed_user_ids": []}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_items():
    try:
        with open("Items.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "menu1": [
                {"name": "XP9999999"},
                {"name": "NP9999"},
                {"name": "猫缶50000"},
                {"name": "バトルアイテム全種999"},
                {"name": "ネコビタン全種999"},
                {"name": "城塞材全種999"},
                {"name": "キャッツアイ全999"},
                {"name": "マタタビ全種99"},
                {"name": "木箱全種09"},
                {"name": "にゃんこチケ&レアチケ999"},
                {"name": "プラチナ29"},
                {"name": "レジェチケ"},
                {"name": "イベチケ&福チケ999"},
                {"name": "リーダーシップ"},
                {"name": "地底迷宮メダル全種999"},
            ],
            "menu2": [
                {"name": "全キャラ開放"},
                {"name": "エラーキャラ削除"},
                {"name": "全キャラLvMAX"},
                {"name": "全キャラ最高形態"},
                {"name": "全キャラ本能全開放"},
                {"name": "メインステージ全クリア"},
                {"name": "本能全開放"},
                {"name": "IDレジェンドをクリア"},
                {"name": "貴レジェンドをクリア"},
                {"name": "メインゾンビステージ全クリア"},
                {"name": "IDレジェンド全クリア"},
                {"name": "真レジェンド全クリア"},
                {"name": "ガマトトLvMAX"},
                {"name": "ガマトト初手全レジェンド化"},
                {"name": "にゃんこ神社LvMAX"},
                {"name": "にゃんこ神社全開放"},
                {"name": "プレイ時間カウスト"},
                {"name": "編成スロット救急拡張"},
                {"name": "ユーザーランク補助受取"},
                {"name": "金お宝"},
                {"name": "オートセーブ全解放LvMAX"},
                {"name": "ゴールド会員化"},
                {"name": "ガマトト助手追加"},
            ],
            # アカウント系特殊メニュー（転送コード不要）
            "menu_account": [
                {"name": "新規アカウント作成",             "special": True},
                {"name": "リスタートパックアカウント作成", "special": True},
            ]
        }

def save_items(data):
    with open("Items.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def is_allowed():
    async def predicate(interaction: discord.Interaction) -> bool:
        if await interaction.client.is_owner(interaction.user):
            return True
        config = load_config()
        allowed_ids = config.get("allowed_user_ids", [])
        if interaction.user.id not in allowed_ids:
            await interaction.response.send_message("🚫 あなたはこのBotの機能を利用する権限がありません。", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

def load_orders():
    try:
        with open("orders.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_orders(data):
    with open("orders.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ===== 実行ログ =====
def load_execution_log():
    if os.path.exists(EXECUTION_LOG_FILE):
        with open(EXECUTION_LOG_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save_execution_log_entry(user, action: str, detail: str = ""):
    logs = load_execution_log()
    logs.append({
        "timestamp": int(time.time()),
        "user_id": str(user.id),
        "user_name": str(user.name),
        "user_display": str(user.display_name),
        "action": action,
        "detail": detail
    })
    if len(logs) > 500:
        logs = logs[-500:]
    with open(EXECUTION_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4, ensure_ascii=False)

async def setup(bot):
    pass
