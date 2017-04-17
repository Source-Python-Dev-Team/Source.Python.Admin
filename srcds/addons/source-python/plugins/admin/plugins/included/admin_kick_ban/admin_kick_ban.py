# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from players.helpers import get_client_language

# Source.Python Admin
from admin.admin import main_menu
from admin.core.features import PlayerBasedFeature
from admin.core.frontends.menus import (
    AdminCommand, AdminMenuSection, PlayerBasedAdminCommand)
from admin.core.frontends.motd import (
    main_motd, MOTDSection, MOTDPageEntry, PlayerBasedFeaturePage)
from admin.core.helpers import log_admin_action

# Included Plugin
from .bans.ip_address import (
    ban_ip_address_feature, banned_ip_address_manager,
    BanIPAddressMenuCommand, BanIPAddressPage,
    lift_any_ip_address_ban_popup_feature, lift_ip_address_ban_popup_feature,
    LiftIPAddressBanPage, review_ip_address_ban_popup_feature,
    ReviewIPAddressBanPage, search_bad_ip_address_bans_popup_feature)
from .bans.steamid import (
    ban_steamid_feature, banned_steamid_manager,
    BanSteamIDMenuCommand, BanSteamIDPage,
    lift_any_steamid_ban_popup_feature, lift_steamid_ban_popup_feature,
    LiftSteamIDBanPage, review_steamid_ban_popup_feature,
    ReviewSteamIDBanPage, search_bad_steamid_bans_popup_feature)
from .strings import plugin_strings


# =============================================================================
# >> CLASSES
# =============================================================================
class _KickFeature(PlayerBasedFeature):
    flag = "admin.admin_kick_ban.kick"
    allow_execution_on_self = False

    def execute(self, client, player):
        language = get_client_language(player.index)
        player_name = player.name

        player.kick(plugin_strings['default_kick_reason'].get_string(language))

        log_admin_action(plugin_strings['message kicked'].tokenized(
            admin_name=client.name,
            player_name=player_name,
        ))

# The singleton object of the _KickFeature class.
kick_feature = _KickFeature()


class _KickMenuCommand(PlayerBasedAdminCommand):
    allow_multiple_choices = False


class _KickPage(PlayerBasedFeaturePage):
    admin_plugin_id = "admin_kick_ban"
    admin_plugin_type = "included"
    page_id = "kick"

    feature = kick_feature
    _base_filter = 'all'
    _ws_base_filter = 'all'


# =============================================================================
# >> MENU ENTRIES
# =============================================================================
menu_section = main_menu.add_entry(AdminMenuSection(
    main_menu, plugin_strings['section_title main']))

menu_section_steamid = menu_section.add_entry(AdminMenuSection(
    menu_section, plugin_strings['section_title steamid_bans']))

menu_section_ip_address = menu_section.add_entry(AdminMenuSection(
    menu_section, plugin_strings['section_title ip_address_bans']))

lift_steamid_ban_popup_feature.ban_popup.parent_menu = (
    menu_section_steamid.popup)
lift_ip_address_ban_popup_feature.ban_popup.parent_menu = (
    menu_section_ip_address.popup)
lift_any_steamid_ban_popup_feature.ban_popup.parent_menu = (
    menu_section_steamid.popup)
lift_any_ip_address_ban_popup_feature.ban_popup.parent_menu = (
    menu_section_ip_address.popup)
review_steamid_ban_popup_feature.ban_popup.parent_menu = (
    menu_section_steamid.popup)
review_ip_address_ban_popup_feature.ban_popup.parent_menu = (
    menu_section_ip_address.popup)

menu_section.add_entry(_KickMenuCommand(
    kick_feature,
    menu_section,
    plugin_strings['popup_title kick']
))
menu_section_steamid.add_entry(BanSteamIDMenuCommand(
    ban_steamid_feature,
    menu_section_steamid,
    plugin_strings['popup_title ban_steamid']))

menu_section_ip_address.add_entry(BanIPAddressMenuCommand(
    ban_ip_address_feature,
    menu_section_ip_address,
    plugin_strings['popup_title ban_ip_address']))

menu_section_steamid.add_entry(AdminCommand(
    review_steamid_ban_popup_feature,
    menu_section_steamid,
    plugin_strings['popup_title review_steamid']))

menu_section_ip_address.add_entry(AdminCommand(
    review_ip_address_ban_popup_feature,
    menu_section_ip_address,
    plugin_strings['popup_title review_ip_address']))

menu_section_steamid.add_entry(AdminCommand(
    lift_steamid_ban_popup_feature,
    menu_section_steamid,
    plugin_strings['popup_title lift_steamid']))

menu_section_ip_address.add_entry(AdminCommand(
    lift_ip_address_ban_popup_feature,
    menu_section_ip_address,
    plugin_strings['popup_title lift_ip_address']))

menu_section_steamid.add_entry(AdminCommand(
    lift_any_steamid_ban_popup_feature,
    menu_section_steamid,
    plugin_strings['popup_title lift_reviewed_steamid']))

menu_section_ip_address.add_entry(AdminCommand(
    lift_any_ip_address_ban_popup_feature,
    menu_section_ip_address,
    plugin_strings['popup_title lift_reviewed_ip_address']))

menu_section_steamid.add_entry(AdminCommand(
    search_bad_steamid_bans_popup_feature,
    menu_section_steamid,
    plugin_strings['popup_title search_bad_bans']))

menu_section_ip_address.add_entry(AdminCommand(
    search_bad_ip_address_bans_popup_feature,
    menu_section_ip_address,
    plugin_strings['popup_title search_bad_bans']))


# =============================================================================
# >> MOTD ENTRIES
# =============================================================================
motd_section = main_motd.add_entry(MOTDSection(
    main_motd, plugin_strings['section_title main'], 'kick_ban'))

motd_section_steamid = motd_section.add_entry(MOTDSection(
    motd_section, plugin_strings['section_title steamid_bans'], 'steamid'))

motd_section_ip_address = motd_section.add_entry(MOTDSection(
    motd_section, plugin_strings['section_title ip_address_bans'],
    'ip_address'))

motd_section.add_entry(MOTDPageEntry(
    motd_section, _KickPage, plugin_strings['popup_title kick'], 'kick'))

motd_section_steamid.add_entry(MOTDPageEntry(
    motd_section_steamid, BanSteamIDPage,
    plugin_strings['popup_title ban_steamid'], 'ban_steamid'))

motd_section_ip_address.add_entry(MOTDPageEntry(
    motd_section_ip_address, BanIPAddressPage,
    plugin_strings['popup_title ban_ip_address'], 'ban_ip_address'))

motd_section_steamid.add_entry(MOTDPageEntry(
    motd_section_steamid, LiftSteamIDBanPage,
    plugin_strings['popup_title lift_steamid'], 'lift_steamid'))

motd_section_ip_address.add_entry(MOTDPageEntry(
    motd_section_ip_address, LiftIPAddressBanPage,
    plugin_strings['popup_title lift_ip_address'], 'lift_ip_address'))

motd_section_steamid.add_entry(MOTDPageEntry(
    motd_section_steamid, ReviewSteamIDBanPage,
    plugin_strings['popup_title review_steamid'], 'review_steamid'))

motd_section_ip_address.add_entry(MOTDPageEntry(
    motd_section_ip_address, ReviewIPAddressBanPage,
    plugin_strings['popup_title review_ip_address'], 'review_ip_address'))


# =============================================================================
# >> SYNCHRONOUS DATABASE OPERATIONS
# =============================================================================
banned_steamid_manager.refresh()
banned_ip_address_manager.refresh()
