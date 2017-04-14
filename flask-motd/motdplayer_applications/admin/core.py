# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python Admin
from motdplayer_applications.admin.wrp import WebRequestProcessor


# =============================================================================
# >> CONSTANTS
# =============================================================================
MAX_PLAYER_ID_LENGTH = 20
MAX_PLAYERS_NUMBER = 1


# =============================================================================
# >> FUNCTIONS
# =============================================================================
def filter_ids(player_ids):
    new_player_ids = []
    for player_id in player_ids:
        if not (isinstance(player_id, str) or isinstance(player_id, int)):
            return None

        if len(str(player_id).encode('utf-8')) > MAX_PLAYER_ID_LENGTH:
            return None

        new_player_ids.append(player_id)

    if len(new_player_ids) > MAX_PLAYERS_NUMBER:
        return None

    return new_player_ids


# =============================================================================
# >> DECORATORS
# =============================================================================
def feature_page_ajax_wrap(callback):
    def new_callback(ex_data_func, data):
        if 'action' not in data:
            return callback(ex_data_func, data)

        if data['action'] == "execute":
            return ex_data_func({
                'action': "execute",
            })

        return callback(ex_data_func, data)

    return new_callback


def player_based_feature_page_ajax_wrap(callback):
    def new_callback(ex_data_func, data):
        if 'action' not in data:
            return callback(ex_data_func, data)

        if data['action'] == "execute":
            if 'player_ids' not in data:
                return

            player_ids = filter_ids(data['player_ids'])
            if player_ids is None:
                return

            return ex_data_func({
                'action': "execute",
                'player_ids': player_ids,
            })

        if data['action'] == "get-players":
            return ex_data_func({
                'action': "get-players",
            })

        return callback(ex_data_func, data)

    return new_callback


def player_based_feature_page_ws_wrap(callback):
    def new_callback(data):
        if 'action' not in data:
            return callback(data)

        if data['action'] == "execute":
            if 'player_ids' not in data:
                return

            player_ids = filter_ids(data['player_ids'])
            if player_ids is None:
                return

            return {
                'action': "execute",
                'player_ids': player_ids,
            }

        if data['action'] == "get-players":
            return {
                'action': "get-players",
            }

        return callback(data)

    return new_callback


# =============================================================================
# >> WEB REQUEST PROCESSORS
# =============================================================================
main_page = WebRequestProcessor('core', 'core', 'main')


# =============================================================================
# >> WEB REQUEST PROCESSOR CALLBACKS
# =============================================================================
# main_page
@main_page.register_regular_callback
def callback(ex_data_func):
    return "admin/core/main.html", dict()
