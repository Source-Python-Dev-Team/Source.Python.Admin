# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from commands import CommandReturn
from commands.typed import TypedClientCommand, TypedSayCommand
from filters.players import PlayerIter

# Source.Python Admin
from admin.core.clients import clients


# =============================================================================
# >> FUNCTIONS
# =============================================================================
def filter_player(filter_str, filter_args, issuer, player):
    if filter_str[0] == '!':
        return not filter_player(filter_str[1:], filter_args, issuer, player)

    if filter_str[0] == '@':
        player_filter = filter_str[1:]
        if player_filter in PlayerIter.filters:
            return PlayerIter.filters[player_filter](player)

        if player_filter in ('me', 'self'):
            return issuer == player

        return False

    if filter_str[0] == '#':
        try:
            userid = int(filter_str[1:])
        except ValueError:
            return False

        return player.userid == userid

    if filter_str.lower() == 'name':
        return player.name.casefold() == filter_args.casefold()

    if filter_str.lower() in ('steamid', 'steam'):
        return player.steamid.lower() == filter_args.lower()

    if filter_str.lower() == 'index':
        try:
            index = int(filter_args)
        except ValueError:
            return False

        return player.index == index

    return False


def iter_filter_targets(filter_str, filter_args, issuer):
    for player in PlayerIter():
        if filter_player(filter_str, filter_args, issuer, player):
            yield player


# =============================================================================
# >> CLASSES
# =============================================================================
class BaseFeatureCommand:
    def __init__(self, commands, feature):
        if isinstance(commands, str):
            commands = [commands, ]

        commands = list(commands)

        self.feature = feature

        TypedSayCommand(
            ['!spa', ] + commands, feature.flag
        )(self._get_public_chat_callback())

        TypedSayCommand(
            ['/spa', ] + commands, feature.flag
        )(self._get_private_chat_callback())

        TypedClientCommand(
            ['spa', ] + commands, feature.flag
        )(self._get_client_callback())

    def _get_public_chat_callback(self):
        raise NotImplementedError

    def _get_private_chat_callback(self):
        raise NotImplementedError

    def _get_client_callback(self):
        raise NotImplementedError


class FeatureCommand(BaseFeatureCommand):
    def _execute(self, command_info):
        client = clients[command_info.index]

        # Sync execution to avoid issuer replacement if the feature itself
        # is going to execute any commands
        client.sync_execution(self.feature.execute, (client,))

    def _get_public_chat_callback(self):
        def public_chat_callback(command_info):
            self._execute(command_info)
            return CommandReturn.CONTINUE

        return public_chat_callback

    def _get_private_chat_callback(self):
        def private_chat_callback(command_info):
            self._execute(command_info)
            return CommandReturn.BLOCK

        return private_chat_callback

    def _get_client_callback(self):
        def client_callback(command_info):
            self._execute(command_info)

        return client_callback


class PlayerBasedFeatureCommand(BaseFeatureCommand):
    def __init__(self, commands, feature, deny_mass_execution=False):
        super().__init__(commands, feature)

        self._deny_mass_execution = deny_mass_execution

    def _execute(self, command_info, filter_str, filter_args):
        client = clients[command_info.index]

        players = []
        for player in iter_filter_targets(
                filter_str, filter_args, client.player):

            if not self.feature.filter(client, player):
                continue

            players.append(player)

        if self._deny_mass_execution and len(players) > 1:
            return

        for player in players:
            client.sync_execution(self.feature.execute, (client, player))

    def _get_public_chat_callback(self):
        def public_chat_callback(
                command_info, filter_str:str, filter_args:str=""):

            self._execute(command_info, filter_str, filter_args)
            return CommandReturn.CONTINUE

        return public_chat_callback

    def _get_private_chat_callback(self):
        def private_chat_callback(
                command_info, filter_str:str, filter_args:str=""):

            self._execute(command_info, filter_str, filter_args)
            return CommandReturn.BLOCK

        return private_chat_callback

    def _get_client_callback(self):
        def client_callback(command_info, filter_str:str, filter_args:str=""):
            self._execute(command_info, filter_str, filter_args)

        return client_callback