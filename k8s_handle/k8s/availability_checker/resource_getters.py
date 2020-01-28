from typing import List, Set

from k8s_handle.k8s.api_extensions import ResourcesAPI, CoreResourcesAPI

VERSION_DELIMITER = "/"


class AbstractResourceGetter(object):
    def is_processable_version(self, api_group: str) -> bool:
        raise NotImplementedError

    def get_resources_by_version(self, api_group: str) -> Set[str]:
        raise NotImplementedError


class CoreResourceGetter(AbstractResourceGetter):

    def __init__(self, resource_api: CoreResourcesAPI):
        self.api = resource_api
        self.versions = {}

    def is_processable_version(self, api_group: str) -> bool:
        return len(api_group.split(VERSION_DELIMITER, 1)) == 1

    def get_resources_by_version(self, api_group: str) -> Set[str]:
        if api_group in self.versions:
            return self.versions[api_group]

        resp = self.api.list_api_resources(api_group)

        if not resp:
            return set()

        kinds = {r.kind for r in resp.resources}
        self.versions[api_group] = kinds

        return kinds


class RegularResourceGetter(AbstractResourceGetter):

    def __init__(self, resource_api: ResourcesAPI):
        self.api = resource_api
        self.versions = {}

    def is_processable_version(self, api_group: str) -> bool:
        return len(api_group.split(VERSION_DELIMITER, 1)) == 2

    def get_resources_by_version(self, api_group: str) -> Set[str]:
        if api_group in self.versions:
            return self.versions[api_group]

        group, version = api_group.split("/", 1)
        resp = self.api.list_api_resource_arbitrary(group, version)

        if not resp:
            return set()

        kinds = {r.kind for r in resp.resources}
        self.versions[api_group] = kinds

        return kinds


def make_resource_getters_list() -> List[AbstractResourceGetter]:
    return [
        CoreResourceGetter(CoreResourcesAPI()),
        RegularResourceGetter(ResourcesAPI())
    ]
