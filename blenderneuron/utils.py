from blenderneuron.compat import string_types, integer_types

def serialize(obj):
    """Serialize supported values as a shallow, deep-tree-safe JSON table."""
    import json

    nodes = []
    pending = []
    container_types = (dict, list, tuple)
    scalar_types = string_types + integer_types + (float, bool, type(None))

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


def deserialize(payload):
    """Decode the current flat JSON format, including a table from json.load().

    Decoding an already parsed table leaves it reusable. String payloads own
    their decoded lists, so the transport can reuse them without copying.
    Older wire formats and ordinary nested JSON are intentionally unsupported.
    """
    import json

    parsed_table = isinstance(payload, dict)
    decoded = payload if parsed_table else json.loads(payload)
    if not (isinstance(decoded, dict)
            and decoded.get("__blenderneuron_flat__") == 2
            and set(decoded) == {"__blenderneuron_flat__", "root", "nodes"}):
        raise ValueError("Expected BlenderNEURON flat JSON version 2; "
                         "regenerate files and use matching add-on versions")

    if parsed_table:
        decoded = dict(decoded, nodes=[
            [node[0], list(node[1]), node[2]] for node in decoded["nodes"]])
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
