import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    PROJECT_NAME: str = 'DigiSafe Digital Safety & Record Protection'
    VERSION: str = '1.0.0'
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'digisafe-secret-key-super-secure-knust-2026')
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    
    # 32-byte key for AES-256
    raw_key = os.getenv('DIGISAFE_AES_KEY', 'DigiSafeSecretEncryptionKey2026!')
    if len(raw_key.encode('utf-8')) >= 32:
        AES_KEY: bytes = raw_key.encode('utf-8')[:32]
    else:
        AES_KEY: bytes = raw_key.encode('utf-8').ljust(32, b'#')
        
    DATABASE_URL: str = os.getenv('DATABASE_URL', f'sqlite:///{BASE_DIR}/digisafe.db')

    # Demonstration data is OFF by default.
    #
    # This is a real platform, not a showcase: a deployed instance starts with an
    # empty database and fills up with people who actually register. Seeding it
    # with invented complainants and fabricated harassment cases would mean a
    # visitor's first view of an evidence system is fictional records, and the
    # one-click role logins would hand any visitor an administrator session.
    #
    # Set DIGISAFE_SEED_DEMO=true locally when you want the sample cases back
    # for a walkthrough.
    SEED_DEMO_DATA: bool = os.getenv('DIGISAFE_SEED_DEMO', 'false').strip().lower() in ('1', 'true', 'yes', 'on')
    
    UPLOAD_DIR: Path = BASE_DIR / 'storage' / 'evidence_files'
    REPORTS_DIR: Path = BASE_DIR / 'storage' / 'reports'
    
settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
