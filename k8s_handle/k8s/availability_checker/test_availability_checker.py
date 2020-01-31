from unittest import TestCase

from .checker import ResourceAvailabilityChecker
from .resource_getters import CoreResourceGetter, RegularResourceGetter
from .mocks import MockResource

from k8s_handle.k8s.mocks import ResourcesAPIMock
from k8s_handle.exceptions import ResourceNotAvailableError


class TestAvailabilityChecker(TestCase):

    def setUp(self):
        core_getter = CoreResourceGetter(
            ResourcesAPIMock(group_version="v1", resources=[MockResource("Pod"), MockResource("CronJob")])
        )

        regular_getter = RegularResourceGetter(
            ResourcesAPIMock(group_version="app/v1", resources=[MockResource("Deployment"), MockResource("Service")])
        )

        self.checker = ResourceAvailabilityChecker([core_getter, regular_getter])

    def test_is_available_kind(self):
        self.assertTrue(self.checker._is_available_kind("v1", "Pod"))
        self.assertTrue(self.checker._is_available_kind("app/v1", "Service"))
        self.assertFalse(self.checker._is_available_kind("v1", "Deployment"))
        self.assertFalse(self.checker._is_available_kind("app/v1", "CronJob"))

    def test_run_with_valid_version(self):
        self.checker.run('k8s_handle/k8s/fixtures/valid_version.yaml')

    def test_run_with_invalid_version(self):
        with self.assertRaises(ResourceNotAvailableError):
            self.checker.run('k8s_handle/k8s/fixtures/invalid_version.yaml')

    def test_run_with_unsupported_version(self):
        with self.assertRaises(ResourceNotAvailableError):
            self.checker.run('k8s_handle/k8s/fixtures/unsupported_version.yaml')
