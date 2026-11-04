"""Read dependency identities through Espressif's native models."""

from idf_component_tools.lock import LockManager
from idf_component_tools.registry.service_details import get_storage_client


def read_native_lock(path):
    lock = LockManager(str(path)).load()
    if lock.target not in {"esp32c3", "linux"}:
        raise ValueError("The initial SDK provider supports ESP32-C3 and Linux targets")
    for component in lock.dependencies:
        if component.source.type not in {"service", "idf"}:
            raise ValueError("This component source requires an additional provider")
        if (
            component.source.type == "service"
            and component.source.registry_url.rstrip("/")
            != "https://components.espressif.com"
        ):
            raise ValueError("Additional component registries require a provider")
        for requirement in component.dependencies or []:
            if requirement.optional_requirement.has_kconfig_option:
                raise ValueError(
                    "Kconfig-dependent resolution requires an additional provider"
                )
    return lock


def selected_artifacts(lock):
    client = get_storage_client("https://components.espressif.com/")
    for component in lock.dependencies:
        if component.source.type == "idf":
            continue
        record = client.component(component.name, str(component.version))
        if record["component_hash"] != component.component_hash:
            raise ValueError("Selected registry component identity changed")
        yield component.name, str(component.version), record
