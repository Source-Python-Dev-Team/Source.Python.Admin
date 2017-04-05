# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from configparser import ConfigParser

# Source.Python Admin
from .paths import ADMIN_DATA_PATH


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
CONFIG_FILE = ADMIN_DATA_PATH / "config.ini"

config = ConfigParser()
config.read(CONFIG_FILE)
