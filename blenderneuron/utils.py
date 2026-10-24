def serialize(obj):
    """Serialize supported values as a shallow, deep-tree-safe JSON table."""
    import json

    nodes = []
    pending = []
    container_types = (dict, list, tuple)
    scalar_types = (str, int, float, bool, type(None))

    def reserve(value):
        index = len(nodes)
        nodes.append(None)
        pending.append((index, value))
        return index

    if isinstance(obj, container_types):
        root = [reserve(obj)]
    elif isinstance(obj, scalar_types):
        root = obj
    else:
        raise TypeError("Unsupported type: %s" % type(obj))

    while pending:
        index, value = pending.pop()
        if isinstance(value, dict):
            values = []
            references = []
            for key, item in value.items():
                # Container keys could not be reconstructed as hashable values
                # after tuples become lists, so they have never round-tripped.
                if not isinstance(key, scalar_types):
                    raise TypeError("Unsupported dict key type: %s" % type(key))
                values.append(key)
                values.append(item)
                if isinstance(item, container_types):
                    values[-1] = reserve(item)
                    references.append(len(values) - 1)
                elif not isinstance(item, scalar_types):
                    raise TypeError("Unsupported type: %s" % type(item))
            node = [0, values, references]
        else:
            # Make one fast C-level copy, then visit only to locate nested
            # containers. The decoder can reuse this list directly.
            values = list(value)
            references = []
            for item_index, item in enumerate(values):
                if isinstance(item, container_types):
                    values[item_index] = reserve(item)
                    references.append(item_index)
                elif not isinstance(item, scalar_types):
                    raise TypeError("Unsupported type: %s" % type(item))
            node = [1, values, references]
        nodes[index] = node

    envelope = {
        "__blenderneuron_flat__": 2,
        "root": root,
        "nodes": nodes,
    }
    return json.dumps(envelope, ensure_ascii=False, separators=(',', ':'))


def deserialize(input_str):
    """Deserialize the transport format without using Python recursion.

    Current peers encode containers in a shallow table, so the standard
    library's fast C decoder is safe at every morphology depth. Reconstruction
    is iterative. A direct scanner remains available for legacy payloads that
    predate the table format.
    """
    import json

    try:
        decoded = json.loads(input_str)
    except (ValueError, RecursionError):
        # Old peers emitted Python-style strings/names, and json.loads rejects
        # extreme nesting before overflowing Python's call stack. The scanner
        # below handles both cases iteratively.
        decoded = None

    if (isinstance(decoded, dict)
            and decoded.get("__blenderneuron_flat__") == 2
            and set(decoded) == {"__blenderneuron_flat__", "root", "nodes"}):
        encoded_nodes = decoded["nodes"]
        # List payloads are already decoded into exactly the objects the caller
        # needs. Reuse them instead of copying every scalar in Python.
        containers = [({} if node[0] == 0 else node[1]) for node in encoded_nodes]

        def resolve(value):
            return containers[value[0]] if isinstance(value, list) else value

        for index, node in enumerate(encoded_nodes):
            values = node[1]
            for reference_index in node[2]:
                values[reference_index] = containers[values[reference_index]]
            container = containers[index]
            if node[0] == 0:
                iterator = iter(values)
                container.update(zip(iterator, iterator))
        return resolve(decoded["root"])

    if (isinstance(decoded, dict)
            and decoded.get("__blenderneuron_flat__") == 1
            and set(decoded) == {"__blenderneuron_flat__", "root", "nodes"}):
        encoded_nodes = decoded["nodes"]
        containers = [({} if node[0] == 0 else []) for node in encoded_nodes]

        def resolve_v1(value):
            return containers[value[0]] if isinstance(value, list) else value

        for index, node in enumerate(encoded_nodes):
            container = containers[index]
            if node[0] == 0:
                for item_index in range(1, len(node), 2):
                    container[resolve_v1(node[item_index])] = resolve_v1(
                        node[item_index + 1])
            else:
                container.extend(resolve_v1(value) for value in node[1:])
        return resolve_v1(decoded["root"])

    if decoded is not None:
        return decoded

    length = len(input_str)
    pos = 0
    stack = []
    result = None
    have_result = False

    # Container states. Lists use 0=value/end and 1=comma/end. Dicts use
    # 0=key/end, 1=colon, 2=value, and 3=comma/end.
    def invalid(position):
        snippet = input_str[position:position + 40]
        raise ValueError(
            "Invalid token at position %d: '%s'" % (position, snippet))

    def add_value(value):
        nonlocal result, have_result
        if not stack:
            if have_result:
                invalid(pos)
            result = value
            have_result = True
            return

        frame = stack[-1]
        if frame[0] == 'list':
            frame[1].append(value)
            frame[2] = 1
        elif frame[2] == 0:
            # Dict keys are scalar in the supported wire format.
            try:
                hash(value)
            except TypeError:
                invalid(pos)
            frame[3] = value
            frame[2] = 1
        else:
            frame[1][frame[3]] = value
            frame[3] = None
            frame[2] = 3

    def parse_string(start):
        quote = input_str[start]
        index = start + 1
        chunk_start = index
        pieces = None
        escapes = {
            'a': '\a', 'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r',
            't': '\t', 'v': '\v', '\\': '\\', "'": "'", '"': '"',
        }

        while index < length:
            char = input_str[index]
            if char == quote:
                if pieces is None:
                    return input_str[chunk_start:index], index + 1
                pieces.append(input_str[chunk_start:index])
                return ''.join(pieces), index + 1
            if char != '\\':
                index += 1
                continue

            if pieces is None:
                pieces = []
            pieces.append(input_str[chunk_start:index])
            index += 1
            if index >= length:
                invalid(index - 1)
            escape = input_str[index]
            if escape in escapes:
                pieces.append(escapes[escape])
                index += 1
            elif escape in ('x', 'u', 'U'):
                digits = {'x': 2, 'u': 4, 'U': 8}[escape]
                end = index + 1 + digits
                if end > length:
                    invalid(index - 1)
                try:
                    pieces.append(chr(int(input_str[index + 1:end], 16)))
                except (ValueError, OverflowError):
                    invalid(index - 1)
                index = end
            else:
                # Match unicode_escape's historical treatment of unknown
                # escapes while retaining the backslash.
                pieces.append('\\' + escape)
                index += 1
            chunk_start = index

        invalid(start)

    while True:
        while pos < length and input_str[pos].isspace():
            pos += 1

        if have_result and not stack:
            if pos == length:
                return result
            invalid(pos)
        if pos == length:
            break

        if stack:
            frame = stack[-1]
            char = input_str[pos]
            if frame[0] == 'list' and frame[2] == 1:
                if char == ',':
                    frame[2] = 0
                    pos += 1
                    continue
                if char == frame[3]:
                    stack.pop()
                    pos += 1
                    continue
                invalid(pos)
            if frame[0] == 'dict':
                if frame[2] == 1:
                    if char != ':':
                        invalid(pos)
                    frame[2] = 2
                    pos += 1
                    continue
                if frame[2] == 3:
                    if char == ',':
                        frame[2] = 0
                        pos += 1
                        continue
                    if char == '}':
                        stack.pop()
                        pos += 1
                        continue
                    invalid(pos)
            # Empty containers (and trailing commas, accepted historically).
            if frame[2] == 0 and char == frame[3 if frame[0] == 'list' else 4]:
                stack.pop()
                pos += 1
                continue

        char = input_str[pos]
        if char == '{':
            value = {}
            add_value(value)
            stack.append(['dict', value, 0, None, '}'])
            pos += 1
        elif char == '[' or char == '(':
            value = []
            add_value(value)
            stack.append(['list', value, 0, ']' if char == '[' else ')'])
            pos += 1
        elif char == "'" or char == '"':
            value, pos = parse_string(pos)
            add_value(value)
        elif char == 'T' and input_str.startswith('True', pos):
            add_value(True)
            pos += 4
        elif char == 'F' and input_str.startswith('False', pos):
            add_value(False)
            pos += 5
        elif char == 'N' and input_str.startswith('None', pos):
            add_value(None)
            pos += 4
        elif char == 't' and input_str.startswith('true', pos):
            add_value(True)
            pos += 4
        elif char == 'f' and input_str.startswith('false', pos):
            add_value(False)
            pos += 5
        elif char == 'n' and input_str.startswith('null', pos):
            add_value(None)
            pos += 4
        elif char == '-' or char.isdigit():
            start = pos
            if char == '-':
                pos += 1
            digits_start = pos
            while pos < length and input_str[pos].isdigit():
                pos += 1
            if pos == digits_start:
                invalid(start)
            is_float = False
            if pos < length and input_str[pos] == '.':
                is_float = True
                pos += 1
                while pos < length and input_str[pos].isdigit():
                    pos += 1
            if pos < length and input_str[pos] in 'eE':
                is_float = True
                pos += 1
                if pos < length and input_str[pos] in '+-':
                    pos += 1
                exponent_start = pos
                while pos < length and input_str[pos].isdigit():
                    pos += 1
                if pos == exponent_start:
                    invalid(start)
            text = input_str[start:pos]
            add_value(float(text) if is_float else int(text))
        else:
            invalid(pos)

    raise ValueError("Invalid input string for deserialization.")
