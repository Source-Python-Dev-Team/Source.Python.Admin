"""Provides the Source.Python Admin logger instance."""

# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from config.manager import ConfigManager
from loggers import LogManager
from translations.strings import LangStrings


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
_config_strings = LangStrings('admin/config/logger')

# Create the logging config
with ConfigManager('admin/logging_settings', 'admin_logging_') as _config:

    with _config.cvar('level', 0, _config_strings['level']) as _level:
        pass

    with _config.cvar('areas', 1, _config_strings['areas']) as _areas:
        pass

# Get the Source.Python Admin logger
admin_logger = LogManager(
    'admin',
    _level,
    _areas,
    'admin',
    '%(asctime)s - %(name)s\t-\t%(levelname)s\n%(message)s',
    '%m-%d-%Y %H:%M:%S',
)
