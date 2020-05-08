import logging

import semver

from k8s_handle.templating import get_template_contexts

log = logging.getLogger(__name__)


class ApiDeprecationChecker:
    def __init__(self, server_version):
        self.server_version = server_version
        self.deprecated_versions = {
            "extensions/v1beta1": {
                "Deployment": {
                    "since": "1.8.0",
                    "until": "1.16.0",
                },
                "DaemonSet": {
                    "since": "1.8.0",
                    "until": "1.16.0",
                },
                "ReplicaSet": {
                    "since": "1.8.0",
                    "until": "1.16.0",
                },
                "NetworkPolicy": {
                    "since": "1.9.0",
                    "until": "1.16.0",
                },
                "PodSecurityPolicy": {
                    "since": "1.10.0",
                    "until": "1.16.0",
                },
                "Ingress": {
                    "since": "1.14.0",
                    "until": "1.20.0",
                },
            },
            "apps/v1beta1": {
                "Deployment": {
                    "since": "1.9.0",
                    "until": "1.16.0",
                },
                "DaemonSet": {
                    "since": "1.9.0",
                    "until": "1.16.0",
                },
                "ReplicaSet": {
                    "since": "1.9.0",
                    "until": "1.16.0",
                },
                "StatefulSet": {
                    "since": "1.9.0",
                    "until": "1.16.0",
                },
            },
            "apps/v1beta2": {
                "Deployment": {
                    "since": "1.9.0",
                    "until": "1.16.0",
                },
                "DaemonSet": {
                    "since": "1.9.0",
                    "until": "1.16.0",
                },
                "ReplicaSet": {
                    "since": "1.9.0",
                    "until": "1.16.0",
                },
                "StatefulSet": {
                    "since": "1.9.0",
                    "until": "1.16.0",
                },
            },
            "scheduling.k8s.io/v1alpha1": {
                "PriorityClass": {
                    "since": "1.14.0",
                    "until": "1.17.0",
                },
            },
            "scheduling.k8s.io/v1beta1": {
                "PriorityClass": {
                    "since": "1.14.0",
                    "until": "1.17.0",
                },
            },
            "apiextensions.k8s.io/v1beta1": {
                "CustomResourceDefinition": {
                    "since": "1.16.0",
                    "until": "1.19.0",
                },
            },
            "admissionregistration.k8s.io/v1beta1": {
                "MutatingWebhookConfiguration": {
                    "since": "1.16.0",
                    "until": "1.19.0",
                },
                "ValidatingWebhookConfiguration": {
                    "since": "1.16.0",
                    "until": "1.19.0",
                },
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
        if api_version not in self.deprecated_versions:
            return False

        if kind not in self.deprecated_versions[api_version]:
            return False

        if self.deprecated_versions[api_version][kind]["until"]:
            if self._is_server_version_greater(self.deprecated_versions[api_version][kind]["until"]):
                log.warning(message.format(
                    api_version=api_version,
                    kind=kind,
                    status="unsupported",
                    k8s_version=self.deprecated_versions[api_version][kind]["until"],
                ))
                return True

        if self._is_server_version_greater(self.deprecated_versions[api_version][kind]["since"]):
            log.warning(message.format(
                api_version=api_version,
                kind=kind,
                status="deprecated",
                k8s_version=self.deprecated_versions[api_version][kind]["since"],
            ))
            return True

        return False

    def run(self, file_path):
        for template_body in get_template_contexts(file_path):
            self._is_deprecated(
                template_body.get('apiVersion'),
                template_body.get('kind'),
            )
