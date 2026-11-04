from pathlib import Path
import sys

root = Path(sys.argv[1])
service = root / 'idf_component_tools/registry/service_details.py'
text = service.read_text()
before, read = text.split('def get_storage_client(', 1)
needle = '    profile = profile or get_profile(profile_name, config_path)'
assert read.count(needle) == 1
read = read.replace(needle, '''    import os
    locked_mirror = os.environ.get('ESP_IDF_PURIFIER_MIRROR')
    if locked_mirror:
        if registry_url and registry_url.rstrip('/') != 'https://components.espressif.com':
            raise RuntimeError('Additional component registries require a provider')
        from pathlib import Path
        from urllib.parse import unquote, urlparse
        class FrozenStorageClient(MultiStorageClient):
            def component(self, *args, **kwargs):
                result = super().component(*args, **kwargs)
                root = Path(unquote(urlparse(locked_mirror).path))
                for key in ('download_url', 'checksums_url'):
                    parsed = urlparse(result[key])
                    path = Path(os.path.normpath(unquote(parsed.path)))
                    if parsed.scheme != 'file' or parsed.netloc or parsed.query or parsed.fragment or not path.is_relative_to(root):
                        raise RuntimeError('Component artifact is outside the locked Nix mirror')
                return result
        return FrozenStorageClient(
            registry_url=None,
            storage_urls=[locked_mirror],
            local_storage_urls=[],
            default_namespace=namespace,
            local_first_mode=True,
        )
''' + needle)
service.write_text(before + 'def get_storage_client(' + read)

dependencies = root / 'idf_component_manager/dependencies.py'
text = dependencies.read_text()
needle = '    lock_manager = LockManager(lock_path)'
assert text.count(needle) == 1
text = text.replace(needle, '''    import json
    frozen_context = os.environ.get('ESP_IDF_PURIFIER_CONTEXT')
    if frozen_context:
        expected = json.loads(Path(frozen_context).read_text())
        if project_requirements.manifest_hash != expected['manifest_hash'] or project_requirements.target != expected['target']:
            raise RuntimeError('Component dependency selection changed; relock the project')
        for manifest in project_requirements.manifests:
            for requirement in manifest.requirements:
                if requirement.optional_requirement.has_kconfig_option:
                    raise RuntimeError('Kconfig-dependent resolution requires an additional provider')
                if requirement.source.type not in {'service', 'idf'}:
                    raise RuntimeError('This component source requires an additional provider')
        current = LockManager(lock_path).load().model_dump(mode='json')
        if any(record['source']['type'] not in {'service', 'idf'} for record in current['dependencies'].values()):
            raise RuntimeError('This transitive component source requires an additional provider')
        if current != expected:
            raise RuntimeError('Native component pins changed; relock the project')
''' + needle)
dependencies.write_text(text)

core = root / 'idf_component_manager/core.py'
text = core.read_text()
needle = "        self.managed_components_path = self.path / 'managed_components'"
assert text.count(needle) == 1
text = text.replace(needle, "        self.managed_components_path = Path(os.environ['ESP_IDF_PURIFIER_COMPONENTS']) if os.environ.get('ESP_IDF_PURIFIER_COMPONENTS') else self.path / 'managed_components'")
core.write_text(text)

extensions = root / 'idf_component_manager/idf_extensions.py'
text = extensions.read_text()
needle = '    def global_callback(ctx, global_args, tasks):\n'
assert text.count(needle) == 1
text = text.replace(needle, needle + '''        profile = os.environ.get('ESP_IDF_PURIFIER_PROFILE')
        if profile and tasks and any(task.name not in {'clean', 'fullclean', 'remove_managed_components'} for task in tasks):
            from pathlib import Path
            stamp = Path(global_args.build_dir) / '.esp-idf-purifier-profile'
            current = stamp.read_text() if stamp.exists() else None
            if current != profile:
                configure = next((task for task in tasks if task.name == 'reconfigure'), None)
                if configure is None:
                    configure = ctx.invoke(ctx.command.get_command(ctx, 'reconfigure'))
                    configure.action_args = {}
                    tasks.insert(0, configure)
                original_configure = configure.callback
                def record_profile(*args, **kwargs):
                    original_configure(*args, **kwargs)
                    stamp.parent.mkdir(parents=True, exist_ok=True)
                    stamp.write_text(profile)
                configure.callback = record_profile
''')
extensions.write_text(text)
