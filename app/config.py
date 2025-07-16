import os
from dotenv import load_dotenv
import logging
from typing import Optional

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Config:
    DB_HOST: Optional[str] = os.getenv("DB_HOST")
    DB_PORT: Optional[str] = os.getenv("DB_PORT")
    DB_NAME: Optional[str] = os.getenv("DB_NAME")
    DB_USER: Optional[str] = os.getenv("DB_USER")
    DB_PASSWORD: Optional[str] = os.getenv("DB_PASSWORD")
    SQLALCHEMY_DATABASE_URL: Optional[str] = None
    UPLOAD_FOLDER: str = os.getenv("UPLOAD_FOLDER", "/app/data/to_check")

    if all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
        SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    @classmethod
    def validate(cls):
        missing_vars = [
            name for name, var in zip([
                "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"
            ], [cls.DB_HOST, cls.DB_PORT, cls.DB_NAME, cls.DB_USER, cls.DB_PASSWORD])
            if var is None
        ]
        if missing_vars:
            logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
            raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")

Config.validate()
