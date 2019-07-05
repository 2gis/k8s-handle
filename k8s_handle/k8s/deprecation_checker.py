import logging

import semver

from k8s_handle.templating import get_template_contexts
from k8s_handle.exceptions import DeprecationError

log = logging.getLogger(__name__)


class ApiDeprecationChecker:
    def __init__(self, server_version):
        self.server_version = server_version
        self.deprecated_versions = {
            "extensions/v1beta1": {
                "since": "1.8.0",
                "until": "1.16.0",
                "resources": [
                    "Deployment",
                    "DaemonSet",
                    "ReplicaSet",
                    "StatefulSet",
                    "PodSecurityPolicy",
                    "NetworkPolicy",
                ],
            },
            "apps/v1beta1": {
                "since": "1.9.0",
                "until": "1.16.0",
                "resources": [
                    "Deployment",
                    "DaemonSet",
                    "ReplicaSet",
                ],
            },
            "apps/v1beta2": {
                "since": "1.9.0",
                "until": "1.16.0",
                "resources": [
                    "Deployment",
                    "DaemonSet",
                    "ReplicaSet",
                ],
            },
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

        if self.deprecated_versions[api_version]["until"]:
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
        for template_body in get_template_contexts(file_path):
            self._is_deprecated(
                template_body.get('apiVersion'),
                template_body.get('kind'),
            )
