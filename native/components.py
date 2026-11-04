"""Populate an immutable component tree through Espressif's own installer."""

import json
import sys
from pathlib import Path

from idf_component_manager.dependencies import dependency_validate
from idf_component_tools.manifest import SolvedManifest
from idf_component_tools.sources.fetcher import ComponentFetcher

lock = SolvedManifest.fromdict(json.loads(Path(sys.argv[1]).read_text()))
output = Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=True)
for component in lock.dependencies:
    if component.source.type == "idf":
        continue
    if component.source.type != "service":
        raise ValueError("This component source requires an additional provider")
    destination = output / component.name.replace("/", "__")
    installed = ComponentFetcher(component, destination).download()
    dependency_validate(component, installed)
