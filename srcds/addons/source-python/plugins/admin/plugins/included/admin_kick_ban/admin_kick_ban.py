# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from time import time

# Source.Python
from core import GAME_NAME
from engines.server import server
from events import Event
from listeners import OnClientConnect, OnNetworkidValidated
from listeners.tick import GameThread
from memory import make_object
from memory.hooks import PostHook
from players import Client
from players.helpers import get_client_language
from translations.manager import language_manager

# Source.Python Admin
from admin.admin import main_menu
from admin.core.config import config
from admin.core.features import PlayerBasedFeature
from admin.core.frontends.menus import (AdminMenuSection,
                                        PlayerBasedAdminCommand)
from admin.core.memory import custom_server
from admin.core.orm import Session
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


# =============================================================================
# >> CLASSES
# =============================================================================
class _BannedSteamIDManager(dict):
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

            self[banned_user.steamid] = banned_user.expires_timestamp

        session.close()

    def is_steamid_banned(self, steamid):
        if steamid not in self:
            return False

        if self[steamid] < 0:
            return True

        if self[steamid] < time():
            del self[steamid]
            return False

        return True

    @staticmethod
    def save_steamid_to_database(client, steamid, name, duration):
        session = Session()

        banned_steamid = BannedSteamID()
        session.add(banned_steamid)

        current_time = time()
        banned_steamid.steamid = steamid
        banned_steamid.name = name
        banned_steamid.admin_steamid = client.player.steamid
        banned_steamid.reviewed = False
        banned_steamid.banned_timestamp = current_time
        banned_steamid.expires_timestamp = current_time + duration
        banned_steamid.unbanned = False
        banned_steamid.reason = ""
        banned_steamid.notes = ""

        session.commit()
        session.close()

# The singleton object for the _BannedSteamIDManager class.
banned_steamid_manager = _BannedSteamIDManager()


class _BannedIPAddressManager(dict):
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

            self[banned_user.ip_address] = banned_user.expires_timestamp

        session.close()

    def is_ip_address_banned(self, ip_address):
        if ip_address not in self:
            return False

        if self[ip_address] < 0:
            return True

        if self[ip_address] < time():
            del self[ip_address]
            return False

        return True

    @staticmethod
    def save_ip_address_to_database(client, ip_address, name, duration):
        session = Session()

        banned_ip_address = BannedIPAddress()
        session.add(banned_ip_address)

        current_time = time()
        banned_ip_address.ip_address = ip_address
        banned_ip_address.name = name
        banned_ip_address.admin_steamid = client.player.steamid
        banned_ip_address.reviewed = False
        banned_ip_address.banned_timestamp = current_time
        banned_ip_address.expires_timestamp = current_time + duration
        banned_ip_address.unbanned = False
        banned_ip_address.reason = ""
        banned_ip_address.notes = ""

        session.commit()
        session.close()

# The singleton object for the _BannedIPAddressManager class.
banned_ip_address_manager = _BannedIPAddressManager()


class _KickFeature(PlayerBasedFeature):
    flag = "admin.admin_kick_ban.kick"
    allow_execution_on_self = False

    @staticmethod
    def execute(client, player):
        language = get_client_language(player.index)
        player.kick(plugin_strings['default_kick_reason'].get_string(language))

# The singleton object of the _KickFeature class.
kick_feature = _KickFeature()


class _BanSteamIDFeature(PlayerBasedFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    allow_execution_on_self = False

    @staticmethod
    def execute(client, player):
        if player.is_fake_client():
            return

        language = get_client_language(player.index)

        # Save player name and SteamID so that we don't crash when accessing
        # properties of a disconnected player
        player_name = player.name
        player_steamid = player.steamid

        # Disconnect the player
        player.kick(plugin_strings['default_ban_reason'].get_string(language))

        duration = int(config['settings']['default_ban_time_seconds'])
        banned_steamid_manager[player_steamid] = time() + duration

        GameThread(
            target=banned_steamid_manager.save_steamid_to_database,
            args=(client, player_steamid, player_name, duration)
        ).start()

# The singleton object of the _BanSteamIDFeature class.
ban_steamid_feature = _BanSteamIDFeature()


class _BanIPAddressFeature(PlayerBasedFeature):
    flag = "admin.admin_kick_ban.ban_ip_address"
    allow_execution_on_self = False

    @staticmethod
    def execute(client, player):
        if player.is_fake_client():
            return

        ip_address = extract_ip_address(player.address)
        language = get_client_language(player.index)

        # Save player name so that we don't crash when accessing properties
        # of a disconnected player
        player_name = player.name

        # Disconnect the player
        player.kick(plugin_strings['default_ban_reason'].get_string(language))

        duration = int(config['settings']['default_ban_time_seconds'])
        banned_ip_address_manager[ip_address] = time() + duration

        GameThread(
            target=banned_ip_address_manager.save_ip_address_to_database,
            args=(client, ip_address, player_name, duration)
        ).start()

# The singleton object of the _BanIPAddressFeature class.
ban_ip_address_feature = _BanIPAddressFeature()


class KickMenuCommand(PlayerBasedAdminCommand):
    allow_multiple_choices = False


class BanMenuCommand(PlayerBasedAdminCommand):
    base_filter = 'human'
    allow_multiple_choices = False


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
plugin_strings = PluginStrings("admin_kick_ban")
menu_section = main_menu.add_entry(AdminMenuSection(
    main_menu, plugin_strings['section_title']))

kick_menu_command = menu_section.add_entry(KickMenuCommand(
    kick_feature,
    menu_section,
    plugin_strings['popup title kick']
))
ban_steamid_menu_command = menu_section.add_entry(BanMenuCommand(
    ban_steamid_feature,
    menu_section,
    plugin_strings['popup title ban_steamid']
))
ban_ip_address_menu_command = menu_section.add_entry(BanMenuCommand(
    ban_ip_address_feature,
    menu_section,
    plugin_strings['popup title ban_ip_address']
))


# =============================================================================
# >> LISTENERS
# =============================================================================
@OnNetworkidValidated
def listener_on_networkid_validated(name, steamid):
    if not banned_steamid_manager.is_steamid_banned(steamid):
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
    if not banned_ip_address_manager.is_ip_address_banned(ip_address):
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
    if not banned_steamid_manager.is_steamid_banned(client.steamid):
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
