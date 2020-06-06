from blenderneuron.blender.views.objectview import ViewAbstract
import os
import numpy as np
import pprint
import json

class JsonView(ViewAbstract):

    def __init__(self, rootgroup):
        self.group = rootgroup

    def show(self):

        group_dict = self.group.to_dict(
            include_root_children=True,
            include_coords_and_radii=True
        )

        return group_dict

    def update_group(self):
        pass