from dotenv import dotenv_values
import os

def load_api_key_from_dotenv() -> None:
    """
    If OPENAI_API_KEY is set in a .env file, inject it into os.environ.
    """
    env = dotenv_values()
    key = env.get("OPENAI_API_KEY")
    if key is not None:
        os.environ["OPENAI_API_KEY"] = str(key)
