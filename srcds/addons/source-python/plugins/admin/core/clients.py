# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from auth.manager import auth_manager
from filters.players import PlayerIter
from listeners.tick import Delay
from messages import SayText2
from players.dictionary import PlayerDictionary
from players.entity import Player

# Source.Python Admin
from .strings import strings_common


# =============================================================================
# >> CLASSES
# =============================================================================
class BaseClient:
    def has_permission(self, permission):
        raise NotImplementedError

    @property
    def name(self):
        raise NotImplementedError

    @property
    def steamid(self):
        raise NotImplementedError

    def sync_execution(self, callback, args=(), kwargs=None):
        raise NotImplementedError


class RemoteClient(BaseClient):
    name = None
    steamid = None

    def __init__(self, name, steamid):
        super().__init__()

        self.name = name
        self.steamid = steamid

    def has_permission(self, permission):
        permissions = auth_manager.get_player_permissions_from_steamid(
            self.steamid)

        if permissions is None:
            return False

        return permission in permissions

    def sync_execution(self, callback, args=(), kwargs=None):
        Delay(0, callback, args, kwargs)


class Client(BaseClient):
    def __init__(self, index):
        super().__init__()

        self.player = Player(index)
        self.active_popup = None

    def has_permission(self, permission):
        return auth_manager.is_player_authorized(self.player.index, permission)

    def send_popup(self, popup):
        if self.active_popup is not None:
            self.active_popup.close(self.player.index)

        self.active_popup = popup
        popup.send(self.player.index)

    def tell(self, message):
        SayText2(strings_common['chat_base'].tokenized(message=message)).send(
            self.player.index)

    def sync_execution(self, callback, args=(), kwargs=None):
        self.player.delay(0, callback, args, kwargs)

    @property
    def name(self):
        return self.player.name

    @property
    def steamid(self):
        return self.player.steamid

clients = PlayerDictionary(Client)
