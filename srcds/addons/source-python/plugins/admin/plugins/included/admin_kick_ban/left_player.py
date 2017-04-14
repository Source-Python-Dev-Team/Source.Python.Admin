# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from filters.players import PlayerIter
from listeners import OnClientDisconnect
from players.entity import Player

# Source.Python Admin
from admin.core.clients import RemoteClient
from admin.core.features import BaseFeature
from admin.core.frontends.menus import BasePlayerBasedAdminCommand

# Included Plugin
from .config import plugin_config


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
LEFT_PLAYERS_LIMIT = int(plugin_config['settings']['left_players_limit'])
_left_players = []


# =============================================================================
# >> CLASSES
# =============================================================================
class LeftPlayer:
    """Class that is able to describe any player - be it a disconnected one
    or not."""
    def __init__(self, index):
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


class LeftPlayerIter(PlayerIter):
    @staticmethod
    def iterator():
        seen_steamids = []
        result = []
        for player in PlayerIter.iterator():
            seen_steamids.append(player.steamid)
            result.append(LeftPlayer(player.index))

        for left_player in _left_players:
            if left_player.steamid in seen_steamids:
                continue

            result.insert(0, left_player)

        yield from result

# Copy filters from PlayerIter to LeftPlayerIter
for _filter_name, _filter_func in PlayerIter.filters.items():
    LeftPlayerIter.register_filter(_filter_name, _filter_func)


class LeftPlayerBasedFeature(BaseFeature):
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


class LeftPlayerBasedAdminCommand(BasePlayerBasedAdminCommand):
    base_filter = 'all'

    def _get_player_id(self, player):
        return player.steamid

    def _iter(self):
        yield from LeftPlayerIter(self.base_filter)


# =============================================================================
# >> LISTENERS
# =============================================================================
@OnClientDisconnect
def listener_on_client_disconnect(index):
    left_player = LeftPlayer(index)

    for left_player_ in _left_players:
        if left_player_.steamid == left_player.steamid:
            _left_players.remove(left_player_)
            break

    _left_players.append(left_player)

    if len(_left_players) > LEFT_PLAYERS_LIMIT:
        _left_players.pop(0)
