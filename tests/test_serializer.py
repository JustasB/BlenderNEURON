import copy
import json
import unittest

from blenderneuron.utils import serialize, deserialize


class TestSerialization(unittest.TestCase):
    def test_current_format_values_and_reusable_tables(self):
        for value in [None, True, False, 0, -1.25e-6, "α's \\ branch", [], {},
                      {"empty": {}, "list": [[]]},
                      {"__blenderneuron_flat__": 99, "root": 0, "nodes": []},
                      {None: "none", 2: "integer", 1.25: "float"}]:
            with self.subTest(value=value):
                payload = serialize(value)
                table = json.loads(payload)
                before = copy.deepcopy(table)
                self.assertEqual(deserialize(payload), value)
                self.assertEqual(deserialize(table), value)
                self.assertEqual(deserialize(table), value)
                self.assertEqual(table, before)

    def test_reject_legacy_and_unversioned_payloads(self):
        for payload in ["{'key': True}", "(1, 2)", "[True, False, None]",
                        "null", "[]", "{}", "[1, 2}", "", "{} trailing",
                        json.dumps({"__blenderneuron_flat__": 1, "root": [0],
                                    "nodes": [[1, 1, 2]]}),
                        json.dumps({"__blenderneuron_flat__": 99, "root": 0,
                                    "nodes": []}),
                        json.dumps({"__blenderneuron_flat__": 2, "root": 0,
                                    "nodes": [], "extra": 1})]:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    deserialize(payload)

    def test_serialize_list(self):
        data = [1, 2, 3]
        result = serialize(data)
        self.assertEqual(deserialize(result), data)
        self.assertEqual(json.loads(result)["nodes"], [[1, [1, 2, 3], []]])

    def test_serialize_scalar_root(self):
        self.assertEqual(deserialize(serialize("soma")), "soma")

    def test_serialize_tuple(self):
        data = (1, 2, 3)
        result = serialize(data)
        self.assertEqual(deserialize(result), list(data))

    def test_serialize_unsupported_type(self):
        class Unsupported:
            pass

        with self.assertRaises(TypeError):
            serialize(Unsupported())

        with self.assertRaises(TypeError):
            serialize({"value": Unsupported()})

        with self.assertRaises(TypeError):
            serialize([Unsupported()])

        with self.assertRaises(TypeError):
            serialize({("tuple", "key"): "value"})

    def test_round_trip_deep_morphology_without_python_recursion(self):
        """The transport must support arbitrarily deep single-child trees."""
        depth = 5000
        source = {
            "name": "root",
            "enabled": True,
            "disabled": False,
            "optional": None,
            "offset": -1.25e-6,
            "children": [],
        }
        node = source
        for index in range(depth):
            child = {"name": "section-%d" % index, "children": []}
            node["children"].append(child)
            node = child

        restored = deserialize(serialize(source))
        # The wire representation itself stays shallow enough for native JSON,
        # even though the restored morphology is thousands of levels deep.
        json.loads(serialize(source))
        node = restored
        for index in range(depth):
            self.assertEqual(node["name"], "root" if index == 0 else "section-%d" % (index - 1))
            self.assertEqual(len(node["children"]), 1)
            node = node["children"][0]
        self.assertEqual(node["name"], "section-%d" % (depth - 1))
        self.assertEqual(node["children"], [])


if __name__ == "__main__":
    unittest.main()
