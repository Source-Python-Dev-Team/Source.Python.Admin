# =============================================================================
# >> IMPORTS
# =============================================================================
# Site-Package
from sqlalchemy import Boolean, Column, Integer, String, Text

# Source.Python Admin
from admin.core.config import config
from admin.core.orm import Base


# =============================================================================
# >> MODEL CLASSES
# =============================================================================
class BannedSteamID(Base):
    __tablename__ = config['database']['prefix'] + "banned_steamid"

    id = Column(Integer, primary_key=True)
    steamid = Column(String(32))
    name = Column(String(64))
    admin_steamid = Column(String(32))
    reviewed = Column(Boolean)

    banned_timestamp = Column(Integer)
    expires_timestamp = Column(Integer)

    unbanned = Column(Boolean)

    reason = Column(Text)
    notes = Column(Text)


class BannedIPAddress(Base):
    __tablename__ = config['database']['prefix'] + "banned_ip_address"

    id = Column(Integer, primary_key=True)
    ip_address = Column(String(48))
    name = Column(String(64))
    admin_steamid = Column(String(32))
    reviewed = Column(Boolean)

    banned_timestamp = Column(Integer)
    expires_timestamp = Column(Integer)

    unbanned = Column(Boolean)

    reason = Column(Text)
    notes = Column(Text)
