# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python Admin
from motdplayer_applications.admin.wrp import WebRequestProcessor


# =============================================================================
# >> CONSTANTS
# =============================================================================
MAX_USERID_ABS_VALUE = 100000000
MAX_PLAYERS_NUMBER = 256


# =============================================================================
# >> FUNCTIONS
# =============================================================================
def filter_userids(userids):
    new_userids = []
    for userid in userids:
        if not isinstance(userid, int):
            return None

        if not (-MAX_USERID_ABS_VALUE <= userid <= MAX_USERID_ABS_VALUE):
            return None

        new_userids.append(userid)

    if len(userids) > MAX_PLAYERS_NUMBER:
        return None

    return new_userids


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
            if 'player_userids' not in data:
                return

            player_userids = filter_userids(data['player_userids'])
            if player_userids is None:
                return

            return ex_data_func({
                'action': "execute",
                'player_userids': player_userids,
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
            if 'player_userids' not in data:
                return

            player_userids = filter_userids(data['player_userids'])
            if player_userids is None:
                return

            return {
                'action': "execute",
                'player_userids': player_userids,
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
