from .curve_container import CurveContainer, _get_curve_template, _get_default_color

_objects = {}
_next_object_id = 0

def register_object(obj):
    global _objects, _next_object_id

    id = _next_object_id
    _objects[_next_object_id] = obj
    _next_object_id += 1
    return id


def register_cell(cell):
    id = register_object(cell)
    cell._id = id
    cc = _create_curve_container(cell)
    cell.curve_container = cc

def _create_curve_container(cell):
    name = get_blender_name(cell)
    return CurveContainer(cell, _get_curve_template(name), True, _get_default_color(name), 1.0)

def get_blender_name(obj):
    try:
        return "bn_obj_" + str(obj._id)
    except:
        raise ValueError(f"Could not determine blender object name of '{obj}'.")
