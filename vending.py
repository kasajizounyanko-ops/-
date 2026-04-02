import discord
from discord import app_commands, ui
from discord.ext import commands
import time
import json
import os
import uuid
from Cogs.utils import load_items, load_config, save_config, is_allowed, save_execution_log_entry
from Cogs.nyanko_editor import CloudEditor
from Cogs.Account_vending import AccountModal, SpecialAccountModal, SPECIAL_ITEMS

VENDING_DATA_FILE = "vending_data.json"
LOG_CHANNEL_FILE = "log_channels.json"
SALES_FILE = "sales_history.json"


def load_vending_data():
    if os.path.exists(VENDING_DATA_FILE):
        with open(VENDING_DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}


def save_vending_data(data):
    with open(VENDING_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_log_channels():
    if os.path.exists(LOG_CHANNEL_FILE):
        with open(LOG_CHANNEL_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}


def save_log_channels(data):
    with open(LOG_CHANNEL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_sales_history():
    if os.path.exists(SALES_FILE):
        with open(SALES_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}


def save_sales_history(data):
    with open(SALES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


class ProductSelectDropdown(ui.Select):
    def __init__(self, items, vending_id, user, guild, bot, offset=0, label_suffix=""):
        self.items = items
        self.vending_id = vending_id
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
            local_idx = int(idx) - self.offset
            item = self.items[local_idx]
            selected_items.append({'name': item['name'], 'quantity': 1, 'subtotal': 0})

        # 特殊アイテム（新規作成系）の検知
        special = [item for item in selected_items if item['name'] in SPECIAL_ITEMS]
        if special:
            item_name = special[0]['name']
            if item_name == "新規アカウント作成":
                return await interaction.response.send_modal(
                    SpecialAccountModal("new", self.user, self.guild, self.bot)
                )
            elif item_name == "リスタートパックアカウント作成":
                return await interaction.response.send_modal(
                    SpecialAccountModal("restart_pack", self.user, self.guild, self.bot)
                )

        # 通常アイテム
        embed = discord.Embed(title="注文確認", color=0x2ecc71)
        embed.add_field(
            name="選択アイテム",
            value="\n".join([f"{item['name']} × {item['quantity']}個" for item in selected_items]),
            inline=False
        )

        view = ui.View()

        async def buy_cb(it):
            await it.response.send_modal(OrderModal(selected_items, self.user, self.guild, self.bot, self.vending_id))

        btn = ui.Button(label="購入する", style=discord.ButtonStyle.success)
        btn.callback = buy_cb
        view.add_item(btn)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class OrderModal(ui.Modal, title="引継ぎコード入力"):
    transfer_code = ui.TextInput(label="引継ぎコード *", placeholder="引継ぎコード", required=True)
    pin = ui.TextInput(label="PIN *", placeholder="PIN", required=True)

    def __init__(self, selected_items, user, guild, bot, vending_id):
        super().__init__()
        self.selected_items = selected_items
        self.user = user
        self.guild = guild
        self.bot = bot
        self.vending_id = vending_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            items_text = "、".join([item['name'] for item in self.selected_items])
            save_execution_log_entry(self.user, "改造", items_text)

            await interaction.followup.send(
                embed=discord.Embed(title="🔄 代行中", description="セーブファイルを改造中...", color=0xFFB700),
                ephemeral=True
            )

            editor = CloudEditor(
                self.transfer_code.value,
                self.pin.value,
                self.user,
                self.guild.id,
                modifications=self.selected_items
            )

            if not editor.download_save():
                return await interaction.followup.send(
                    embed=discord.Embed(title="❌ エラー", description="引継ぎコードまたはPINが正しくありません", color=0xff0000),
                    ephemeral=True
                )

            if not editor.apply_modifications():
                return await interaction.followup.send(
                    embed=discord.Embed(title="❌ エラー", description=editor.last_error, color=0xff0000),
                    ephemeral=True
                )

            new_code, new_pin = editor.upload_save()

            if new_code and new_pin:
                sales_history = load_sales_history()
                if self.vending_id not in sales_history:
                    sales_history[self.vending_id] = []
                sales_history[self.vending_id].append({
                    "timestamp": int(time.time()),
                    "user_id": str(self.user.id),
                    "user_name": str(self.user.name),
                    "items": self.selected_items
                })
                save_sales_history(sales_history)

                items_disp = "\n".join([f"{item['name']} × {item['quantity']}個" for item in self.selected_items])
                dm_embed = discord.Embed(title="✅ 代行完了", color=0x2ecc71)
                dm_embed.add_field(name="購入商品", value=items_disp, inline=False)
                dm_embed.add_field(name="新しい引継ぎコード", value=f"`{new_code}`", inline=False)
                dm_embed.add_field(name="PIN", value=f"`{new_pin}`", inline=False)
                dm_embed.set_footer(text="必ず保存してください")

                try:
                    await self.user.send(embed=dm_embed)
                except:
                    pass

                await interaction.followup.send(
                    embed=discord.Embed(title="✅ 代行完了", description="新しい引継ぎコードをDMで送信しました", color=0x2ecc71),
                    ephemeral=True
                )

                # ロール付与
                vending_data = load_vending_data()
                vm = vending_data.get(self.vending_id, {})
                if vm.get("role_id"):
                    role = self.guild.get_role(vm["role_id"])
                    if role and role not in self.user.roles:
                        try:
                            await self.user.add_roles(role)
                        except:
                            pass

                # ログ記録
                log_channels = load_log_channels()
                guild_logs = log_channels.get(str(self.guild.id), {})

                if guild_logs.get("public"):
                    ch = self.bot.get_channel(guild_logs["public"])
                    if ch:
                        log_embed = discord.Embed(title="✅ 代行完了", color=0x2ecc71)
                        log_embed.set_author(name=self.user.name, icon_url=self.user.display_avatar.url)
                        log_embed.add_field(name="ユーザー", value=self.user.mention, inline=False)
                        log_embed.add_field(name="商品", value=items_disp, inline=False)
                        log_embed.add_field(name="日時", value=f"<t:{int(time.time())}:F>", inline=False)
                        await ch.send(embed=log_embed)

                if guild_logs.get("private"):
                    ch = self.bot.get_channel(guild_logs["private"])
                    if ch:
                        log_embed = discord.Embed(title="✅ 代行完了", color=0x3498db)
                        log_embed.set_author(name=self.user.name, icon_url=self.user.display_avatar.url)
                        log_embed.add_field(name="ユーザー", value=self.user.mention, inline=False)
                        log_embed.add_field(name="商品", value=items_disp, inline=False)
                        log_embed.add_field(name="新コード", value=f"`{new_code}`", inline=False)
                        log_embed.add_field(name="日時", value=f"<t:{int(time.time())}:F>", inline=False)
                        await ch.send(embed=log_embed)
            else:
                await interaction.followup.send(
                    embed=discord.Embed(title="❌ エラー", description=f"アップロード失敗: {editor.last_error}", color=0xff0000),
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                embed=discord.Embed(title="❌ エラー", description=f"```{str(e)}```", color=0xff0000),
                ephemeral=True
            )


class VendingView(ui.View):
    def __init__(self, all_items, account_items, vending_id, user, guild, bot):
        super().__init__()

        mid = len(all_items) // 2
        self.add_item(ProductSelectDropdown(all_items[:mid], vending_id, user, guild, bot, offset=0, label_suffix="（前半）"))
        self.add_item(ProductSelectDropdown(all_items[mid:], vending_id, user, guild, bot, offset=mid, label_suffix="（後半）"))

        # アカウント系特殊メニュー
        if account_items:
            self.add_item(ProductSelectDropdown(account_items, vending_id, user, guild, bot, offset=len(all_items), label_suffix="（アカウント作成）"))

        # アカウント複製ボタン
        copy_btn = ui.Button(label="アカウント複製", style=discord.ButtonStyle.primary, row=3)

        async def copy_cb(it: discord.Interaction):
            await it.response.send_modal(AccountModal("copy", user, guild, bot))

        copy_btn.callback = copy_cb
        self.add_item(copy_btn)


async def vending_machine_autocomplete(interaction: discord.Interaction, current: str):
    vending_data = load_vending_data()
    user_id_str = str(interaction.user.id)
    user_machines = [
        (vm_id, vm_data) for vm_id, vm_data in vending_data.items()
        if vm_data.get("owner_id") == user_id_str
    ]
    return [
        app_commands.Choice(name=vm_data.get("name", "名称未設定"), value=vm_id)
        for vm_id, vm_data in user_machines
        if current.lower() in vm_data.get("name", "").lower()
    ]


class VendingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="vending_create", description="自販機を作成")
    @is_allowed()
    async def create_vending(self, interaction: discord.Interaction, name: str):
        vending_data = load_vending_data()
        vm_id = str(uuid.uuid4())
        vending_data[vm_id] = {"name": name, "owner_id": str(interaction.user.id), "role_id": None, "custom_items": []}
        save_vending_data(vending_data)
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ 自販機作成", description=f"自販機「{name}」を作成しました\n**ID:** `{vm_id}`", color=0x2ecc71),
            ephemeral=True
        )

    @app_commands.command(name="vending_add_item", description="自販機に商品を追加")
    @is_allowed()
    @app_commands.autocomplete(vending_id=vending_machine_autocomplete)
    async def add_item(self, interaction: discord.Interaction, vending_id: str, name: str):
        vending_data = load_vending_data()
        vm = vending_data.get(vending_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません", ephemeral=True)
        vm["custom_items"].append({"name": name})
        save_vending_data(vending_data)
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ 商品追加", description=f"商品「{name}」を追加しました", color=0x2ecc71),
            ephemeral=True
        )

    @app_commands.command(name="vending", description="自動販売機")
    @is_allowed()
    @app_commands.autocomplete(vending_id=vending_machine_autocomplete)
    async def vending_machine(self, interaction: discord.Interaction, vending_id: str):
        vending_data = load_vending_data()
        vm = vending_data.get(vending_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません", ephemeral=True)

        items = load_items()
        if vm.get("custom_items"):
            items['menu1'].extend(vm["custom_items"])

        all_items = items['menu1'] + items['menu2']
        account_items = items.get('menu_account', [
            {"name": "新規アカウント作成", "special": True},
            {"name": "リスタートパックアカウント作成", "special": True},
        ])

        embed = discord.Embed(
            title=vm['name'],
            description="購入したいアイテムを以下から選択してください。",
            color=0x2b2d31
        )

        menu1_lines = "\n".join([f"**{item['name']}**" for item in items['menu1']])
        menu2_lines = "\n".join([f"**{item['name']}**" for item in items['menu2']])
        account_lines = "\n".join([f"**{item['name']}**" for item in account_items])

        if menu1_lines:
            embed.add_field(name="メニュー1", value=menu1_lines, inline=False)
        if menu2_lines:
            embed.add_field(name="メニュー2", value=menu2_lines, inline=False)
        if account_lines:
            embed.add_field(name="アカウント作成", value=account_lines, inline=False)

        view = VendingView(all_items, account_items, vending_id, interaction.user, interaction.guild, self.bot)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="vending_sales", description="販売履歴を表示")
    @is_allowed()
    @app_commands.autocomplete(vending_id=vending_machine_autocomplete)
    async def show_sales(self, interaction: discord.Interaction, vending_id: str):
        vending_data = load_vending_data()
        vm = vending_data.get(vending_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません", ephemeral=True)

        sales = load_sales_history().get(vending_id, [])
        if not sales:
            return await interaction.response.send_message(
                embed=discord.Embed(title=f"📊 {vm['name']} - 販売履歴", description="まだ販売実績がありません", color=0x3498db),
                ephemeral=True
            )

        item_stats = {}
        for sale in sales:
            for item in sale['items']:
                name = item['name']
                item_stats[name] = item_stats.get(name, 0) + item['quantity']

        embed = discord.Embed(title=f"📊 {vm['name']} - 販売履歴", color=0x3498db)
        embed.add_field(name="販売件数", value=f"{len(sales)}件", inline=False)
        embed.add_field(name="商品別販売数", value="```\n" + "\n".join([
            f"{name}: {qty}個"
            for name, qty in sorted(item_stats.items(), key=lambda x: x[1], reverse=True)
        ]) + "```", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="vending_set_role", description="購入時に付与するロールを設定")
    @is_allowed()
    @app_commands.autocomplete(vending_id=vending_machine_autocomplete)
    async def set_vending_role(self, interaction: discord.Interaction, vending_id: str, role: discord.Role):
        vending_data = load_vending_data()
        vm = vending_data.get(vending_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません", ephemeral=True)
        vm["role_id"] = role.id
        save_vending_data(vending_data)
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ ロール設定", description=f"購入時に {role.mention} を付与するように設定しました", color=0x2ecc71),
            ephemeral=True
        )

    @app_commands.command(name="log_channel", description="公開ログチャンネルを設定")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        log_channels = load_log_channels()
        guild_id = str(interaction.guild.id)
        if guild_id not in log_channels:
            log_channels[guild_id] = {}
        log_channels[guild_id]["public"] = channel.id
        save_log_channels(log_channels)
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ 公開ログチャンネル設定", description=f"{channel.mention} に設定しました", color=0x2ecc71),
            ephemeral=True
        )

    @app_commands.command(name="private_log_channel", description="非公開ログチャンネルを設定")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_private_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        log_channels = load_log_channels()
        guild_id = str(interaction.guild.id)
        if guild_id not in log_channels:
            log_channels[guild_id] = {}
        log_channels[guild_id]["private"] = channel.id
        save_log_channels(log_channels)
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ 非公開ログチャンネル設定", description=f"{channel.mention} に設定しました", color=0x2ecc71),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(VendingCog(bot))
