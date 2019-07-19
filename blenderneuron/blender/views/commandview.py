from blenderneuron.blender.views.objectview import ViewAbstract
import os
import numpy as np
import pprint

class CommandView(ViewAbstract):

    def __init__(self, rootgroup):
        self.group = rootgroup

    def show(self):

        group_coords = {}

        for root in self.group.roots.values():
            self.get_section_coords(root, result=group_coords)

        template = self.template()

        # One long row
        # rows = str(group_coords)

        # Indented, but takes up more space
        # rows = pprint.pformat(group_coords)

        # Manually formatted, somewhat of a compromise between readability and space use
        rows = ""
        for sec_name in group_coords.keys():
            coords = group_coords[sec_name]

            row = ""
            row += "   '" + sec_name + "': {" + "\n"
            row += "       'x':" + str(coords["x"]) + "," + "\n"
            row += "       'y':" + str(coords["y"]) + "," + "\n"
            row += "       'z':" + str(coords["z"]) + "," + "\n"
            row += "       'diam':" + str(coords["diam"]) + "\n"
            row += "   }," + "\n"

            rows += row + "\n"

        template = template.replace("[SECTION_COORDS]", rows)

        return template

    def template(self):
        dir_path = os.path.dirname(__file__)
        template_path = os.path.join(dir_path, "commandviewtemplate.py")

        with open(template_path, "r") as f:
            template = f.read()

        return template

    def get_section_coords(self, root, result):

        coords = np.array(root.coords).reshape((-1, 3))
        diams = np.array(root.radii) * 2.0

        result[root.name] = {
            "x": list(coords[:,0]),
            "y": list(coords[:,1]),
            "z": list(coords[:,2]),
            "diam": list(diams)
        }

        del coords, diams

        for child in root.children:
            self.get_section_coords(child, result)


    def update_group(self):
        pass