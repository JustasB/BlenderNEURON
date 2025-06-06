def serialize(obj):
    result = []
    stack = []

    # Start by pushing the initial object onto the stack
    stack.append(('value', obj))

    while stack:
        frame = stack.pop()
        frame_type = frame[0]

        if frame_type == 'value':
            obj = frame[1]

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
                # Always use single quotes and escape single quotes in the string
                escaped_str = obj.replace('\\', '\\\\').replace("'", "\\'")
                result.append(f"'{escaped_str}'")

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
                stack.append(('value', item))
            # No else needed

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
                stack.append(('value', value))
                # Append colon and space after key and before value
                stack.append(('literal', ': '))
                stack.append(('value', key))
            # No else needed

        elif frame_type == 'end':
            closing_char = frame[1]
            result.append(closing_char)

        elif frame_type == 'literal':
            text = frame[1]
            result.append(text)

    return ''.join(result)


def deserialize(input_str):
    import re

    token_spec = r"""
        (?P<lbrace>\{) |
        (?P<rbrace>\}) |
        (?P<lbracket>\[) |
        (?P<rbracket>\]) |
        (?P<lparen>\() |
        (?P<rparen>\)) |
        (?P<colon>:) |
        (?P<comma>,) |
        (?P<string>'([^'\\]*(?:\\.[^'\\]*)*)' |
                  "([^"\\]*(?:\\.[^"\\]*)*)") |
        (?P<number>-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?) |
        (?P<name>True|False|None)
    """

    master_pattern = re.compile(
        r'\s*(?:' + token_spec + r')', re.VERBOSE)

    tokens = master_pattern.finditer(input_str)

    stack = []
    current = None
    key = None
    expecting_key = False

    tokens_consumed = False  # Flag to check if any tokens were consumed
    pos = 0  # Position in the input string

    for token in tokens:
        if token.start() != pos:
            # There's invalid or unrecognized text in the input
            raise ValueError(f"Invalid token at position {pos}: '{input_str[pos:token.start()]}'")
        tokens_consumed = True
        pos = token.end()
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

        elif kind == 'lbracket' or kind == 'lparen':
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
            if kind == 'lparen':
                # Mark that this list should be converted to a tuple on close
                stack.append(('tuple', obj))

        elif kind == 'rbrace' or kind == 'rbracket' or kind == 'rparen':
            finished = current
            if stack and stack[-1][0] == 'tuple' and stack[-1][1] is finished:
                # Closing a tuple; convert the accumulated list
                stack.pop()  # remove tuple marker
                finished = tuple(finished)
                if not stack:
                    current = finished
                    break
                parent, key, expecting_key = stack.pop()
                if isinstance(parent, dict):
                    parent[key] = finished
                    key = None
                elif isinstance(parent, list):
                    parent[-1] = finished
                current = parent
            else:
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
            # Correctly handle escape sequences and Unicode characters
            import codecs
            str_value = value[1:-1].encode('utf-8').decode('unicode_escape')
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
            num_value = float(value) if ('.' in value or 'e' in value or 'E' in value) else int(value)
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

        else:
            # If an unknown token is encountered
            raise ValueError(f"Unknown token: {value}")

    # Consume any trailing whitespace
    remaining_input = input_str[pos:].strip()
    if remaining_input:
        raise ValueError(f"Invalid token at position {pos}: '{remaining_input}'")

    if not tokens_consumed or current is None or stack:
        raise ValueError("Invalid input string for deserialization.")

    return current

