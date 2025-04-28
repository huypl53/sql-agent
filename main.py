import logging.config
from omegaconf import OmegaConf, DictConfig
import hydra
import logging
import pathlib
import os


@hydra.main(version_base=None, config_path="conf", config_name="config")
def main(cfg: DictConfig) -> None:
    # Create log directory if it doesn't exist
    log_dir = pathlib.Path(cfg.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_config = OmegaConf.to_container(cfg.logging, resolve=True)
    logging.config.dictConfig(log_config)
    logger = logging.getLogger("main")
    logger.info(f"Working directory: {os.getcwd()}")
    # logger.info("Logging configuration loaded successfully.")
    # logger.info(f"Logging level set to: {logger.level}")
    # logger.debug("Debugging information.")


if __name__ == "__main__":
    main()
