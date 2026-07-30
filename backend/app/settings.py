from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # No real default on purpose - this signs JWTs and derives the key that
    # encrypts stored device credentials, so it must come from backend/.env
    # (an untracked file), never be hardcoded/committed here.
    SECRET_KEY: str = "insecure-default-set-a-real-SECRET_KEY-in-backend/.env"
    ALGORITHM: str = "HS256"
    # Default access token expiry: 8 hours
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    DB_URL: str = "sqlite:///./abs.db"
    TIMEZONE: str = "Asia/Jakarta"
    BACKUP_DIR: str = "./backups"
    ZABBIX_URL: str = ""
    ZABBIX_USERNAME: str = ""
    ZABBIX_PASSWORD: str = ""
    class Config: env_file = ".env"

settings = Settings()
