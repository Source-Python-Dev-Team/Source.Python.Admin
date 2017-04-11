# =============================================================================
# >> IMPORTS
# =============================================================================
# Flask-MOTDPlayer
from motdplayer import WebRequestProcessor as _WebRequestProcessor


# =============================================================================
# >> CLASSES
# =============================================================================
class WebRequestProcessor(_WebRequestProcessor):
    def __init__(self, plugin_type, plugin_id, page_id):
        super().__init__("admin", "{}.{}.{}".format(
            plugin_type, plugin_id, page_id))

    def register_regular_callback(self, callback):
        def new_callback(ex_data_func):
            our_context = ex_data_func({
                'spa_action': "init",
            })
            template_name, context = callback(ex_data_func)

            if context is None:
                context = our_context
            else:
                context.update(our_context)

            return template_name, context

        return super().register_regular_callback(new_callback)
