# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from engines.server import server
from listeners import OnNetworkidValidated
from listeners.tick import GameThread
from players.entity import Player
from players.helpers import get_client_language

# Source.Python Admin
from admin.core import admin_core_logger
from admin.core.helpers import format_player_name, log_admin_action

# Custom Package
try:
    from connect_filter import ConnectFilter
except ImportError:

    # TODO: Don't log into core
    admin_core_logger.log_message(
        "ConnectFilter package is not installed, we won't be able to reject "
        "banned SteamIDs early (before their validation)")

    ConnectFilter = lambda callback: callback

# Included Plugin
from ..config import plugin_config
from ..left_player import (
    LeftPlayerBasedMenuCommand, LeftPlayerBasedFeature,
    LeftPlayerBasedFeaturePage, LeftPlayerIter)
from ..models import BannedSteamID
from ..strings import plugin_strings
from .base import (
    BannedUniqueIDManager, LiftBanMOTDFeature, LiftBanPopupFeature,
    LiftAnyBanPopupFeature, ReviewBanMOTDFeature, ReviewBanPopupFeature,
    LiftBanPage, ReviewBanPage, SearchBadBansPopupFeature)


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


class _SearchBadSteamIDBansPopupFeature(SearchBadBansPopupFeature):
    flag = "admin.admin_kick_ban.search_bad_steamid_bans"
    popup_title = plugin_strings['popup_title search_bad_bans']
    banned_uniqueid_manager = banned_steamid_manager

# The singleton object of the _SearchBadSteamIDBansPopupFeature class.
search_bad_steamid_bans_popup_feature = _SearchBadSteamIDBansPopupFeature()


class BanSteamIDMenuCommand(LeftPlayerBasedMenuCommand):
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

    client.disconnect(plugin_strings['default_ban_reason'].get_string())


# =============================================================================
# >> CONNECT FILTERS
# =============================================================================
@ConnectFilter
def connect_filter(client):
    if banned_steamid_manager.is_banned(client.steamid):
        return plugin_strings['default_ban_reason']

    return None
