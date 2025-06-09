import unittest

from blenderneuron.utils import serialize, deserialize


class TestSerialization(unittest.TestCase):

    def test_serialize_list(self):
        # Test for line 29: if isinstance(obj, list)
        data = [1, 2, 3]
        result = serialize(data)
        expected = "[1, 2, 3]"
        self.assertEqual(result, expected)

    def test_serialize_tuple(self):
        # Test for line 33: else: result.append('(')
        data = (1, 2, 3)
        result = serialize(data)
        expected = "(1, 2, 3)"
        self.assertEqual(result, expected)

    def test_deserialize_tuple(self):
        data = "(1, 2, 3)"
        result = deserialize(data)
        expected = (1, 2, 3)
        self.assertEqual(result, expected)

    def test_deserialize_empty_tuple(self):
        data = "()"
        result = deserialize(data)
        self.assertEqual(result, ())

    def test_deserialize_nested_tuple(self):
        data = "[1, (2, 3), {'a': (4, 5)}]"
        result = deserialize(data)
        expected = [1, (2, 3), {'a': (4, 5)}]
        self.assertEqual(result, expected)

    def test_deserialize_tuple_of_tuples(self):
        data = "((1, 2), (3, 4))"
        result = deserialize(data)
        expected = ((1, 2), (3, 4))
        self.assertEqual(result, expected)

    def test_serialize_unsupported_type(self):
        # Test for line 52: raise TypeError(f"Unsupported type: {type(obj)}")
        class Unsupported:
            pass

        with self.assertRaises(TypeError):
            serialize(Unsupported())





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
