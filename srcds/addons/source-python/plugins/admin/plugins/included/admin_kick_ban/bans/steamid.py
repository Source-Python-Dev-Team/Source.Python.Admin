# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from core import GAME_NAME
from engines.server import server
from listeners import OnNetworkidValidated
from listeners.tick import GameThread
from memory import make_object
from memory.hooks import PostHook
from players import Client
from players.entity import Player
from players.helpers import get_client_language
from translations.manager import language_manager

# Source.Python Admin
from admin.core.helpers import format_player_name, log_admin_action
from admin.core.memory import custom_server

# Included Plugin
from ..config import plugin_config
from ..left_player import (
    LeftPlayerBasedAdminCommand, LeftPlayerBasedFeature,
    LeftPlayerBasedFeaturePage, LeftPlayerIter)
from ..models import BannedSteamID
from ..strings import plugin_strings
from .base import (
    BannedUniqueIDManager, LiftBanMOTDFeature, LiftBanPopupFeature,
    LiftAnyBanPopupFeature, ReviewBanMOTDFeature, ReviewBanPopupFeature,
    LiftBanPage, ReviewBanPage)


# =============================================================================
# >> FUNCTIONS
# =============================================================================
def find_client(steamid):
    for x in range(server.num_clients):
        client = server.get_client(x)
        if client.steamid == steamid:
            return client

    return None


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
_ws_ban_steamid_pages = []
_ws_lift_steamid_pages = []
_ws_review_steamid_ban_pages = []


# =============================================================================
# >> CLASSES
# =============================================================================
class _BannedSteamIDManager(BannedUniqueIDManager):
    model = BannedSteamID

    def _convert_uniqueid_to_db_format(self, uniqueid):
        return self._convert_steamid_to_db_format(uniqueid)

# The singleton object for the _BannedSteamIDManager class.
banned_steamid_manager = _BannedSteamIDManager()


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


class _LiftSteamIDBanMOTDFeature(LiftBanMOTDFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    banned_uniqueid_manager = banned_steamid_manager
    ws_lift_ban_pages = _ws_lift_steamid_pages

# The singleton object of the _LiftSteamIDBanMOTDFeature class.
lift_steamid_ban_motd_feature = _LiftSteamIDBanMOTDFeature()


class _LiftSteamIDBanPopupFeature(LiftBanPopupFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    popup_title = plugin_strings['popup_title lift_steamid']
    banned_uniqueid_manager = banned_steamid_manager

# The singleton object of the _LiftSteamIDBanPopupFeature class.
lift_steamid_ban_popup_feature = _LiftSteamIDBanPopupFeature()


class _LiftAnySteamIDBanPopupFeature(LiftAnyBanPopupFeature):
    flag = "admin.admin_kick_ban.lift_reviewed_steamid"
    popup_title = plugin_strings['popup_title lift_reviewed_steamid']
    banned_uniqueid_manager = banned_steamid_manager

# The singleton object of the _LiftAnySteamIDBanPopupFeature class.
lift_any_steamid_ban_popup_feature = _LiftAnySteamIDBanPopupFeature()


class _ReviewSteamIDBanMOTDFeature(ReviewBanMOTDFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    banned_uniqueid_manager = banned_steamid_manager
    ws_review_ban_pages = _ws_review_steamid_ban_pages

# The singleton object of the _ReviewSteamIDBanMOTDFeature class.
review_steamid_ban_motd_feature = _ReviewSteamIDBanMOTDFeature()


class _ReviewSteamIDBanPopupFeature(ReviewBanPopupFeature):
    flag = "admin.admin_kick_ban.ban_steamid"
    popup_title = plugin_strings['popup_title review_steamid']
    banned_uniqueid_manager = banned_steamid_manager

# The singleton object of the _ReviewSteamIDBanPopupFeature class.
review_steamid_ban_popup_feature = _ReviewSteamIDBanPopupFeature()


class BanSteamIDMenuCommand(LeftPlayerBasedAdminCommand):
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


class BanSteamIDPage(LeftPlayerBasedFeaturePage):
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


class LiftSteamIDBanPage(LiftBanPage):
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


class ReviewSteamIDBanPage(ReviewBanPage):
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
