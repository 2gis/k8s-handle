import logging
from time import sleep

from kubernetes import client
from kubernetes.client.rest import ApiException

from k8s_handle import settings
from k8s_handle.exceptions import ProvisioningError
from k8s_handle.transforms import add_indent, split_str_by_capital_letters
from .api_extensions import ResourcesAPI
from .api_clients import ApiClientWithWarningHandler
from .mocks import K8sClientMock

log = logging.getLogger(__name__)

RE_CREATE_TRIES = 10
RE_CREATE_TIMEOUT = 1


class Adapter:
    api_versions = {
        'v1': client.CoreV1Api,
        'batch/v1': client.BatchV1Api,
        'policy/v1': client.PolicyV1Api,
        'storage.k8s.io/v1': client.StorageV1Api,
        'apps/v1': client.AppsV1Api,
        'autoscaling/v1': client.AutoscalingV1Api,
        'autoscaling/v2': client.AutoscalingV2Api,
        'rbac.authorization.k8s.io/v1': client.RbacAuthorizationV1Api,
        'scheduling.k8s.io/v1': client.SchedulingV1Api,
        'networking.k8s.io/v1': client.NetworkingV1Api,
        'apiextensions.k8s.io/v1': client.ApiextensionsV1Api,
    }
    kinds_builtin = [
        'ConfigMap', 'CronJob', 'DaemonSet', 'Deployment', 'Endpoints',
        'Job', 'Namespace', 'PodDisruptionBudget', 'ResourceQuota',
        'Secret', 'Service', 'ServiceAccount', 'StatefulSet', 'StorageClass',
        'PersistentVolume', 'PersistentVolumeClaim', 'HorizontalPodAutoscaler',
        'Role', 'RoleBinding', 'ClusterRole', 'ClusterRoleBinding', 'CustomResourceDefinition',
        'PriorityClass', 'PodSecurityPolicy', 'LimitRange', 'NetworkPolicy'
    ]

    def __init__(self, spec):
        self.body = spec
        self.kind = spec.get('kind', "")
        self.name = spec.get('metadata', {}).get('name')
        self.namespace = spec.get('metadata', {}).get('namespace', "") or settings.K8S_NAMESPACE

    @staticmethod
    def get_instance(spec, api_custom_objects=None, api_resources=None, warning_handler=None):
        api_client = ApiClientWithWarningHandler(warning_handler=warning_handler)

        # due to https://github.com/kubernetes-client/python/issues/387
        if spec.get('kind') in Adapter.kinds_builtin:
            if spec.get('apiVersion') == 'test/test':
                return AdapterBuiltinKind(spec, K8sClientMock(spec.get('metadata', {}).get('name')))

            api = Adapter.api_versions.get(spec.get('apiVersion'))

            if not api:
                return None

            return AdapterBuiltinKind(spec, api(api_client=api_client))

        api_custom_objects = api_custom_objects or client.CustomObjectsApi(api_client=api_client)
        api_resources = api_resources or ResourcesAPI(api_client=api_client)
        return AdapterCustomKind(spec, api_custom_objects, api_resources)


class AdapterBuiltinKind(Adapter):
    def __init__(self, spec, api=None):
        super().__init__(spec)
        self.kind = split_str_by_capital_letters(spec['kind'])
        self.replicas = spec.get('spec', {}).get('replicas')
        self.api = api

    def get(self):
        try:
            if hasattr(self.api, "read_namespaced_{}".format(self.kind)):
                response = getattr(self.api, 'read_namespaced_{}'.format(self.kind))(
                    self.name, namespace=self.namespace)
            else:
                response = getattr(self.api, 'read_{}'.format(self.kind))(self.name)
        except ApiException as e:
            if e.reason == 'Not Found':
                return None
            log.error('Exception when calling "read_namespaced_{}": {}'.format(self.kind, add_indent(e.body)))
            raise ProvisioningError(e)

        return response

    def get_pods_by_selector(self, label_selector):
        try:
            if not isinstance(self.api, K8sClientMock):
                self.api = client.CoreV1Api()

            return self.api.list_namespaced_pod(
                namespace=self.namespace, label_selector='job-name={}'.format(label_selector))

        except ApiException as e:
            log.error('Exception when calling CoreV1Api->list_namespaced_pod: {}', e)
            raise e

    def read_pod_status(self, name):
        try:
            if not isinstance(self.api, K8sClientMock):
                self.api = client.CoreV1Api()

            return self.api.read_namespaced_pod_status(name, namespace=self.namespace)
        except ApiException as e:
            log.error('Exception when calling CoreV1Api->read_namespaced_pod_status: {}', e)
            raise e

    def read_pod_logs(self, name, container):
        log.info('Read logs for pod "{}", container "{}"'.format(name, container))
        try:
            if not isinstance(self.api, K8sClientMock):
                self.api = client.CoreV1Api()
            if settings.COUNT_LOG_LINES:
                return self.api.read_namespaced_pod_log(name, namespace=self.namespace, timestamps=True,
                                                        tail_lines=settings.COUNT_LOG_LINES, container=container)
            return self.api.read_namespaced_pod_log(name, namespace=self.namespace, timestamps=True,
                                                    container=container)
        except ApiException as e:
            log.error('Exception when calling CoreV1Api->read_namespaced_pod_log: {}', e)
            raise e

    def create(self):
        try:
            if hasattr(self.api, "create_namespaced_{}".format(self.kind)):
                return getattr(self.api, 'create_namespaced_{}'.format(self.kind))(
                    body=self.body, namespace=self.namespace)

            return getattr(self.api, 'create_{}'.format(self.kind))(body=self.body)
        except ApiException as e:
            log.error('Exception when calling "create_namespaced_{}": {}'.format(self.kind, add_indent(e.body)))
            raise ProvisioningError(e)
        except ValueError as e:
            log.error(e)
            # WORKAROUND:
            # - https://github.com/kubernetes-client/gen/issues/52
            # - https://github.com/kubernetes-client/python/issues/1098
            if self.kind not in ['custom_resource_definition', 'horizontal_pod_autoscaler']:
                raise e

    def replace(self, parameters):
        try:
            if self.kind in ['service', 'custom_resource_definition', 'pod_disruption_budget']:
                if 'resourceVersion' in parameters:
                    self.body['metadata']['resourceVersion'] = parameters['resourceVersion']

            if self.kind in ['service']:
                if 'clusterIP' not in self.body['spec'] and 'clusterIP' in parameters:
                    self.body['spec']['clusterIP'] = parameters['clusterIP']

            if self.kind in ['custom_resource_definition']:
                return self.api.replace_custom_resource_definition(
                    self.name, self.body,
                )

            if self.kind in ['service_account']:
                return getattr(self.api, 'patch_namespaced_{}'.format(self.kind))(
                    name=self.name, body=self.body, namespace=self.namespace
                )

            # Use patch() for Secrets with ServiceAccount's token to preserve data fields (ca.crt, token, namespace),
            # "kubernetes.io/service-account.uid" annotation and "kubernetes.io/legacy-token-last-used" label
            # populated by serviceaccount-token controller.
            #
            # See for details:
            # https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/#manually-create-an-api-token-for-a-serviceaccount
            if self.kind in ['secret']:
                if ('type' in self.body and self.body['type'] == 'kubernetes.io/service-account-token' and
                        'annotations' in self.body['metadata'] and
                        'kubernetes.io/service-account.name' in self.body['metadata']['annotations']):

                    return getattr(self.api, 'patch_namespaced_{}'.format(self.kind))(
                        name=self.name, body=self.body, namespace=self.namespace
                    )

            if hasattr(self.api, "replace_namespaced_{}".format(self.kind)):
                return getattr(self.api, 'replace_namespaced_{}'.format(self.kind))(
                    name=self.name, body=self.body, namespace=self.namespace)

            return getattr(self.api, 'replace_{}'.format(self.kind))(
                name=self.name, body=self.body)
        except ApiException as e:
            if self.kind in ['pod_disruption_budget'] and e.status == 422:
                return self.re_create()
            log.error('Exception when calling "replace_namespaced_{}": {}'.format(self.kind, add_indent(e.body)))
            raise ProvisioningError(e)

    def delete(self):
        try:
            if hasattr(self.api, "delete_namespaced_{}".format(self.kind)):
                return getattr(self.api, 'delete_namespaced_{}'.format(self.kind))(
                    name=self.name, body=client.V1DeleteOptions(propagation_policy='Foreground'),
                    namespace=self.namespace)

            return getattr(self.api, 'delete_{}'.format(self.kind))(
                name=self.name, body=client.V1DeleteOptions(propagation_policy='Foreground'))
        except ApiException as e:
            if e.reason == 'Not Found':
                return None
            log.error('Exception when calling "delete_namespaced_{}": {}'.format(self.kind, add_indent(e.body)))
            raise ProvisioningError(e)

    def re_create(self):
        log.info('Re-creating {}'.format(self.kind))
        self.body['metadata'].pop('resourceVersion', None)
        self.delete()

        for i in range(0, RE_CREATE_TRIES):
            if self.get() is not None:
                sleep(RE_CREATE_TIMEOUT)

        return self.create()


class AdapterCustomKind(Adapter):
    def __init__(self, spec, api_custom_objects, api_resources):
        super().__init__(spec)
        self.api = api_custom_objects
        self.api_resources = api_resources
        self.plural = None

        try:
            api_version_splitted = spec.get('apiVersion').split('/', 1)
            self.group = api_version_splitted[0]
            self.version = api_version_splitted[1]
        except (IndexError, AttributeError):
            self.group = None
            self.version = None

        resources_list = self.api_resources.list_api_resource_arbitrary(self.group, self.version)

        if not resources_list:
            return

        for resource in resources_list.resources:
            if resource.kind != self.kind:
                continue

            self.plural = resource.name

            if not resource.namespaced:
                self.namespace = ""

            break

    def get(self):
        self._validate()

        try:
            if self.namespace:
                return self.api.get_namespaced_custom_object(
                    self.group, self.version, self.namespace, self.plural, self.name
                )

            return self.api.get_cluster_custom_object(self.group, self.version, self.plural, self.name)

        except ApiException as e:
            if e.reason == 'Not Found':
                return None

            log.error('{}'.format(add_indent(e.body)))
            raise ProvisioningError(e)

    def create(self):
        self._validate()

        try:
            if self.namespace:
                return self.api.create_namespaced_custom_object(
                    self.group, self.version, self.namespace, self.plural, self.body
                )

            return self.api.create_cluster_custom_object(self.group, self.version, self.plural, self.body)

        except ApiException as e:
            log.error('{}'.format(add_indent(e.body)))
            raise ProvisioningError(e)

    def delete(self):
        self._validate()

        try:
            if self.namespace:
                return self.api.delete_namespaced_custom_object(
                    self.group, self.version, self.namespace, self.plural, self.name,
                    body=client.V1DeleteOptions(propagation_policy='Foreground')
                )

            return self.api.delete_cluster_custom_object(
                self.group, self.version, self.plural, self.name,
                body=client.V1DeleteOptions(propagation_policy='Foreground')
            )

        except ApiException as e:
            if e.reason == 'Not Found':
                return None

            log.error(
                '{}'.format(add_indent(e.body)))
            raise ProvisioningError(e)

    def replace(self, parameters):
        self._validate()

        if 'resourceVersion' in parameters:
            self.body['metadata']['resourceVersion'] = parameters['resourceVersion']

        try:
            if self.namespace:
                return self.api.replace_namespaced_custom_object(
                    self.group, self.version, self.namespace, self.plural, self.name, self.body
                )

            return self.api.replace_cluster_custom_object(
                self.group, self.version, self.plural, self.name, self.body
            )
        except ApiException as e:
            log.error('{}'.format(add_indent(e.body)))
            raise ProvisioningError(e)

    def _validate(self):
        if not self.plural:
            raise RuntimeError("No valid plural name of resource definition discovered")

        if not self.group:
            raise RuntimeError("No valid resource definition group discovered")

        if not self.version:
            raise RuntimeError("No valid version of resource definition supplied")
