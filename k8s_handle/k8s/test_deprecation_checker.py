import unittest

from k8s_handle.k8s.deprecation_checker import ApiDeprecationChecker


class TestApiDeprecationChecker(unittest.TestCase):

    def test_version_not_in_list(self):
        checker = ApiDeprecationChecker("1.9.7")
        checker.deprecated_versions = {
            "test/v1": {
                "Deployment": {
                    "since": "1.8.0",
                    "until": "1.10.0",
                },
            }
        }
        self.assertFalse(checker._is_deprecated("test/v2", "Deployment"))

    def test_kind_not_in_list(self):
        checker = ApiDeprecationChecker("1.9.7")
        checker.deprecated_versions = {
            "test/v1": {
                "Deployment": {
                    "since": "1.8.0",
                    "until": "1.10.0",
                },
            }
        }
        self.assertFalse(checker._is_deprecated("test/v1", "StatefulSet"))

    def test_version_not_deprecated_yet(self):
        checker = ApiDeprecationChecker("1.7.9")
        checker.deprecated_versions = {
            "test/v1": {
                "Deployment": {
                    "since": "1.8.0",
                    "until": "1.10.0",
                },
            }
        }
        self.assertFalse(checker._is_deprecated("test/v1", "Deployment"))

    def test_version_is_deprecated_equal(self):
        checker = ApiDeprecationChecker("1.8.0")
        checker.deprecated_versions = {
            "test/v1": {
                "Deployment": {
                    "since": "1.8.0",
                    "until": "1.10.0",
                },
            }
        }
        self.assertTrue(checker._is_deprecated("test/v1", "Deployment"))

    def test_version_is_deprecated(self):
        checker = ApiDeprecationChecker("1.9.9")
        checker.deprecated_versions = {
            "test/v1": {
                "Deployment": {
                    "since": "1.8.0",
                    "until": "1.10.0",
                },
            }
        }
        self.assertTrue(checker._is_deprecated("test/v1", "Deployment"))

    def test_version_is_unsupported_equal(self):
        checker = ApiDeprecationChecker("1.10.0")
        checker.deprecated_versions = {
            "test/v1": {
                "Deployment": {
                    "since": "1.8.0",
                    "until": "1.10.0",
                },
            }
        }
        self.assertTrue(checker._is_deprecated("test/v1", "Deployment"))

    def test_version_is_unsupported(self):
        checker = ApiDeprecationChecker("1.10.6")
        checker.deprecated_versions = {
            "test/v1": {
                "Deployment": {
                    "since": "1.8.0",
                    "until": "1.10.0",
                },
            }
        }
        self.assertTrue(checker._is_deprecated("test/v1", "Deployment"))

    def test_version_no_until(self):
        checker = ApiDeprecationChecker("1.10.6")
        checker.deprecated_versions = {
            "test/v1": {
                "Deployment": {
                    "since": "1.8.0",
                    "until": "",
                },
            }
        }
        self.assertTrue(checker._is_deprecated("test/v1", "Deployment"))
