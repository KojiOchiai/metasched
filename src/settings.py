from pydantic_settings import BaseSettings, SettingsConfigDict


class MaholoSettings(BaseSettings):
    host: str = "localhost"
    port: int = 63001
    base_path: str = "C:\\BioApl\\DataSet\\proteo-03\\Protocol\\"
    microscope_image_dir: str = "./nikon_save/"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="MAHOLO_"
    )


maholo_settings = MaholoSettings()
