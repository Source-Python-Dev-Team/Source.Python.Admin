# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from events import Event
from players.dictionary import PlayerDictionary
from players.entity import Player
from players.teams import teams_by_number

# Source.Python Admin
from admin.core.features import PlayerBasedFeature
from admin.core.frontends.menus import (
    main_menu, MenuSection, PlayerBasedMenuCommand)
from admin.core.helpers import log_admin_action
from admin.core.plugins.strings import PluginStrings


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
plugin_strings = PluginStrings("admin_team_management")
delayed_swaps = PlayerDictionary(lambda index: None)


# =============================================================================
# >> CLASSES
# =============================================================================
class _MoveToSpecFeature(PlayerBasedFeature):
    flag = "admin.admin_team_management.spec"

    def execute(self, client, player):
        player.team = 1

        log_admin_action(plugin_strings['message spec'].tokenized(
            admin_name=client.player.name,
            player_name=player.name,
        ))

# The singleton object of the _MoveToSpecFeature class.
move_to_spec_feature = _MoveToSpecFeature()


class _MoveToTeamFeature(PlayerBasedFeature):
    flag = "admin.admin_team_management.swap"
    team = None

    def execute(self, client, player):
        player.team = self.team

        log_admin_action(plugin_strings['message swapped'].tokenized(
            admin_name=client.player.name,
            player_name=player.name,
            team=teams_by_number[self.team].upper()
        ))


class _MoveToTFeature(_MoveToTeamFeature):
    team = 2

# The singleton object of the _MoveToTFeature class.
move_to_t_feature = _MoveToTFeature()


class _MoveToCTFeature(_MoveToTeamFeature):
    team = 3

# The singleton object of the _MoveToCTFeature class.
move_to_ct_feature = _MoveToCTFeature()


class _DelayedMoveToTeamFeature(PlayerBasedFeature):
    flag = "admin.admin_team_management.delayed_swap"
    team = None

    def execute(self, client, player):
        delayed_swaps[player.index] = self.team

        log_admin_action(plugin_strings['message delayed_swap'].tokenized(
            admin_name=client.player.name,
            player_name=player.name,
            team=teams_by_number[self.team].upper()
        ))


class _DelayedMoveToTFeature(_DelayedMoveToTeamFeature):
    team = 2

# The singleton object of the _DelayedMoveToTFeature class.
delayed_move_to_t_feature = _DelayedMoveToTFeature()


class _DelayedMoveToCTFeature(_DelayedMoveToTeamFeature):
    team = 3

# The singleton object of the _DelayedMoveToCTFeature class.
delayed_move_to_ct_feature = _DelayedMoveToCTFeature()


# =============================================================================
# >> MENU ENTRIES
# =============================================================================
menu_section = main_menu.add_entry(MenuSection(
    main_menu, plugin_strings['section_title']))

move_to_spec_menu_command = menu_section.add_entry(PlayerBasedMenuCommand(
    move_to_spec_feature,
    menu_section,
    plugin_strings['popup_title move_to_spec']
))

move_to_t_menu_command = menu_section.add_entry(PlayerBasedMenuCommand(
    move_to_t_feature,
    menu_section,
    plugin_strings['popup_title move_to_t']
))

move_to_ct_menu_command = menu_section.add_entry(PlayerBasedMenuCommand(
    move_to_ct_feature,
    menu_section,
    plugin_strings['popup_title move_to_ct']
))

delayed_move_to_t_menu_command = menu_section.add_entry(
    PlayerBasedMenuCommand(
        delayed_move_to_t_feature,
        menu_section,
        plugin_strings['popup_title move_to_t_delayed']
))

delayed_move_to_ct_menu_command = menu_section.add_entry(
    PlayerBasedMenuCommand(
        delayed_move_to_ct_feature,
        menu_section,
        plugin_strings['popup_title move_to_ct_delayed']
))


# =============================================================================
# >> EVENTS
# =============================================================================
@Event('round_end')
def on_round_end(ev):
    for index, team in delayed_swaps.items():
        if team is None:
            continue

        Player(index).team = team
        delayed_swaps[index] = None
