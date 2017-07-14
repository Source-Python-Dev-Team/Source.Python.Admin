# =============================================================================
# >> IMPORTS
# =============================================================================
# Site-Package
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Source.Python Admin
from .config import config
from .paths import ADMIN_DATA_PATH


# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
engine = create_engine(config['database']['uri'].format(
    admin_data_path=ADMIN_DATA_PATH,
))
Base = declarative_base()
Session = sessionmaker(bind=engine)


# =============================================================================
# >> CLASSES
# =============================================================================
class SessionContext:
    def __init__(self):
        self.session = None

    def __enter__(self):
        self.session = Session()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
        self.session.close()
        self.session = None
