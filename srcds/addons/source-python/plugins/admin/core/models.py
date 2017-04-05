# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from importlib import import_module

# Source.Python Admin
from .paths import ADMIN_PLUGINS_PATH
from .plugins.valid import valid_plugins


# =============================================================================
# >> SUB-PLUGIN CUSTOM MODEL REGISTRATION
# =============================================================================
for plugin_name in valid_plugins.all:
    plugin_type = valid_plugins.get_plugin_type(plugin_name)
    if ADMIN_PLUGINS_PATH.joinpath(
        plugin_type, plugin_name, 'models.py',
    ).isfile():
        import_module(
            'admin.plugins.{plugin_type}.{plugin_name}.models'.format(
                plugin_type=plugin_type,
                plugin_name=plugin_name,
            )
        )
