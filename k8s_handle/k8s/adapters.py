import logging

from kubernetes import client
from kubernetes.client.rest import ApiException

from k8s_handle import settings
from k8s_handle.exceptions import ProvisioningError
from k8s_handle.transforms import add_indent, split_str_by_capital_letters
from .mocks import K8sClientMock

log = logging.getLogger(__name__)


class Adapter:
    api_versions = {
        'apps/v1beta1': client.AppsV1beta1Api,
        'v1': client.CoreV1Api,
        'extensions/v1beta1': client.ExtensionsV1beta1Api,
        'batch/v1': client.BatchV1Api,
        'batch/v2alpha1': client.BatchV2alpha1Api,
        'batch/v1beta1': client.BatchV1beta1Api,
        'policy/v1beta1': client.PolicyV1beta1Api,
        'storage.k8s.io/v1': client.StorageV1Api,
        'apps/v1': client.AppsV1Api,
        'autoscaling/v1': client.AutoscalingV1Api,
        'rbac.authorization.k8s.io/v1': client.RbacAuthorizationV1Api,
        'scheduling.k8s.io/v1alpha1': client.SchedulingV1alpha1Api,
        'scheduling.k8s.io/v1beta1': client.SchedulingV1beta1Api,
        'networking.k8s.io/v1': client.NetworkingV1Api,
        'apiextensions.k8s.io/v1beta1': client.ApiextensionsV1beta1Api,
    }
    kinds_builtin = [
        'ConfigMap', 'CronJob', 'DaemonSet', 'Deployment', 'Endpoints',
        'Ingress', 'Job', 'Namespace', 'PodDisruptionBudget', 'ResourceQuota',
        'Secret', 'Service', 'ServiceAccount', 'StatefulSet', 'StorageClass',
        'PersistentVolume', 'PersistentVolumeClaim', 'HorizontalPodAutoscaler',
        'Role', 'RoleBinding', 'ClusterRole', 'ClusterRoleBinding', 'CustomResourceDefinition',
        'PriorityClass', 'PodSecurityPolicy', 'LimitRange', 'NetworkPolicy'
    ]

    def __init__(self, spec):
        self.body = spec
        self.kind = spec.get('kind', "")
        self.name = spec.get('metadata', {}).get('name')

    @staticmethod
    def get_instance(spec, custom_objects_api=None, definitions_api=None):
        # due to https://github.com/kubernetes-client/python/issues/387
        if spec.get('kind') in Adapter.kinds_builtin:
            if spec.get('apiVersion') == 'test/test':
                return AdapterBuiltinKind(spec, K8sClientMock(spec.get('metadata', {}).get('name')))

            api = Adapter.api_versions.get(spec.get('apiVersion'))

            if not api:
                return None

            return AdapterBuiltinKind(spec, api())

        custom_objects_api = custom_objects_api or client.CustomObjectsApi()
        definitions_api = definitions_api or client.ApiextensionsV1beta1Api()

        return AdapterCustomKind(spec, custom_objects_api, DefinitionQualifier(definitions_api))


class AdapterBuiltinKind(Adapter):
    def __init__(self, spec, api=None):
        super().__init__(spec)
        self.kind = split_str_by_capital_letters(spec['kind'])
        self.replicas = spec.get('spec', {}).get('replicas')
        self.namespace = spec.get('metadata', {}).get('namespace', "") or settings.K8S_NAMESPACE
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
            # WORKAROUND https://github.com/kubernetes-client/python/issues/466
            # also https://github.com/kubernetes-client/gen/issues/52
            if self.kind not in ['pod_disruption_budget', 'custom_resource_definition']:
                raise e

    def replace(self, parameters):
        try:
            if self.kind in ['custom_resource_definition']:
                self.body['metadata']['resourceVersion'] = parameters['resourceVersion']
                return self.api.replace_custom_resource_definition(
                    self.name, self.body,
                )

            if self.kind in ['service', 'service_account']:
                if 'spec' in self.body:
                    self.body['spec']['ports'] = parameters.get('ports')

                return getattr(self.api, 'patch_namespaced_{}'.format(self.kind))(
                    name=self.name, body=self.body, namespace=self.namespace
                )

            if hasattr(self.api, "replace_namespaced_{}".format(self.kind)):
                return getattr(self.api, 'replace_namespaced_{}'.format(self.kind))(
                    name=self.name, body=self.body, namespace=self.namespace)

            return getattr(self.api, 'replace_{}'.format(self.kind))(
                name=self.name, body=self.body)
        except ApiException as e:
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


class AdapterCustomKind(Adapter):
    def __init__(self, spec, api, qualifier):
        super().__init__(spec)
        self.namespace = None
        self.api = api

        try:
            api_version_splitted = spec.get('apiVersion').split('/', 1)
            self.group = api_version_splitted[0]
            self.version = api_version_splitted[1]
        except (IndexError, AttributeError):
            self.group = None
            self.version = None

        qualifier.qualify(self.kind, self.group, self.version)
        self.plural = qualifier.plural
        self.namespace = qualifier.namespace or spec.get('metadata', {}).get('namespace', "")

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
                    client.V1DeleteOptions(propagation_policy='Foreground')
                )

            return self.api.delete_cluster_custom_object(
                self.group, self.version, self.plural, self.name,
                client.V1DeleteOptions(propagation_policy='Foreground')
            )

        except ApiException as e:
            if e.reason == 'Not Found':
                return None

            log.error(
                '{}'.format(add_indent(e.body)))
            raise ProvisioningError(e)

    def replace(self, _):
        self._validate()

        try:
            if self.namespace:
                return self.api.patch_namespaced_custom_object(
                    self.group, self.version, self.namespace, self.plural, self.name, self.body
                )

            return self.api.patch_cluster_custom_object(
                self.group, self.version, self.plural, self.name, self.body
            )
        except ApiException as e:
            log.error('{}'.format(add_indent(e.body)))
            raise ProvisioningError(e)

    def _validate(self):
        if not self.plural:
            raise ProvisioningError("No valid plural name of resource definition discovered")

        if not self.group:
            raise ProvisioningError("No valid resource definition group discovered")

        if not self.version:
            raise ProvisioningError("No valid version of resource definition supplied")


class DefinitionQualifier:
    def __init__(self, api):
        self._api = api
        self._plural = None
        self._namespace = None

    @property
    def plural(self):
        return self._plural

    @property
    def namespace(self):
        return self._namespace

    def qualify(self, kind, group, version):
        for definition in self._api.list_custom_resource_definition().items:
            if definition.status.accepted_names.kind != kind:
                continue

            if definition.spec.group != group:
                continue

            match = False

            for version_ in definition.spec.versions:
                if version_.name != version:
                    continue

                match = True
                break

            if not match:
                continue

            match = False

            for condition in definition.status.conditions:
                if condition.type != 'Established':
                    continue

                if condition.status != 'True':
                    continue

                match = True

            if not match:
                continue

            self._plural = definition.spec.names.plural

            if definition.spec.scope == 'Namespaced':
                self._namespace = definition.metadata.namespace

            break
