"""Registers the "admin" command."""

# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from contextlib import suppress
from textwrap import TextWrapper

# Source.Python
from messages import TextMsg
from plugins.command import SubCommandManager
from translations.strings import LangStrings

# Source.Python Admin
from ...info import info
from ..credits import admin_credits
from . import plugin_strings, admin_plugins_logger
from .manager import admin_plugin_manager
from .queue import plugin_queue
from .valid import valid_plugins


# =============================================================================
# >> ALL DECLARATION
# =============================================================================
__all__ = (
    '_AdminSubCommandManager',
    'admin_command_manager',
    'admin_plugins_command_logger',
)


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
admin_plugins_command_logger = admin_plugins_logger.command

command_strings = LangStrings('admin/sub_commands')


# =============================================================================
# >> CLASSES
# =============================================================================
class _AdminSubCommandManager(SubCommandManager):
    """Class used to integrate the "admin" command."""

    def __init__(self, *args, **kwargs):
        """Initialize the instance and set the queue prefix."""
        super().__init__(*args, **kwargs)

        plugin_queue.prefix = self.prefix
        admin_plugin_manager.translations = self.translations

    def load_plugin(self, plugin_name, index=None):
        """Load a plugin by name."""
        # Get the plugin name with the admin_ prefix
        if not plugin_name.startswith('admin_'):
            plugin_name = 'admin_' + plugin_name

        # Is the plugin already loaded?
        if plugin_name in self.manager:

            # Is the plugin in the "unload" queue?
            if (
                'unload' in plugin_queue and
                plugin_name in plugin_queue['unload']
            ):

                # Remove the plugin from the "unload" queue
                plugin_queue['unload'].discard(plugin_name)

            # No need to go further
            return

        # Was an invalid plugin name given?
        if plugin_name not in valid_plugins.all:
            self._send_message(
                self.prefix +
                command_strings['invalid_plugin'].get_string(
                    plugin_name=plugin_name,
                ),
                index,
            )
            return

        # Add the plugin to the current queue
        plugin_queue['load'].add(plugin_name)

    def unload_plugin(self, plugin_name, index=None):
        """Unload a plugin by name."""
        # Get the plugin name with the admin_ prefix
        if not plugin_name.startswith('admin_'):
            plugin_name = 'admin_' + plugin_name

        # Is the plugin loaded?
        if plugin_name not in self.manager:

            # Is the plugin in the "load" queue?
            if 'load' in plugin_queue and plugin_name in plugin_queue['load']:

                # Remove the plugin from the "load" queue
                plugin_queue['load'].discard(plugin_name)

            # Was an invalid plugin name given?
            if plugin_name not in valid_plugins.all:
                self._send_message(
                    self.prefix +
                    command_strings['invalid_plugin'].get_string(
                        plugin_name=plugin_name,
                    ),
                    index,
                )
                return

            # No need to go further
            return

        # Add the plugin to the current queue
        plugin_queue['unload'].add(plugin_name)

    def reload_plugin(self, plugin_name, index=None):
        """Reload a plugin by name."""
        # Get the plugin name with the admin_ prefix
        if not plugin_name.startswith('admin_'):
            plugin_name = 'admin_' + plugin_name

        # Is the plugin not loaded?
        if plugin_name not in self.manager:

            # Was an invalid plugin name given?
            if plugin_name not in valid_plugins.all:
                self._send_message(
                    self.prefix +
                    command_strings['invalid_plugin'].get_string(
                        plugin_name=plugin_name,
                    ),
                    index,
                )
                return

            # Attempt to load the plugin
            self.load_plugin(plugin_name)

            # No need to go further
            return

        # Add the plugin to the unload queue
        plugin_queue['unload'].add(plugin_name)

        # Add the plugin to the reload queue
        plugin_queue['reload'].add(plugin_name)

    def print_plugins(self, index=None):
        """List all currently loaded plugins."""
        # Get header messages
        message = self.prefix + plugin_strings[
            'Plugins'
        ].get_string() + '\n' + '=' * 61 + '\n\n'

        wrapper = TextWrapper(
            width=79,
            initial_indent='',
            subsequent_indent=' ' * 27,
        )

        for plugin_name in sorted(self.manager):
            plugin_info = self.manager[plugin_name].info

            message += '{plugin_name} ({plugin_type}):\n'.format(
                plugin_name=plugin_name,
                plugin_type=valid_plugins.get_plugin_type(plugin_name),
            )

            message += '   title:               {plugin_info.verbose_name}\n'

            if plugin_info.author is not None:
                message += '   author:              {plugin_info.author}\n'

            if plugin_info.description is not None:
                description = wrapper.wrap(
                    '   description:         {plugin_info.description}'.format(
                        plugin_info=plugin_info,
                    )
                )
                message += '\n'.join(description) + '\n'

            if plugin_info.version != 'unversioned':
                message += '   version:             {plugin_info.version}\n'

            if plugin_info.url is not None:
                message += '   url:                 {plugin_info.url}\n'

            if plugin_info.public_convar:
                message += (
                    '   public convar:       '
                    '{plugin_info.public_convar.name}\n'
                )

            with suppress(KeyError):
                message += '   required plugins:    {required}\n'.format(
                    required='\n                        '.join(
                        plugin_info.required
                    ),
                )

            with suppress(KeyError):
                message += '   plugin conflicts:    {conflicts}\n'.format(
                    conflicts='\n                        '.join(
                        plugin_info.conflicts,
                    ),
                )

            for attr in plugin_info.display_in_listing:
                message += (
                    '   {name}:'.format(name=attr).ljust(20) +
                    str(getattr(plugin_info, attr)) + '\n'
                )

            message = message.format(plugin_info=plugin_info) + '\n'

        # Print the message
        self._send_message(message, index)

    def print_version(self, index=None):
        """Print the Source.Python Admin version information."""
        self._send_message(
            self.prefix + command_strings['version_check'].get_string(
                version=info.version,
            ),
            index
        )

    def print_credits(self, index=None):
        """Print the Source.Python Admin credits."""
        # Get header messages
        message = '\n' + self.prefix + plugin_strings[
            'Credits'
        ].get_string() + '\n' + '=' * 61 + '\n\n'

        # Loop through all groups in the credits
        for group in admin_credits:

            # Add the current group's name
            message += '\t' + group + ':\n'

            # Loop through all names in the current group
            for name, values in admin_credits[group].items():

                # Add the current name
                message += '\t\t' + name + ' ' * (
                    20 - len(name)
                ) + values['username'] + '\n'

            # Add 1 blank line between groups
            message += '\n'

        # Print the message
        self._send_message(message + '=' * 61 + '\n\n', index)

    def _send_message(self, message, index):
        if index is None:
            self.logger.log_message(message)
        else:
            for line in message.splitlines():
                TextMsg(line).send(index)

    def unload_all_plugins(self):
        """Unload all plugins when Source.Python Admin is unloading."""
        for plugin_name in list(self.manager):
            del self.manager[plugin_name]

# Get the "admin" command instance
admin_command_manager = _AdminSubCommandManager(
    manager=admin_plugin_manager,
    command='admin',
    logger=admin_plugins_command_logger,
)


@admin_command_manager.server_sub_command(['plugin', 'load'])
@admin_command_manager.client_sub_command(['plugin', 'load'], 'admin.load')
def _admin_plugin_load(command_info, plugin):
    admin_command_manager.load_plugin(plugin, command_info.index)


@admin_command_manager.server_sub_command(['plugin', 'unload'])
@admin_command_manager.client_sub_command(
    ['plugin', 'unload'], 'admin.unload')
def _admin_plugin_unload(command_info, plugin):
    admin_command_manager.unload_plugin(plugin, command_info.index)


@admin_command_manager.server_sub_command(['plugin', 'reload'])
@admin_command_manager.client_sub_command(
    ['plugin', 'reload'], 'admin.reload')
def _admin_plugin_reload(command_info, plugin):
    admin_command_manager.reload_plugin(plugin, command_info.index)


@admin_command_manager.server_sub_command(['plugin', 'list'])
@admin_command_manager.client_sub_command(['plugin', 'list'])
def _admin_plugin_list(command_info):
    admin_command_manager.print_plugins(command_info.index)


@admin_command_manager.server_sub_command(['version'])
@admin_command_manager.client_sub_command(['version'])
def _admin_version(command_info):
    admin_command_manager.print_version(command_info.index)


@admin_command_manager.server_sub_command(['credits'])
@admin_command_manager.client_sub_command(['credits'])
def _admin_credits(command_info):
    admin_command_manager.print_credits(command_info.index)
