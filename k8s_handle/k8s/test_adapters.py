import unittest

from kubernetes.client import V1APIResource

from k8s_handle.exceptions import ProvisioningError
from k8s_handle.transforms import split_str_by_capital_letters
from .adapters import Adapter, AdapterBuiltinKind, AdapterCustomKind
from .mocks import K8sClientMock, CustomObjectsAPIMock, ResourcesAPIMock


class TestAdapterBuiltInKind(unittest.TestCase):
    def test_get_app_kind(self):
        self.assertEqual(split_str_by_capital_letters('ConfigMap'), 'config_map')
        self.assertEqual(split_str_by_capital_letters('Namespace'), 'namespace')
        self.assertEqual(split_str_by_capital_letters('PodDisruptionBudget'), 'pod_disruption_budget')

    def test_app_get_fail(self):
        deployment = AdapterBuiltinKind(
            api=K8sClientMock('fail'),
            spec={'kind': 'Deployment', 'metadata': {'name': 'fail'}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            deployment.get()
        self.assertTrue('Get deployment fail' in str(context.exception))

        storage = AdapterBuiltinKind(
            api=K8sClientMock('fail'),
            spec={'kind': 'StorageClass', 'metadata': {'name': 'fail'}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            storage.get()
        self.assertTrue('Get storage class fail' in str(context.exception))

    def test_app_get_not_found(self):
        deployment = AdapterBuiltinKind(
            api=K8sClientMock('404'),
            spec={'kind': 'Deployment', 'metadata': {'name': '404'}, 'spec': {'replicas': 1}})
        res = deployment.get()
        self.assertEqual(res, None)

        storage = AdapterBuiltinKind(
            api=K8sClientMock('404'),
            spec={'kind': 'StorageClass', 'metadata': {'name': '404'}, 'spec': {'replicas': 1}})
        res = storage.get()
        self.assertEqual(res, None)

    def test_app_get(self):
        deployment = AdapterBuiltinKind(
            api=K8sClientMock(),
            spec={'kind': 'Deployment', 'metadata': {'name': 'test'}, 'spec': {'replicas': 1}})
        res = deployment.get()

        self.assertEqual(res.metadata, {'key1': 'value1'})

        storage = AdapterBuiltinKind(
            api=K8sClientMock(),
            spec={'kind': 'StorageClass', 'metadata': {'name': 'test'}, 'spec': {'replicas': 1}})
        res = storage.get()

        self.assertEqual(res.metadata, {'key1': 'value1'})

    def test_app_create_fail(self):
        deployment = AdapterBuiltinKind(
            api=K8sClientMock('fail'),
            spec={'kind': 'Deployment', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            deployment.create()
        self.assertTrue('Create deployment fail' in str(context.exception))

        storage = AdapterBuiltinKind(
            api=K8sClientMock('fail'),
            spec={'kind': 'StorageClass', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            storage.create()
        self.assertTrue('Create storage class fail' in str(context.exception))

    def test_app_create(self):
        deployment = AdapterBuiltinKind(
            api=K8sClientMock(''),
            spec={'kind': 'Deployment', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        res = deployment.create()
        self.assertEqual(res, {'key1': 'value1'})

        storage = AdapterBuiltinKind(
            api=K8sClientMock(''),
            spec={'kind': 'StorageClass', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        res = storage.create()
        self.assertEqual(res, {'key1': 'value1'})

    def test_app_replace_fail(self):
        deployment = AdapterBuiltinKind(
            api=K8sClientMock('fail'),
            spec={'kind': 'Deployment', 'metadata': {'name': 'fail'}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            deployment.replace({})
        self.assertTrue('Replace deployment fail' in str(context.exception))

        storage = AdapterBuiltinKind(
            api=K8sClientMock('fail'),
            spec={'kind': 'StorageClass', 'metadata': {'name': 'fail'}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            storage.replace({})
        self.assertTrue('Replace storage class fail' in str(context.exception))

    def test_app_replace(self):
        deployment = AdapterBuiltinKind(
            api=K8sClientMock(''),
            spec={'kind': 'Deployment', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        res = deployment.replace({})
        self.assertEqual(res, {'key1': 'value1'})

        storage = AdapterBuiltinKind(
            api=K8sClientMock(''),
            spec={'kind': 'StorageClass', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        res = storage.replace({})
        self.assertEqual(res, {'key1': 'value1'})

    def test_app_replace_service(self):
        service = AdapterBuiltinKind(
            api=K8sClientMock(''),
            spec={'kind': 'Service', 'metadata': {'name': ''}, 'spec': {'type': 'ClusterIP'}})
        res = service.replace({})
        self.assertEqual(res, {'key1': 'value1'})

    def test_app_delete_fail(self):
        client = AdapterBuiltinKind(
            api=K8sClientMock('fail'),
            spec={'kind': 'Deployment', 'metadata': {'name': 'fail'}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            client.delete()
        self.assertTrue('Delete deployment fail' in str(context.exception))

        storage = AdapterBuiltinKind(
            api=K8sClientMock('fail'),
            spec={'kind': 'StorageClass', 'metadata': {'name': 'fail'}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            storage.delete()
        self.assertTrue('Delete storage class fail' in str(context.exception))

    def test_app_delete_not_found(self):
        client = AdapterBuiltinKind(
            api=K8sClientMock('404'),
            spec={'kind': 'Deployment', 'metadata': {'name': '404'}, 'spec': {'replicas': 1}})
        res = client.delete()
        self.assertEqual(res, None)

        storage = AdapterBuiltinKind(
            api=K8sClientMock('404'),
            spec={'kind': 'StorageClass', 'metadata': {'name': '404'}, 'spec': {'replicas': 1}})
        res = storage.delete()
        self.assertEqual(res, None)

    def test_app_delete(self):
        client = AdapterBuiltinKind(
            api=K8sClientMock(),
            spec={'kind': 'Deployment', 'metadata': {'name': 'test'}, 'spec': {'replicas': 1}})
        res = client.delete()

        self.assertEqual(res, {'key1': 'value1'})

        storage = AdapterBuiltinKind(
            api=K8sClientMock(),
            spec={'kind': 'StorageClass', 'metadata': {'name': 'test'}, 'spec': {'replicas': 1}})
        res = storage.delete()

        self.assertEqual(res, {'key1': 'value1'})


class TestAdapter(unittest.TestCase):
    def test_get_instance_custom(self):
        self.assertIsInstance(
            Adapter.get_instance({'kind': "CustomKind"}, CustomObjectsAPIMock(), ResourcesAPIMock()),
            AdapterCustomKind
        )
        self.assertIsInstance(
            Adapter.get_instance({'kind': "CustomKind"}, CustomObjectsAPIMock(), ResourcesAPIMock()),
            AdapterCustomKind
        )

    def test_get_instance_test(self):
        self.assertIsInstance(
            Adapter.get_instance(
                {
                    'kind': Adapter.kinds_builtin[0],
                    'apiVersion': 'test/test'
                }
            ).api, K8sClientMock)

    def test_get_instance_builtin(self):
        self.assertIsInstance(
            Adapter.get_instance(
                {
                    'kind': Adapter.kinds_builtin[0],
                    'apiVersion': 'apps/v1'
                }
            ), AdapterBuiltinKind)

    def test_get_instance_negative(self):
        self.assertIsNone(
            Adapter.get_instance(
                {
                    'kind': Adapter.kinds_builtin[0],
                    'apiVersion': 'unknown'
                }
            )
        )


class TestAdapterCustomKind(unittest.TestCase):
    @staticmethod
    def _resources_api_mock():
        return ResourcesAPIMock(
            'version',
            'group/version',
            [V1APIResource(None, 'group', 'kind', 'kinds', True, [], 'kind', [], verbs=[])]
        )

    def test_initialization_positive(self):
        adapter = Adapter.get_instance(
            {
                'kind': 'kind',
                'apiVersion': 'group/version',
                'metadata': {
                    "namespace": 'test_namespace'
                }
            }, CustomObjectsAPIMock(), TestAdapterCustomKind._resources_api_mock()
        )
        self.assertEqual(adapter.kind, 'kind')
        self.assertEqual(adapter.namespace, 'test_namespace')
        self.assertEqual(adapter.group, 'group')
        self.assertEqual(adapter.version, 'version')
        self.assertEqual(adapter.plural, 'kinds')
        self.assertIsInstance(adapter.api, CustomObjectsAPIMock)

    def test_initialization_kind_missing(self):
        adapter = Adapter.get_instance({}, CustomObjectsAPIMock(), TestAdapterCustomKind._resources_api_mock())
        self.assertFalse(adapter.kind)
        self.assertFalse(adapter.plural)

    def test_initialization_api_version_invalid(self):
        adapter = Adapter.get_instance({}, CustomObjectsAPIMock(), TestAdapterCustomKind._resources_api_mock())
        self.assertFalse(adapter.group)
        self.assertFalse(adapter.version)

        adapter = Adapter.get_instance(
            {'apiVersion': 'noslash'},
            CustomObjectsAPIMock(),
            TestAdapterCustomKind._resources_api_mock()
        )
        self.assertFalse(adapter.group)
        self.assertFalse(adapter.version)

        adapter = Adapter.get_instance(
            {'apiVersion': 'domain/version/something'},
            CustomObjectsAPIMock(),
            ResourcesAPIMock()
        )
        self.assertEqual(adapter.group, 'domain')
        self.assertEqual(adapter.version, 'version/something')
