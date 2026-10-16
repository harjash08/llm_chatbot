from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file=".env",extra="ignore")
    DATABASE_URL:str
    ACCESS_TOKEN_EXPIRE_MINUTES:int 
    SECRET_KEY:str
    ALGORITHM:str
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str

settings=Settings()
