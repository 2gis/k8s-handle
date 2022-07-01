import logging

from kubernetes import client
from kubernetes.client.rest import ApiException

from k8s_handle.exceptions import ProvisioningError
from k8s_handle.transforms import add_indent

log = logging.getLogger(__name__)


class ResourcesAPI(client.ApisApi):
    def list_api_resource_arbitrary(self, group, version):
        try:
            log.debug(f"calling /apis/{group}/{version}")
            return self.api_client.call_api(
                '/apis/{}/{}'.format(group, version), 'GET',
                {},
                [],
                {
                    'Accept': self.api_client.select_header_accept(
                        ['application/json', 'application/yaml', 'application/vnd.kubernetes.protobuf']
                    ),
                    'Content-Type': self.api_client.select_header_content_type(
                        ['application/json', 'application/yaml', 'application/vnd.kubernetes.protobuf']
                    )
                },
                body=None,
                post_params=[],
                files={},
                response_type='V1APIResourceList',
                auth_settings=['BearerToken'],
                async_req=None,
                _return_http_data_only=True,
                _preload_content=True,
                _request_timeout=None,
                collection_formats={}
            )
        except ApiException as e:
            if e.reason == 'Not Found':
                log.error('The resource definition with the specified group and version was not found')
                return None

            log.error('{}'.format(add_indent(e.body)))
            raise ProvisioningError(e)


class CoreResourcesAPI(client.CoreApi):

    def list_api_resources(self, version):
        try:
            return self.api_client.call_api(
                resource_path='/api/{}'.format(version),
                method='GET',
                header_params={
                    'Accept': self.api_client.select_header_accept(
                        ['application/json', 'application/yaml', 'application/vnd.kubernetes.protobuf']
                    ),
                    'Content-Type': self.api_client.select_header_content_type(
                        ['application/json', 'application/yaml', 'application/vnd.kubernetes.protobuf']
                    )
                },
                response_type='V1APIResourceList',
                auth_settings=['BearerToken'],
                _return_http_data_only=True,
                _preload_content=True,
            )
        except ApiException as e:
            if e.reason == 'Not Found':
                log.error('The resource definition with the specified version was not found')
                return None

            log.error('{}'.format(add_indent(e.body)))
            raise ProvisioningError(e)
