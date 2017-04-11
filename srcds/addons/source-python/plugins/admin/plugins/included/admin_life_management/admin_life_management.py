# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python Admin
from admin.admin import main_menu
from admin.core.features import PlayerBasedFeature
from admin.core.frontends.menus import (
    AdminMenuSection, PlayerBasedAdminCommand)
from admin.core.frontends.motd import (
    main_motd, MOTDSection, MOTDPageEntry, PlayerBasedFeaturePage)
from admin.core.helpers import log_admin_action
from admin.core.plugins.strings import PluginStrings


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
plugin_strings = PluginStrings("admin_life_management")


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


# =============================================================================
# >> MENU ENTRIES
# =============================================================================
menu_section = main_menu.add_entry(AdminMenuSection(
    main_menu, plugin_strings['section_title']))

slay_menu_command = menu_section.add_entry(PlayerBasedAdminCommand(
    slay_feature,
    menu_section,
    plugin_strings['popup_title slay']
))

resurrect_menu_command = menu_section.add_entry(PlayerBasedAdminCommand(
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
