# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from events import Event
from players.entity import Player

# Source.Python Admin
from admin.core.features import PlayerBasedFeature
from admin.core.frontends.commands import PlayerBasedFeatureCommand
from admin.core.frontends.menus import (
    main_menu, MenuSection, PlayerBasedMenuCommand)
from admin.core.frontends.motd import (
    main_motd, MOTDSection, MOTDPageEntry, PlayerBasedFeaturePage)
from admin.core.helpers import log_admin_action
from admin.core.plugins.strings import PluginStrings


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
plugin_strings = PluginStrings("admin_life_management")
_ws_slay_pages = []
_ws_resurrect_pages = []


# =============================================================================
# >> CLASSES
# =============================================================================
class _SlayFeature(PlayerBasedFeature):
    flag = "admin.admin_life_management.slay"

    def execute(self, client, player):
        player.slay()

        log_admin_action(plugin_strings['message slayed'].tokenized(
            admin_name=client.player.name,
            player_name=player.name,
        ))

# The singleton object of the _SlayFeature class.
slay_feature = _SlayFeature()


class _ResurrectFeature(PlayerBasedFeature):
    flag = "admin.admin_life_management.resurrect"

    def execute(self, client, player):
        player.spawn()

        log_admin_action(plugin_strings['message resurrected'].tokenized(
            admin_name=client.player.name,
            player_name=player.name,
        ))

# The singleton object of the _ResurrectFeature class.
resurrect_feature = _ResurrectFeature()


class _SlayPage(PlayerBasedFeaturePage):
    admin_plugin_id = "admin_life_management"
    admin_plugin_type = "included"
    page_id = "slay"

    feature = slay_feature
    _base_filter = 'all'
    _ws_base_filter = 'alive'

    def __init__(self, index, page_request_type):
        super().__init__(index, page_request_type)

        if self.is_websocket:
            _ws_slay_pages.append(self)

    def on_error(self, error):
        super().on_error(error)

        if self.is_websocket and self in _ws_slay_pages:
            _ws_slay_pages.remove(self)


class _ResurrectPage(PlayerBasedFeaturePage):
    admin_plugin_id = "admin_life_management"
    admin_plugin_type = "included"
    page_id = "resurrect"

    feature = resurrect_feature
    _base_filter = 'all'
    _ws_base_filter = 'dead'

    def __init__(self, index, page_request_type):
        super().__init__(index, page_request_type)

        if self.is_websocket:
            _ws_resurrect_pages.append(self)

    def on_error(self, error):
        super().on_error(error)

        if self.is_websocket and self in _ws_resurrect_pages:
            _ws_resurrect_pages.remove(self)


# =============================================================================
# >> COMMAND FRONTEND
# =============================================================================
PlayerBasedFeatureCommand("slay", slay_feature)
PlayerBasedFeatureCommand("resurrect", resurrect_feature)


# =============================================================================
# >> MENU ENTRIES
# =============================================================================
menu_section = main_menu.add_entry(MenuSection(
    main_menu, plugin_strings['section_title']))

slay_menu_command = menu_section.add_entry(PlayerBasedMenuCommand(
    slay_feature,
    menu_section,
    plugin_strings['popup_title slay']
))

resurrect_menu_command = menu_section.add_entry(PlayerBasedMenuCommand(
    resurrect_feature,
    menu_section,
    plugin_strings['popup_title resurrect']
))


# =============================================================================
# >> MOTD ENTRIES
# =============================================================================
motd_section = main_motd.add_entry(MOTDSection(
    main_motd, plugin_strings['section_title'], 'life_management'))

motd_slay_page_entry = motd_section.add_entry(MOTDPageEntry(
    motd_section, _SlayPage, plugin_strings['popup_title slay'], 'slay'))

motd_resurrect_page_entry = motd_section.add_entry(MOTDPageEntry(
    motd_section, _ResurrectPage, plugin_strings['popup_title resurrect'],
    'resurrect'))


# =============================================================================
# >> EVENTS
# =============================================================================
@Event('player_death')
def on_player_death(ev):
    player = Player.from_userid(ev['userid'])
    for ws_slay_page in _ws_slay_pages:
        ws_slay_page.send_remove_id(player)

    for ws_resurrect_page in _ws_resurrect_pages:
        if not ws_resurrect_page.filter(player):
            continue

        ws_resurrect_page.send_add_player(player)


@Event('player_spawn')
def on_player_spawn(ev):
    player = Player.from_userid(ev['userid'])
    for ws_slay_page in _ws_slay_pages:
        if not ws_slay_page.filter(player):
            continue

        ws_slay_page.send_add_player(player)

    for ws_resurrect_page in _ws_resurrect_pages:
        ws_resurrect_page.send_remove_id(player)
