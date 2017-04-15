# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python Admin
from motdplayer_applications.admin.core import (
    player_based_feature_page_ajax_wrap, player_based_feature_page_ws_wrap)
from motdplayer_applications.admin.wrp import WebRequestProcessor


# =============================================================================
# >> CONSTANTS
# =============================================================================
MAX_BAN_ID_ABS_VALUE = 3000000000


# =============================================================================
# >> WEB REQUEST PROCESSORS
# =============================================================================
kick_page = WebRequestProcessor('included', 'admin_kick_ban', 'kick')
ban_steamid_page = WebRequestProcessor(
    'included', 'admin_kick_ban', 'ban_steamid')
ban_ip_address_page = WebRequestProcessor(
    'included', 'admin_kick_ban', 'ban_ip_address')
lift_steamid_page = WebRequestProcessor(
    'included', 'admin_kick_ban', 'lift_steamid')
lift_ip_address_page = WebRequestProcessor(
    'included', 'admin_kick_ban', 'lift_ip_address')


# =============================================================================
# >> WEB REQUEST PROCESSOR CALLBACKS
# =============================================================================
# kick_page
@kick_page.register_regular_callback
def callback(ex_data_func):
    return "admin/included/admin_kick_ban/kick.html", dict()


@kick_page.register_ajax_callback
@player_based_feature_page_ajax_wrap
def callback(ex_data_func, data):
    pass


@kick_page.register_ws_callback
@player_based_feature_page_ws_wrap
def callback(data):
    pass


# ban_steamid_page
@ban_steamid_page.register_regular_callback
def callback(ex_data_func):
    return "admin/included/admin_kick_ban/ban_steamid.html", dict()


@ban_steamid_page.register_ajax_callback
@player_based_feature_page_ajax_wrap
def callback(ex_data_func, data):
    pass


@ban_steamid_page.register_ws_callback
@player_based_feature_page_ws_wrap
def callback(data):
    pass


# ban_ip_address_page
@ban_ip_address_page.register_regular_callback
def callback(ex_data_func):
    return "admin/included/admin_kick_ban/ban_ip_address.html", dict()


@ban_ip_address_page.register_ajax_callback
@player_based_feature_page_ajax_wrap
def callback(ex_data_func, data):
    pass


@ban_ip_address_page.register_ws_callback
@player_based_feature_page_ws_wrap
def callback(data):
    pass


# lift_steamid_page
@lift_steamid_page.register_regular_callback
def callback(ex_data_func):
    return "admin/included/admin_kick_ban/lift_steamid.html", dict()


# lift_ip_address_page
@lift_ip_address_page.register_regular_callback
def callback(ex_data_func):
    return "admin/included/admin_kick_ban/lift_ip_address.html", dict()


# lift_steamid_page/lift_ip_address_page
@lift_steamid_page.register_ajax_callback
@lift_ip_address_page.register_ajax_callback
def callback(ex_data_func, data):
    if 'action' not in data:
        return

    if data['action'] == "execute":
        if 'banId' not in data:
            return

        ban_id = data['banId']

        if not isinstance(ban_id, int):
            return

        if not (-MAX_BAN_ID_ABS_VALUE <= ban_id <= MAX_BAN_ID_ABS_VALUE):
            return

        return ex_data_func({
            'action': "execute",
            'banId': ban_id,
        })

    if data['action'] == "get-bans":
        return ex_data_func({
            'action': "get-bans",
        })


@lift_steamid_page.register_ws_callback
@lift_ip_address_page.register_ws_callback
def callback(data):
    if 'action' not in data:
        return

    if data['action'] == "execute":
        if 'banId' not in data:
            return

        ban_id = data['banId']

        if not isinstance(ban_id, int):
            return

        if not (-MAX_BAN_ID_ABS_VALUE <= ban_id <= MAX_BAN_ID_ABS_VALUE):
            return

        return {
            'action': "execute",
            'banId': ban_id,
        }

    if data['action'] == "get-bans":
        return {
            'action': "get-bans",
        }
