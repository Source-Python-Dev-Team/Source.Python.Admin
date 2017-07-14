# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from filters.players import PlayerIter
from listeners import OnClientActive, OnClientDisconnect
from players.entity import Player

# Source.Python Admin
from admin.core.clients import RemoteClient
from admin.core.features import BaseFeature
from admin.core.frontends.menus import BasePlayerBasedMenuCommand
from admin.core.frontends.motd import BasePlayerBasedFeaturePage

# Included Plugin
from .config import plugin_config


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
LEFT_PLAYERS_LIMIT = int(plugin_config['settings']['left_players_limit'])
_left_players = []
_ws_left_player_based_pages = []


# =============================================================================
# >> CLASSES
# =============================================================================
class LeftPlayer:
    """Class that is able to describe any player - be it a disconnected one
    or not."""
    def __init__(self, index, disconnected):
        self._disconnected = disconnected
        player = Player(index)

        self.userid = player.userid
        self.steamid = player.steamid
        self.name = player.name
        self.address = player.address

        # Add some stuff to be able to be filtered by filters.players...
        self._fake_client = player.is_fake_client()
        self._hltv = player.is_hltv()
        self.dead = player.dead
        self.team = player.team

    def is_fake_client(self):
        return self._fake_client

    def is_hltv(self):
        return self._hltv

    @property
    def disconnected(self):
        return self._disconnected


class LeftPlayerIter(PlayerIter):
    @staticmethod
    def iterator():
        seen_steamids = []
        result = []
        for player in PlayerIter.iterator():
            seen_steamids.append(player.steamid)
            result.append(LeftPlayer(player.index, disconnected=False))

        for left_player in _left_players:
            if left_player.steamid in seen_steamids:
                continue

            result.insert(0, left_player)

        yield from result

# Copy filters from PlayerIter to LeftPlayerIter
for _filter_name, _filter_func in PlayerIter.filters.items():
    LeftPlayerIter.register_filter(_filter_name, _filter_func)

# Replace bot and human filters with their improved alternatives that work
# in the OnClientActive listener
# TODO: Suggest an improvement for these filters to Source.Python team
LeftPlayerIter.unregister_filter('bot')
LeftPlayerIter.unregister_filter('human')
LeftPlayerIter.register_filter('bot', lambda left_player: (
    left_player.is_fake_client() or 'BOT' in left_player.steamid))
LeftPlayerIter.register_filter('human', lambda left_player: (
    not left_player.is_fake_client() and 'BOT' not in left_player.steamid))


class LeftPlayerBasedFeature(BaseFeature):
    feature_abstract = True

    # Allow clients to execute this feature on themselves?
    allow_execution_on_self = True

    # Allow clients to execute this feature on those clients that have
    # permissions to execute this command, too?
    allow_execution_on_equal_priority = False

    def execute(self, client, left_player):
        """Execute the feature on the given player.

        :param client: Client that performs the action.
        :param left_player: LeftPlayer to perform the action on.
        """
        raise NotImplementedError

    def filter(self, client, left_player):
        """Determine if a client is able to execute the feature on the given
        player.

        :param client: Client that performs the action.
        :param left_player: LeftPlayer to perform the action on.
        :return: Whether to allow or disallow the action.
        :rtype: bool
        """
        if (
                not self.allow_execution_on_self and
                client.steamid == left_player.steamid):

            return False

        if self.allow_execution_on_equal_priority:
            return True

        another_client = RemoteClient(left_player.name, left_player.steamid)
        return not another_client.has_permission(self.flag)


class LeftPlayerBasedMenuCommand(BasePlayerBasedMenuCommand):
    base_filter = 'all'

    def _get_player_id(self, player):
        return player.steamid

    def _iter(self):
        yield from LeftPlayerIter(self.base_filter)


class LeftPlayerBasedFeaturePage(BasePlayerBasedFeaturePage):
    abstract = True
    page_abstract = True
    feature_page_abstract = True

    # Base filters that will be passed to PlayerIter
    _base_filter = 'all'
    _ws_base_filter = 'all'

    def __init__(self, index, page_request_type):
        super().__init__(index, page_request_type)

        if self.is_websocket:
            _ws_left_player_based_pages.append(self)

    @property
    def base_filter(self):
        return self._ws_base_filter if self.is_websocket else self._base_filter

    def _get_player_id(self, left_player):
        return left_player.steamid

    def _iter(self):
        yield from LeftPlayerIter(self.base_filter)

    def _execute(self, client, steamid):
        for left_player in self._iter():
            if left_player.steamid == steamid:
                self.feature.execute(client, left_player)
                break

    def _render_player_name(self, left_player):
        if left_player.disconnected:
            return "*DISCONNECTED* {}".format(left_player.name)
        return left_player.name

    def filter(self, left_player):
        if not LeftPlayerIter.filters[self.base_filter](left_player):
            return False

        if not super().filter(left_player):
            return False

        return True

    def on_error(self, error):
        if self.is_websocket and self in _ws_left_player_based_pages:
            _ws_left_player_based_pages.remove(self)


# =============================================================================
# >> LISTENERS
# =============================================================================
@OnClientActive
def listener_on_client_active(index):
    left_player = LeftPlayer(index, disconnected=False)
    for ws_left_player_based_page in _ws_left_player_based_pages:
        if not ws_left_player_based_page.filter(left_player):
            continue

        ws_left_player_based_page.send_add_player(left_player)


@OnClientDisconnect
def listener_on_client_disconnect(index):
    try:
        left_player = LeftPlayer(index, disconnected=True)
    except ValueError:

        # Sometimes (if the client disconnects before activation) we're
        # unable to get data of the disconnected player
        return

    for left_player_ in _left_players:
        if left_player_.steamid == left_player.steamid:
            _left_players.remove(left_player_)

            for ws_left_player_based_page in _ws_left_player_based_pages:
                ws_left_player_based_page.send_remove_id(left_player_)

            break

    _left_players.append(left_player)

    for ws_left_player_based_page in _ws_left_player_based_pages:
        if not ws_left_player_based_page.filter(left_player):
            continue

        ws_left_player_based_page.send_add_player(left_player)

    if len(_left_players) > LEFT_PLAYERS_LIMIT:
        left_player_ = _left_players.pop(0)

        for ws_left_player_based_page in _ws_left_player_based_pages:
            ws_left_player_based_page.send_remove_id(left_player_)
