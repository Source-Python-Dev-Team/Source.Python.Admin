# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from configparser import ConfigParser

# Source.Python Admin
from ..paths import ADMIN_DATA_PATH
from .valid import valid_plugins


# =============================================================================
# >> FUNCTIONS
# =============================================================================
def load_plugin_config(plugin_name, config_name):
    base_path = (
        ADMIN_DATA_PATH /
        "{}_plugins".format(valid_plugins.get_plugin_type(plugin_name)) /
        plugin_name
    )
    path = base_path / "{}.ini".format(config_name)
    path_server = base_path / "{}_server.ini".format(config_name)

    config = ConfigParser()
    if path_server.isfile():
        config.read(path_server)
    else:
        config.read(path)
    return config
