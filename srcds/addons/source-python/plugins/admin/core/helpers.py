# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from messages import SayText2
from translations.manager import language_manager

# Source.Python Admin
from . import admin_core_logger
from .strings import strings_common


# =============================================================================
# >> CONSTANTS
# =============================================================================
MAX_NAME_LENGTH_BYTES = 24
THREE_DOTS = "…"

# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
admin_performed_actions_logger = admin_core_logger.performed_actions


# =============================================================================
# >> FUNCTIONS
# =============================================================================
def extract_ip_address(address):

    # We don't just do address.split(':')[0] - because that'd drop IPv6 support
    return address[:address.rfind(':')]


def format_player_name(player_name):
    if len(player_name.encode('utf-8')) <= MAX_NAME_LENGTH_BYTES:
        return player_name

    player_name_encoded = player_name.encode('utf-8')
    player_name_encoded = player_name_encoded[
        :MAX_NAME_LENGTH_BYTES-len(THREE_DOTS)]

    return player_name_encoded.decode('utf-8', 'ignore') + THREE_DOTS


def log_admin_action(message):
    SayText2(strings_common['chat_base'].tokenized(message=message)).send()
    admin_performed_actions_logger.log_message(
        message.get_string(language_manager.default))
