import unittest

from k8s_handle import dictionary


class TestDictionaryMerge(unittest.TestCase):
    def test_dictionary_merge(self):
        dictionary_x = {
            "0": "",
            1: [0, 1, 2],
            2: {"inflated_key_0": "inflated_value_0"},
            3: {0, 1}
        }

        dictionary_y = {
            "0": "override_0",
            1: ["value_0", "value_1", "value_2"],
            2: {"inflated_key_1": "inflated_value_1"},
            3: "override_1",
        }

        assert dictionary.merge(dictionary_x, dictionary_y) == {
            "0": "override_0",
            1: ["value_0", "value_1", "value_2"],
            2:
                {
                    "inflated_key_0": "inflated_value_0",
                    "inflated_key_1": "inflated_value_1"
                },
            3: "override_1"
        }
