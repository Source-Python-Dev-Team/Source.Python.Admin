"""Provides base paths for Source.Python Admin."""

# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from paths import CFG_PATH, LOG_PATH, PLUGIN_DATA_PATH, PLUGIN_PATH, SOUND_PATH

# Source.Python Admin
from ..info import info


# =============================================================================
# >> FUNCTIONS
# =============================================================================
def get_server_file(path):
    server_path = path.dirname() / (path.namebase + "_server" + path.ext)
    if server_path.isfile():
        return server_path
    return path


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
# ../addons/source-python/plugins/admin
ADMIN_BASE_PATH = PLUGIN_PATH / info.name

# ../cfg/source-python/admin
ADMIN_CFG_PATH = CFG_PATH / info.name

# ../addons/source-python/data/plugins/admin
ADMIN_DATA_PATH = PLUGIN_DATA_PATH / info.name

# ../logs/source-python/admin
ADMIN_LOG_PATH = LOG_PATH / info.name

# ../addons/source-python/plugins/admin/plugins
ADMIN_PLUGINS_PATH = ADMIN_BASE_PATH / "plugins"

# ../sound/source-python/admin
ADMIN_SOUND_PATH = SOUND_PATH / info.name
