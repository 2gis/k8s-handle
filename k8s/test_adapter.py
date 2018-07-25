import unittest
from .resource import Adapter
from .mocks import K8sClientMock

from .resource import ProvisioningError


class TestAdapter(unittest.TestCase):

    def test_get_app_kind(self):
        self.assertEqual(Adapter._get_app_kind('ConfigMap'), 'config_map')
        self.assertEqual(Adapter._get_app_kind('Namespace'), 'namespace')
        self.assertEqual(Adapter._get_app_kind('PodDisruptionBudget'), 'pod_disruption_budget')

    def test_app_kind_invalid(self):
        with self.assertRaises(RuntimeError) as context:
            Adapter(spec={'kind': 'UnknownKind', 'metadata': {'name': 'fail'}, 'spec': {'replicas': 1}})
        self.assertTrue('Unknown kind "UnknownKind" in generated file' in str(context.exception))

    def test_app_get_fail(self):
        deployment = Adapter(
            api=K8sClientMock('fail'),
            spec={'kind': 'Deployment', 'metadata': {'name': 'fail'}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            deployment.get()
        self.assertTrue('Get deployment fail' in str(context.exception))

        storage = Adapter(
            api=K8sClientMock('fail'),
            spec={'kind': 'StorageClass', 'metadata': {'name': 'fail'}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            storage.get()
        self.assertTrue('Get storage class fail' in str(context.exception))

    def test_app_get_not_found(self):
        deployment = Adapter(
            api=K8sClientMock('404'),
            spec={'kind': 'Deployment', 'metadata': {'name': '404'}, 'spec': {'replicas': 1}})
        res = deployment.get()
        self.assertEqual(res, None)

        storage = Adapter(
            api=K8sClientMock('404'),
            spec={'kind': 'StorageClass', 'metadata': {'name': '404'}, 'spec': {'replicas': 1}})
        res = storage.get()
        self.assertEqual(res, None)

    def test_app_get(self):
        deployment = Adapter(
            api=K8sClientMock(),
            spec={'kind': 'Deployment', 'metadata': {'name': 'test'}, 'spec': {'replicas': 1}})
        res = deployment.get()

        self.assertEqual(res.metadata, {'key1': 'value1'})

        storage = Adapter(
            api=K8sClientMock(),
            spec={'kind': 'StorageClass', 'metadata': {'name': 'test'}, 'spec': {'replicas': 1}})
        res = storage.get()

        self.assertEqual(res.metadata, {'key1': 'value1'})

    def test_app_create_fail(self):
        deployment = Adapter(
            api=K8sClientMock('fail'),
            spec={'kind': 'Deployment', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            deployment.create()
        self.assertTrue('Create deployment fail' in str(context.exception))

        storage = Adapter(
            api=K8sClientMock('fail'),
            spec={'kind': 'StorageClass', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            storage.create()
        self.assertTrue('Create storage class fail' in str(context.exception))

    def test_app_create(self):
        deployment = Adapter(
            api=K8sClientMock(''),
            spec={'kind': 'Deployment', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        res = deployment.create()
        self.assertEqual(res, {'key1': 'value1'})

        storage = Adapter(
            api=K8sClientMock(''),
            spec={'kind': 'StorageClass', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        res = storage.create()
        self.assertEqual(res, {'key1': 'value1'})

    def test_app_replace_fail(self):
        deployment = Adapter(
            api=K8sClientMock('fail'),
            spec={'kind': 'Deployment', 'metadata': {'name': 'fail'}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            deployment.replace()
        self.assertTrue('Replace deployment fail' in str(context.exception))

        storage = Adapter(
            api=K8sClientMock('fail'),
            spec={'kind': 'StorageClass', 'metadata': {'name': 'fail'}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            storage.replace()
        self.assertTrue('Replace storage class fail' in str(context.exception))

    def test_app_replace(self):
        deployment = Adapter(
            api=K8sClientMock(''),
            spec={'kind': 'Deployment', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        res = deployment.replace()
        self.assertEqual(res, {'key1': 'value1'})

        storage = Adapter(
            api=K8sClientMock(''),
            spec={'kind': 'StorageClass', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        res = storage.replace()
        self.assertEqual(res, {'key1': 'value1'})

    def test_app_replace_service(self):
        deployment = Adapter(
            api=K8sClientMock(''),
            spec={'kind': 'Service', 'metadata': {'name': ''}, 'spec': {'replicas': 1}})
        res = deployment.replace()
        self.assertEqual(res, {'key1': 'value1'})

    def test_app_delete_fail(self):
        client = Adapter(
            api=K8sClientMock('fail'),
            spec={'kind': 'Deployment', 'metadata': {'name': 'fail'}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            client.delete()
        self.assertTrue('Delete deployment fail' in str(context.exception))

        storage = Adapter(
            api=K8sClientMock('fail'),
            spec={'kind': 'StorageClass', 'metadata': {'name': 'fail'}, 'spec': {'replicas': 1}})
        with self.assertRaises(ProvisioningError) as context:
            storage.delete()
        self.assertTrue('Delete storage class fail' in str(context.exception))

    def test_app_delete_not_found(self):
        client = Adapter(
            api=K8sClientMock('404'),
            spec={'kind': 'Deployment', 'metadata': {'name': '404'}, 'spec': {'replicas': 1}})
        res = client.delete()
        self.assertEqual(res, None)

        storage = Adapter(
            api=K8sClientMock('404'),
            spec={'kind': 'StorageClass', 'metadata': {'name': '404'}, 'spec': {'replicas': 1}})
        res = storage.delete()
        self.assertEqual(res, None)

    def test_app_delete(self):
        client = Adapter(
            api=K8sClientMock(),
            spec={'kind': 'Deployment', 'metadata': {'name': 'test'}, 'spec': {'replicas': 1}})
        res = client.delete()

        self.assertEqual(res, {'key1': 'value1'})

        storage = Adapter(
            api=K8sClientMock(),
            spec={'kind': 'StorageClass', 'metadata': {'name': 'test'}, 'spec': {'replicas': 1}})
        res = storage.delete()

        self.assertEqual(res, {'key1': 'value1'})
