import requests
import secrets
import hmac
import hashlib
import json
import time
import io
from typing import Any, Optional, Tuple

try:
    import bcsfe
    import bcsfe.core as bc
    BCSFE_AVAILABLE = True
except ImportError:
    BCSFE_AVAILABLE = False

class NyankoSignature:
    def __init__(self, inquiry_code: str, data: str):
        self.inquiry_code = inquiry_code
        self.data = data

    def generate_signature(self) -> str:
        random_hex = secrets.token_hex(32)
        key = (self.inquiry_code + random_hex).encode()
        signature = hmac.new(key, self.data.encode(), hashlib.sha256).hexdigest()
        return random_hex + signature

    def generate_signature_v1(self) -> str:
        data_double = self.data + self.data
        random_hex = secrets.token_hex(20)
        key = (self.inquiry_code + random_hex).encode()
        signature = hmac.new(key, data_double.encode(), hashlib.sha1).hexdigest()
        return random_hex + signature

class CloudEditor:
    AUTH_URL = "https://nyanko-auth.ponosgames.com"
    SAVE_URL = "https://nyanko-save.ponosgames.com"

    def __init__(self, transfer_code: str, pin: str, user, guild_id, modifications: list = None):
        self.transfer_code = transfer_code
        self.pin = pin
        self.session = requests.Session()
        self.save_data: Optional[bytes] = None
        self.save_object = None  # 改造後のSaveFileオブジェクトを保持
        self.password = ""
        self.last_error = ""
        self.user = user
        self.guild_id = guild_id
        self.modifications = modifications or []

    def get_common_headers(self, iq: str, data: str) -> dict:
        return {
            "Content-Type": "application/json",
            "Nyanko-Signature": NyankoSignature(iq, data).generate_signature(),
            "Nyanko-Timestamp": str(int(time.time())),
            "Nyanko-Signature-Version": "1",
            "Nyanko-Signature-Algorithm": "HMACSHA256",
            "User-Agent": "Dalvik/2.1.0"
        }

    def download_save(self) -> bool:
        nonce = secrets.token_hex(16)
        url = f"{self.SAVE_URL}/v2/transfers/{self.transfer_code}/reception"
        payload = {
            "clientInfo": {
                "client": {"version": "15.2.1", "countryCode": "ja"},
                "os": {"type": "android", "version": "13"},
                "device": {"model": "SM-S918B"}
            },
            "pin": self.pin,
            "nonce": nonce
        }
        body = json.dumps(payload, separators=(",", ":"))
        headers = {"Content-Type": "application/json"}
        try:
            res = self.session.post(url, headers=headers, data=body)
            if res.status_code == 200 and res.headers.get("Content-Type") == "application/octet-stream":
                self.save_data = res.content
                self.password = res.headers.get("Nyanko-Password", "")
                return True
            self.last_error = res.text
        except Exception as e:
            self.last_error = str(e)
        return False

    def apply_modifications(self) -> bool:
        if not self.save_data:
            self.last_error = "セーブデータがありません"
            return False
        if not BCSFE_AVAILABLE:
            self.last_error = "bcsfeモジュールが見つかりません"
            return False
        try:
            return self._apply_with_bcsfe()
        except Exception as e:
            self.last_error = f"改造エラー: {str(e)}"
            return False

    def _clear_chapters(self, chapters_obj):
        """Chaptersオブジェクトの全ステージをクリア"""
        try:
            for map_i, chap_stars in enumerate(chapters_obj.chapters):
                for star_i, chap in enumerate(chap_stars.chapters):
                    for stage_i in range(len(chap.stages)):
                        try:
                            chapters_obj.clear_stage(map_i, star_i, stage_i, 1)
                        except:
                            pass
        except:
            pass

    def _clear_story(self, save):
        """メインステージ全クリア（EoC/ItW/ItF + お宝金）"""
        try:
            for map_i in range(len(save.story.chapters)):
                chapter = save.story.chapters[map_i]
                for stage_i in range(len(chapter.stages)):
                    try:
                        save.story.clear_stage(map_i, stage_i, 1)
                    except:
                        pass
                # お宝を金に
                for stage_i in range(len(chapter.stages)):
                    try:
                        save.story.set_treasure(map_i, stage_i, 3)
                    except:
                        pass
        except:
            pass

    def _apply_with_bcsfe(self) -> bool:
        try:
            bc.core_data.init_data()
            data = bc.Data(self.save_data)
            save = bc.SaveFile(dt=data, cc=bc.CountryCode("ja"))

            for mod in self.modifications:
                item_name = mod.get('name', '')

                # ===== リソース系 =====
                if 'XP' in item_name:
                    save.set_xp(9999999)

                elif 'NP' in item_name:
                    save.set_np(9999)

                elif '猫缶' in item_name:
                    save.set_catfood(50000)

                elif 'バトルアイテム' in item_name:
                    # BattleItems: 6種類
                    for item in save.battle_items.items:
                        item.amount = 999

                elif 'ネコビタン' in item_name:
                    # catamins: int_list
                    if hasattr(save, 'catamins'):
                        save.catamins = [999] * len(save.catamins)

                elif '城塞材' in item_name or '城素材' in item_name:
                    # Ototo.base_materials
                    if hasattr(save, 'ototo') and hasattr(save.ototo, 'base_materials'):
                        for mat in save.ototo.base_materials.materials:
                            mat.amount = 999

                elif 'キャッツアイ' in item_name or 'キャツアイ' in item_name:
                    if hasattr(save, 'catseyes'):
                        save.catseyes = [999] * len(save.catseyes)

                elif 'マタタビ' in item_name:
                    # catfruit: int_list
                    if hasattr(save, 'catfruit'):
                        save.catfruit = [99] * len(save.catfruit)

                elif '木箱' in item_name:
                    # lucky_tickets: int_list
                    if hasattr(save, 'lucky_tickets'):
                        save.lucky_tickets = [9] * len(save.lucky_tickets)

                elif 'リーダーシップ' in item_name:
                    save.set_leadership(30000)

                elif '地底迷宮メダル' in item_name or 'ラビリンスメダル' in item_name:
                    if hasattr(save, 'labyrinth_medals'):
                        save.labyrinth_medals = [999] * len(save.labyrinth_medals)

                # ===== チケット系 =====
                elif 'にゃんこチケ' in item_name or '銀チケ' in item_name:
                    save.set_normal_tickets(999)
                    save.set_rare_tickets(999)

                elif 'プラチナ' in item_name or 'プラチケ' in item_name:
                    save.set_platinum_tickets(29)

                elif 'レジェチケ' in item_name:
                    save.set_legend_tickets(9)

                elif 'イベチケ' in item_name or '福チケ' in item_name:
                    # event_capsules
                    if hasattr(save, 'event_capsules'):
                        save.event_capsules = [999] * len(save.event_capsules)
                    if hasattr(save, 'event_capsules_2'):
                        save.event_capsules_2 = [999] * len(save.event_capsules_2)

                # ===== キャラ系 =====
                elif '全キャラ開放' in item_name:
                    for cat in save.cats.cats:
                        if cat.unlocked == 0:
                            cat.unlocked = 1
                            cat.gatya_seen = 1

                elif 'エラーキャラ削除' in item_name:
                    for cat in save.cats.cats:
                        if cat.unlocked == 2:
                            cat.unlocked = 0

                elif 'LvMAX' in item_name and 'キャラ' in item_name:
                    for cat in save.cats.cats:
                        if cat.unlocked:
                            cat.upgrade.base = 29  # base+1で30
                            cat.upgrade.plus = 90

                elif '最高形態' in item_name:
                    for cat in save.cats.cats:
                        if cat.unlocked and cat.unlocked_forms > 0:
                            cat.current_form = cat.unlocked_forms

                elif '本能全開放' in item_name:
                    for cat in save.cats.cats:
                        if cat.talents:
                            for talent in cat.talents:
                                talent.level = 999

                # ===== 施設系 =====
                elif 'ガマトトLvMAX' in item_name:
                    if hasattr(save, 'gamatoto'):
                        save.gamatoto.xp = 200000000
                        save.gamatoto.dest_id = 50

                elif 'ガマトト初手全レジェンド化' in item_name:
                    if hasattr(save, 'gamatoto'):
                        from bcsfe.core.game.gamoto.gamatoto import Helper, Helpers
                        # ネコ基本キャラ（ID0〜8）で埋める（確実に存在するID）
                        save.gamatoto.helpers = Helpers([Helper(i) for i in range(9)])

                elif 'ガマトト助手追加' in item_name or 'ガマトト助手' in item_name:
                    if hasattr(save, 'gamatoto'):
                        from bcsfe.core.game.gamoto.gamatoto import Helper, Helpers
                        # 解放済みキャラのうちID100未満の基本キャラのみ使用（安全なID）
                        unlocked = [cat.id for cat in save.cats.cats if cat.unlocked and cat.id < 100]
                        helper_ids = unlocked[:9] if len(unlocked) >= 9 else unlocked
                        if not helper_ids:
                            helper_ids = list(range(9))
                        save.gamatoto.helpers = Helpers([Helper(i) for i in helper_ids])

                elif 'にゃんこ神社LvMAX' in item_name:
                    if hasattr(save, 'cat_shrine'):
                        save.cat_shrine.shrine_gone = False
                        save.cat_shrine.xp_offering = 900000000

                elif 'にゃんこ神社全開放' in item_name:
                    if hasattr(save, 'cat_shrine'):
                        save.cat_shrine.shrine_gone = False
                        if hasattr(save.cat_shrine, 'flags'):
                            save.cat_shrine.flags = [1] * len(save.cat_shrine.flags)

                elif 'オートセーブ' in item_name:
                    if hasattr(save, 'ototo') and save.ototo.cannons:
                        for cannon_id, cannon in save.ototo.cannons.cannons.items():
                            cannon.development = 999
                            cannon.levels = [30] * len(cannon.levels) if cannon.levels else [30]

                elif 'ゴールド会員化' in item_name:
                    # get_gold_pass()専用メソッドを使用（30日×ランダムID）
                    officer_id = bc.NyankoClub.get_random_officer_id()
                    save.officer_pass.gold_pass.get_gold_pass(officer_id, 30, save)

                # ===== 編成スロット =====
                elif '編成スロット' in item_name:
                    # 最大15スロット開放
                    save.lineups.unlocked_slots = 15

                # ===== ユーザーランク =====
                elif 'ユーザーランク' in item_name:
                    if hasattr(save, 'user_rank_rewards'):
                        for reward in save.user_rank_rewards.rewards:
                            reward.claimed = True

                # ===== プレイ時間 =====
                elif 'プレイ時間カンスト' in item_name or 'プレイ時間' in item_name:
                    if hasattr(save, 'officer_pass'):
                        save.officer_pass.play_time = 2**31 - 1

                # ===== ステージ系 =====
                elif 'メインステージ全クリア' in item_name and '金お宝' not in item_name:
                    self._clear_story(save)

                elif '金お宝' in item_name:
                    # お宝を金に（メインステージクリアも込み）
                    self._clear_story(save)

                elif 'メインゾンビ' in item_name or 'ゾンビステージ' in item_name:
                    if hasattr(save, 'outbreaks'):
                        try:
                            for chap in save.outbreaks.chapters.values():
                                for stage_i in range(len(chap.stages)):
                                    try:
                                        chap.clear_stage(stage_i, 1)
                                    except:
                                        pass
                        except:
                            pass

                elif 'IDレジェンド全クリア' in item_name or 'IDレジェンドをクリア' in item_name:
                    if hasattr(save, 'uncanny'):
                        self._clear_chapters(save.uncanny.chapters)

                elif '真レジェンド全クリア' in item_name or '貴レジェンドをクリア' in item_name:
                    if hasattr(save, 'zero_legends'):
                        for map_i, chap_stars in enumerate(save.zero_legends.chapters):
                            for star_i, chap in enumerate(chap_stars.chapters):
                                for stage_i in range(len(chap.stages)):
                                    try:
                                        save.zero_legends.clear_stage(map_i, star_i, stage_i, 1)
                                    except:
                                        pass

                elif '旧レジェンド全クリア' in item_name:
                    if hasattr(save, 'catamin_stages'):
                        self._clear_chapters(save.catamin_stages.chapters)

                elif '零レジェンド全クリア' in item_name:
                    if hasattr(save, 'aku'):
                        for map_i, chap_stars in enumerate(save.aku.chapters):
                            for star_i, chap in enumerate(chap_stars.chapters):
                                for stage_i in range(len(chap.stages)):
                                    try:
                                        save.aku.clear_stage(map_i, star_i, stage_i, 1)
                                    except:
                                        pass

                elif '魔界編全クリア' in item_name:
                    if hasattr(save, 'dojo_chapters'):
                        for map_i, chap_stars in enumerate(save.dojo_chapters.chapters):
                            for star_i, chap in enumerate(chap_stars.chapters):
                                for stage_i in range(len(chap.stages)):
                                    try:
                                        save.dojo_chapters.clear_stage(map_i, star_i, stage_i, 1)
                                    except:
                                        pass

                elif 'イベントステージ全クリア' in item_name:
                    if hasattr(save, 'event_stages'):
                        try:
                            for group in save.event_stages.chapters:
                                for chap in group.chapters:
                                    for stage in chap.stages:
                                        stage.clear_amount = max(stage.clear_amount, 1)
                        except:
                            pass

            # ランクアップセール非表示（常に適用）
            if hasattr(save, 'rank_up_sale_value'):
                save.rank_up_sale_value = 0
            save.max_rank_up_sale()

            # SaveFileオブジェクトをそのまま保持（to_data()はupload時に1回だけ呼ぶ）
            self.save_object = save
            return True

        except Exception as e:
            self.last_error = f"bcsfe改造エラー: {str(e)}"
            return False

    def upload_save(self) -> Tuple[Optional[str], Optional[str]]:
        if not self.save_data and self.save_object is None:
            return None, None

        try:
            bc.core_data.init_data()

            if self.save_object is not None:
                # 改造済みSaveFileをそのまま使う（再ロード不要）
                save = self.save_object
                self.save_object = None
            else:
                # 複製など改造なしの場合はbytesから再ロード
                data = bc.Data(self.save_data)
                save = bc.SaveFile(dt=data, cc=bc.CountryCode("ja"))

            handler = bc.ServerHandler(save, print=False)
            result = handler.get_codes()

            if result is None:
                self.last_error = "アップロード失敗: サーバーエラーまたは認証失敗"
                return None, None

            transfer_code, pin = result
            return transfer_code, pin

        except Exception as e:
            self.last_error = f"アップロードエラー: {str(e)}"
            return None, None

async def setup(bot):
    pass