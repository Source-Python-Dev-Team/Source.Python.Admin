# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python Admin
from motdplayer_applications.admin.core import (
    player_based_feature_page_ajax_wrap)
from motdplayer_applications.admin.wrp import WebRequestProcessor


# =============================================================================
# >> WEB REQUEST PROCESSORS
# =============================================================================
slay_page = WebRequestProcessor('included', 'admin_life_management', 'slay')


# =============================================================================
# >> WEB REQUEST PROCESSOR CALLBACKS
# =============================================================================
# slay_page
@slay_page.register_regular_callback
def callback(ex_data_func):
    return "admin/included/admin_life_management/slay.html", dict()


@slay_page.register_ajax_callback
@player_based_feature_page_ajax_wrap
def callback(ex_data_func, data):
    pass
