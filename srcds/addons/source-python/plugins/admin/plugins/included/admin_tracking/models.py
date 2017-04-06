# =============================================================================
# >> IMPORTS
# =============================================================================
# Site-Package
from sqlalchemy import Column, Integer, String

# Source.Python Admin
from admin.core.config import config
from admin.core.orm import Base


# =============================================================================
# >> MODEL CLASSES
# =============================================================================
class TrackedPlayerRecord(Base):
    __tablename__ = config['database']['prefix'] + "tracked_player_record"

    id = Column(Integer, primary_key=True)
    steamid = Column(String(32))
    name = Column(String(64))
    ip_address = Column(String(48))
    seen_at = Column(Integer)
