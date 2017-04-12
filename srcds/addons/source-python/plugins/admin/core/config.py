# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from configparser import ConfigParser

# Source.Python Admin
from .paths import ADMIN_CFG_PATH, get_server_file


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
CONFIG_FILE = get_server_file(ADMIN_CFG_PATH / "config.ini")

config = ConfigParser()
config.read(CONFIG_FILE)
