from os import getenv


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    def __init__(self) -> None:
        self.app_name = "MergeWise AI"
        self.openai_api_key = getenv("OPENAI_API_KEY", "")
        self.openai_model = getenv("OPENAI_MODEL", "gpt-4.1")
        self.cors_origins = _split_csv(getenv("CORS_ORIGINS", "http://localhost:5173"))

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key.strip())


settings = Settings()