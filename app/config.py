from dataclasses import dataclass

from environs import Env


@dataclass
class BotConfig:
    """
    Data class representing the configuration for the bot.

    Attributes:
    - TOKEN (str): The bot token.
    - DEV_ID (int): The developer's user ID.
    - GROUP_ID (int): The group chat ID.
    - BOT_EMOJI_ID (str): The custom emoji ID for the group's topic.
    - BOT_NAME (str): The custom bot name shows in the main menu
    """
    TOKEN: str
    DEV_ID: int
    GROUP_ID: int
    BOT_EMOJI_ID: str
    BOT_NAME: str


@dataclass
class ApiConfig:
    """
    Data class representing the configuration for the bot.

    Attributes:
    - API_URL (str): SHM API template
    """
    API_URL: str
    BOT_USERNAME: str


@dataclass
class RemnawaveConfig:
    """
    Data class representing the configuration for Remnawave API.

    Attributes:
    - API_URL (str): Remnawave API URL
    - API_KEY (str): Remnawave API key
    """
    API_URL: str
    API_KEY: str


@dataclass
class RedisConfig:
    """
    Data class representing the configuration for Redis.

    Attributes:
    - HOST (str): The Redis host.
    - PORT (int): The Redis port.
    - DB (int): The Redis database number.
    """
    HOST: str
    PORT: int
    DB: int

    def dsn(self) -> str:
        """
        Generates a Redis connection DSN (Data Source Name) using the provided host, port, and database.

        :return: The generated DSN.
        """
        return f"redis://{self.HOST}:{self.PORT}/{self.DB}"


@dataclass
class Config:
    """
    Data class representing the overall configuration for the application.

    Attributes:
    - bot (BotConfig): The bot configuration.
    - redis (RedisConfig): The Redis configuration.
    - api (ApiConfig): The SHM API configuration.
    - remnawave (RemnawaveConfig): The Remnawave API configuration.
    """
    bot: BotConfig
    redis: RedisConfig
    api: ApiConfig
    remnawave: RemnawaveConfig


def load_config() -> Config:
    """
    Load the configuration from environment variables and return a Config object.

    :return: The Config object with loaded configuration.
    """
    env = Env()
    env.read_env()

    return Config(
        bot=BotConfig(
            TOKEN=env.str("BOT_TOKEN"),
            DEV_ID=env.int("BOT_DEV_ID"),
            GROUP_ID=env.int("BOT_GROUP_ID"),
            BOT_EMOJI_ID=env.str("BOT_EMOJI_ID"),
            BOT_NAME=env.str("BOT_NAME"),
        ),
        redis=RedisConfig(
            HOST=env.str("REDIS_HOST"),
            PORT=env.int("REDIS_PORT"),
            DB=env.int("REDIS_DB"),
        ),
        api=ApiConfig(
            API_URL=env.str("API_URL"),
            BOT_USERNAME=env.str("BOT_USERNAME"),
        ),
        remnawave=RemnawaveConfig(
            API_URL=env.str("REMNAWAVE_API_URL"),
            API_KEY=env.str("REMNAWAVE_API_KEY"),
        ),
    )
