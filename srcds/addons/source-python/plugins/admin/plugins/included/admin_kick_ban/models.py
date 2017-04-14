# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from time import time

# Site-Package
from sqlalchemy import Boolean, Column, Integer, String, Text

# Source.Python Admin
from admin.core.config import config
from admin.core.orm import Base


# =============================================================================
# >> MODEL CLASSES
# =============================================================================
class BannedUser(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True)
    name = Column(String(64))
    banned_by = Column(String(32))
    reviewed = Column(Boolean)

    banned_at = Column(Integer)
    expires_at = Column(Integer)

    is_unbanned = Column(Boolean)
    unbanned_by = Column(String(32))

    reason = Column(Text)
    notes = Column(Text)

    def __init__(self, uniqueid, name, banned_by, duration):
        super().__init__()

        current_time = time()

        self.uniqueid = uniqueid
        self.name = name
        self.banned_by = banned_by
        self.reviewed = False
        self.banned_at = int(current_time)
        self.expires_at = int(current_time + duration)
        self.is_unbanned = False
        self.unbanned_by = ""
        self.reason = ""
        self.notes = ""

    def review(self, reason, duration):
        self.reviewed = True
        self.expires_at = int(time() + duration)
        self.reason = reason

    def lift_ban(self, unbanned_by):
        self.is_unbanned = True
        self.unbanned_by = unbanned_by


class BannedSteamID(BannedUser):
    __tablename__ = config['database']['prefix'] + "banned_steamid"

    steamid64 = Column(String(32))

    def get_uniqueid(self):
        return self.steamid64

    def set_uniqueid(self, uniqueid):
        self.steamid64 = uniqueid

    uniqueid = property(get_uniqueid, set_uniqueid)


class BannedIPAddress(BannedUser):
    __tablename__ = config['database']['prefix'] + "banned_ip_address"

    ip_address = Column(String(48))

    def get_uniqueid(self):
        return self.ip_address

    def set_uniqueid(self, uniqueid):
        self.ip_address = uniqueid

    uniqueid = property(get_uniqueid, set_uniqueid)
