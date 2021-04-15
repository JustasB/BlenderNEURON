import warnings
import numpy as np

try:
    import bpy
except:
    inside_blender = False
else:
    inside_blender = True

# `bl_info` is read without evaluating the module. The BlenderNEURON installer will
# replace the `blender` and `location` key with what is appropriate for the detected
# Blender version so that our addon is compatible across Blender versions.
# `bl_info` needs to be defined at the module-level of the file aswell.
bl_info = {
    "name": "BlenderNEURON",
    "description": "A Blender GUI for NEURON simulator",
    "author": "Justas Birgiolas",
    "version": (3, 0),
    "blender": (2, 91, 0),
    "location": "View3D > Properties > BlenderNEURON",
    "wiki_url": "BlenderNEURON.org",
    "tracker_url": "https://github.com/JustasB/BlenderNEURON/issues",
    "support": "COMMUNITY",
    "category": "Import-Export",
}

if inside_blender:
    from ._blender import make_blender_addon

    addon, controller = make_blender_addon()

    def register():
        addon.register()

    def unregister():
        addon.unregister()

else:
    class Reporter:
        @property
        def is_available(self):
            return False

        def __getattr__(self, name):
            warnings.warn("Controller can't be used outside of Blender environment", stacklevel=2)
            return Reporter()

        def __call__(self, *args, **kwargs):
            warnings.warn("Controller can't be used outside of Blender environment", stacklevel=2)

    controller = Reporter()


from . import animation

class Branch:
    """
    A branch is a piece of uninterrupted unbranching cable used to construct
    :class:`cells <.Cell>`.
    """
    def __init__(self, coords, radii, children=None, ref=None):
        """
        Create a branch.

        :param coords: A matrix or list of 3d points describing the branch in space.
        :type coords: np.ndarray (or list of lists-like outside Blender)
        :param children: A collection of branches that are the continuation of this branch
        :type children: list
        :param ref: A reference hash to associate to this object. Can be used to map this
            object to its data source.
        """
        if children is None:
            children = []
        self._children = children
        self._coords = coords
        self._radii = radii
        self._material = None
        self._spline = None
        self._cell = None
        self._ref = ref

    @property
    def children(self):
        """
        The child branches of this branch.
        """
        return self._children

    @property
    def coords(self):
        """
        A list of 3d coordinates that describe this piece of cell morphology
        """
        if self._cell:
            raise NotImplementedError("Reading Blender state not supported yet.")
        else:
            return self._coords

    @coords.setter
    def coords(self):
        if self._cell:
            raise NotImplementedError("Manipulating the Blender object state not supported yet.")
        else:
            self._coords = coords

    @property
    def radii(self):
        """
        A list of radii at the 3d points on this branch
        """
        if self._cell:
            raise NotImplementedError("Reading Blender state not supported yet.")
        else:
            return self._radii

    def to_dict(self):
        d = dict(coords=self.coords)
        if self._ref is not None:
            d["ref"] = self.ref
        return d


class Cell:
    """
    A cell is the 3D representation of a collection of root :class:`Branches <.Branch>`,
    branching out into child Branches.
    """
    def __init__(self, roots):
        self._roots = roots

    def register(self):
        """
        Register the cell with the controller to create its Blender object and manage its
        state. Only available inside Blender.
        """
        controller.register_cell(self)

    @property
    def roots(self):
        """
        A list of 3d coordinates that describe this piece of cell morphology
        """
        return self._roots

    @roots.setter
    def roots(self):
        raise NotImplementedError("Manipulating the Blender object state not supported yet.")

    def __dissolve__(self):
        for root in roots:
            root.__dissolve__()

def create_branch(*args, **kwargs):
    """
    Create a new :class:`.Branch`.
    """
    return Branch(*args, **kwargs)


def create_cell(roots, register=inside_blender):
    """
    Create a new :class:`.Cell` from the given roots.

    :param roots: Collection of :class:`Branches <.Branch>` without parents that start a
        branch of the cell morphology.
    :type roots: iterable
    :param register: Register the cell with the controller to create its Blender object
        and manage its state. Only available inside Blender.
    :type register: bool
    """
    cell = Cell(roots)
    if register:
        cell.register()
    return cell
