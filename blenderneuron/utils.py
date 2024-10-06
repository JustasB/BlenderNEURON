def serialize(obj):
    result = []
    stack = []

    # Start by pushing the initial object onto the stack
    # The initial 'in_container' is False, because we're at the top level
    stack.append(('value', obj, False))

    while stack:
        frame = stack.pop()
        frame_type = frame[0]

        if frame_type == 'value':
            obj = frame[1]
            in_container = frame[2]

            if isinstance(obj, dict):
                # Append opening brace
                result.append('{')
                # Push closing brace onto stack
                stack.append(('end', '}'))
                # Get the items as a list to process them in order
                items = list(obj.items())
                # Reverse the items to process them in order when popping
                items.reverse()
                # Push a 'dict' frame onto the stack
                stack.append(('dict', items, True))  # first = True

            elif isinstance(obj, (list, tuple)):
                # Append opening bracket or parenthesis
                if isinstance(obj, list):
                    result.append('[')
                    closing = ']'
                else:
                    result.append('(')
                    closing = ')'
                # Push closing bracket onto stack
                stack.append(('end', closing))
                # Reverse the items to process them in order when popping
                items = list(obj)
                items.reverse()
                # Push a 'list' frame onto the stack
                stack.append(('list', items, True))  # first = True

            elif isinstance(obj, str):
                if in_container:
                    # Include quotes and escape any single quotes in the string
                    escaped_str = obj.replace("'", "\\'")
                    result.append(f"'{escaped_str}'")
                else:
                    result.append(obj)

            elif isinstance(obj, (int, float, bool, type(None))):
                result.append(str(obj))

            else:
                raise TypeError(f"Unsupported type: {type(obj)}")

        elif frame_type == 'list':
            items = frame[1]
            first = frame[2]
            if items:
                item = items.pop()
                # Push this frame back onto the stack
                stack.append(('list', items, False))
                # If not first, append comma
                if not first:
                    result.append(', ')
                # Push the item onto the stack as a 'value' frame
                stack.append(('value', item, True))  # in_container=True
            # No else needed; when items are exhausted, control passes to 'end' frame

        elif frame_type == 'dict':
            items = frame[1]
            first = frame[2]
            if items:
                key, value = items.pop()
                # Push this frame back onto the stack
                stack.append(('dict', items, False))
                # If not first, append comma
                if not first:
                    result.append(', ')
                # Push value and key onto the stack
                # Push value first, so it's processed after key
                stack.append(('value', value, True))  # in_container=True
                # Append colon and space after key and before value
                stack.append(('literal', ': '))
                stack.append(('value', key, True))  # in_container=True
            # No else needed; when items are exhausted, control passes to 'end' frame

        elif frame_type == 'end':
            closing_char = frame[1]
            result.append(closing_char)

        elif frame_type == 'literal':
            text = frame[1]
            result.append(text)

    return ''.join(result)



def deserialize(input_str):
    import re

    tokens = re.finditer(r"""
        \s*(?:
            (?P<lbrace>\{) |
            (?P<rbrace>\}) |
            (?P<lbracket>\[) |
            (?P<rbracket>\]) |
            (?P<colon>:) |
            (?P<comma>,) |
            (?P<string>'([^'\\]*(?:\\.[^'\\]*)*)' |
                      "([^"\\]*(?:\\.[^"\\]*)*)") |
            (?P<number>-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?) |
            (?P<name>True|False|None)
        )
    """, input_str, re.VERBOSE)

    stack = []
    current = None
    key = None
    expecting_key = False

    for token in tokens:
        kind = token.lastgroup
        value = token.group(token.lastgroup)

        if kind == 'lbrace':
            obj = {}
            if current is not None:
                stack.append((current, key, expecting_key))
                if isinstance(current, dict):
                    current[key] = obj
                    key = None  # Reset key after use
                elif isinstance(current, list):
                    current.append(obj)
            current = obj
            expecting_key = True

        elif kind == 'lbracket':
            obj = []
            if current is not None:
                stack.append((current, key, expecting_key))
                if isinstance(current, dict):
                    current[key] = obj
                    key = None  # Reset key after use
                elif isinstance(current, list):
                    current.append(obj)
            current = obj
            expecting_key = False

        elif kind == 'rbrace' or kind == 'rbracket':
            if not stack:
                break
            current, key, expecting_key = stack.pop()

        elif kind == 'colon':
            expecting_key = False

        elif kind == 'comma':
            if isinstance(current, dict):
                expecting_key = True
                key = None

        elif kind == 'string':
            str_value = value[1:-1].encode().decode('unicode_escape')
            if isinstance(current, dict):
                if expecting_key:
                    key = str_value
                else:
                    current[key] = str_value
                    key = None  # Reset key after use
            elif isinstance(current, list):
                current.append(str_value)
            else:
                current = str_value

        elif kind == 'number':
            num_value = float(value) if '.' in value or 'e' in value or 'E' in value else int(value)
            if isinstance(current, dict):
                current[key] = num_value
                key = None  # Reset key after use
            elif isinstance(current, list):
                current.append(num_value)
            else:
                current = num_value

        elif kind == 'name':
            name_value = {'True': True, 'False': False, 'None': None}[value]
            if isinstance(current, dict):
                current[key] = name_value
                key = None  # Reset key after use
            elif isinstance(current, list):
                current.append(name_value)
            else:
                current = name_value

    return current


