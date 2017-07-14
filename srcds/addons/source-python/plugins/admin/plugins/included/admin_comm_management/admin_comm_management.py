# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python Admin
from admin.admin import main_menu
from admin.core.frontends.menus import AdminMenuSection

# Included Plugin
from .blocks.base import BlockCommAdminCommand
from .blocks.voice import (
    block_voice_feature, blocked_voice_user_manager, unblock_any_voice_feature,
    unblock_my_voice_feature, UnblockAnyVoiceAdminCommand,
    UnblockMyVoiceAdminCommand)
from .strings import plugin_strings


# =============================================================================
# >> MENU ENTRIES
# =============================================================================
menu_section = main_menu.add_entry(AdminMenuSection(
    main_menu, plugin_strings['section_title main']))

menu_section_chat = menu_section.add_entry(AdminMenuSection(
    menu_section, plugin_strings['section_title chat']))

menu_section_voice = menu_section.add_entry(AdminMenuSection(
    menu_section, plugin_strings['section_title voice']))

#menu_section_chat.add_entry(BlockCommAdminCommand(
#    block_chat_feature,
#    menu_section_chat,
#    plugin_strings['popup_title block_chat']))

menu_section_voice.add_entry(BlockCommAdminCommand(
    block_voice_feature,
    menu_section_voice,
    plugin_strings['popup_title block_voice']))

#menu_section_chat.add_entry(UnblockAnyChatAdminCommand(
#    unblock_any_chat_feature,
#    menu_section_chat,
#    plugin_strings['popup_title unblock_chat_any']))

menu_section_voice.add_entry(UnblockAnyVoiceAdminCommand(
    unblock_any_voice_feature,
    menu_section_voice,
    plugin_strings['popup_title unblock_voice_any']))

#menu_section_voice.add_entry(UnblockMyChatAdminCommand(
#    unblock_my_chat_feature,
#    menu_section_chat,
#    plugin_strings['popup_title unblock_chat']))

menu_section_voice.add_entry(UnblockMyVoiceAdminCommand(
    unblock_my_voice_feature,
    menu_section_voice,
    plugin_strings['popup_title unblock_voice']))

# =============================================================================
# >> SYNCHRONOUS DATABASE OPERATIONS
# =============================================================================
#blocked_chat_user_manager.refresh()
blocked_voice_user_manager.refresh()
