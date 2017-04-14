# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from base64 import b64encode
import json
from time import time

# Source.Python
from filters.players import PlayerIter
from listeners import OnClientActive, OnClientDisconnect
from players.entity import Player
from players.helpers import get_client_language, userid_from_index

# Source.Python Admin
from ...info import info
from .. import admin_core_logger
from ..clients import clients
from ..strings import strings_common

# Custom Package
try:
    import motdplayer
except ImportError:
    admin_core_logger.log_message(
        "MOTDPlayer package is not installed, "
        "MoTD frontend will be disabled.")

    motdplayer = None

# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
_ws_player_based_pages = []

# =============================================================================
# >> CLASSES
# =============================================================================
if motdplayer is None:
    base_page_meta = type
else:
    base_page_meta = motdplayer.PageMeta


class PageMeta(base_page_meta):
    def __init__(cls, name, bases, namespace):
        if namespace.get('page_abstract', False):
            del cls.page_abstract
            return

        if not hasattr(cls, 'admin_plugin_id'):
            raise ValueError("Class '{}' doesn't have 'admin_plugin_id' "
                             "attribute".format(cls))

        if not hasattr(cls, 'admin_plugin_type'):
            raise ValueError("Class '{}' doesn't have 'admin_plugin_type' "
                             "attribute".format(cls))

        if not hasattr(cls, 'page_id'):
            raise ValueError("Class '{}' doesn't have 'page_id' "
                             "attribute".format(cls))

        if cls.admin_plugin_id is None:
            raise ValueError("Class '{}' has its 'admin_plugin_id' "
                             "attribute set to None".format(cls))

        if cls.admin_plugin_type is None:
            raise ValueError("Class '{}' has its 'admin_plugin_type' "
                             "attribute set to None".format(cls))

        if cls.page_id is None:
            raise ValueError("Class '{}' has its 'page_id' "
                             "attribute set to None".format(cls))

        cls.plugin_id = "admin"
        cls.page_id = "{}.{}.{}".format(
            cls.admin_plugin_type, cls.admin_plugin_id, cls.page_id)

        # Only after we set the attribute, call parent meta's __init__
        super().__init__(name, bases, namespace)


if motdplayer is None:
    class Page(metaclass=PageMeta):
        abstract = True
        page_abstract = True

        page_id = None
        ws_support = False

        admin_plugin_id = None
        admin_plugin_type = None
        flag = None
        nav_path = None

        @classmethod
        def send(cls, index):
            pass

else:
    class Page(motdplayer.Page, metaclass=PageMeta):
        abstract = True
        page_abstract = True

        admin_plugin_id = None
        admin_plugin_type = None
        flag = None
        nav_path = None

        def _extract_nav_data(self, nav, client, language):
            sub_nav_data = []

            if isinstance(nav, list):
                for sub_nav in nav:
                    if not sub_nav.is_visible(client):
                        continue

                    sub_nav_data.append(self._extract_nav_data(
                        sub_nav, client, language))

            switches_to = None
            if isinstance(nav, MOTDPageEntry):
                switches_to = nav.page_class.page_id

            return {
                'id': nav.id,
                'title': nav.title.get_string(client.player),
                'selectable': nav.is_selectable(client),
                'subNavs': sub_nav_data,
                'switchesTo': switches_to,
                'navPath': nav.get_nav_path(),
            }

        def on_data_received(self, data):
            if 'spa_action' not in data:
                self.on_page_data_received(data)
                return

            client = clients[self.index]
            language = get_client_language(client.player.index)

            nav_data = {
                'navData': self._extract_nav_data(main_motd, client, language),
                'currentPath': self.nav_path,
            }
            nav_init_b64 = b64encode(
                json.dumps(nav_data).encode('utf-8')).decode('utf-8')

            if data['spa_action'] == "init":
                self.send_data({
                    'admin_version': info.version,
                    'admin_author': info.author,
                    'server_time': time(),
                    'nav_init_b64': nav_init_b64,
                })
                return

        def on_page_data_received(self, data):
            pass


class FeaturePageMeta(PageMeta):
    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)

        if namespace.get('feature_page_abstract', False):
            del cls.feature_page_abstract
            return

        # TODO: There's no sense checking the "feature" attribute for presence,
        # because it's set to None in the base class and can't be removed
        if not hasattr(cls, 'feature'):
            raise ValueError(
                "Class '{}' doesn't have 'feature' attribute".format(cls))

        if cls.feature is None:
            raise ValueError("Class '{}' has its 'feature' "
                             "attribute set to None".format(cls))

        cls.flag = cls.feature.flag


class BaseFeaturePage(Page, metaclass=FeaturePageMeta):
    abstract = True
    page_abstract = True
    feature_page_abstract = True
    feature = None

    ws_support = True


class FeaturePage(BaseFeaturePage):
    abstract = True
    page_abstract = True
    feature_page_abstract = True

    def on_page_data_received(self, data):
        if data['action'] == "execute":
            client = clients[self.index]
            client.sync_execution(self.feature.execute, (client,))

            self.send_data({
                'feature-executed': "scheduled"
            })


class BasePlayerBasedFeaturePage(BaseFeaturePage):
    abstract = True
    page_abstract = True
    feature_page_abstract = True

    # Allow selecting multiple players at once?
    allow_multiple_choices = True

    def filter(self, player):
        if not self.feature.filter(clients[self.index], player):
            return False

        return True

    def _get_player_id(self, player):
        raise NotImplementedError

    def _iter(self):
        raise NotImplementedError

    def _filter_player_ids(self, client, player_ids):
        """Filter out invalid IDs from the given list.

        :param client: Client that performs the action.
        :param list player_ids: Unfiltered list of IDs.
        :return: Filtered list of :class:`players.entity.Player` instances.
        :rtype: list
        """
        players = []
        for player in self._iter():
            if self._get_player_id(player) not in player_ids:
                continue

            # Does player still fit our conditions?
            if not self.feature.filter(client, player):
                continue

            players.append(player)

        return players

    def _execute(self, client, id_):
        raise NotImplementedError

    def on_page_data_received(self, data):
        client = clients[self.index]

        if data['action'] == "execute":
            player_ids = data['player_ids']

            for player in self._filter_player_ids(client, player_ids):
                client.sync_execution(
                    self._execute, (client, self._get_player_id(player)))

            self.send_data({
                'feature-executed': "scheduled"
            })

        if data['action'] == "get-players":
            if self.ws_instance:
                for player in self._iter():
                    if not self.feature.filter(client, player):
                        continue

                    self.send_data({
                        'action': "add-player",
                        'player': {
                            'id': self._get_player_id(player),
                            'name': player.name,
                        },
                    })

            else:
                player_data = []
                for player in self._iter():
                    if not self.feature.filter(client, player):
                        continue

                    player_data.append({
                        'id': self._get_player_id(player),
                        'name': player.name,
                    })

                self.send_data({
                    'players': player_data
                })

    def on_error(self, error):
        if self.ws_instance and self in _ws_player_based_pages:
            _ws_player_based_pages.remove(self)


class PlayerBasedFeaturePage(BasePlayerBasedFeaturePage):
    abstract = True
    page_abstract = True
    feature_page_abstract = True

    # Base filters that will be passed to PlayerIter
    _base_filter = 'all'
    _ws_base_filter = 'all'

    def __init__(self, index, ws_instance):
        super().__init__(index, ws_instance)

        if ws_instance:
            _ws_player_based_pages.append(self)

    @property
    def base_filter(self):
        return self._ws_base_filter if self.ws_instance else self._base_filter

    def _get_player_id(self, player):
        return player.userid

    def _iter(self):
        yield from PlayerIter(self.base_filter)

    def _execute(self, client, id_):
        self.feature.execute(client, Player.from_userid(id_))

    def filter(self, player):
        if not PlayerIter.filters[self.base_filter](player):
            return False

        if not super().filter(player):
            return False

        return True


class MOTDEntry:
    """Represent a selectable entry."""

    def __init__(self, parent, title, id_):
        self.parent = parent
        self.title = title
        self.id = id_

    def is_visible(self, client):
        """Return if this entry is visible for the given client.

        :param Client client: Given client.
        :return: Whether or not visible.
        :rtype: bool
        """
        return True

    def is_selectable(self, client):
        """Return is this entry appears selectable for the given client.

        :param Client client: Given client.
        :return: Whether or not selectable.
        :rtype: bool
        """
        return True

    def get_nav_path(self):
        entry, result = self, []
        while entry.parent is not None:
            result.append(entry.id)
            entry = entry.parent
        return list(reversed(result))


class MOTDSection(MOTDEntry, list):
    """Represents a selectable section of other entries."""

    def __init__(self, parent, title, id_):
        super().__init__(parent, title, id_)

        # Entries appear in the same order their IDs appear in self.order
        self.order = []

    def add_entry(self, entry):
        """Add another entry to this section then sort again.

        :param MOTDEntry entry: Given entry.
        :return: Passed entry without alteration.
        :rtype: MOTDEntry
        """
        self.append(entry)
        self.sort(key=lambda entry_: (self.order.index(entry_.id)
                                      if entry_.id in self.order else -1))

        return entry

    def is_visible(self, client):
        """Return if this section is visible for the given client.

        :param Client client: Given client.
        :return: Whether or not visible.
        :rtype: bool
        """
        default = super().is_visible(client)
        if not default:
            return False

        for item in self:
            if item.is_visible(client):
                return True

        return False

    def is_selectable(self, client):
        """Return if this section is selectable for the given client.

        :param Client client: Given client.
        :return: Whether or not visible.
        :rtype: bool
        """
        default = super().is_selectable(client)
        if not default:
            return False

        for item in self:
            if item.is_selectable(client):
                return True

        return False


class MOTDPageEntry(MOTDEntry):
    """Base class for the entry that is bound to a specific Page."""

    def __init__(self, parent, page_class, title, id_):
        super().__init__(parent, title, id_)

        self.page_class = page_class

        page_class.nav_path = self.get_nav_path()

    def is_visible(self, client):
        """Return if this entry is visible for the given client.

        :param Client client: Given client.
        :return: Whether or not visible.
        :rtype: bool
        """
        default = super().is_visible(client)
        if not default:
            return False

        # Do we even need to check the permission?
        if self.page_class.flag is None:
            return True

        return client.has_permission(self.page_class.flag)

    def is_selectable(self, client):
        """Return if this section is selectable for the given client.

        :param Client client: Given client.
        :return: Whether or not visible.
        :rtype: bool
        """
        default = super().is_selectable(client)
        if not default:
            return False

        # Do we even need to check the permission?
        if self.page_class.flag is None:
            return True

        return client.has_permission(self.page_class.flag)


class MOTDPageSection(MOTDPageEntry, MOTDSection):
    pass


class MainPage(Page):
    admin_plugin_id = 'core'
    admin_plugin_type = 'core'
    page_id = 'main'
    nav_path = ()


# =============================================================================
# >> MAIN SECTION
# =============================================================================
main_motd = MOTDPageSection(
    None, MainPage, strings_common['title motd'], 'admin')


# =============================================================================
# >> LISTENERS
# =============================================================================
@OnClientActive
def listener_on_client_active(index):
    player = Player(index)
    for ws_player_based_page in _ws_player_based_pages:
        if not ws_player_based_page.filter(player):
            continue

        ws_player_based_page.send_data({
            'action': 'add-player',
            'player': {
                'id': player.userid,
                'name': player.name,
            },
        })


@OnClientDisconnect
def listener_on_client_disconnect(index):
    userid = userid_from_index(index)
    for ws_player_based_page in _ws_player_based_pages:
        ws_player_based_page.send_data({
            'action': 'remove-id',
            'id': userid,
        })
