# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from filters.players import PlayerIter
from menus import PagedMenu, PagedOption
from translations.strings import LangStrings

# Source.Python Admin
from ..clients import clients
from ..helpers import format_player_name
from ..strings import strings_common


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
strings_menus = LangStrings("admin/menus")


# =============================================================================
# >> CLASSES
# =============================================================================
class AdminMenuEntry:
    """Represent a selectable entry in main admin menu or its submenus."""
    def __init__(self, parent, title, id_=None):
        self._parent = parent
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

    def select(self, client):
        raise NotImplementedError


class AdminMenuSection(AdminMenuEntry, list):
    """Represents a selectable section of other entries in admin menus."""
    def __init__(self, parent, title, id_=None):
        super().__init__(parent, title, id_)

        # Entries appear in the same order their IDs appear in self.order
        self.order = []

        self.popup = PagedMenu(title=title)

        if parent is not None:
            self.popup.parent_menu = parent.popup

        @self.popup.register_select_callback
        def select_callback(popup, index, option):
            option.value.select(clients[index])

        @self.popup.register_build_callback
        def build_callback(popup, index):
            client = clients[index]
            popup.clear()

            for item in self:
                if not item.is_visible(client):
                    continue

                selectable = item.is_selectable(client)
                if isinstance(item, AdminMenuSection):
                    title = strings_menus['extensible'].tokenized(
                        item=item.title)
                else:
                    title = item.title

                popup.append(PagedOption(
                    text=title,
                    value=item,
                    highlight=selectable,
                    selectable=selectable
                ))

    def add_entry(self, entry):
        """Add another entry to this section then sort again.

        :param AdminMenuEntry entry: Given entry.
        :return: Passed entry without alteration.
        :rtype: AdminMenuEntry
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

    def select(self, client):
        if not self.is_visible(client) or not self.is_selectable(client):
            client.tell(strings_common['unavailable'])
            return

        client.send_popup(self.popup)


class AdminCommand(AdminMenuEntry):
    """Base class for entry that is bound to execute a feature."""
    def __init__(self, feature, parent, title, id_=None):
        """Initialize AdminCommand instance.

        :param feature: Feature instance this entry is bound to execute.
        :param parent: Parent AdminMenuSection instance.
        :param title: TranslationStrings instance.
        :param str|None id_: String ID that will be used to sort this item.
        """
        super().__init__(parent, title, id_)

        self.feature = feature

    def is_visible(self, client):
        """Return if this section is visible for the given client.

        :param Client client: Given client.
        :return: Whether or not visible.
        :rtype: bool
        """
        default = super().is_visible(client)
        if not default:
            return False

        # Do we even need to check the permission?
        if self.feature.flag is None:
            return True

        return client.has_permission(self.feature.flag)

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
        if self.feature.flag is None:
            return True

        return client.has_permission(self.feature.flag)

    def select(self, client):
        client.active_popup = None

        self.feature.execute(client)

        # Does client still not have an active popup?
        if client.active_popup is None:

            # Display our parent menu
            self._parent.select(client)


class PlayerBasedSelectionFrame:
    """This class describes a selected option of the player-based menu."""
    # Current player list of targets (don't store Player instances in case
    # somebody disconnects)
    player_userids = None

    # In multiple selection mode?
    selecting_multiple = False

    # Last selection was "Select multiple"/"Select single"/"Ready"?
    special_toggle_multiple = False


class PlayerBasedMenuDraft:
    """This class describes a player-based menu that should be built by the
    build callback."""
    # Menu title
    title = None

    def __init__(self):

        # Options list
        self.options = []


class PlayerBasedAdminCommand(AdminCommand):
    """Base class for entry that is bound to perform a command on the players.
    """
    # Base filter that will be passed to PlayerIter
    base_filter = 'all'

    # Allow selecting multiple players at once?
    allow_multiple_choices = True

    def __init__(self, feature, parent, title, id_=None):
        """Initialize PlayerBasedAdminCommand instance.

        :param feature: PlayerBasedFeature instance this entry is bound to
        execute.
        :param parent: Parent AdminMenuSection instance.
        :param title: TranslationStrings instance.
        :param str|None id_: String ID that will be used to sort this item.
        """
        super().__init__(feature, parent, title, id_)

        self.popup = PagedMenu()
        self._draft = None

        if parent is not None:
            self.popup.parent_menu = parent.popup

        if self.allow_multiple_choices:
            @self.popup.register_select_callback
            def select_callback(popup, index, option):

                # Obtain PlayerBasedSelectionFrame instance from selected
                # option
                frame = option.value

                # Get the Client instance by player index
                client = clients[index]

                # Create a new draft
                draft = self._draft = PlayerBasedMenuDraft()

                # Save selecting_multiple flag
                selecting_multiple = frame.selecting_multiple

                # Was option #1 pressed?
                if frame.special_toggle_multiple:

                    # Were we selecting multiple players?
                    if frame.selecting_multiple:

                        # Were any players selected?
                        if frame.player_userids:

                            # Call selection callback with them then and return
                            self._player_select(client, frame.player_userids)
                            return

                        # Toggle selecting_multiple flag
                        selecting_multiple = False

                    else:

                        # Toggle selecting_multiple flag
                        selecting_multiple = True

                else:

                    # We were not selecting multiple players?
                    if not frame.selecting_multiple:

                        # Call selection callback with newly selected player
                        # and return
                        self._player_select(client, frame.player_userids)
                        return

                # Determine the title (plural or singular form)
                if selecting_multiple:
                    draft.title = strings_menus['title select_players']
                else:
                    draft.title = strings_menus['title select_player']

                draft.title = draft.title.tokenized(base=title)

                # Filter unavailable players out of the menu
                selected_players = self._filter_player_userids(
                    client, frame.player_userids)
                selected_player_userids = [
                    player.userid for player in selected_players]

                if selecting_multiple:

                    # Multi-selection mode
                    for player in PlayerIter(self.base_filter):
                        if not self.feature.filter(client, player):
                            continue

                        player_userids = selected_player_userids[:]
                        if player.userid in player_userids:

                            # This option appears if a player is selected
                            # - its player list will lack this player
                            player_userids.remove(player.userid)
                            string = strings_menus['select_player selected']
                        else:

                            # This option appears if a player is not selected
                            # - its player list will contain this player
                            player_userids.append(player.userid)
                            string = strings_menus['select_player unselected']

                        # Create a selection frame for this player
                        new_frame = PlayerBasedSelectionFrame()
                        new_frame.player_userids = player_userids
                        new_frame.selecting_multiple = True
                        new_frame.special_toggle_multiple = False

                        draft.options.append(PagedOption(
                            text=string.tokenized(
                                base=self.render_player_name(player)),
                            value=new_frame
                        ))

                    # Create a "Ready"/"Select single" selection frame
                    new_frame = PlayerBasedSelectionFrame()
                    new_frame.player_userids = selected_player_userids
                    new_frame.selecting_multiple = True
                    new_frame.special_toggle_multiple = True

                    if selected_players:
                        string = strings_menus['select_player done_selecting']
                    else:
                        string = strings_menus[
                            'select_player turn_selection_off']

                    draft.options.insert(0, PagedOption(
                        text=string,
                        value=new_frame
                    ))

                else:

                    # Single-selection mode
                    # Create a "Select multiple" selection frame
                    new_frame = PlayerBasedSelectionFrame()
                    new_frame.player_userids = selected_player_userids
                    new_frame.selecting_multiple = False
                    new_frame.special_toggle_multiple = True

                    string = strings_menus['select_player turn_selection_on']

                    draft.options.append(PagedOption(
                        text=string,
                        value=new_frame
                    ))

                    for player in PlayerIter(self.base_filter):
                        if not self.feature.filter(client, player):
                            continue

                        player_userids = selected_player_userids + [
                            player.userid]

                        string = strings_menus['select_player single']

                        new_frame = PlayerBasedSelectionFrame()
                        new_frame.player_userids = player_userids
                        new_frame.selecting_multiple = False
                        new_frame.special_toggle_multiple = False

                        draft.options.append(PagedOption(
                            text=string.tokenized(
                                base=self.render_player_name(player)),
                            value=new_frame
                        ))

                    client.send_popup(popup)

        else:
            @self.popup.register_select_callback
            def select_callback(popup, index, option):

                # Obtain PlayerBasedSelectionFrame instance from selected
                # option
                frame = option.value

                # Get the Client instance by player index
                client = clients[index]

                # Call selection callback with newly selected player
                self._player_select(client, frame.player_userids)

        @self.popup.register_build_callback
        def build_callback(popup, index):

            # Clear the popup
            popup.clear()

            # If popup is sent without draft, build a brand new one
            if self._draft is None:

                # Get the Client instance by player index
                client = clients[index]

                # Create a new draft
                draft = self._draft = PlayerBasedMenuDraft()
                draft.title = strings_menus[
                    'title select_player'].tokenized(base=title)

                if self.allow_multiple_choices:

                    # Create a "Select multiple" selection frame
                    new_frame = PlayerBasedSelectionFrame()
                    new_frame.player_userids = []
                    new_frame.selecting_multiple = False
                    new_frame.special_toggle_multiple = True

                    string = strings_menus['select_player turn_selection_on']

                    draft.options.append(PagedOption(
                        text=string,
                        value=new_frame
                    ))

                # Add proper players to the draft
                for player in PlayerIter(self.base_filter):
                    if not self.feature.filter(client, player):
                        continue

                    player_userids = [player.userid]

                    string = strings_menus['select_player single']

                    new_frame = PlayerBasedSelectionFrame()
                    new_frame.player_userids = player_userids
                    new_frame.selecting_multiple = False
                    new_frame.special_toggle_multiple = False

                    draft.options.append(PagedOption(
                        text=string.tokenized(
                            base=self.render_player_name(player)),
                        value=new_frame
                    ))

            popup.title = self._draft.title
            popup[:] = self._draft.options[:]

            # Set draft back to None
            self._draft = None

    def _filter_player_userids(self, client, player_userids):
        """Filter out invalid UserIDs from the given list, return list of
        :class:`players.entity.Player` instances.

        :param client: Client that performs the action.
        :param list player_userids: Unfiltered list of UserIDs.
        :return: Filtered list of :class:`players.entity.Player` instances.
        :rtype: list
        """
        players = []
        for player in PlayerIter(self.base_filter):
            if player.userid not in player_userids:
                continue

            # Does player still fit our conditions?
            if not self.feature.filter(client, player):
                continue

            players.append(player)

        return players

    def _player_select(self, client, player_userids):
        """Filter out invalid userids and call player_select with a list of
        :class:`players.entity.Player` instances.

        :param client: Client that performs the action.
        :param list player_userids: Unfiltered list of UserIDs.
        """

        client.active_popup = None

        for player in self._filter_player_userids(client, player_userids):
            self.feature.execute(client, player)

        # Does client still not have an active popup?
        if client.active_popup is None:

            # Display our parent menu
            self._parent.select(client)

    @staticmethod
    def render_player_name(player):
        """Return a name of the given player as it should appear in the menu.

        :param players.entity.Player player: Given player.
        :return: Formatted player's name.
        :rtype: str
        """
        return format_player_name(player.name)

    def select(self, client):
        if not self.is_visible(client) or not self.is_selectable(client):
            client.tell(strings_common['unavailable'])
            return

        client.send_popup(self.popup)
