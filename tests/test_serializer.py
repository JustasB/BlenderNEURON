import unittest
import json

from blenderneuron.utils import serialize, deserialize


class TestSerialization(unittest.TestCase):

    def test_legacy_scanner_literals_and_numbers(self):
        # A tuple forces the legacy scanner even for otherwise valid JSON
        # tokens. Exercise compatibility with both generations of peers.
        payload = "(true, false, null, True, False, None, -12, 1.25, -2.5e+3, 4E-2,)"
        self.assertEqual(deserialize(payload),
                         [True, False, None, True, False, None, -12, 1.25, -2500., .04])
        self.assertEqual(deserialize("  ({'items': [], 'empty': {},}, (),)  "),
                         [{'items': [], 'empty': {}}, []])
        self.assertEqual(deserialize("{'a': 1, 'b': 2}"), {'a': 1, 'b': 2})

    def test_legacy_scanner_escape_boundaries(self):
        self.assertEqual(deserialize(r"'\a\b\f\n\r\t\v\\\'\"'"),
                         '\a\b\f\n\r\t\v\\\'"')
        for payload in ["'unterminated", "'trailing\\", r"'\x1'", r"'\uZZZZ'",
                        r"'\U00110000'", "{'a': 1 'b': 2}", "{[]: 1}",
                        "(-,)", "(1e,)", "(1e+,)", "(1e-,)", "(1 2)",
                        "(1,]", "{'a':}", "", "   "]:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    deserialize(payload)

    def test_flat_transport_empty_and_nested_values(self):
        for version, nodes in [
                (1, [[0, 'empty', [1], 'list', [2]], [0], [1, [3]], [1]]),
                (2, [[0, ['empty', 1, 'list', 2], [1, 3]], [0, [], []],
                     [1, [3], [0]], [1, [], []]])]:
            with self.subTest(version=version):
                self.assertEqual(deserialize(json.dumps({
                    '__blenderneuron_flat__': version, 'root': [0], 'nodes': nodes})),
                    {'empty': {}, 'list': [[]]})
        # Similar-looking ordinary dictionaries must not be interpreted as
        # envelopes, nor should scalar/empty roots need a node table entry.
        for value in [None, True, False, 0, 1.25, [], {},
                      {'__blenderneuron_flat__': 99, 'root': 0, 'nodes': []},
                      {'__blenderneuron_flat__': 2, 'root': 0, 'nodes': [], 'extra': 1}]:
            with self.subTest(value=value):
                self.assertEqual(deserialize(serialize(value)), value)
                self.assertEqual(deserialize(json.dumps(value)), value)

    def test_serialize_list(self):
        data = [1, 2, 3]
        result = serialize(data)
        self.assertEqual(deserialize(result), data)
        self.assertEqual(json.loads(result)["nodes"], [[1, [1, 2, 3], []]])

    def test_deserialize_v1_flat_transport(self):
        data = {
            "__blenderneuron_flat__": 1,
            "root": [0],
            "nodes": [[0, "children", [1]], [1, 1, 2, 3]],
        }
        self.assertEqual(deserialize(json.dumps(data)), {"children": [1, 2, 3]})

        scalar_data = {
            "__blenderneuron_flat__": 1,
            "root": "scalar",
            "nodes": [],
        }
        self.assertEqual(deserialize(json.dumps(scalar_data)), "scalar")

    def test_serialize_scalar_root(self):
        self.assertEqual(deserialize(serialize("soma")), "soma")

    def test_serialize_tuple(self):
        data = (1, 2, 3)
        result = serialize(data)
        self.assertEqual(deserialize(result), list(data))

    def test_serialize_unsupported_type(self):
        # Test for line 52: raise TypeError(f"Unsupported type: {type(obj)}")
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





    def test_deserialize_dict(self):
        # Test for deserialization of a dictionary
        data = "{'key': 'value'}"
        result = deserialize(data)
        expected = {'key': 'value'}
        self.assertEqual(result, expected)


    #### Test the `lbracket` token (list):
    def test_deserialize_list(self):
        # Test for deserialization of a list
        data = "[1, 2, 3]"
        result = deserialize(data)
        expected = [1, 2, 3]
        self.assertEqual(result, expected)


    #### Test unsupported tokens:
    def test_deserialize_invalid(self):
        # Test for invalid token raising ValueError
        data = "{key: value}"
        with self.assertRaises(ValueError):
            deserialize(data)

    def test_invalid_token_position(self):
        # Test for lines 129-131: raise ValueError for unrecognized text
        invalid_input = "{'key': value}"  # Invalid token 'value' (unquoted string)
        with self.assertRaises(ValueError) as context:
            deserialize(invalid_input)
        self.assertIn("Invalid token at position", str(context.exception))

    def test_deserialize_lbrace_dict(self):
        # Test for line 138-139: kind == 'lbrace' and obj = {}
        data = "{'key': 'value'}"
        result = deserialize(data)
        expected = {'key': 'value'}
        self.assertEqual(result, expected)

    def test_deserialize_lbracket_list(self):
        # Test for lines 150-157: kind == 'lbracket' or 'lparen'
        data = "[1, 2, 3]"
        result = deserialize(data)
        expected = [1, 2, 3]
        self.assertEqual(result, expected)

    def test_deserialize_list_append(self):
        # Test for lines 156-157: current.append(obj)
        data = "[1, [2, 3]]"
        result = deserialize(data)
        expected = [1, [2, 3]]
        self.assertEqual(result, expected)

    def test_deserialize_string_escape(self):
        # Test for lines 175-178: escape sequences in string
        data = "'Hello\\nWorld'"
        result = deserialize(data)
        expected = "Hello\nWorld"
        self.assertEqual(result, expected)

    def test_deserialize_unicode_and_escaped_quotes(self):
        source = {"label": "dendrite α's \\ branch", "children": []}
        self.assertEqual(deserialize(serialize(source)), source)

    def test_deserialize_legacy_unicode_and_unknown_escapes(self):
        data = r"['\x41','\u03b1','\U0001F600','\q']"
        self.assertEqual(deserialize(data), ['A', 'α', '😀', '\\q'])

    def test_deserialize_rejects_incomplete_and_mismatched_containers(self):
        invalid_values = [
            "{'key': 'value'",
            "[1, 2}",
            "{'key' 'value'}",
            "[1 2]",
        ]
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    deserialize(value)

    def test_deserialize_list_append_string(self):
        # Test for line 185: current.append(str_value)
        data = "['Hello', 'World']"
        result = deserialize(data)
        expected = ['Hello', 'World']
        self.assertEqual(result, expected)

    def test_deserialize_string_value(self):
        # Test for line 187: current = str_value
        data = "'Hello'"
        result = deserialize(data)
        expected = "Hello"
        self.assertEqual(result, expected)

    def test_deserialize_number_float(self):
        # Test for lines 190-197: num_value (float) and list append
        data = "[1.23, 4.56]"
        result = deserialize(data)
        expected = [1.23, 4.56]
        self.assertEqual(result, expected)

    def test_deserialize_number_assignment(self):
        # Test for line 197: current = num_value
        data = "123"
        result = deserialize(data)
        expected = 123
        self.assertEqual(result, expected)

    def test_deserialize_name_value(self):
        # Test for lines 205-207: current = name_value (True, False, None)
        data = "[True, False, None]"
        result = deserialize(data)
        expected = [True, False, None]
        self.assertEqual(result, expected)

    def test_unknown_token(self):
        # Test for lines 210-211: raise ValueError for unknown token
        data = "{'key': @value}"  # Invalid token '@'
        with self.assertRaises(ValueError) as context:
            deserialize(data)
        self.assertIn("Invalid token", str(context.exception))

    def test_remaining_input(self):
        # Test for lines 215-216: raise ValueError for remaining input
        data = "{'key': 'value'} extra_text"
        with self.assertRaises(ValueError) as context:
            deserialize(data)
        self.assertIn("Invalid token at position", str(context.exception))

    # def test_incomplete_deserialization(self):
    #     # Test for lines 218-219: raise ValueError for incomplete deserialization
    #     data = "{'key': 'value'"
    #     with self.assertRaises(ValueError) as context:
    #         deserialize(data)
    #     self.assertIn("Invalid input string for deserialization", str(context.exception))


if __name__ == '__main__':
    unittest.main()
