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
