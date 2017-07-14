# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python Admin
from admin.core.frontends.menus import main_menu, MenuSection

# Included Plugin
from .blocks.base import BlockCommMenuCommand
from .blocks.chat import (
    block_chat_feature, blocked_chat_user_manager, unblock_any_chat_feature,
    unblock_my_chat_feature, UnblockAnyChatMenuCommand,
    UnblockMyChatMenuCommand)
from .blocks.voice import (
    block_voice_feature, blocked_voice_user_manager, unblock_any_voice_feature,
    unblock_my_voice_feature, UnblockAnyVoiceMenuCommand,
    UnblockMyVoiceMenuCommand)
from .strings import plugin_strings


# =============================================================================
# >> MENU ENTRIES
# =============================================================================
menu_section = main_menu.add_entry(MenuSection(
    main_menu, plugin_strings['section_title main']))

menu_section_chat = menu_section.add_entry(MenuSection(
    menu_section, plugin_strings['section_title chat']))

menu_section_voice = menu_section.add_entry(MenuSection(
    menu_section, plugin_strings['section_title voice']))

menu_section_chat.add_entry(BlockCommMenuCommand(
    block_chat_feature,
    menu_section_chat,
    plugin_strings['popup_title block_chat']))

menu_section_voice.add_entry(BlockCommMenuCommand(
    block_voice_feature,
    menu_section_voice,
    plugin_strings['popup_title block_voice']))

menu_section_chat.add_entry(UnblockAnyChatMenuCommand(
    unblock_any_chat_feature,
    menu_section_chat,
    plugin_strings['popup_title unblock_chat_any']))

menu_section_voice.add_entry(UnblockAnyVoiceMenuCommand(
    unblock_any_voice_feature,
    menu_section_voice,
    plugin_strings['popup_title unblock_voice_any']))

menu_section_chat.add_entry(UnblockMyChatMenuCommand(
    unblock_my_chat_feature,
    menu_section_chat,
    plugin_strings['popup_title unblock_chat']))

menu_section_voice.add_entry(UnblockMyVoiceMenuCommand(
    unblock_my_voice_feature,
    menu_section_voice,
    plugin_strings['popup_title unblock_voice']))

# =============================================================================
# >> SYNCHRONOUS DATABASE OPERATIONS
# =============================================================================
blocked_chat_user_manager.refresh()
blocked_voice_user_manager.refresh()
