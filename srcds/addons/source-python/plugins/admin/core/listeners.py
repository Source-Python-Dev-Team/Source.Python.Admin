# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from listeners import ListenerManager, ListenerManagerDecorator


# =============================================================================
# >> ALL DECLARATION
# =============================================================================
__all__ = ('on_spa_loaded_listener_manager',
           'on_spa_unloaded_listener_manager',
           'OnSPALoaded',
           'OnSPAUnloaded',
           )


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
on_spa_loaded_listener_manager = ListenerManager()
on_spa_unloaded_listener_manager = ListenerManager()


# =============================================================================
# >> CLASSES
# =============================================================================
class OnSPALoaded(ListenerManagerDecorator):
    """Register/unregister an SPA loaded listener."""

    manager = on_spa_loaded_listener_manager


class OnSPAUnloaded(ListenerManagerDecorator):
    """Register/unregister an SPA unloaded listener."""

    manager = on_spa_unloaded_listener_manager
