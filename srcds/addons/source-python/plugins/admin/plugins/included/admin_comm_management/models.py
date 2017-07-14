# =============================================================================
# >> IMPORTS
# =============================================================================
# Python
from time import time

# Site-Package
from sqlalchemy import Boolean, Column, Integer, String

# Source.Python Admin
from admin.core.config import config
from admin.core.orm import Base


# =============================================================================
# >> MODEL CLASSES
# =============================================================================
class _BlockedCommUser(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True)
    steamid64 = Column(String(32))
    name = Column(String(64))
    blocked_by = Column(String(32))

    blocked_at = Column(Integer)
    expires_at = Column(Integer)

    is_unblocked = Column(Boolean)
    unblocked_by = Column(String(32))

    def __init__(self, steamid64, name, blocked_by, duration):
        super().__init__()

        current_time = time()

        self.steamid64 = steamid64
        self.name = name
        self.blocked_by = blocked_by
        self.blocked_at = int(current_time)
        self.expires_at = int(current_time + duration)
        self.is_unblocked = False
        self.unblocked_by = ""

    def lift_block(self, unblocked_by):
        self.is_unblocked = True
        self.unblocked_by = unblocked_by


class BlockedChatUser(_BlockedCommUser):
    __tablename__ = config['database']['prefix'] + "blocked_chat_user"


class BlockedVoiceUser(_BlockedCommUser):
    __tablename__ = config['database']['prefix'] + "blocked_voice_user"
