import discord
from discord import app_commands, ui
from discord.ext import commands
import json
import os
import time
from Cogs.utils import load_items, is_allowed, load_execution_log
from Cogs.nyanko_editor import CloudEditor

ADMIN_USERS_FILE = "admin_users.json"


def load_admin_users():
    if os.path.exists(ADMIN_USERS_FILE):
        with open(ADMIN_USERS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []


def save_admin_users(data):
    with open(ADMIN_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


class TestProductSelectDropdown(ui.Select):
    def __init__(self, items, all_items, user, guild, bot, offset=0, label_suffix=""):
        self.all_items = all_items
        self.user = user
        self.guild = guild
        self.bot = bot
        self.offset = offset

        options = [
            discord.SelectOption(label=item['name'], value=str(offset + i))
            for i, item in enumerate(items)
        ]

        super().__init__(
            placeholder=f"購入したいアイテムを選択してください{label_suffix}",
            min_values=1,
            max_values=min(25, len(items)),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_items = []
        for idx in self.values:
            item = self.all_items[int(idx)]
            selected_items.append({'name': item['name'], 'quantity': 1, 'subtotal': 0})

        embed = discord.Embed(title="注文確認", color=0xFFB700)
        embed.add_field(
            name="選択アイテム",
            value="\n".join([f"{item['name']} × {item['quantity']}個" for item in selected_items]),
            inline=False
        )

        view = ui.View()

        async def confirm_cb(it):
            await it.response.send_modal(TestModal(selected_items, self.user, self.guild, self.bot))

        btn = ui.Button(label="テスト実行", style=discord.ButtonStyle.success)
        btn.callback = confirm_cb
        view.add_item(btn)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class TestVendingView(ui.View):
    def __init__(self, all_items, user, guild, bot):
        super().__init__()
        mid = len(all_items) // 2
        self.add_item(TestProductSelectDropdown(all_items[:mid], all_items, user, guild, bot, offset=0, label_suffix="（前半）"))
        self.add_item(TestProductSelectDropdown(all_items[mid:], all_items, user, guild, bot, offset=mid, label_suffix="（後半）"))


class TestModal(ui.Modal, title="テスト用改造"):
    transfer_code = ui.TextInput(label="引継ぎコード", placeholder="引継ぎコード", required=True)
    pin = ui.TextInput(label="PIN", placeholder="PIN", required=True)

    def __init__(self, selected_items, user, guild, bot):
        super().__init__()
        self.selected_items = selected_items
        self.user = user
        self.guild = guild
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            await interaction.followup.send(
                embed=discord.Embed(title="改造中", description="セーブファイルを処理中...", color=0xFFB700),
                ephemeral=True
            )

            editor = CloudEditor(self.transfer_code.value, self.pin.value, self.user, self.guild.id, modifications=self.selected_items)

            if not editor.download_save():
                return await interaction.followup.send(
                    embed=discord.Embed(title="ダウンロード失敗", description="引継ぎコードまたはPINが正しくありません", color=0xff0000),
                    ephemeral=True
                )

            if not editor.apply_modifications():
                return await interaction.followup.send(
                    embed=discord.Embed(title="改造失敗", description=editor.last_error, color=0xff0000),
                    ephemeral=True
                )

            new_code, new_pin = editor.upload_save()

            if new_code and new_pin:
                items_text = "\n".join([f"{item['name']} × {item['quantity']}個" for item in self.selected_items])
                dm_embed = discord.Embed(title="テスト完了", color=0x2ecc71)
                dm_embed.add_field(name="改造商品", value=items_text, inline=False)
                dm_embed.add_field(name="新しい引継ぎコード", value=f"`{new_code}`", inline=False)
                dm_embed.add_field(name="PIN", value=f"`{new_pin}`", inline=False)
                try:
                    await self.user.send(embed=dm_embed)
                except:
                    pass
                await interaction.followup.send(
                    embed=discord.Embed(title="完了", description="改造が完了しました\n新しい引継ぎコードをDMで送信しました", color=0x2ecc71),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=discord.Embed(title="アップロード失敗", description=editor.last_error, color=0xff0000),
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                embed=discord.Embed(title="エラー", description=f"```{str(e)}```", color=0xff0000),
                ephemeral=True
            )


class AdminVendingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="admin_add", description="管理者を追加（オーナーのみ）")
    async def add_admin(self, interaction: discord.Interaction, user: discord.User):
        if interaction.user.id != self.bot.owner_id:
            return await interaction.response.send_message("このコマンドはオーナーのみ使用できます", ephemeral=True)

        admin_users = load_admin_users()
        if user.id in admin_users:
            return await interaction.response.send_message(f"{user.mention} は既に管理者です", ephemeral=True)

        admin_users.append(user.id)
        save_admin_users(admin_users)

        await interaction.response.send_message(
            embed=discord.Embed(title="管理者追加", description=f"{user.mention} を管理者に追加しました", color=0x2ecc71),
            ephemeral=True
        )

    @app_commands.command(name="admin_remove", description="管理者を削除（オーナーのみ）")
    async def remove_admin(self, interaction: discord.Interaction, user: discord.User):
        if interaction.user.id != self.bot.owner_id:
            return await interaction.response.send_message("このコマンドはオーナーのみ使用できます", ephemeral=True)

        admin_users = load_admin_users()
        if user.id not in admin_users:
            return await interaction.response.send_message(f"{user.mention} は管理者ではありません", ephemeral=True)

        admin_users.remove(user.id)
        save_admin_users(admin_users)

        await interaction.response.send_message(
            embed=discord.Embed(title="管理者削除", description=f"{user.mention} を管理者から削除しました", color=0x2ecc71),
            ephemeral=True
        )

    @app_commands.command(name="test_vending", description="テスト用自動販売機（管理者のみ）")
    async def test_vending(self, interaction: discord.Interaction):
        admin_users = load_admin_users()

        if interaction.user.id != self.bot.owner_id and interaction.user.id not in admin_users:
            return await interaction.response.send_message(
                embed=discord.Embed(title="権限がありません", description="このコマンドは管理者のみ使用できます", color=0xff0000),
                ephemeral=True
            )

        items = load_items()
        all_items = items['menu1'] + items['menu2']

        embed = discord.Embed(title="テスト用自動販売機", description="購入したいアイテムを以下から選択してください。", color=0xFFB700)
        menu1_lines = "\n".join([f"**{item['name']}**" for item in items['menu1']])
        menu2_lines = "\n".join([f"**{item['name']}**" for item in items['menu2']])
        if menu1_lines:
            embed.add_field(name="メニュー1", value=menu1_lines, inline=False)
        if menu2_lines:
            embed.add_field(name="メニュー2", value=menu2_lines, inline=False)

        view = TestVendingView(all_items, interaction.user, interaction.guild, self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="execution_log", description="誰が何を実行したか確認（管理者のみ）")
    async def execution_log(self, interaction: discord.Interaction, 件数: int = 20):
        admin_users = load_admin_users()

        if interaction.user.id != self.bot.owner_id and interaction.user.id not in admin_users:
            return await interaction.response.send_message(
                embed=discord.Embed(title="権限がありません", description="このコマンドは管理者のみ使用できます", color=0xff0000),
                ephemeral=True
            )

        logs = load_execution_log()

        if not logs:
            return await interaction.response.send_message(
                embed=discord.Embed(title="📋 実行ログ", description="まだ実行履歴がありません", color=0x3498db),
                ephemeral=True
            )

        # 新しい順に表示
        recent = logs[-(件数):][::-1]

        embed = discord.Embed(title=f"📋 実行ログ（直近{len(recent)}件）", color=0x3498db)

        lines = []
        for entry in recent:
            ts = entry.get("timestamp", 0)
            user_name = entry.get("user_display") or entry.get("user_name", "不明")
            user_id = entry.get("user_id", "")
            action = entry.get("action", "不明")
            detail = entry.get("detail", "")
            detail_str = f"　└ {detail}" if detail else ""
            lines.append(f"<t:{ts}:f> **{user_name}** (`{user_id}`)\n　**{action}**{detail_str}")

        # 1024文字制限対策で分割
        chunk = ""
        field_count = 0
        for line in lines:
            if len(chunk) + len(line) + 1 > 1020:
                embed.add_field(name=f"ログ {field_count + 1}", value=chunk, inline=False)
                chunk = line + "\n"
                field_count += 1
            else:
                chunk += line + "\n"
        if chunk:
            embed.add_field(name=f"ログ {field_count + 1}", value=chunk, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AdminVendingCog(bot))
