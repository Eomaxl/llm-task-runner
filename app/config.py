from pydantic import BaseModel
import os

class Settings(BaseModel):
    max_steps: int = int(os.getenv("APP_MAX_STEPS", "5"))
    step_timeout_seconds: float = float(os.getenv("APP_STEP_TIMEOUT_SECONDS","8"))
    max_concurrent_tasks: int = int(os.getenv("APP_MAX_CONCURRENT_TASKS", "10"))

    #Retry Configuration
    retry_max_attempts: int = int(os.getenv("APP_RETRY_MAX_ATTEMPTS","3"))
    retry_base_attempts: float = float(os.getenv("APP_RETRY_BASE_ATTEMPTS","0.3"))
    retry_max_delay: float = float(os.getenv("APP_RETRY_MAX_DELAY","2.0"))
    retry_jitter: float = float(os.getenv("APP_RETRY_JITTER","0.2"))

settings = Settings()
