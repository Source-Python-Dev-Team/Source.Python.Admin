# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python
from core import GAME_NAME
from engines.server import server
from memory import get_object_pointer, make_object
from memory.manager import TypeManager

# Source.Python Admin
from .paths import ADMIN_DATA_PATH


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
manager = TypeManager()
server_ptr = get_object_pointer(server)

CustomServer = manager.create_type_from_file(
    'CBaseServer',
    ADMIN_DATA_PATH / 'memory' / GAME_NAME / 'CBaseServer.ini'
)

custom_server = make_object(CustomServer, server_ptr)
