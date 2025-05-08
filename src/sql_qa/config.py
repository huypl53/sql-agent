import pathlib
from omegaconf import OmegaConf

_CONFIG_PATH = pathlib.Path(__file__).parent / "config.yaml"
_DEFAULT_CONFIG = OmegaConf.load(_CONFIG_PATH)


def get_config():
    return _DEFAULT_CONFIG
