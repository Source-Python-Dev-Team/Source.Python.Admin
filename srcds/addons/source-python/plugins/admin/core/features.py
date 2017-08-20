# =============================================================================
# >> IMPORTS
# =============================================================================
from .clients import clients


# =============================================================================
# >> CLASSES
# =============================================================================
class FeatureMeta(type):
    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)

        if namespace.get('feature_abstract', False):
            del cls.feature_abstract
            return

        if not hasattr(cls, 'flag'):
            raise ValueError("Class '{}' doesn't have 'flag' "
                             "attribute".format(cls))

        if cls.flag is None:
            raise ValueError("Class '{}' has its 'flag' "
                             "attribute set to None".format(cls))


class BaseFeature(metaclass=FeatureMeta):
    feature_abstract = True

    # Required permission in Source.Python auth system to execute this feature
    flag = None


class Feature(BaseFeature):
    feature_abstract = True

    def execute(self, client):
        """Execute the feature.

        :param client: Client that performs the action.
        """
        raise NotImplementedError


class BasePlayerBasedFeature(BaseFeature):
    feature_abstract = True

    # Allow clients to execute this feature on themselves?
    allow_execution_on_self = True

    # Allow clients to execute this feature on those clients that have
    # permissions to execute this command, too?
    allow_execution_on_equal_priority = False

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

        if self.allow_execution_on_equal_priority or client.player == player:
            return True

        another_client = clients[player.index]
        return not another_client.has_permission(self.flag)


class PlayerBasedFeature(BasePlayerBasedFeature):
    feature_abstract = True

    def execute(self, client, player):
        """Execute the feature on the given player.

        :param client: Client that performs the action.
        :param player: Player to perform the action on.
        """
        raise NotImplementedError
