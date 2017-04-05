"""Source.Python Admin translations functionality."""

# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from translations.strings import LangStrings

# Source.Python Admin
from .valid import valid_plugins


# =============================================================================
# >> ALL DECLARATION
# =============================================================================
__all__ = (
    'PluginStrings',
)


# =============================================================================
# >> CLASSES
# =============================================================================
class PluginStrings(LangStrings):
    """Class used to retrieve Source.Python Admin sub-plugin translations."""

    def __init__(self, name):
        """Add 'admin' and the plugin type to the path."""
        super().__init__(
            'admin/{plugin_type}_plugins/{plugin_name}'.format(
                plugin_type=valid_plugins.get_plugin_type(name),
                plugin_name=name,
            )
        )
