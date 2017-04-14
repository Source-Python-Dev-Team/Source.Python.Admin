# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from configparser import ConfigParser

# Source.Python Admin
from admin.core.paths import ADMIN_CFG_PATH, get_server_file


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
PLUGIN_CONFIG_FILE = get_server_file(
    ADMIN_CFG_PATH / "included_plugins" / "admin_kick_ban" / "config.ini")

plugin_config = ConfigParser()
plugin_config.read(PLUGIN_CONFIG_FILE)
