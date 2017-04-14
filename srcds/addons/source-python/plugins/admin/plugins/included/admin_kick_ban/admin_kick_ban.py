# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from collections import OrderedDict
from configparser import ConfigParser
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
from players.helpers import get_client_language
from translations.manager import language_manager

# Source.Python Admin
from admin.admin import main_menu
from admin.core.clients import clients
from admin.core.features import Feature, PlayerBasedFeature
from admin.core.frontends.menus import (
    AdminCommand, AdminMenuSection, PlayerBasedAdminCommand)
from admin.core.helpers import (
    extract_ip_address, format_player_name, log_admin_action)
from admin.core.memory import custom_server
from admin.core.orm import Session
from admin.core.paths import ADMIN_CFG_PATH, get_server_file
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
PLUGIN_CONFIG_FILE = get_server_file(
    ADMIN_CFG_PATH / "included_plugins" / "admin_kick_ban" / "config.ini")

plugin_config = ConfigParser()
plugin_config.read(PLUGIN_CONFIG_FILE)

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
    def __init__(self, id_, name, banned_by, reviewed, expires_timestamp,
                 reason, notes):

        self.id = id_
        self.name = name
        self.banned_by = banned_by
        self.reviewed = reviewed
        self.expires_timestamp = expires_timestamp
        self.reason = reason
        self.notes = notes


class _BannedUniqueIDManager(dict):
    model = None

    def refresh(self):
        self.clear()

        session = Session()

        banned_users = session.query(self.model).all()

        current_time = time()
        for banned_user in banned_users:
            if banned_user.is_unbanned:
                continue

            if -1 < banned_user.expires_timestamp < current_time:
                continue

            self[banned_user.uniqueid] = _BannedPlayerInfo(
                banned_user.id, banned_user.name, banned_user.banned_by,
                banned_user.reviewed, banned_user.expires_timestamp,
                banned_user.reason, banned_user.notes
            )

        session.close()

    def is_banned(self, uniqueid):
        if uniqueid not in self:
            return False

        if self[uniqueid].expires_timestamp < 0:
            return True

        if self[uniqueid].expires_timestamp < time():
            del self[uniqueid]
            return False

        return True

    def save_ban_to_database(self, banned_by, uniqueid, name, duration):
        session = Session()

        banned_user = self.model(uniqueid, name, banned_by, duration)

        session.add(banned_user)
        session.commit()

        self[uniqueid] = _BannedPlayerInfo(
            banned_user.id, name, banned_by, False,
            banned_user.expires_timestamp, "", "")

        session.close()

    def get_bans(self, banned_by=None, reviewed=None):
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

            if banned_player_info.expires_timestamp < current_time:
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
            banned_player_info.expires_timestamp = time() + duration
            banned_player_info.reason = reason
            break

    def lift_ban(self, ban_id, unbanned_by):
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
    uniqueid_attr = 'steamid'

# The singleton object for the _BannedSteamIDManager class.
banned_steamid_manager = _BannedSteamIDManager()


class _BannedIPAddressManager(_BannedUniqueIDManager):
    model = BannedIPAddress
    uniqueid_attr = 'ip_address'

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


class _BanSteamIDFeature(PlayerBasedFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    allow_execution_on_self = False

    def execute(self, client, player):
        if player.is_fake_client() or player.is_hltv():
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

        duration = int(plugin_config['settings']['default_ban_time_seconds'])

        GameThread(
            target=banned_steamid_manager.save_ban_to_database,
            args=(client.steamid, player_steamid, player_name, duration)
        ).start()

        log_admin_action(plugin_strings['message banned'].tokenized(
            admin_name=client.name,
            player_name=player_name,
        ))

# The singleton object of the _BanSteamIDFeature class.
ban_steamid_feature = _BanSteamIDFeature()


class _BanIPAddressFeature(PlayerBasedFeature):
    flag = "admin.admin_kick_ban.ban_ip_address"
    allow_execution_on_self = False

    def execute(self, client, player):
        if player.is_fake_client() or player.is_hltv():
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

        duration = int(plugin_config['settings']['default_ban_time_seconds'])

        GameThread(
            target=banned_ip_address_manager.save_ban_to_database,
            args=(client.steamid, ip_address, player_name, duration)
        ).start()

        log_admin_action(plugin_strings['message banned'].tokenized(
            admin_name=client.name,
            player_name=player_name,
        ))

# The singleton object of the _BanIPAddressFeature class.
ban_ip_address_feature = _BanIPAddressFeature()


class _LiftBanPopupFeature(Feature):
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

            bans = self.banned_uniqueid_manager.get_bans(reviewed=True)

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

# The singleton object of the _LiftReviewedSteamIDBanPopupFeature class.
lift_reviewed_ip_address_ban_popup_feature = (
    _LiftReviewedIPAddressBanPopupFeature())


class _ReviewBanPopupFeature(Feature):
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
lift_reviewed_steamid_ban_popup_feature.ban_popup.parent_menu = (
    menu_section.popup)
lift_reviewed_ip_address_ban_popup_feature.ban_popup.parent_menu = (
    menu_section.popup)
review_steamid_ban_popup_feature.ban_popup.parent_menu = menu_section.popup
review_ip_address_ban_popup_feature.ban_popup.parent_menu = menu_section.popup

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
review_steamid_ban_menu_command = menu_section.add_entry(AdminCommand(
    review_steamid_ban_popup_feature,
    menu_section,
    plugin_strings['popup_title review_steamid']
))
review_ip_address_ban_menu_command = menu_section.add_entry(AdminCommand(
    review_ip_address_ban_popup_feature,
    menu_section,
    plugin_strings['popup_title review_ip_address']
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
lift_reviewed_steamid_ban_menu_command = menu_section.add_entry(AdminCommand(
    lift_reviewed_steamid_ban_popup_feature,
    menu_section,
    plugin_strings['popup_title lift_reviewed_steamid']
))
lift_reviewed_ip_address_ban_menu_command = menu_section.add_entry(
    AdminCommand(
        lift_reviewed_ip_address_ban_popup_feature,
        menu_section,
        plugin_strings['popup_title lift_reviewed_ip_address']
    )
)


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
