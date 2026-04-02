import discord
from discord import app_commands, ui
from discord.ext import commands
import json
import os
from Cogs.utils import load_items, is_allowed, save_execution_log_entry
from Cogs.nyanko_editor import CloudEditor

ADMIN_USERS_FILE = "admin_users.json"

# リスタートパックで適用するアイテム一覧
RESTART_PACK_ITEMS = [
    {"name": "XP9999999",           "quantity": 1, "subtotal": 0},
    {"name": "NP9999",              "quantity": 1, "subtotal": 0},
    {"name": "猫缶50000",           "quantity": 1, "subtotal": 0},
    {"name": "バトルアイテム全種999","quantity": 1, "subtotal": 0},
    {"name": "ネコビタン全種999",   "quantity": 1, "subtotal": 0},
    {"name": "キャッツアイ全999",   "quantity": 1, "subtotal": 0},
    {"name": "マタタビ全種99",      "quantity": 1, "subtotal": 0},
    {"name": "にゃんこチケ&レアチケ999","quantity": 1, "subtotal": 0},
    {"name": "プラチナ29",          "quantity": 1, "subtotal": 0},
    {"name": "全キャラ開放",        "quantity": 1, "subtotal": 0},
    {"name": "全キャラLvMAX",       "quantity": 1, "subtotal": 0},
    {"name": "全キャラ最高形態",    "quantity": 1, "subtotal": 0},
    {"name": "メインステージ全クリア","quantity": 1, "subtotal": 0},
    {"name": "金お宝",              "quantity": 1, "subtotal": 0},
    {"name": "ガマトトLvMAX",       "quantity": 1, "subtotal": 0},
    {"name": "ゴールド会員化",      "quantity": 1, "subtotal": 0},
]

# 特殊アイテム名（転送コード不要）
SPECIAL_ITEMS = {"新規アカウント作成", "リスタートパックアカウント作成"}


def load_admin_users():
    if os.path.exists(ADMIN_USERS_FILE):
        with open(ADMIN_USERS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []


def get_all_modifications():
    items = load_items()
    all_items = items['menu1'] + items['menu2']
    return [
        {'name': item['name'], 'quantity': 1, 'subtotal': 0}
        for item in all_items
    ]


# ===== 通常モーダル（引継ぎコード入力） =====
class AccountModal(ui.Modal, title="引継ぎコード入力"):
    transfer_code = ui.TextInput(label="引継ぎコード", placeholder="引継ぎコード", required=True)
    pin = ui.TextInput(label="PIN", placeholder="PIN", required=True)

    def __init__(self, mode, user, guild, bot):
        super().__init__()
        self.mode = mode
        self.user = user
        self.guild = guild
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            embed=discord.Embed(title="処理中", description="セーブファイルを処理中...", color=0xFFB700),
            ephemeral=True
        )
        handler = AccountHandler(self.transfer_code.value, self.pin.value, self.user, self.guild, self.bot)
        if self.mode == "full":
            await handler.handle_full(interaction)
        elif self.mode == "copy":
            await handler.handle_copy(interaction)
        elif self.mode == "restore":
            await handler.handle_restore(interaction)


# ===== 特殊モーダル（転送コード不要・アカウント新規作成系） =====
class SpecialAccountModal(ui.Modal, title="アカウント作成確認"):
    confirm = ui.TextInput(label="確認", placeholder="「作成」と入力してください", required=True)

    def __init__(self, mode, user, guild, bot):
        super().__init__()
        self.mode = mode
        self.user = user
        self.guild = guild
        self.bot = bot
        if mode == "restart_pack":
            self.title = "リスタートパック作成確認"
        else:
            self.title = "新規アカウント作成確認"

    async def on_submit(self, interaction: discord.Interaction):
        if self.confirm.value.strip() != "作成":
            return await interaction.response.send_message(
                embed=discord.Embed(title="キャンセル", description="「作成」と入力されなかったためキャンセルしました", color=0xff0000),
                ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            embed=discord.Embed(title="処理中", description="アカウントを作成中...", color=0xFFB700),
            ephemeral=True
        )
        handler = AccountHandler(None, None, self.user, self.guild, self.bot)
        if self.mode == "new":
            await handler.handle_new(interaction)
        elif self.mode == "restart_pack":
            await handler.handle_restart_pack(interaction)


# ===== アカウント新規作成モーダル（vending_accountコマンド用） =====
class AccountNewModal(ui.Modal, title="新規アカウント作成"):
    confirm = ui.TextInput(label="確認", placeholder="「作成」と入力してください", required=True)

    def __init__(self, user, guild, bot):
        super().__init__()
        self.user = user
        self.guild = guild
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            embed=discord.Embed(title="処理中", description="新規アカウントを作成中...", color=0xFFB700),
            ephemeral=True
        )
        handler = AccountHandler(None, None, self.user, self.guild, self.bot)
        await handler.handle_new(interaction)


# ===== 共通処理クラス =====
class AccountHandler:
    def __init__(self, transfer_code, pin, user, guild, bot):
        self.transfer_code = transfer_code
        self.pin = pin
        self.user = user
        self.guild = guild
        self.bot = bot

    async def handle_full(self, interaction):
        save_execution_log_entry(self.user, "代行全適用アカウント")
        mods = get_all_modifications()
        editor = CloudEditor(self.transfer_code, self.pin, self.user, self.guild.id, modifications=mods)

        if not editor.download_save():
            return await interaction.followup.send(
                embed=discord.Embed(title="ダウンロード失敗", description="引継ぎコードまたはPINが正しくありません", color=0xff0000),
                ephemeral=True
            )
        if not editor.apply_modifications():
            return await interaction.followup.send(
                embed=discord.Embed(title="失敗", description=editor.last_error, color=0xff0000),
                ephemeral=True
            )

        new_code, new_pin = editor.upload_save()
        if new_code and new_pin:
            dm_embed = discord.Embed(title="代行全適用 完了", color=0x2ecc71)
            dm_embed.add_field(name="新しい引継ぎコード", value=f"`{new_code}`", inline=False)
            dm_embed.add_field(name="PIN", value=f"`{new_pin}`", inline=False)
            try:
                await self.user.send(embed=dm_embed)
            except:
                pass
            await interaction.followup.send(
                embed=discord.Embed(title="完了", description="全適用が完了しました\n新しい引継ぎコードをDMで送信しました", color=0x2ecc71),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                embed=discord.Embed(title="アップロード失敗", description=editor.last_error, color=0xff0000),
                ephemeral=True
            )

    async def handle_copy(self, interaction):
        save_execution_log_entry(self.user, "アカウント複製")
        editor = CloudEditor(self.transfer_code, self.pin, self.user, self.guild.id, modifications=[])

        if not editor.download_save():
            return await interaction.followup.send(
                embed=discord.Embed(title="ダウンロード失敗", description="引継ぎコードまたはPINが正しくありません", color=0xff0000),
                ephemeral=True
            )

        original_save_data = editor.save_data
        new_code, new_pin = editor.upload_save()
        if not (new_code and new_pin):
            return await interaction.followup.send(
                embed=discord.Embed(title="複製失敗", description=editor.last_error, color=0xff0000),
                ephemeral=True
            )

        editor.save_data = original_save_data
        orig_new_code, orig_new_pin = editor.upload_save()

        dm_embed = discord.Embed(title="アカウント複製 完了", color=0x2ecc71)
        if orig_new_code and orig_new_pin:
            dm_embed.add_field(name="元アカウント コード", value=f"`{orig_new_code}`", inline=False)
            dm_embed.add_field(name="元アカウント PIN", value=f"`{orig_new_pin}`", inline=False)
        else:
            dm_embed.add_field(name="元アカウント", value="再発行失敗（手動で再発行してください）", inline=False)
        dm_embed.add_field(name="複製アカウント コード", value=f"`{new_code}`", inline=False)
        dm_embed.add_field(name="複製アカウント PIN", value=f"`{new_pin}`", inline=False)
        dm_embed.set_footer(text="どちらも新しいコードで引継ぎしてください")

        try:
            await self.user.send(embed=dm_embed)
        except:
            pass

        await interaction.followup.send(
            embed=discord.Embed(title="完了", description="複製が完了しました\n元・複製アカウント両方のコードをDMで送信しました", color=0x2ecc71),
            ephemeral=True
        )

    async def handle_restore(self, interaction):
        save_execution_log_entry(self.user, "アカウント復旧")
        editor = CloudEditor(self.transfer_code, self.pin, self.user, self.guild.id, modifications=[])

        if not editor.download_save():
            return await interaction.followup.send(
                embed=discord.Embed(title="ダウンロード失敗", description="引継ぎコードまたはPINが正しくありません", color=0xff0000),
                ephemeral=True
            )

        try:
            import bcsfe.core as bc
            bc.core_data.init_data()
            data = bc.Data(editor.save_data)
            save = bc.SaveFile(dt=data, cc=bc.CountryCode("ja"))
            if hasattr(save, 'show_ban_message'):
                save.show_ban_message = False
            if hasattr(save, 'rank_up_sale_value'):
                save.rank_up_sale_value = 0
            save.max_rank_up_sale()
            out = save.to_data()
            editor.save_data = out.to_bytes()
        except Exception as e:
            return await interaction.followup.send(
                embed=discord.Embed(title="復旧処理失敗", description=str(e), color=0xff0000),
                ephemeral=True
            )

        new_code, new_pin = editor.upload_save()
        if new_code and new_pin:
            dm_embed = discord.Embed(title="アカウント復旧 完了", color=0x2ecc71)
            dm_embed.add_field(name="新しい引継ぎコード", value=f"`{new_code}`", inline=False)
            dm_embed.add_field(name="PIN", value=f"`{new_pin}`", inline=False)
            try:
                await self.user.send(embed=dm_embed)
            except:
                pass
            await interaction.followup.send(
                embed=discord.Embed(title="完了", description="復旧が完了しました\n新しい引継ぎコードをDMで送信しました", color=0x2ecc71),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                embed=discord.Embed(title="アップロード失敗", description=editor.last_error, color=0xff0000),
                ephemeral=True
            )

    async def _create_new_account(self):
        """新規アカウント発行の共通処理。(code, pin) または (None, None) を返す"""
        import bcsfe.core as bc
        bc.core_data.init_data()
        tmp_save = bc.SaveFile(cc=bc.CountryCode("ja"), load=False)
        tmp_save.init_save()
        tmp_handler = bc.ServerHandler(tmp_save, print=False)
        new_iq = tmp_handler.get_new_inquiry_code()
        if new_iq is None:
            return None, None
        tmp_save.inquiry_code = new_iq
        result = tmp_handler.get_codes()
        if result is None:
            return None, None
        return result  # (code, pin)

    async def handle_new(self, interaction):
        save_execution_log_entry(self.user, "新規アカウント作成")
        try:
            new_code, new_pin = await self._create_new_account()
            if not new_code:
                return await interaction.followup.send(
                    embed=discord.Embed(title="作成失敗", description="新規アカウントの作成に失敗しました", color=0xff0000),
                    ephemeral=True
                )

            dm_embed = discord.Embed(title="新規アカウント作成 完了", color=0x2ecc71)
            dm_embed.add_field(name="引継ぎコード", value=f"`{new_code}`", inline=False)
            dm_embed.add_field(name="PIN", value=f"`{new_pin}`", inline=False)
            dm_embed.set_footer(text="必ず保存してください")
            try:
                await self.user.send(embed=dm_embed)
            except:
                pass

            await interaction.followup.send(
                embed=discord.Embed(title="完了", description="新規アカウントを作成しました\n引継ぎコードをDMで送信しました", color=0x2ecc71),
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                embed=discord.Embed(title="エラー", description=f"```{str(e)}```", color=0xff0000),
                ephemeral=True
            )

    async def handle_restart_pack(self, interaction):
        save_execution_log_entry(self.user, "リスタートパックアカウント作成")
        try:
            import bcsfe.core as bc

            # 新規アカウント発行
            new_code, new_pin = await self._create_new_account()
            if not new_code:
                return await interaction.followup.send(
                    embed=discord.Embed(title="作成失敗", description="新規アカウントの作成に失敗しました", color=0xff0000),
                    ephemeral=True
                )

            await interaction.followup.send(
                embed=discord.Embed(title="処理中", description="リスタートパックを適用中...", color=0xFFB700),
                ephemeral=True
            )

            # 発行したコードでダウンロード → 改造 → アップロード
            editor = CloudEditor(new_code, new_pin, self.user, self.guild.id, modifications=RESTART_PACK_ITEMS)

            if not editor.download_save():
                # ダウンロード失敗でも発行済みコードは送る
                dm_embed = discord.Embed(title="⚠️ 部分的に完了", color=0xFFB700)
                dm_embed.add_field(name="引継ぎコード（改造なし）", value=f"`{new_code}`", inline=False)
                dm_embed.add_field(name="PIN", value=f"`{new_pin}`", inline=False)
                dm_embed.set_footer(text="リスタートパックの適用には失敗しましたが、アカウント自体は作成されています")
                try:
                    await self.user.send(embed=dm_embed)
                except:
                    pass
                return await interaction.followup.send(
                    embed=discord.Embed(title="⚠️ 警告", description="アカウント作成済みですが改造に失敗しました\nDMを確認してください", color=0xFFB700),
                    ephemeral=True
                )

            if not editor.apply_modifications():
                dm_embed = discord.Embed(title="⚠️ 部分的に完了", color=0xFFB700)
                dm_embed.add_field(name="引継ぎコード（改造なし）", value=f"`{new_code}`", inline=False)
                dm_embed.add_field(name="PIN", value=f"`{new_pin}`", inline=False)
                dm_embed.set_footer(text="リスタートパックの適用には失敗しましたが、アカウント自体は作成されています")
                try:
                    await self.user.send(embed=dm_embed)
                except:
                    pass
                return await interaction.followup.send(
                    embed=discord.Embed(title="⚠️ 警告", description="アカウント作成済みですが改造に失敗しました\nDMを確認してください", color=0xFFB700),
                    ephemeral=True
                )

            final_code, final_pin = editor.upload_save()
            if final_code and final_pin:
                pack_list = "\n".join([f"・{item['name']}" for item in RESTART_PACK_ITEMS])
                dm_embed = discord.Embed(title="リスタートパックアカウント 完了", color=0x2ecc71)
                dm_embed.add_field(name="引継ぎコード", value=f"`{final_code}`", inline=False)
                dm_embed.add_field(name="PIN", value=f"`{final_pin}`", inline=False)
                dm_embed.add_field(name="適用済みパック内容", value=pack_list, inline=False)
                dm_embed.set_footer(text="必ず保存してください")
                try:
                    await self.user.send(embed=dm_embed)
                except:
                    pass
                await interaction.followup.send(
                    embed=discord.Embed(title="完了", description="リスタートパックアカウントを作成しました\n引継ぎコードをDMで送信しました", color=0x2ecc71),
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


class AccountVendingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="vending_account", description="アカウント自動販売機")
    @is_allowed()
    async def vending_account(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="アカウント自動販売機",
            description="実行したいメニューを選択してください。",
            color=0x2b2d31
        )
        embed.add_field(name="代行全適用アカウント", value="全適用", inline=True)
        embed.add_field(name="アカウント複製", value="複製", inline=True)
        embed.add_field(name="アカウント復旧", value="復旧", inline=True)
        embed.add_field(name="新規アカウント作成", value="新規作成", inline=True)
        embed.add_field(name="リスタートパックアカウント作成", value="新規+パック適用", inline=True)

        view = ui.View()

        async def full_cb(it):
            await it.response.send_modal(AccountModal("full", interaction.user, interaction.guild, self.bot))
        async def copy_cb(it):
            await it.response.send_modal(AccountModal("copy", interaction.user, interaction.guild, self.bot))
        async def restore_cb(it):
            await it.response.send_modal(AccountModal("restore", interaction.user, interaction.guild, self.bot))
        async def new_cb(it):
            await it.response.send_modal(AccountNewModal(interaction.user, interaction.guild, self.bot))
        async def restart_cb(it):
            await it.response.send_modal(SpecialAccountModal("restart_pack", interaction.user, interaction.guild, self.bot))

        btn_full = ui.Button(label="代行全適用アカウント", style=discord.ButtonStyle.primary)
        btn_full.callback = full_cb
        btn_copy = ui.Button(label="アカウント複製", style=discord.ButtonStyle.secondary)
        btn_copy.callback = copy_cb
        btn_restore = ui.Button(label="アカウント復旧", style=discord.ButtonStyle.success)
        btn_restore.callback = restore_cb
        btn_new = ui.Button(label="新規アカウント作成", style=discord.ButtonStyle.secondary)
        btn_new.callback = new_cb
        btn_restart = ui.Button(label="リスタートパックアカウント作成", style=discord.ButtonStyle.primary, row=1)
        btn_restart.callback = restart_cb

        view.add_item(btn_full)
        view.add_item(btn_copy)
        view.add_item(btn_restore)
        view.add_item(btn_new)
        view.add_item(btn_restart)

        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(AccountVendingCog(bot))
