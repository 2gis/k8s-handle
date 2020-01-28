from typing import List

from k8s_handle.templating import get_template_contexts
from k8s_handle.exceptions import ResourceNotAvailableError

from .resource_getters import AbstractResourceGetter


class ResourceAvailabilityChecker(object):

    def __init__(self, resources_getters: List[AbstractResourceGetter]):
        self.resources = resources_getters
        self.versions = {}

    def _is_available_kind(self, api_group: str, kind: str) -> bool:
        kinds = []
        for api in self.resources:
            if api.is_processable_version(api_group):
                kinds = api.get_resources_by_version(api_group)

        return kind in kinds

    def run(self, file_path: str):
        for template_body in get_template_contexts(file_path):
            if not self._is_available_kind(template_body.get('apiVersion'), template_body.get('kind')):
                raise ResourceNotAvailableError(
                    "The resource with kind {} is not supported with version {}. File: {}".format(
                        template_body.get('kind'), template_body.get('apiVersion'), file_path
                    )
                )
