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
from events import Event
from listeners import OnClientConnect, OnNetworkidValidated
from listeners.tick import GameThread
from memory import make_object
from memory.hooks import PostHook
from menus import PagedMenu, PagedOption
from players import Client
from players.helpers import get_client_language
from translations.manager import language_manager

# Source.Python Admin
from admin.admin import main_menu
from admin.core.clients import clients
from admin.core.config import config
from admin.core.features import Feature, PlayerBasedFeature
from admin.core.frontends.menus import (
    AdminCommand, AdminMenuSection, PlayerBasedAdminCommand)
from admin.core.helpers import format_player_name, log_admin_action
from admin.core.memory import custom_server
from admin.core.orm import Session
from admin.core.paths import ADMIN_DATA_PATH
from admin.core.plugins.strings import PluginStrings

# Included Plugin
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


def extract_ip_address(address):

    # We don't just do address.split(':')[0] - because that'd drop IPv6 support
    port_pos = address.rfind(':')
    return address[:port_pos]


def load_stock_ban_reasons():
    with open(ADMIN_DATA_PATH / "included_plugins" /
              "admin_kick_ban" / "ban_reasons.json") as f:

        ban_reasons_json = json.load(f)

    try:
        with open(ADMIN_DATA_PATH / "included_plugins" /
                  "admin_kick_ban" / "ban_reasons_server.json") as f:

            ban_reasons_server_json = json.load(f)

    except FileNotFoundError:
        ban_reasons_server_json = []

    ban_reasons = OrderedDict()
    for ban_reason_json in ban_reasons_json:
        stock_ban_reason = _StockBanReason(ban_reason_json)
        ban_reasons[stock_ban_reason.id] = stock_ban_reason

    for ban_reason_json in ban_reasons_server_json:
        stock_ban_reason = _StockBanReason(ban_reason_json)
        ban_reasons[stock_ban_reason.id] = stock_ban_reason

    return ban_reasons


def load_stock_ban_durations():
    with open(ADMIN_DATA_PATH / "included_plugins" /
              "admin_kick_ban" / "ban_durations.json") as f:

        ban_durations_json = json.load(f)

    try:
        with open(ADMIN_DATA_PATH / "included_plugins" /
                  "admin_kick_ban" / "ban_durations_server.json") as f:

            ban_durations_server_json = json.load(f)

    except FileNotFoundError:
        ban_durations_server_json = []

    ban_durations = ban_durations_json + ban_durations_server_json
    ban_durations.sort()

    return ban_durations


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


# =============================================================================
# >> CLASSES
# =============================================================================
class _StockBanReason:
    def __init__(self, data):
        self.id = data['id']
        self.translation = plugin_strings[data['translation']]
        self.duration = data['suggestedBanDuration']


class _BannedPlayerInfo:
    def __init__(self, id_, name, admin_steamid, reviewed, expires_timestamp):
        self.id = id_
        self.name = name
        self.admin_steamid = admin_steamid
        self.reviewed = reviewed
        self.expires_timestamp = expires_timestamp


class _BannedUniqueIDManager(dict):
    def refresh(self):
        raise NotImplementedError

    def is_banned(self, uniqueid):
        if uniqueid not in self:
            return False

        if self[uniqueid].expires_timestamp < 0:
            return True

        if self[uniqueid].expires_timestamp < time():
            del self[uniqueid]
            return False

        return True

    def save_ban_to_database(self, client, uniqueid, name, duration):
        raise NotImplementedError

    def get_unreviewed_bans_for_admin(self, admin_steamid):
        current_time = time()

        result = []
        for uniqueid, banned_player_info in self.items():
            if banned_player_info.admin_steamid != admin_steamid:
                continue

            if banned_player_info.reviewed:
                continue

            if banned_player_info.expires_timestamp < current_time:
                continue

            result.append((uniqueid, banned_player_info))

        return result

    def review_ban(self, ban_id, reason, duration):
        raise NotImplementedError

    def lift_ban(self, ban_id):
        raise NotImplementedError


class _BannedSteamIDManager(_BannedUniqueIDManager):
    def refresh(self):
        self.clear()

        session = Session()

        banned_users = session.query(BannedSteamID).all()

        current_time = time()
        for banned_user in banned_users:
            if banned_user.unbanned:
                continue

            if -1 < banned_user.expires_timestamp < current_time:
                continue

            self[banned_user.steamid] = _BannedPlayerInfo(
                banned_user.id, banned_user.name, banned_user.admin_steamid,
                banned_user.reviewed, banned_user.expires_timestamp)

        session.close()

    def save_ban_to_database(self, client, uniqueid, name, duration):
        session = Session()

        banned_steamid = BannedSteamID()
        session.add(banned_steamid)

        current_time = time()
        banned_steamid.steamid = uniqueid
        banned_steamid.name = name
        banned_steamid.admin_steamid = client.player.steamid
        banned_steamid.reviewed = False
        banned_steamid.banned_timestamp = current_time
        banned_steamid.expires_timestamp = current_time + duration
        banned_steamid.unbanned = False
        banned_steamid.reason = ""
        banned_steamid.notes = ""

        session.commit()

        self[uniqueid] = _BannedPlayerInfo(
            banned_steamid.id, name, client.player.steamid, False,
            current_time + duration)

        session.close()

    def review_ban(self, ban_id, reason, duration):
        session = Session()

        banned_steamid = session.query(
            BannedSteamID).filter_by(id=ban_id).first()

        if banned_steamid is None:
            session.close()
            return

        current_time = time()

        banned_steamid.reviewed = True
        banned_steamid.expires_timestamp = current_time + duration
        banned_steamid.reason = reason

        session.commit()
        session.close()

        for banned_player_info in self.values():
            if banned_player_info.id != ban_id:
                continue

            banned_player_info.reviewed = True
            banned_player_info.expires_timestamp = current_time + duration
            break

    def lift_ban(self, ban_id):
        session = Session()

        banned_steamid = session.query(
            BannedSteamID).filter_by(id=ban_id).first()

        if banned_steamid is None:
            session.close()
            return

        banned_steamid.unbanned = True

        session.commit()
        session.close()

        for steamid, banned_player_info in self.items():
            if banned_player_info.id != ban_id:
                continue

            del self[steamid]
            break


# The singleton object for the _BannedSteamIDManager class.
banned_steamid_manager = _BannedSteamIDManager()


class _BannedIPAddressManager(_BannedUniqueIDManager):
    def refresh(self):
        self.clear()

        session = Session()

        banned_users = session.query(BannedIPAddress).all()

        current_time = time()
        for banned_user in banned_users:
            if banned_user.unbanned:
                continue

            if -1 < banned_user.expires_timestamp < current_time:
                continue

            self[banned_user.ip_address] = _BannedPlayerInfo(
                banned_user.id, banned_user.name, banned_user.admin_steamid,
                banned_user.reviewed, banned_user.expires_timestamp)

        session.close()

    def save_ban_to_database(self, client, uniqueid, name, duration):
        session = Session()

        banned_ip_address = BannedIPAddress()
        session.add(banned_ip_address)

        current_time = time()
        banned_ip_address.ip_address = uniqueid
        banned_ip_address.name = name
        banned_ip_address.admin_steamid = client.player.steamid
        banned_ip_address.reviewed = False
        banned_ip_address.banned_timestamp = current_time
        banned_ip_address.expires_timestamp = current_time + duration
        banned_ip_address.unbanned = False
        banned_ip_address.reason = ""
        banned_ip_address.notes = ""

        session.commit()

        self[uniqueid] = _BannedPlayerInfo(
            banned_ip_address.id, name, client.player.steamid, False,
            current_time + duration)

        session.close()

    def review_ban(self, ban_id, reason, duration):
        session = Session()

        banned_ip_address = session.query(
            BannedIPAddress).filter_by(id=ban_id).first()

        if banned_ip_address is None:
            session.close()
            return

        current_time = time()

        banned_ip_address.reviewed = True
        banned_ip_address.expires_timestamp = current_time + duration
        banned_ip_address.reason = reason

        session.commit()
        session.close()

        for banned_player_info in self.values():
            if banned_player_info.id != ban_id:
                continue

            banned_player_info.reviewed = True
            banned_player_info.expires_timestamp = current_time + duration
            break

    def lift_ban(self, ban_id):
        session = Session()

        banned_ip_address = session.query(
            BannedIPAddress).filter_by(id=ban_id).first()

        if banned_ip_address is None:
            session.close()
            return

        banned_ip_address.unbanned = True

        session.commit()
        session.close()

        for ip_address, banned_player_info in self.items():
            if banned_player_info.id != ban_id:
                continue

            del self[ip_address]
            break

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
            admin_name=client.player.name,
            player_name=player_name,
        ))

# The singleton object of the _KickFeature class.
kick_feature = _KickFeature()


class _BanSteamIDFeature(PlayerBasedFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    allow_execution_on_self = False

    def execute(self, client, player):
        if player.is_fake_client():
            client.tell(plugin_strings['error bot_cannot_ban'])
            return

        if banned_steamid_manager.is_banned(player.steamid):
            client.tell(plugin_strings['error already_ban_in_effect'])
            return

        language = get_client_language(player.index)

        # Save player name and SteamID so that we don't crash when accessing
        # properties of a disconnected player
        player_name = player.name
        player_steamid = player.steamid

        # Disconnect the player
        player.kick(plugin_strings['default_ban_reason'].get_string(language))

        duration = int(config['settings']['default_ban_time_seconds'])

        GameThread(
            target=banned_steamid_manager.save_ban_to_database,
            args=(client, player_steamid, player_name, duration)
        ).start()

        log_admin_action(plugin_strings['message banned'].tokenized(
            admin_name=client.player.name,
            player_name=player_name,
        ))

# The singleton object of the _BanSteamIDFeature class.
ban_steamid_feature = _BanSteamIDFeature()


class _BanIPAddressFeature(PlayerBasedFeature):
    flag = "admin.admin_kick_ban.ban_ip_address"
    allow_execution_on_self = False

    def execute(self, client, player):
        if player.is_fake_client():
            client.tell(plugin_strings['error bot_cannot_ban'])
            return

        ip_address = extract_ip_address(player.address)
        if banned_ip_address_manager.is_banned(ip_address):
            client.tell(plugin_strings['error already_ban_in_effect'])
            return

        language = get_client_language(player.index)

        # Save player name so that we don't crash when accessing properties
        # of a disconnected player
        player_name = player.name

        # Disconnect the player
        player.kick(plugin_strings['default_ban_reason'].get_string(language))

        duration = int(config['settings']['default_ban_time_seconds'])

        GameThread(
            target=banned_ip_address_manager.save_ban_to_database,
            args=(client, ip_address, player_name, duration)
        ).start()

        log_admin_action(plugin_strings['message banned'].tokenized(
            admin_name=client.player.name,
            player_name=player_name,
        ))

# The singleton object of the _BanIPAddressFeature class.
ban_ip_address_feature = _BanIPAddressFeature()


class _LiftBanPopupFeature(Feature):
    popup_title = None
    banned_uniqueid_manager = None

    def __init__(self):
        self.ban_popup = PagedMenu(title=plugin_strings[self.popup_title])

        @self.ban_popup.register_build_callback
        def build_callback(popup, index):
            client = clients[index]
            popup.clear()

            bans = self.banned_uniqueid_manager.get_unreviewed_bans_for_admin(
                client.player.steamid)

            for uniqueid, banned_player_info in bans:
                popup.append(PagedOption(
                    text=plugin_strings['unreviewed_ban'].tokenized(
                        id=uniqueid, name=format_player_name(
                            banned_player_info.name)),
                    value=banned_player_info
                ))

        @self.ban_popup.register_select_callback
        def select_callback(popup, index, option):
            client = clients[index]

            GameThread(
                target=self.banned_uniqueid_manager.lift_ban,
                args=(option.value.id, )
            ).start()

            log_admin_action(plugin_strings['message ban_lifted'].tokenized(
                admin_name=client.player.name,
                player_name=option.value.name,
            ))

    def execute(self, client):
        self.ban_popup.send(client.player.index)


class _LiftSteamIDBanPopupFeature(_LiftBanPopupFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    popup_title = 'popup_title lift_steamid'
    banned_uniqueid_manager = banned_steamid_manager

# The singleton object of the _LiftSteamIDBanPopupFeature class.
lift_steamid_ban_popup_feature = _LiftSteamIDBanPopupFeature()


class _LiftIPAddressBanPopupFeature(_LiftBanPopupFeature):
    flag = "admin.admin_kick_ban.ban_ip_address"
    popup_title = 'popup_title lift_ip_address'
    banned_uniqueid_manager = banned_ip_address_manager

# The singleton object of the _LiftIPAddressBanPopupFeature class.
lift_ip_address_ban_popup_feature = _LiftIPAddressBanPopupFeature()


class _SpecifyBanPopupFeature(Feature):
    popup_title = None
    banned_uniqueid_manager = None

    def __init__(self):
        self._selected_ban = (None, "", -1)

        self.ban_popup = PagedMenu(title=plugin_strings[self.popup_title])
        self.reason_popup = PagedMenu(title=plugin_strings[self.popup_title],
                                      parent_menu=self.ban_popup)

        # We do not allow returning back to reason popup from duration popup,
        # because we won't have valid self._selected_ban to build a reason
        # popup with. Hence we don't provide parent_menu here.
        self.duration_popup = PagedMenu(title=plugin_strings[self.popup_title])

        @self.ban_popup.register_build_callback
        def build_callback(popup, index):
            client = clients[index]
            popup.clear()

            bans = self.banned_uniqueid_manager.get_unreviewed_bans_for_admin(
                client.player.steamid)

            for uniqueid, banned_player_info in bans:
                popup.append(PagedOption(
                    text=plugin_strings['unreviewed_ban'].tokenized(
                        id=uniqueid, name=format_player_name(
                            banned_player_info.name)),
                    value=(banned_player_info, "", -1)
                ))

        @self.ban_popup.register_select_callback
        def select_callback(popup, index, option):
            self._selected_ban = option.value
            self.reason_popup.send(index)

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
            self.duration_popup.send(index)

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
                admin_name=client.player.name,
                player_name=option.value[0].name,
                duration=format_ban_duration(option.value[2])
            ))

    def execute(self, client):
        self.ban_popup.send(client.player.index)


class _SpecifySteamIDBanPopupFeature(_SpecifyBanPopupFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    popup_title = 'popup_title specify_steamid'
    banned_uniqueid_manager = banned_steamid_manager

# The singleton object of the _SpecifySteamIDBanPopupFeature class.
specify_steamid_ban_popup_feature = _SpecifySteamIDBanPopupFeature()


class _SpecifyIPAddressBanPopupFeature(_SpecifyBanPopupFeature):
    flag = "admin.admin_kick_ban.ban_ip_address"
    popup_title = 'popup_title specify_ip_address'
    banned_uniqueid_manager = banned_ip_address_manager

# The singleton object of the _SpecifySteamIDBanPopupFeature class.
specify_ip_address_ban_popup_feature = _SpecifyIPAddressBanPopupFeature()


class _KickMenuCommand(PlayerBasedAdminCommand):
    allow_multiple_choices = False


class _BanSteamIDMenuCommand(PlayerBasedAdminCommand):
    base_filter = 'human'
    allow_multiple_choices = False

    @staticmethod
    def render_player_name(player):
        return plugin_strings['player_name'].tokenized(
            name=format_player_name(player.name),
            id=player.steamid
        )


class _BanIPAddressMenuCommand(PlayerBasedAdminCommand):
    base_filter = 'human'
    allow_multiple_choices = False

    @staticmethod
    def render_player_name(player):
        return plugin_strings['player_name'].tokenized(
            name=format_player_name(player.name),
            id=extract_ip_address(player.address)
        )


# =============================================================================
# >> MENU ENTRIES
# =============================================================================
stock_ban_reasons = load_stock_ban_reasons()
stock_ban_durations = load_stock_ban_durations()

menu_section = main_menu.add_entry(AdminMenuSection(
    main_menu, plugin_strings['section_title']))

lift_steamid_ban_popup_feature.ban_popup.parent_menu = menu_section.popup
lift_ip_address_ban_popup_feature.ban_popup.parent_menu = menu_section.popup
specify_steamid_ban_popup_feature.ban_popup.parent_menu = menu_section.popup
specify_ip_address_ban_popup_feature.ban_popup.parent_menu = menu_section.popup

kick_menu_command = menu_section.add_entry(_KickMenuCommand(
    kick_feature,
    menu_section,
    plugin_strings['popup_title kick']
))
ban_steamid_menu_command = menu_section.add_entry(_BanSteamIDMenuCommand(
    ban_steamid_feature,
    menu_section,
    plugin_strings['popup_title ban_steamid']
))
ban_ip_address_menu_command = menu_section.add_entry(_BanIPAddressMenuCommand(
    ban_ip_address_feature,
    menu_section,
    plugin_strings['popup_title ban_ip_address']
))
specify_steamid_ban_menu_command = menu_section.add_entry(AdminCommand(
    specify_steamid_ban_popup_feature,
    menu_section,
    plugin_strings['popup_title specify_steamid']
))
specify_ip_address_ban_menu_command = menu_section.add_entry(AdminCommand(
    specify_ip_address_ban_popup_feature,
    menu_section,
    plugin_strings['popup_title specify_ip_address']
))
lift_steamid_ban_menu_command = menu_section.add_entry(AdminCommand(
    lift_steamid_ban_popup_feature,
    menu_section,
    plugin_strings['popup_title lift_steamid']
))
lift_ip_address_ban_menu_command = menu_section.add_entry(AdminCommand(
    lift_ip_address_ban_popup_feature,
    menu_section,
    plugin_strings['popup_title lift_ip_address']
))


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
# >> EVENTS
# =============================================================================
@Event('admin_plugin_loaded')
def on_admin_plugin_loaded(ev):
    if ev['plugin'] != "admin_kick_ban":
        return

    banned_steamid_manager.refresh()
    banned_ip_address_manager.refresh()


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
