# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from auth.manager import auth_manager
from filters.players import PlayerIter
from messages import SayText2
from players.dictionary import PlayerDictionary
from players.entity import Player

# Source.Python Admin
from .strings import strings_common


# =============================================================================
# >> CLASSES
# =============================================================================
class ClientDictionary(PlayerDictionary):
    @staticmethod
    def broadcast(message):
        say_text2 = SayText2(strings_common['chat_base'].tokenized(
            message=message))

        for player in PlayerIter('human'):
            say_text2.send(player.index)


class Client:
    def __init__(self, index):
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

clients = ClientDictionary(Client)
