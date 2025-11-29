from abc import ABCMeta

from blenderneuron.activity import Activity


class Section:
    __metaclass__ = ABCMeta

    def __init__(self):
        self.name = ""

        self.nseg = None
        self.point_count = 0
        self.coords = []
        self.radii = []

        self.children = []
        self.parent_connection_loc = -1
        self.connection_end = -1

        self.activity = Activity()
        self.segment_activity = {}   # {segment_index: Activity()}

    def __str__(self):
        return self.name

    def to_dict(self, include_activity=True, include_children=True, include_coords_and_radii=True):
        # Helper function to build a dict for a given node
        def build_node_dict(node):
            node_dict = {
                "name": node.name,
                "parent_connection_loc": node.parent_connection_loc,
                "connection_end": node.connection_end,
            }

            if include_activity:
                node_dict["activity"] = node.activity.to_dict()
                node_dict["segment_activity"] = {
                    str(i): act.to_dict() for i, act in node.segment_activity.items()
                }

            if include_coords_and_radii:
                node_dict["nseg"] = node.nseg
                node_dict["point_count"] = node.point_count
                node_dict["coords"] = node.coords if isinstance(node.coords, list) else node.coords.tolist()
                node_dict["radii"] = node.radii if isinstance(node.radii, list) else node.radii.tolist()

            return node_dict

        # Initial result for the current node
        result = build_node_dict(self)

        if include_children:
            result["children"] = []
            stack = [(self, result["children"])]  # Stack holds (node, parent_children_list)

            while stack:
                current_node, current_children_list = stack.pop()
                for child in current_node.children:
                    child_dict = build_node_dict(child)
                    current_children_list.append(child_dict)
                    stack.append((child, child_dict.setdefault("children", [])))

        return result

    def clear_segment_activity(self):
        # Clear the activity of the 3D segments in the current object
        self.segment_activity = {}

        # Use a stack to iteratively clear the 3D segment activity of the children
        stack = list(self.children)
        while stack:
            current = stack.pop()

            # Clear the activity of the 3D segments of the current child
            current.segment_activity = {}

            # Add the current child's children to the stack for further processing
            stack.extend(current.children)

    def clear_activity(self, recursive):
        self.activity.clear()

        if recursive:
            stack = list(self.children)
            while stack:
                current = stack.pop()
                current.activity.clear()
                stack.extend(current.children)
