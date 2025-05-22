from typing import Any, Type
import importlib


def str2class(class_path: str) -> Type:
    module_name, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def create_instance(config: dict) -> Any:
    class_path = config["class_path"]
    kwargs = config["kwargs"]
    class_ = str2class(class_path)
    if not isinstance(class_, type):
        raise ValueError(f"{class_path} is not a class")
    processed_kwargs = {
        key: (
            create_instance(value)
            if isinstance(value, dict) and "class_path" in value
            else value
        )
        for key, value in kwargs.items()
    }
    attrs = config["attrs"]
    processed_attrs = {
        key: (
            create_instance(value)
            if isinstance(value, dict) and "class_path" in value
            else value
        )
        for key, value in attrs.items()
    }
    object_instance = class_(**processed_kwargs)
    for attr, value in processed_attrs.items():
        setattr(object_instance, attr, value)
    return object_instance
