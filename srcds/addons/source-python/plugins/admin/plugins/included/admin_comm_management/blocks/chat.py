# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from commands import CommandReturn
from commands.say import SayFilter

# Source.Python Admin
from admin.core.clients import clients
from admin.core.helpers import log_admin_action

# Included Plugin
from ..models import BlockedChatUser
from ..strings import plugin_strings
from .base import (
    BlockCommFeature, BlockedCommUserManager, UnblockAnyCommMenuCommand,
    UnblockCommFeature, UnblockMyCommMenuCommand)


# =============================================================================
# >> CLASSES
# =============================================================================
class _BlockedChatUserManager(BlockedCommUserManager):
    model = BlockedChatUser

# The singleton object for the _BlockedChatUserManager class.
blocked_chat_user_manager = _BlockedChatUserManager()


class _BlockChatFeature(BlockCommFeature):
    flag = "admin.admin_comm_management.block_chat"
    blocked_comm_user_manager = blocked_chat_user_manager

    def execute(self, client, player, duration):
        super().execute(client, player, duration)

        log_admin_action(plugin_strings['message chat_blocked'].tokenized(
            admin_name=client.name,
            player_name=player.name,
        ))

# The singleton object of the _BlockChatFeature class.
block_chat_feature = _BlockChatFeature()


class _UnblockChatFeature(UnblockCommFeature):
    feature_abstract = True
    blocked_comm_user_manager = blocked_chat_user_manager

    def execute(self, client, blocked_comm_user_info):
        super().execute(client, blocked_comm_user_info)

        log_admin_action(plugin_strings['message chat_unblocked'].tokenized(
            admin_name=client.name,
            player_name=blocked_comm_user_info.name,
        ))


class _UnblockAnyChatFeature(_UnblockChatFeature):
    flag = "admin.admin_comm_management.unblock_any_chat"

# The singleton object of the _UnblockAnyChatFeature class.
unblock_any_chat_feature = _UnblockAnyChatFeature()


class _UnblockMyChatFeature(_UnblockChatFeature):
    flag = "admin.admin_comm_management.block_chat"

# The singleton object of the _UnblockMyChatFeature class.
unblock_my_chat_feature = _UnblockMyChatFeature()


class UnblockAnyChatMenuCommand(UnblockAnyCommMenuCommand):
    popup_title = plugin_strings['popup_title unblock_chat_any']


class UnblockMyChatMenuCommand(UnblockMyCommMenuCommand):
    popup_title = plugin_strings['popup_title unblock_chat']


# =============================================================================
# >> COMMAND FILTERS
# =============================================================================
@SayFilter
def say_filter(command, index, team_only):
    client = clients[index]

    if blocked_chat_user_manager.is_blocked(client.steamid):
        client.tell(plugin_strings['error chat_block'])
        return CommandReturn.BLOCK

    return CommandReturn.CONTINUE
