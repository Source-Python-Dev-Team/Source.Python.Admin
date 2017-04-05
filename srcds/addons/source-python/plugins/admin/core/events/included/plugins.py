"""Sub-plugin based events."""

# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from events.custom import CustomEvent
from events.variable import StringVariable

# Source.Python Admin
from ..resource import AdminResourceFile


# =============================================================================
# >> ALL DECLARATION
# =============================================================================
__all__ = (
    'Admin_Plugin_Loaded',
    'Admin_Plugin_Unloaded',
)


# =============================================================================
# >> CLASSES
# =============================================================================
class Admin_Plugin_Loaded(CustomEvent):
    """Called when a Source.Python Admin sub-plugin is loaded."""

    plugin = StringVariable('The name of the plugin that was loaded')
    plugin_type = StringVariable('The type of plugin that was loaded')


class Admin_Plugin_Unloaded(CustomEvent):
    """Called when a Source.Python Admin sub-plugin is unloaded."""

    plugin = StringVariable('The name of the plugin that was unloaded')
    plugin_type = StringVariable('The type of plugin that was unloaded')


# =============================================================================
# >> RESOURCE FILE
# =============================================================================
AdminResourceFile('plugins', Admin_Plugin_Loaded, Admin_Plugin_Unloaded)
