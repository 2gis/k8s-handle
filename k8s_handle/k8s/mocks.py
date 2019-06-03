from collections import namedtuple

from kubernetes.client import V1APIResourceList
from kubernetes.client.rest import ApiException


class K8sClientMock:
    def __init__(self, name=None):
        self.name = name
        pass

    # Deployment
    def read_namespaced_deployment(self, name, namespace):
        if self.name == 'fail':
            raise ApiException('Get deployment fail')
        if self.name == '404' or name == '404':
            raise ApiException(reason='Not Found')

        my_response = namedtuple('my_response', 'metadata status spec')
        my_status = namedtuple('my_status',
                               'replicas available_replicas ready_replicas updated_replicas unavailable_replicas')
        my_spec = namedtuple('my_spec', 'replicas')
        if self.name == 'test1':
            return my_response(metadata={}, spec=my_spec(replicas=3),
                               status=my_status(replicas=3,
                                                available_replicas=2,
                                                ready_replicas=1,
                                                updated_replicas=None,
                                                unavailable_replicas=1))
        if self.name == 'test2' or name == 'test2':
            return my_response(metadata={}, spec=my_spec(replicas=1),
                               status=my_status(replicas=1,
                                                available_replicas=1,
                                                ready_replicas=1,
                                                updated_replicas=1,
                                                unavailable_replicas=None))

        return my_response(metadata={'key1': 'value1'}, status={'key1': 'value1'}, spec={'key1': 'value1'})

    def create_namespaced_deployment(self, body, namespace):
        if self.name == 'fail':
            raise ApiException('Create deployment fail')

        return {'key1': 'value1'}

    def replace_namespaced_deployment(self, name, body, namespace):
        if self.name == 'fail':
            raise ApiException('Replace deployment fail')

        return {'key1': 'value1'}

    def delete_namespaced_deployment(self, name, body, namespace):
        if self.name == 'fail':
            raise ApiException('Delete deployment fail')
        if self.name == '404' or name == '404':
            raise ApiException(reason='Not Found')

        if self.name == 'test1' or name == 'test1':
            my_response = namedtuple('my_response', 'message')
            return my_response(message='Failed')

        if self.name == 'test2' or name == 'test2':
            my_response = namedtuple('my_response', 'message')
            return my_response(message=None)

        return {'key1': 'value1'}

    # Service
    def read_namespaced_service(self, name, namespace, body=None):
        if self.name == 'fail':
            raise ApiException('Get service fail')
        if self.name == '404':
            raise ApiException(reason='Not Found')

        my_response = namedtuple('my_response', 'metadata status spec')
        my_status = namedtuple('my_status',
                               'replicas available_replicas ready_replicas updated_replicas unavailable_replicas')
        my_spec = namedtuple('my_spec', 'ports')
        my_port = namedtuple('my_port', 'port name')

        if self.name == 'test1':
            return my_response(metadata={}, spec=my_spec(ports=[my_port(port=123, name='test1')]),
                               status=my_status(replicas=3,
                                                available_replicas=2,
                                                ready_replicas=1,
                                                updated_replicas=None,
                                                unavailable_replicas=1))
        if self.name == 'test2':
            return my_response(metadata={}, spec=my_spec(ports=[]),
                               status=my_status(replicas=1,
                                                available_replicas=1,
                                                ready_replicas=1,
                                                updated_replicas=1,
                                                unavailable_replicas=None))

        return my_response(metadata={'key1': 'value1'}, status={'key1': 'value1'}, spec={})

    def replace_namespaced_service(self, name, body, namespace):
        if self.name == 'fail':
            raise ApiException('Replace service fail')

        return {'key1': 'value1'}

    def delete_namespaced_service(self, name, namespace, body=None):
        my_response = namedtuple('my_response', 'message')
        return my_response(message='Failed')

    def patch_namespaced_service(self, name, body, namespace):
        return {'key1': 'value1'}

    # StatefulSet
    def read_namespaced_stateful_set(self, name, namespace):
        if self.name == 'fail':
            raise ApiException('Get statefulset fail')
        if self.name == '404':
            raise ApiException(reason='Not Found')

        my_response = namedtuple('my_response', 'metadata status spec')
        my_status = namedtuple('my_status',
                               'current_replicas current_revision ready_replicas replicas update_revision')
        my_spec = namedtuple('my_spec', 'replicas')

        if self.name == 'test1':
            return my_response(metadata={}, spec=my_spec(replicas=3),
                               status=my_status(current_replicas=2,
                                                current_revision='revision-123',
                                                ready_replicas=1,
                                                replicas=3,
                                                update_revision='revision-321'))

        if self.name == 'test2':
            return my_response(metadata={},  spec=my_spec(replicas=3),
                               status=my_status(current_replicas=3,
                                                current_revision='revision-123',
                                                ready_replicas=3,
                                                replicas=3,
                                                update_revision='revision-123'))

        return my_response(metadata={'key1': 'value1'}, status={'key1': 'value1'}, spec={'key1': 'value1'})

    # DaemonSet
    def read_namespaced_daemon_set(self, name, namespace):
        if self.name == 'fail':
            raise ApiException('Get daemonset fail')
        if self.name == '404':
            raise ApiException(reason='Not Found')

        my_response = namedtuple('my_response', 'metadata status')
        my_status = namedtuple('my_status', 'desired_number_scheduled number_available '
                                            'number_ready updated_number_scheduled number_unavailable')

        if self.name == 'test1':
            return my_response(metadata={}, status=my_status(desired_number_scheduled=2,
                                                             number_available=2,
                                                             number_ready=1,
                                                             updated_number_scheduled=1,
                                                             number_unavailable=1))
        if self.name == 'test2':
            return my_response(metadata={}, status=my_status(desired_number_scheduled=2,
                                                             number_available=2,
                                                             number_ready=2,
                                                             updated_number_scheduled=2,
                                                             number_unavailable=None))

        return my_response(metadata={'key1': 'value1'}, status={'key1': 'value1'})

    # Job
    def read_namespaced_job(self, name, namespace):
        if self.name == 'fail':
            raise ApiException('Get daemonset fail')
        if self.name == '404':
            raise ApiException(reason='Not Found')

        my_response = namedtuple('my_response', 'metadata status')
        my_status = namedtuple('my_status', 'failed conditions')

        if self.name == 'test1':
            return my_response(metadata={}, status=my_status(failed='Failed',
                                                             conditions=[]))
        if self.name == 'test2':
            my_conditions = namedtuple('my_conditions', 'type')
            return my_response(metadata={}, status=my_status(failed=None,
                                                             conditions=[my_conditions(type='Failed')]))
        if self.name == 'test3':
            my_conditions = namedtuple('my_conditions', 'type')
            return my_response(metadata={}, status=my_status(failed=None,
                                                             conditions=[my_conditions(type='Complete')]))

        return my_response(metadata={'key1': 'value1'}, status={'key1': 'value1'})

    # StorageClass
    def read_storage_class(self, name):
        if self.name == 'fail':
            raise ApiException('Get storage class fail')
        if self.name == '404' or name == '404':
            raise ApiException(reason='Not Found')

        my_response = namedtuple('my_response', 'metadata status')
        my_status = namedtuple('my_status',
                               'replicas available_replicas ready_replicas updated_replicas unavailable_replicas')

        if self.name == 'test1':
            return my_response(metadata={}, status=my_status(replicas=3,
                                                             available_replicas=2,
                                                             ready_replicas=1,
                                                             updated_replicas=None,
                                                             unavailable_replicas=1))
        if self.name == 'test2' or name == 'test2':
            return my_response(metadata={}, status=my_status(replicas=1,
                                                             available_replicas=1,
                                                             ready_replicas=1,
                                                             updated_replicas=1,
                                                             unavailable_replicas=None))

        return my_response(metadata={'key1': 'value1'}, status={'key1': 'value1'})

    def create_storage_class(self, body):
        if self.name == 'fail':
            raise ApiException('Create storage class fail')

        return {'key1': 'value1'}

    def replace_storage_class(self, name, body):
        if self.name == 'fail':
            raise ApiException('Replace storage class fail')

        return {'key1': 'value1'}

    def delete_storage_class(self, name, body):
        if self.name == 'fail':
            raise ApiException('Delete storage class fail')
        if self.name == '404' or name == '404':
            raise ApiException(reason='Not Found')

        if self.name == 'test1' or name == 'test1':
            my_response = namedtuple('my_response', 'message')
            return my_response(message='Failed')

        if self.name == 'test2' or name == 'test2':
            my_response = namedtuple('my_response', 'message')
            return my_response(message=None)

        return {'key1': 'value1'}

    # PersistentVolumeClaim
    def read_namespaced_persistent_volume_claim(self, name, namespace):
        my_response = namedtuple('my_response', 'spec metadata')
        my_spec = namedtuple('my_spec',
                             'access_modes resources selector storage_class_name')

        if self.name == 'test1' or name == 'test1':
            return my_response(metadata={}, spec=my_spec(access_modes=['ReadWriteOnce'],
                                                         resources={'requests': {'storage': '1Gi'}},
                                                         storage_class_name='test',
                                                         selector={'matchLabels': {'volume': 'test'}}))

        if self.name == 'test2' or name == 'test2':
            return my_response(metadata={}, spec=my_spec(access_modes=['ReadWriteOnce'],
                                                         resources={'requests': {'storage': '2Gi'}},
                                                         storage_class_name='test',
                                                         selector={'matchLabels': {'volume': 'test'}}))

        return my_response(metadata={'key1': 'value1'}, spec={'key1': 'value1'})

    def replace_namespaced_persistent_volume_claim(self, name, body, namespace):
        if self.name == 'test2' or name == 'test2':
            raise ApiException('Replace persistent volume claim fail')


class ServiceMetadata:
    labels = {}

    def __init__(self, annotations, labels):
        if annotations is not None:
            self.annotations = annotations
        self.labels = labels


class ServiceSpec:
    def __init__(self, case):
        if case in ['case1', 'case2', 'case3']:
            self.ports = [ServicePort(55)]
        if case in ['case4', 'case5', 'case7', 'case8']:
            self.ports = [ServicePort(55, 'test')]
        if case in ['case6']:
            self.ports = [ServicePort(55, 'test', 90)]


class ServicePort:
    def __init__(self, port, name=None, target_port=None, node_port=None, protocol='TCP'):
        self.port = port
        self.name = name
        self.node_port = node_port
        self.protocol = protocol
        if target_port is None:
            self.target_port = port
        else:
            self.target_port = port


class CustomObjectsAPIMock:
    pass


class ResourcesAPIMock:
    def __init__(self, api_version=None, group_version=None, resources=None):
        self._resources = resources
        self._api_version = api_version
        self._group_version = group_version
        self._kind = 'APIResourceList'

    def list_api_resource_arbitrary(self, group, version):
        if not self._resources or self._group_version != '{}/{}'.format(group, version):
            return None

        return V1APIResourceList(self._api_version, self._group_version, self._kind, self._resources)
