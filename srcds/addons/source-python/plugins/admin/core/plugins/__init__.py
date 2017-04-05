"""Plugin based functionality."""

# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from translations.strings import LangStrings

# Source.Python Admin
from .. import admin_core_logger


# =============================================================================
# >> ALL DECLARATION
# =============================================================================
__all__ = (
    'admin_plugins_logger',
    'plugin_strings',
)


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
admin_plugins_logger = admin_core_logger.plugins
plugin_strings = LangStrings('_core/plugin_strings')
