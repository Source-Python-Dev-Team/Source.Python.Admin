"""Source-engine Server Administration."""

# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from commands.typed import TypedClientCommand, TypedSayCommand

# Source.Python Admin
from .core import models
from .core.clients import clients
from .core.events.storage import admin_resource_list
from .core.helpers import chat_message
from .core.listeners import (on_spa_loaded_listener_manager,
                             on_spa_unloaded_listener_manager)
from .core.frontends.menus import main_menu
from .core.frontends.motd import MainPage
from .core.orm import Base, engine
from .core.plugins.command import admin_command_manager
from .core.strings import strings_common
from .info import info


# =============================================================================
# >> DATABASE CREATION
# =============================================================================
Base.metadata.create_all(engine)


# =============================================================================
# >> LOAD & UNLOAD FUNCTIONS
# =============================================================================
def load():
    admin_resource_list.load_all_events()
    on_spa_loaded_listener_manager.notify()
    chat_message(strings_common['load'])


def unload():
    admin_command_manager.unload_all_plugins()
    on_spa_unloaded_listener_manager.notify()
    chat_message(strings_common['unload'])


# =============================================================================
# >> MAIN COMMANDS
# =============================================================================
@TypedClientCommand(['spa', 'menu'], 'admin.base')
@TypedSayCommand(['!spa', 'menu'], 'admin.base')
@TypedSayCommand(['/spa', 'menu'], 'admin.base')  # TODO: Suppress the message
def _admin_command(command_info):
    main_menu.popup.send(command_info.index)


@TypedClientCommand(['spa', 'motd'], 'admin.base')
@TypedSayCommand(['!spa', 'motd'], 'admin.base')
@TypedSayCommand(['/spa', 'motd'], 'admin.base')  # TODO: Suppress the message
def _admin_command(command_info):
    MainPage.send(command_info.index)
