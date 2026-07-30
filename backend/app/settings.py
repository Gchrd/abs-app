from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str = "2502011285-josephcristianlubis"
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
