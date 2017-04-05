"""Source.Python Admin event resource file functionality."""

# =============================================================================
# >> IMPORTS
# =============================================================================
# Site-Package
from path import Path

# Source.Python
from events.resource import ResourceFile

# Source.Python Admin
from .storage import admin_resource_list


# =============================================================================
# >> ALL DECLARATION
# =============================================================================
__all__ = (
    'AdminResourceFile',
)


# =============================================================================
# >> CLASSES
# =============================================================================
class AdminResourceFile(ResourceFile):
    """Class used for Source.Python Admin res files."""

    def __init__(self, file_path, *events):
        """Add 'admin' to the path before initialization."""
        super().__init__(Path('admin') / file_path, *events)
        admin_resource_list.append(self)
