"""Event storage functionality."""


# =============================================================================
# >> ALL DECLARATION
# =============================================================================
__all__ = (
    '_AdminResourceList',
    'admin_resource_list',
)


# =============================================================================
# >> CLASSES
# =============================================================================
class _AdminResourceList(list):
    """Class used to store a list of all Source.Python Admin res files."""

    def append(self, resource):
        """Add the res file and write it."""
        super().append(resource)
        resource.write()

    def write_all_events(self):
        """Write all files in the list."""
        for resource in self:
            resource.write()

    def load_all_events(self):
        """Load all events from all res files."""
        for resource in self:
            resource.load_events()

# The singleton object of the _AdminResourceList class.
admin_resource_list = _AdminResourceList()
