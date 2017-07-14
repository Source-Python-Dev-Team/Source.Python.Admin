# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from filters.players import PlayerIter
from listeners import OnClientActive
from listeners.tick import Delay
from players.dictionary import PlayerDictionary
from players.voice import mute_manager

# Source.Python Admin
from admin.core.helpers import log_admin_action

# Included Plugin
from ..models import BlockedVoiceUser
from ..strings import plugin_strings
from .base import (
    BlockCommFeature, BlockedCommUserManager, UnblockAnyCommMenuCommand,
    UnblockCommFeature, UnblockMyCommMenuCommand)


# =============================================================================
# >> FUNCTIONS
# =============================================================================
def sync_voice_blocked_players():
    for player in PlayerIter('human'):
        if blocked_voice_user_manager.is_blocked(player.steamid):
            mute_manager.mute_player(player.index)
        else:
            mute_manager.unmute_player(player.index)


# =============================================================================
# >> CLASSES
# =============================================================================
class _BlockedVoiceUserManager(BlockedCommUserManager):
    model = BlockedVoiceUser

    def _on_change(self):
        sync_voice_blocked_players()

# The singleton object for the _BlockedVoiceUserManager class.
blocked_voice_user_manager = _BlockedVoiceUserManager()


class _BlockVoiceFeature(BlockCommFeature):
    flag = "admin.admin_comm_management.block_voice"
    blocked_comm_user_manager = blocked_voice_user_manager

    def execute(self, client, player, duration):
        super().execute(client, player, duration)

        if player_unmute_delays[player.index] is not None:
            if player_unmute_delays[player.index].running:
                player_unmute_delays[player.index].cancel()
            player_unmute_delays[player.index] = None

        if duration >= 0:
            player_unmute_delays[player.index] = Delay(
                duration + 0.1, sync_voice_blocked_players)

        log_admin_action(plugin_strings['message voice_blocked'].tokenized(
            admin_name=client.name,
            player_name=player.name,
        ))

# The singleton object of the _BlockVoiceFeature class.
block_voice_feature = _BlockVoiceFeature()


class _UnblockVoiceFeature(UnblockCommFeature):
    feature_abstract = True
    blocked_comm_user_manager = blocked_voice_user_manager

    def execute(self, client, blocked_comm_user_info):
        super().execute(client, blocked_comm_user_info)

        log_admin_action(plugin_strings['message voice_unblocked'].tokenized(
            admin_name=client.name,
            player_name=blocked_comm_user_info.name,
        ))


class _UnblockAnyVoiceFeature(_UnblockVoiceFeature):
    flag = "admin.admin_comm_management.unblock_any_voice"

# The singleton object of the _UnblockAnyVoiceFeature class.
unblock_any_voice_feature = _UnblockAnyVoiceFeature()


class _UnblockMyVoiceFeature(_UnblockVoiceFeature):
    flag = "admin.admin_comm_management.block_voice"

# The singleton object of the _UnblockMyVoiceFeature class.
unblock_my_voice_feature = _UnblockMyVoiceFeature()


class UnblockAnyVoiceMenuCommand(UnblockAnyCommMenuCommand):
    popup_title = plugin_strings['popup_title unblock_voice_any']


class UnblockMyVoiceMenuCommand(UnblockMyCommMenuCommand):
    popup_title = plugin_strings['popup_title unblock_voice']


class _PlayerUnmuteDelaysDictionary(PlayerDictionary):
    def on_automatically_removed(self, index):
        delay = self[index]
        delay.cancel()

# The singleton object of the _PlayerUnmuteDelaysDictionary class.
player_unmute_delays = _PlayerUnmuteDelaysDictionary(lambda index: None)


# =============================================================================
# >> LISTENERS
# =============================================================================
@OnClientActive
def listener_on_client_active(index):
    sync_voice_blocked_players()
