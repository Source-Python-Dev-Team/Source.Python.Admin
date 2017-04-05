# =============================================================================
# >> IMPORTS
# =============================================================================
from .clients import clients


# =============================================================================
# >> CLASSES
# =============================================================================
class BaseFeature:
    # Required permission in Source.Python auth system to execute this feature
    flag = None


class Feature(BaseFeature):
    @staticmethod
    def execute(client):
        """Execute the feature.

        :param client: Client that performs the action.
        """
        raise NotImplementedError


class PlayerBasedFeature(BaseFeature):
    # Allow clients to execute this feature on themselves?
    allow_execution_on_self = True

    # Allow clients to execute this feature on those clients that have
    # permissions to execute this command, too?
    allow_execution_on_equal_priority = False

    @staticmethod
    def execute(client, player):
        """Execute the feature on the given player.

        :param client: Client that performs the action.
        :param player: Player to perform the action on.
        """
        raise NotImplementedError

    def filter(self, client, player):
        """Determine if a client is able to execute the feature on the given
        player.

        :param client: Client that performs the action.
        :param player: Player to perform the action on.
        :return: Whether to allow or disallow the action.
        :rtype: bool
        """
        if not self.allow_execution_on_self and client.player == player:
            return False

        if self.allow_execution_on_equal_priority:
            return True

        another_client = clients[player.index]
        return not another_client.has_permission(self.flag)
