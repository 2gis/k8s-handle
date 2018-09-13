import logging

import semver

from templating import get_template_context

log = logging.getLogger(__name__)


class DeprecationError(Exception):
    pass


class ApiDeprecationChecker:
    def __init__(self, server_version):
        self.server_version = server_version
        self.deprecated_versions = {
            "extensions/v1beta1": {
                "since": "1.8.0",
                "until": "1.11.0",
                "resources": [
                    "Deployment",
                    "DaemonSet",
                    "ReplicaSet",
                    "StatefulSet",
                ],
            }
        }

    def _is_server_version_greater(self, checked_version):
        return True if semver.compare(self.server_version, checked_version) >= 0 else False

    def _is_deprecated(self, api_version, kind):
        message = """
        ▄▄
       ████
      ██▀▀██
     ███  ███     Version {api_version}
    ████▄▄████    for resource type {kind}
   █████  █████   is {status} since {k8s_version}
  ██████████████
                  """
        if api_version not in self.deprecated_versions.keys():
            return False

        if kind not in self.deprecated_versions[api_version].get("resources"):
            return False

        if self._is_server_version_greater(self.deprecated_versions[api_version]["until"]):
            log.warning(message.format(
                api_version=api_version,
                kind=kind,
                status="unsupported",
                k8s_version=self.deprecated_versions[api_version]["until"],
            ))
            raise DeprecationError(
                "Version {} for resourse type '{}' is unsupported since kubernetes {}".format(
                    api_version,
                    kind,
                    self.deprecated_versions[api_version]["until"]
                )
            )

        if self._is_server_version_greater(self.deprecated_versions[api_version]["since"]):
            log.warning(message.format(
                api_version=api_version,
                kind=kind,
                status="deprecated",
                k8s_version=self.deprecated_versions[api_version]["since"],
            ))
            return True

        return False

    def run(self, file_path):
        template_body = get_template_context(file_path)
        self._is_deprecated(
            template_body.get('apiVersion'),
            template_body.get('kind'),
        )
