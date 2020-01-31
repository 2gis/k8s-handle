from unittest import TestCase

from k8s_handle.k8s.mocks import ResourcesAPIMock

from .resource_getters import CoreResourceGetter, RegularResourceGetter
from .mocks import MockResource


class TestCoreResourceGetter(TestCase):

    def setUp(self):
        self.getter = CoreResourceGetter(
            ResourcesAPIMock(group_version="v1", resources=[MockResource("Pod"), MockResource("CronJob")])
        )

    def test_is_processable_version(self):
        self.assertTrue(self.getter.is_processable_version("v1"))
        self.assertFalse(self.getter.is_processable_version("app/v1"))
        self.assertFalse(self.getter.is_processable_version("/"))
        self.assertFalse(self.getter.is_processable_version(""))

    def test_get_resources_by_version(self):
        self.assertSetEqual({"Pod", "CronJob"}, self.getter.get_resources_by_version("v1"))
        self.assertSetEqual(set(), self.getter.get_resources_by_version("v2"))


class TestRegularResourceGetter(TestCase):

    def setUp(self):
        self.getter = RegularResourceGetter(
            ResourcesAPIMock(group_version="app/v1", resources=[MockResource("Pod"), MockResource("CronJob")])
        )

    def test_is_processable_version(self):
        self.assertFalse(self.getter.is_processable_version("v1"))
        self.assertTrue(self.getter.is_processable_version("app/betav1"))
        self.assertTrue(self.getter.is_processable_version("app/v1"))
        self.assertFalse(self.getter.is_processable_version("/"))
        self.assertFalse(self.getter.is_processable_version(""))

    def test_get_resources_by_version(self):
        self.assertSetEqual({"Pod", "CronJob"}, self.getter.get_resources_by_version("app/v1"))
        self.assertSetEqual(set(), self.getter.get_resources_by_version("app/betav1"))
