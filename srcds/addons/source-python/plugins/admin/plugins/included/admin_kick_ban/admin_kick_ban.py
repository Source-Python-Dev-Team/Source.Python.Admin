# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from collections import OrderedDict

import json
from time import time

# Source.Python
from core import GAME_NAME
from engines.server import server
from listeners import OnClientConnect, OnNetworkidValidated
from listeners.tick import GameThread
from memory import make_object
from memory.hooks import PostHook
from menus import PagedMenu, PagedOption, SimpleMenu, SimpleOption, Text
from players import Client
from players.entity import Player
from players.helpers import get_client_language
from steam import SteamID
from translations.manager import language_manager

# Source.Python Admin
from admin.admin import main_menu
from admin.core.clients import clients
from admin.core.features import BaseFeature, Feature, PlayerBasedFeature
from admin.core.frontends.menus import (
    AdminCommand, AdminMenuSection, PlayerBasedAdminCommand)
from admin.core.frontends.motd import (
    BaseFeaturePage, main_motd, MOTDSection, MOTDPageEntry,
    PlayerBasedFeaturePage)
from admin.core.helpers import (
    extract_ip_address, format_player_name, log_admin_action)
from admin.core.memory import custom_server
from admin.core.orm import Session
from admin.core.paths import ADMIN_CFG_PATH, get_server_file
from admin.core.plugins.strings import PluginStrings

# Included Plugin
from .config import plugin_config
from .left_player import (
    LeftPlayerBasedAdminCommand, LeftPlayerBasedFeature,
    LeftPlayerBasedFeaturePage, LeftPlayerIter)
from .models import BannedIPAddress, BannedSteamID


# =============================================================================
# >> FUNCTIONS
# =============================================================================
def find_client(steamid):
    for x in range(server.num_clients):
        client = server.get_client(x)
        if client.steamid == steamid:
            return client

    return None


def load_stock_ban_reasons():
    with open(get_server_file(
            ADMIN_CFG_PATH / "included_plugins" / "admin_kick_ban" /
            "ban_reasons.json")) as f:

        ban_reasons_json = json.load(f)

    ban_reasons = OrderedDict()
    for ban_reason_json in ban_reasons_json:
        stock_ban_reason = _StockBanReason(ban_reason_json)
        ban_reasons[stock_ban_reason.id] = stock_ban_reason

    return ban_reasons


def load_stock_ban_durations():
    with open(get_server_file(
            ADMIN_CFG_PATH / "included_plugins" / "admin_kick_ban" /
            "ban_durations.json")) as f:

        ban_durations_json = json.load(f)

    ban_durations_json.sort()

    return ban_durations_json


def format_ban_duration(seconds):
    if seconds < 0:
        return plugin_strings['duration permanent']

    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    if days:
        return plugin_strings['duration days'].tokenized(
            days=days, hours=hours, mins=minutes, secs=seconds)

    if hours:
        return plugin_strings['duration hours'].tokenized(
            hours=hours, mins=minutes, secs=seconds)

    if minutes:
        return plugin_strings['duration minutes'].tokenized(
            mins=minutes, secs=seconds)

    return plugin_strings['duration seconds'].tokenized(secs=seconds)


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
plugin_strings = PluginStrings("admin_kick_ban")
_ws_ban_steamid_pages = []
_ws_ban_ip_address_pages = []
_ws_lift_steamid_pages = []
_ws_lift_ip_address_pages = []
_ws_review_steamid_ban_pages = []
_ws_review_ip_address_ban_pages = []


# =============================================================================
# >> CLASSES
# =============================================================================
class _StockBanReason:
    def __init__(self, data):
        self.id = data['id']
        self.translation = plugin_strings[data['translation']]
        self.duration = data['suggestedBanDuration']


class _BannedPlayerInfo:
    def __init__(self, id_, name, banned_by, reviewed, expires_at, reason,
                 notes):

        self.id = id_
        self.name = name
        self.banned_by = banned_by
        self.reviewed = reviewed
        self.expires_at = expires_at
        self.reason = reason
        self.notes = notes


class _BannedUniqueIDManager(dict):
    model = None

    def _convert_uniqueid_to_db_format(self, uniqueid):
        raise NotImplementedError

    def _convert_steamid_to_db_format(self, steamid):
        return str(SteamID.parse(steamid).to_uint64())

    def refresh(self):
        self.clear()

        session = Session()

        banned_users = session.query(self.model).all()

        current_time = time()
        for banned_user in banned_users:
            if banned_user.is_unbanned:
                continue

            if -1 < banned_user.expires_at < current_time:
                continue

            self[banned_user.uniqueid] = _BannedPlayerInfo(
                banned_user.id, banned_user.name, banned_user.banned_by,
                banned_user.reviewed, banned_user.expires_at,
                banned_user.reason, banned_user.notes
            )

        session.close()

    def is_banned(self, uniqueid):
        uniqueid = self._convert_uniqueid_to_db_format(uniqueid)

        if uniqueid not in self:
            return False

        if self[uniqueid].expires_at < 0:
            return True

        if self[uniqueid].expires_at < time():
            del self[uniqueid]
            return False

        return True

    def save_ban_to_database(self, banned_by, uniqueid, name, duration):
        uniqueid = self._convert_uniqueid_to_db_format(uniqueid)
        banned_by = self._convert_steamid_to_db_format(banned_by)

        session = Session()

        banned_user = self.model(uniqueid, name, banned_by, duration)

        session.add(banned_user)
        session.commit()

        self[uniqueid] = _BannedPlayerInfo(
            banned_user.id, name, banned_by, False,
            banned_user.expires_at, "", "")

        session.close()

    def get_bans(self, banned_by=None, reviewed=None):
        if banned_by is not None:
            banned_by = self._convert_steamid_to_db_format(banned_by)

        current_time = time()

        result = []
        for uniqueid, banned_player_info in self.items():
            if (
                    banned_by is not None and
                    banned_player_info.banned_by != banned_by):

                continue

            if reviewed is False and banned_player_info.reviewed:
                continue

            if reviewed is True and not banned_player_info.reviewed:
                continue

            if banned_player_info.expires_at < current_time:
                continue

            result.append((uniqueid, banned_player_info))

        return result

    def review_ban(self, ban_id, reason, duration):
        session = Session()

        banned_user = session.query(self.model).filter_by(id=ban_id).first()

        if banned_user is None:
            session.close()
            return

        banned_user.review(reason, duration)

        session.commit()
        session.close()

        for banned_player_info in self.values():
            if banned_player_info.id != ban_id:
                continue

            banned_player_info.reviewed = True
            banned_player_info.expires_at = banned_user.expires_at
            banned_player_info.reason = reason
            break

    def lift_ban(self, ban_id, unbanned_by):
        unbanned_by = self._convert_steamid_to_db_format(unbanned_by)

        session = Session()

        banned_user = session.query(self.model).filter_by(id=ban_id).first()

        if banned_user is None:
            session.close()
            return

        banned_user.lift_ban(unbanned_by)

        session.commit()
        session.close()

        for uniqueid, banned_player_info in self.items():
            if banned_player_info.id != ban_id:
                continue

            del self[uniqueid]
            break


class _BannedSteamIDManager(_BannedUniqueIDManager):
    model = BannedSteamID

    def _convert_uniqueid_to_db_format(self, uniqueid):
        return self._convert_steamid_to_db_format(uniqueid)


# The singleton object for the _BannedSteamIDManager class.
banned_steamid_manager = _BannedSteamIDManager()


class _BannedIPAddressManager(_BannedUniqueIDManager):
    model = BannedIPAddress

    def _convert_uniqueid_to_db_format(self, uniqueid):
        return uniqueid

# The singleton object for the _BannedIPAddressManager class.
banned_ip_address_manager = _BannedIPAddressManager()


class _KickFeature(PlayerBasedFeature):
    flag = "admin.admin_kick_ban.kick"
    allow_execution_on_self = False

    def execute(self, client, player):
        language = get_client_language(player.index)
        player_name = player.name

        player.kick(plugin_strings['default_kick_reason'].get_string(language))

        log_admin_action(plugin_strings['message kicked'].tokenized(
            admin_name=client.name,
            player_name=player_name,
        ))

# The singleton object of the _KickFeature class.
kick_feature = _KickFeature()


class _BanSteamIDFeature(LeftPlayerBasedFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    allow_execution_on_self = False

    def execute(self, client, left_player):
        if left_player.is_fake_client() or left_player.is_hltv():
            client.tell(plugin_strings['error bot_cannot_ban'])
            return

        if banned_steamid_manager.is_banned(left_player.steamid):
            client.tell(plugin_strings['error already_ban_in_effect'])
            return

        try:
            player = Player.from_userid(left_player.userid)
        except (OverflowError, ValueError):
            pass
        else:
            language = get_client_language(player.index)

            # Disconnect the player
            player.kick(
                plugin_strings['default_ban_reason'].get_string(language))

        duration = int(plugin_config['settings']['default_ban_time_seconds'])

        GameThread(
            target=banned_steamid_manager.save_ban_to_database,
            args=(
                client.steamid,
                left_player.steamid,
                left_player.name,
                duration
            )
        ).start()

        for ws_ban_steamid_page in _ws_ban_steamid_pages:
            ws_ban_steamid_page.send_remove_id(left_player)

        log_admin_action(plugin_strings['message banned'].tokenized(
            admin_name=client.name,
            player_name=left_player.name,
        ))

# The singleton object of the _BanSteamIDFeature class.
ban_steamid_feature = _BanSteamIDFeature()


class _BanIPAddressFeature(LeftPlayerBasedFeature):
    flag = "admin.admin_kick_ban.ban_ip_address"
    allow_execution_on_self = False

    def execute(self, client, left_player):
        if left_player.is_fake_client() or left_player.is_hltv():
            client.tell(plugin_strings['error bot_cannot_ban'])
            return

        ip_address = extract_ip_address(left_player.address)
        if banned_ip_address_manager.is_banned(ip_address):
            client.tell(plugin_strings['error already_ban_in_effect'])
            return

        try:
            player = Player.from_userid(left_player.userid)
        except (OverflowError, ValueError):
            pass
        else:
            language = get_client_language(player.index)

            # Disconnect the player
            player.kick(
                plugin_strings['default_ban_reason'].get_string(language))

        duration = int(plugin_config['settings']['default_ban_time_seconds'])

        GameThread(
            target=banned_ip_address_manager.save_ban_to_database,
            args=(client.steamid, ip_address, left_player.name, duration)
        ).start()

        for ws_ban_ip_address_page in _ws_ban_ip_address_pages:
            ws_ban_ip_address_page.send_remove_id(left_player)

        log_admin_action(plugin_strings['message banned'].tokenized(
            admin_name=client.name,
            player_name=left_player.name,
        ))

# The singleton object of the _BanIPAddressFeature class.
ban_ip_address_feature = _BanIPAddressFeature()


class _LiftBanMOTDFeature(BaseFeature):
    feature_abstract = True
    banned_uniqueid_manager = None
    ws_lift_ban_pages = None

    def get_bans(self, client):
        bans = self.banned_uniqueid_manager.get_bans(
            banned_by=client.steamid, reviewed=False)

        for uniqueid, banned_player_info in bans:
            yield uniqueid, banned_player_info

    def get_ban_by_id(self, client, ban_id):
        for uniqueid, banned_player_info in self.get_bans(client):
            if banned_player_info.id == ban_id:
                return banned_player_info
        return None

    def execute(self, client, ban_id, player_name):
        GameThread(
            target=self.banned_uniqueid_manager.lift_ban,
            args=(ban_id, client.steamid)
        ).start()

        for ws_lift_ban_page in self.ws_lift_ban_pages:
            ws_lift_ban_page.send_remove_ban_id(ban_id)

        log_admin_action(plugin_strings['message ban_lifted'].tokenized(
            admin_name=client.name,
            player_name=player_name,
        ))


class _LiftSteamIDBanMOTDFeature(_LiftBanMOTDFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    banned_uniqueid_manager = banned_steamid_manager
    ws_lift_ban_pages = _ws_lift_steamid_pages

# The singleton object of the _LiftSteamIDBanMOTDFeature class.
lift_steamid_ban_motd_feature = _LiftSteamIDBanMOTDFeature()


class _LiftIPAddressBanMOTDFeature(_LiftBanMOTDFeature):
    flag = "admin.admin_kick_ban.ban_ip_address"
    banned_uniqueid_manager = banned_ip_address_manager
    ws_lift_ban_pages = _ws_lift_ip_address_pages

# The singleton object of the _LiftSteamIDBanMOTDFeature class.
lift_ip_address_ban_motd_feature = _LiftIPAddressBanMOTDFeature()


class _LiftBanPopupFeature(Feature):
    feature_abstract = True
    popup_title = None
    banned_uniqueid_manager = None

    def __init__(self):
        self.ban_popup = PagedMenu(title=self.popup_title)

        @self.ban_popup.register_build_callback
        def build_callback(popup, index):
            client = clients[index]
            popup.clear()

            bans = self.banned_uniqueid_manager.get_bans(
                banned_by=client.steamid, reviewed=False)

            for uniqueid, banned_player_info in bans:
                popup.append(PagedOption(
                    text=plugin_strings['ban_record'].tokenized(
                        id=uniqueid, name=format_player_name(
                            banned_player_info.name)),
                    value=banned_player_info
                ))

        @self.ban_popup.register_select_callback
        def select_callback(popup, index, option):
            client = clients[index]

            GameThread(
                target=self.banned_uniqueid_manager.lift_ban,
                args=(option.value.id, client.steamid)
            ).start()

            log_admin_action(plugin_strings['message ban_lifted'].tokenized(
                admin_name=client.name,
                player_name=option.value.name,
            ))

    def execute(self, client):
        client.send_popup(self.ban_popup)


class _LiftSteamIDBanPopupFeature(_LiftBanPopupFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    popup_title = plugin_strings['popup_title lift_steamid']
    banned_uniqueid_manager = banned_steamid_manager

# The singleton object of the _LiftSteamIDBanPopupFeature class.
lift_steamid_ban_popup_feature = _LiftSteamIDBanPopupFeature()


class _LiftIPAddressBanPopupFeature(_LiftBanPopupFeature):
    flag = "admin.admin_kick_ban.ban_ip_address"
    popup_title = plugin_strings['popup_title lift_ip_address']
    banned_uniqueid_manager = banned_ip_address_manager

# The singleton object of the _LiftIPAddressBanPopupFeature class.
lift_ip_address_ban_popup_feature = _LiftIPAddressBanPopupFeature()


class _LiftReviewedBanPopupFeature(Feature):
    feature_abstract = True
    popup_title = None
    banned_uniqueid_manager = None

    def __init__(self):
        # (_BannedPlayerInfo instance, IP/SteamID, whether confirmed or not)
        self._selected_ban = (None, "", False)

        self.ban_popup = PagedMenu(title=self.popup_title)
        self.confirm_popup = SimpleMenu()

        @self.ban_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            # Get all bans
            bans = self.banned_uniqueid_manager.get_bans()

            for uniqueid, banned_player_info in bans:
                popup.append(PagedOption(
                    text=plugin_strings['ban_record'].tokenized(
                        id=uniqueid, name=format_player_name(
                            banned_player_info.name)),
                    value=(banned_player_info, uniqueid, False)
                ))

        @self.ban_popup.register_select_callback
        def select_callback(popup, index, option):
            self._selected_ban = option.value
            clients[index].send_popup(self.confirm_popup)

        @self.confirm_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            popup.append(Text(plugin_strings['ban_record'].tokenized(
                name=self._selected_ban[0].name, id=self._selected_ban[1])))

            popup.append(Text(
                plugin_strings['ban_record admin_steamid'].tokenized(
                    admin_steamid=self._selected_ban[0].banned_by)))

            popup.append(Text(plugin_strings['ban_record reason'].tokenized(
                reason=self._selected_ban[0].reason)))

            if self._selected_ban[0].notes:
                popup.append(Text(plugin_strings['ban_record notes'].tokenized(
                    notes=self._selected_ban[0].notes)))

            popup.append(SimpleOption(
                choice_index=1,
                text=plugin_strings['lift_reviewed_ban_confirmation no'],
                value=(self._selected_ban[0], self._selected_ban[1], False),
            ))
            popup.append(SimpleOption(
                choice_index=2,
                text=plugin_strings['lift_reviewed_ban_confirmation yes'],
                value=(self._selected_ban[0], self._selected_ban[1], True),
            ))

        @self.confirm_popup.register_select_callback
        def select_callback(popup, index, option):
            if not option.value[2]:
                return

            client = clients[index]

            GameThread(
                target=self.banned_uniqueid_manager.lift_ban,
                args=(option.value[0].id, client.steamid)
            ).start()

            log_admin_action(plugin_strings['message ban_lifted'].tokenized(
                admin_name=client.name,
                player_name=option.value[0].name,
            ))

    def execute(self, client):
        client.send_popup(self.ban_popup)


class _LiftReviewedSteamIDBanPopupFeature(_LiftReviewedBanPopupFeature):
    flag = "admin.admin_kick_ban.lift_reviewed_steamid"
    popup_title = plugin_strings['popup_title lift_reviewed_steamid']
    banned_uniqueid_manager = banned_steamid_manager

# The singleton object of the _LiftReviewedSteamIDBanPopupFeature class.
lift_reviewed_steamid_ban_popup_feature = _LiftReviewedSteamIDBanPopupFeature()


class _LiftReviewedIPAddressBanPopupFeature(_LiftReviewedBanPopupFeature):
    flag = "admin.admin_kick_ban.lift_reviewed_ip_address"
    popup_title = plugin_strings['popup_title lift_reviewed_ip_address']
    banned_uniqueid_manager = banned_ip_address_manager

# The singleton object of the _LiftReviewedIPAddressBanPopupFeature class.
lift_reviewed_ip_address_ban_popup_feature = (
    _LiftReviewedIPAddressBanPopupFeature())


class _ReviewBanMOTDFeature(BaseFeature):
    feature_abstract = True
    banned_uniqueid_manager = None
    ws_review_ban_pages = None

    def get_bans(self, client):
        bans = self.banned_uniqueid_manager.get_bans(
            banned_by=client.steamid, reviewed=False)

        for uniqueid, banned_player_info in bans:
            yield uniqueid, banned_player_info

    def get_ban_by_id(self, client, ban_id):
        for uniqueid, banned_player_info in self.get_bans(client):
            if banned_player_info.id == ban_id:
                return banned_player_info
        return None

    def execute(self, client, ban_id, reason, duration, player_name):
        GameThread(
            target=self.banned_uniqueid_manager.review_ban,
            args=(ban_id, reason, duration)
        ).start()

        for ws_review_ban_page in self.ws_review_ban_pages:
            ws_review_ban_page.send_remove_ban_id(ban_id)

        log_admin_action(plugin_strings['message ban_reviewed'].tokenized(
            admin_name=client.name,
            player_name=player_name,
            duration=format_ban_duration(duration)
        ))


class _ReviewSteamIDBanMOTDFeature(_ReviewBanMOTDFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    banned_uniqueid_manager = banned_steamid_manager
    ws_review_ban_pages = _ws_review_steamid_ban_pages

# The singleton object of the _ReviewSteamIDBanMOTDFeature class.
review_steamid_ban_motd_feature = _ReviewSteamIDBanMOTDFeature()


class _ReviewIPAddressBanMOTDFeature(_ReviewBanMOTDFeature):
    flag = "admin.admin_kick_ban.ban_ip_address"
    banned_uniqueid_manager = banned_ip_address_manager
    ws_review_ban_pages = _ws_review_ip_address_ban_pages

# The singleton object of the _ReviewIPAddressBanMOTDFeature class.
review_ip_address_ban_motd_feature = _ReviewIPAddressBanMOTDFeature()


class _ReviewBanPopupFeature(Feature):
    feature_abstract = True
    popup_title = None
    banned_uniqueid_manager = None

    def __init__(self):
        # (_BannedPlayerInfo instance, reason, duration)
        self._selected_ban = (None, "", -1)

        self.ban_popup = PagedMenu(title=self.popup_title)
        self.reason_popup = PagedMenu(title=self.popup_title,
                                      parent_menu=self.ban_popup)

        # We do not allow returning back to reason popup from duration popup,
        # because we won't have valid self._selected_ban to build a reason
        # popup with. Hence we don't provide parent_menu here.
        self.duration_popup = PagedMenu(title=self.popup_title)

        @self.ban_popup.register_build_callback
        def build_callback(popup, index):
            client = clients[index]
            popup.clear()

            bans = self.banned_uniqueid_manager.get_bans(
                banned_by=client.steamid, reviewed=False)

            for uniqueid, banned_player_info in bans:
                popup.append(PagedOption(
                    text=plugin_strings['ban_record'].tokenized(
                        id=uniqueid, name=format_player_name(
                            banned_player_info.name)),
                    value=(banned_player_info, "", -1)
                ))

        @self.ban_popup.register_select_callback
        def select_callback(popup, index, option):
            self._selected_ban = option.value
            clients[index].send_popup(self.reason_popup)

        @self.reason_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            for stock_ban_reason in stock_ban_reasons.values():
                popup.append(PagedOption(
                    text=stock_ban_reason.translation,
                    value=(
                        self._selected_ban[0],
                        stock_ban_reason.translation.get_string(
                            language_manager.default),
                        stock_ban_reason.duration,
                    )
                ))

        @self.reason_popup.register_select_callback
        def select_callback(popup, index, option):
            self._selected_ban = option.value
            clients[index].send_popup(self.duration_popup)

        @self.duration_popup.register_build_callback
        def build_callback(popup, index):
            popup.clear()

            if self._selected_ban[2] is not None:
                popup.append(PagedOption(
                    text=plugin_strings['default_duration'].tokenized(
                        default=format_ban_duration(self._selected_ban[2])),
                    value=self._selected_ban
                ))

            for stock_ban_duration in stock_ban_durations:
                popup.append(PagedOption(
                    text=format_ban_duration(stock_ban_duration),
                    value=(
                        self._selected_ban[0],
                        self._selected_ban[1],
                        stock_ban_duration,
                    )
                ))

        @self.duration_popup.register_select_callback
        def select_callback(popup, index, option):
            client = clients[index]

            GameThread(
                target=self.banned_uniqueid_manager.review_ban,
                args=(option.value[0].id, option.value[1], option.value[2])
            ).start()

            log_admin_action(plugin_strings['message ban_reviewed'].tokenized(
                admin_name=client.name,
                player_name=option.value[0].name,
                duration=format_ban_duration(option.value[2])
            ))

    def execute(self, client):
        client.send_popup(self.ban_popup)


class _ReviewSteamIDBanPopupFeature(_ReviewBanPopupFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    popup_title = plugin_strings['popup_title review_steamid']
    banned_uniqueid_manager = banned_steamid_manager

# The singleton object of the _ReviewSteamIDBanPopupFeature class.
review_steamid_ban_popup_feature = _ReviewSteamIDBanPopupFeature()


class _ReviewIPAddressBanPopupFeature(_ReviewBanPopupFeature):
    flag = "admin.admin_kick_ban.ban_ip_address"
    popup_title = plugin_strings['popup_title review_ip_address']
    banned_uniqueid_manager = banned_ip_address_manager

# The singleton object of the _ReviewSteamIDBanPopupFeature class.
review_ip_address_ban_popup_feature = _ReviewIPAddressBanPopupFeature()


class _KickMenuCommand(PlayerBasedAdminCommand):
    allow_multiple_choices = False


class _BanSteamIDMenuCommand(LeftPlayerBasedAdminCommand):
    base_filter = 'human'
    allow_multiple_choices = False

    @staticmethod
    def render_player_name(left_player):
        return plugin_strings['player_name'].tokenized(
            name=format_player_name(left_player.name),
            id=left_player.steamid
        )

    def _iter(self):
        for left_player in LeftPlayerIter(self.base_filter):
            if banned_steamid_manager.is_banned(left_player.steamid):
                continue

            yield left_player


class _BanIPAddressMenuCommand(LeftPlayerBasedAdminCommand):
    base_filter = 'human'
    allow_multiple_choices = False

    @staticmethod
    def render_player_name(left_player):
        return plugin_strings['player_name'].tokenized(
            name=format_player_name(left_player.name),
            id=extract_ip_address(left_player.address)
        )

    def _iter(self):
        for left_player in LeftPlayerIter(self.base_filter):
            ip_address = extract_ip_address(left_player.address)
            if banned_ip_address_manager.is_banned(ip_address):
                continue

            yield left_player


class _KickPage(PlayerBasedFeaturePage):
    admin_plugin_id = "admin_kick_ban"
    admin_plugin_type = "included"
    page_id = "kick"

    feature = kick_feature
    _base_filter = 'all'
    _ws_base_filter = 'all'


class _BanSteamIDPage(LeftPlayerBasedFeaturePage):
    admin_plugin_id = "admin_kick_ban"
    admin_plugin_type = "included"
    page_id = "ban_steamid"

    feature = ban_steamid_feature
    _base_filter = 'human'
    _ws_base_filter = 'human'

    def __init__(self, index, page_request_type):
        super().__init__(index, page_request_type)

        if self.is_websocket:
            _ws_ban_steamid_pages.append(self)

    def filter(self, left_player):
        if not super().filter(left_player):
            return False

        if banned_steamid_manager.is_banned(left_player.steamid):
            return False

        return True

    def on_error(self, error):
        super().on_error(error)

        if self.is_websocket and self in _ws_ban_steamid_pages:
            _ws_ban_steamid_pages.remove(self)


class _BanIPAddressPage(LeftPlayerBasedFeaturePage):
    admin_plugin_id = "admin_kick_ban"
    admin_plugin_type = "included"
    page_id = "ban_ip_address"

    feature = ban_ip_address_feature
    _base_filter = 'human'
    _ws_base_filter = 'human'

    def __init__(self, index, page_request_type):
        super().__init__(index, page_request_type)

        if self.is_websocket:
            _ws_ban_ip_address_pages.append(self)

    def filter(self, left_player):
        if not super().filter(left_player):
            return False

        ip_address = extract_ip_address(left_player.address)
        if banned_ip_address_manager.is_banned(ip_address):
            return False

        return True

    def on_error(self, error):
        super().on_error(error)

        if self.is_websocket and self in _ws_ban_ip_address_pages:
            _ws_ban_ip_address_pages.remove(self)


class _BaseBanPage(BaseFeaturePage):
    abstract = True
    page_abstract = True
    feature_page_abstract = True

    def send_remove_ban_id(self, ban_id):
        self.send_data({
            'action': 'remove-ban-id',
            'banId': ban_id,
        })


class _LiftBanPage(_BaseBanPage):
    abstract = True
    page_abstract = True
    feature_page_abstract = True

    def on_page_data_received(self, data):
        client = clients[self.index]

        if data['action'] == "execute":
            ban_id = data['banId']

            banned_player_info = self.feature.get_ban_by_id(client, ban_id)
            if banned_player_info is None:

                # Might just as well log the ban id and the client, looks like
                # this client has tried to lift somebody else's ban
                return

            client.sync_execution(self.feature.execute, (
                client, banned_player_info.id, banned_player_info.name))

            self.send_data({
                'feature-executed': "scheduled"
            })
            return

        if data['action'] == "get-bans":
            ban_data = []

            for uniqueid, banned_player_info in self.feature.get_bans(client):
                ban_data.append({
                    'uniqueid': str(uniqueid),
                    'banId': banned_player_info.id,
                    'name': banned_player_info.name,
                })

            self.send_data({
                'action': "bans",
                'bans': ban_data,
            })


class _LiftSteamIDBanPage(_LiftBanPage):
    admin_plugin_id = "admin_kick_ban"
    admin_plugin_type = "included"
    page_id = "lift_steamid"
    feature = lift_steamid_ban_motd_feature

    def __init__(self, index, page_request_type):
        super().__init__(index, page_request_type)

        if self.is_websocket:
            _ws_lift_steamid_pages.append(self)

    def on_error(self, error):
        super().on_error(error)

        if self.is_websocket and self in _ws_lift_steamid_pages:
            _ws_lift_steamid_pages.remove(self)


class _LiftIPAddressBanPage(_LiftBanPage):
    admin_plugin_id = "admin_kick_ban"
    admin_plugin_type = "included"
    page_id = "lift_ip_address"
    feature = lift_ip_address_ban_motd_feature

    def __init__(self, index, page_request_type):
        super().__init__(index, page_request_type)

        if self.is_websocket:
            _ws_lift_ip_address_pages.append(self)

    def on_error(self, error):
        super().on_error(error)

        if self.is_websocket and self in _ws_lift_ip_address_pages:
            _ws_lift_ip_address_pages.remove(self)


class _ReviewBanPage(_BaseBanPage):
    abstract = True
    page_abstract = True
    feature_page_abstract = True

    def on_page_data_received(self, data):
        client = clients[self.index]

        if data['action'] == "execute":
            ban_id = data['banId']
            reason = data['reason']
            duration = data['duration']

            banned_player_info = self.feature.get_ban_by_id(client, ban_id)
            if banned_player_info is None:
                # Might just as well log the ban id and the client, looks like
                # this client has tried to lift somebody else's ban
                return

            client.sync_execution(self.feature.execute, (
                client, banned_player_info.id, reason, duration,
                banned_player_info.name))

            self.send_data({
                'feature-executed': "scheduled"
            })
            return

        if data['action'] == "get-ban-data":
            language = get_client_language(self.index)

            ban_durations = []
            for stock_ban_duration in stock_ban_durations:
                ban_durations.append({
                    'value': stock_ban_duration,
                    'title': format_ban_duration(
                        stock_ban_duration).get_string(language),
                })

            ban_reasons = []
            for stock_ban_reason in stock_ban_reasons.values():
                duration_value = stock_ban_reason.duration
                duration_title = (
                    None if duration_value is None else
                    format_ban_duration(duration_value).get_string(language))

                ban_reasons.append({
                    'hidden': stock_ban_reason.translation.get_string(
                                language_manager.default),
                    'title': stock_ban_reason.translation.get_string(language),
                    'duration-value': duration_value,
                    'duration-title': duration_title,
                })

            ban_data = []
            for uniqueid, banned_player_info in self.feature.get_bans(client):
                ban_data.append({
                    'uniqueid': str(uniqueid),
                    'banId': banned_player_info.id,
                    'name': banned_player_info.name,
                })

            self.send_data({
                'action': "ban-data",
                'bans': ban_data,
                'reasons': ban_reasons,
                'durations': ban_durations,
            })


class _ReviewSteamIDBanPage(_ReviewBanPage):
    admin_plugin_id = "admin_kick_ban"
    admin_plugin_type = "included"
    page_id = "review_steamid"
    feature = review_steamid_ban_motd_feature

    def __init__(self, index, page_request_type):
        super().__init__(index, page_request_type)

        if self.is_websocket:
            _ws_review_steamid_ban_pages.append(self)

    def on_error(self, error):
        super().on_error(error)

        if self.is_websocket and self in _ws_review_steamid_ban_pages:
            _ws_review_steamid_ban_pages.remove(self)


class _ReviewIPAddressBanPage(_ReviewBanPage):
    admin_plugin_id = "admin_kick_ban"
    admin_plugin_type = "included"
    page_id = "review_ip_address"
    feature = review_ip_address_ban_motd_feature

    def __init__(self, index, page_request_type):
        super().__init__(index, page_request_type)

        if self.is_websocket:
            _ws_review_ip_address_ban_pages.append(self)

    def on_error(self, error):
        super().on_error(error)

        if self.is_websocket and self in _ws_review_ip_address_ban_pages:
            _ws_review_ip_address_ban_pages.remove(self)


# =============================================================================
# >> MENU ENTRIES
# =============================================================================
stock_ban_reasons = load_stock_ban_reasons()
stock_ban_durations = load_stock_ban_durations()

menu_section = main_menu.add_entry(AdminMenuSection(
    main_menu, plugin_strings['section_title main']))

menu_section_steamid = menu_section.add_entry(AdminMenuSection(
    menu_section, plugin_strings['section_title steamid_bans']))

menu_section_ip_address = menu_section.add_entry(AdminMenuSection(
    menu_section, plugin_strings['section_title ip_address_bans']))

lift_steamid_ban_popup_feature.ban_popup.parent_menu = (
    menu_section_steamid.popup)
lift_ip_address_ban_popup_feature.ban_popup.parent_menu = (
    menu_section_ip_address.popup)
lift_reviewed_steamid_ban_popup_feature.ban_popup.parent_menu = (
    menu_section_steamid.popup)
lift_reviewed_ip_address_ban_popup_feature.ban_popup.parent_menu = (
    menu_section_ip_address.popup)
review_steamid_ban_popup_feature.ban_popup.parent_menu = (
    menu_section_steamid.popup)
review_ip_address_ban_popup_feature.ban_popup.parent_menu = (
    menu_section_ip_address.popup)

menu_section.add_entry(_KickMenuCommand(
    kick_feature,
    menu_section,
    plugin_strings['popup_title kick']
))
menu_section_steamid.add_entry(_BanSteamIDMenuCommand(
    ban_steamid_feature,
    menu_section_steamid,
    plugin_strings['popup_title ban_steamid']))

menu_section_ip_address.add_entry(_BanIPAddressMenuCommand(
    ban_ip_address_feature,
    menu_section_ip_address,
    plugin_strings['popup_title ban_ip_address']))

menu_section_steamid.add_entry(AdminCommand(
    review_steamid_ban_popup_feature,
    menu_section_steamid,
    plugin_strings['popup_title review_steamid']))

menu_section_ip_address.add_entry(AdminCommand(
    review_ip_address_ban_popup_feature,
    menu_section_ip_address,
    plugin_strings['popup_title review_ip_address']))

menu_section_steamid.add_entry(AdminCommand(
    lift_steamid_ban_popup_feature,
    menu_section_steamid,
    plugin_strings['popup_title lift_steamid']))

menu_section_ip_address.add_entry(AdminCommand(
    lift_ip_address_ban_popup_feature,
    menu_section_ip_address,
    plugin_strings['popup_title lift_ip_address']))

menu_section_steamid.add_entry(AdminCommand(
    lift_reviewed_steamid_ban_popup_feature,
    menu_section_steamid,
    plugin_strings['popup_title lift_reviewed_steamid']))

menu_section_ip_address.add_entry(AdminCommand(
    lift_reviewed_ip_address_ban_popup_feature,
    menu_section_ip_address,
    plugin_strings['popup_title lift_reviewed_ip_address']))


# =============================================================================
# >> MOTD ENTRIES
# =============================================================================
motd_section = main_motd.add_entry(MOTDSection(
    main_motd, plugin_strings['section_title main'], 'kick_ban'))

motd_section_steamid = motd_section.add_entry(MOTDSection(
    motd_section, plugin_strings['section_title steamid_bans'], 'steamid'))

motd_section_ip_address = motd_section.add_entry(MOTDSection(
    motd_section, plugin_strings['section_title ip_address_bans'],
    'ip_address'))

motd_section.add_entry(MOTDPageEntry(
    motd_section, _KickPage, plugin_strings['popup_title kick'], 'kick'))

motd_section_steamid.add_entry(MOTDPageEntry(
    motd_section_steamid, _BanSteamIDPage,
    plugin_strings['popup_title ban_steamid'], 'ban_steamid'))

motd_section_ip_address.add_entry(MOTDPageEntry(
    motd_section_ip_address, _BanIPAddressPage,
    plugin_strings['popup_title ban_ip_address'], 'ban_ip_address'))

motd_section_steamid.add_entry(MOTDPageEntry(
    motd_section_steamid, _LiftSteamIDBanPage,
    plugin_strings['popup_title lift_steamid'], 'lift_steamid'))

motd_section_ip_address.add_entry(MOTDPageEntry(
    motd_section_ip_address, _LiftIPAddressBanPage,
    plugin_strings['popup_title lift_ip_address'], 'lift_ip_address'))

motd_section_steamid.add_entry(MOTDPageEntry(
    motd_section_steamid, _ReviewSteamIDBanPage,
    plugin_strings['popup_title review_steamid'], 'review_steamid'))

motd_section_ip_address.add_entry(MOTDPageEntry(
    motd_section_ip_address, _ReviewIPAddressBanPage,
    plugin_strings['popup_title review_ip_address'], 'review_ip_address'))


# =============================================================================
# >> SYNCHRONOUS DATABASE OPERATIONS
# =============================================================================
banned_steamid_manager.refresh()
banned_ip_address_manager.refresh()


# =============================================================================
# >> LISTENERS
# =============================================================================
@OnNetworkidValidated
def listener_on_networkid_validated(name, steamid):
    if not banned_steamid_manager.is_banned(steamid):
        return

    client = find_client(steamid)
    if client is None:
        return

    client.disconnect(plugin_strings['default_ban_reason'].get_string(
        language_manager.default))


@OnClientConnect
def listener_on_client_connect(
        allow_connect, index, name, address, reject_message, max_reject_len):

    ip_address = extract_ip_address(address)
    if not banned_ip_address_manager.is_banned(ip_address):
        return

    allow_connect.set_bool(False)

    reason = plugin_strings['default_ban_reason'].get_string(
        language_manager.default)
    reason = reason.encode('utf-8')[:max_reject_len].decode('utf-8', 'ignore')

    reject_message.set_string_array(reason)


# =============================================================================
# >> HOOKS
# =============================================================================
@PostHook(custom_server.check_challenge_type)
def post_check_challenge_type(args, return_value=0):
    client = make_object(Client, args[1] + 4)
    if not banned_steamid_manager.is_banned(client.steamid):
        return

    if GAME_NAME == 'csgo':
        custom_server.reject_connection(
            args[3],
            plugin_strings['default_ban_reason'].get_string(
                language_manager.default)
        )
    else:
        custom_server.reject_connection(
            args[3], args[7],
            plugin_strings['default_ban_reason'].get_string(
                language_manager.default)
        )

    return False
