# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from listeners import OnClientConnect
from listeners.tick import GameThread
from players.entity import Player
from players.helpers import get_client_language
from translations.manager import language_manager

# Source.Python Admin
from admin.core.helpers import (
    extract_ip_address, format_player_name, log_admin_action)

# Included Plugin
from ..config import plugin_config
from ..left_player import (
    LeftPlayerBasedMenuCommand, LeftPlayerBasedFeature,
    LeftPlayerBasedFeaturePage, LeftPlayerIter)
from ..models import BannedIPAddress
from ..strings import plugin_strings
from .base import (
    BannedUniqueIDManager, LiftAnyBanMenuCommand, LiftBanFeature, LiftBanPage,
    LiftMyBanMenuCommand, RemoveBadBanFeature, RemoveBadBanMenuCommand,
    ReviewBanFeature, ReviewBanMenuCommand, ReviewBanPage)


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
_ws_ban_ip_address_pages = []
_ws_lift_ip_address_pages = []
_ws_review_ip_address_ban_pages = []


# =============================================================================
# >> CLASSES
# =============================================================================
class _BannedIPAddressManager(BannedUniqueIDManager):
    model = BannedIPAddress

    def _convert_uniqueid_to_db_format(self, uniqueid):
        return uniqueid

# The singleton object for the _BannedIPAddressManager class.
banned_ip_address_manager = _BannedIPAddressManager()


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


class BanIPAddressMenuCommand(LeftPlayerBasedMenuCommand):
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


class _LiftIPAddressBanFeature(LiftBanFeature):
    flag = "admin.admin_kick_ban.ban_ip_address"
    banned_uniqueid_manager = banned_ip_address_manager
    ws_lift_ban_pages = _ws_lift_ip_address_pages

# The singleton object of the _LiftIPAddressBanFeature class.
lift_ip_address_ban_feature = _LiftIPAddressBanFeature()


class LiftAnyIPAddressBanMenuCommand(LiftAnyBanMenuCommand):
    popup_title = plugin_strings['popup_title lift_reviewed_ip_address']


class LiftMyIPAddressBanMenuCommand(LiftMyBanMenuCommand):
    popup_title = plugin_strings['popup_title lift_ip_address']


class _ReviewIPAddressBanFeature(ReviewBanFeature):
    flag = "admin.admin_kick_ban.ban_ip_address"
    banned_uniqueid_manager = banned_ip_address_manager
    ws_review_ban_pages = _ws_review_ip_address_ban_pages

# The singleton object of the _ReviewIPAddressBanFeature class.
review_ip_address_ban_feature = _ReviewIPAddressBanFeature()


class ReviewIPAddressBanMenuCommand(ReviewBanMenuCommand):
    popup_title = plugin_strings['popup_title review_ip_address']


class _RemoveBadIPAddressBanFeature(RemoveBadBanFeature):
    flag = "admin.admin_kick_ban.search_bad_ip_address_bans"
    banned_uniqueid_manager = banned_ip_address_manager

# The singleton object of the _RemoveBadIPAddressBanFeature class.
remove_bad_ip_address_ban_feature = _RemoveBadIPAddressBanFeature()


class RemoveBadIPAddressBanMenuCommand(RemoveBadBanMenuCommand):
    popup_title = plugin_strings['popup_title search_bad_bans']


class BanIPAddressPage(LeftPlayerBasedFeaturePage):
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


class LiftIPAddressBanPage(LiftBanPage):
    admin_plugin_id = "admin_kick_ban"
    admin_plugin_type = "included"
    page_id = "lift_ip_address"
    feature = lift_ip_address_ban_feature

    def __init__(self, index, page_request_type):
        super().__init__(index, page_request_type)

        if self.is_websocket:
            _ws_lift_ip_address_pages.append(self)

    def on_error(self, error):
        super().on_error(error)

        if self.is_websocket and self in _ws_lift_ip_address_pages:
            _ws_lift_ip_address_pages.remove(self)


class ReviewIPAddressBanPage(ReviewBanPage):
    admin_plugin_id = "admin_kick_ban"
    admin_plugin_type = "included"
    page_id = "review_ip_address"
    feature = review_ip_address_ban_feature

    def __init__(self, index, page_request_type):
        super().__init__(index, page_request_type)

        if self.is_websocket:
            _ws_review_ip_address_ban_pages.append(self)

    def on_error(self, error):
        super().on_error(error)

        if self.is_websocket and self in _ws_review_ip_address_ban_pages:
            _ws_review_ip_address_ban_pages.remove(self)


# =============================================================================
# >> LISTENERS
# =============================================================================
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
