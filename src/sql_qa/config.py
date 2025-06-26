import os
from dotenv import load_dotenv
from shared.logger import TurnLogger
import pathlib

import os
from hydra import initialize_config_dir, compose
from omegaconf import OmegaConf
from hydra.core.global_hydra import GlobalHydra

load_dotenv(override=True)

GlobalHydra.instance().clear()
OmegaConf.clear_resolvers()

abs_config_dir = str(pathlib.Path(__file__).parent.parent.parent / "conf")
initialize_config_dir(version_base=None, config_dir=abs_config_dir)

# Register a custom resolver for environment variables
OmegaConf.register_new_resolver(
    "env", lambda *args: os.environ.get(args[0], args[-1] or "")
)

settings = compose(config_name="config")
settings = OmegaConf.create(OmegaConf.to_yaml(cfg=settings, resolve=True))

if not os.path.exists(settings.logging.log_dir):
    os.makedirs(settings.logging.log_dir)

turn_logger = TurnLogger(settings.turn_log_file)

if __name__ == "__main__":
    print(settings.model_dump_json(indent=2))


def get_app_config():
    return settings
