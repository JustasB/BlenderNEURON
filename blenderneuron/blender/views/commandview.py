from blenderneuron.blender.views.objectview import ViewAbstract
import os
import numpy as np
import pprint

class CommandView(ViewAbstract):

    def __init__(self, rootgroup):
        self.group = rootgroup

    def show(self):
        return {root.name: self.get_root_update_commands(root)
                 for root in self.group.roots.values()}

    def get_root_update_commands(self, root):
        root_coords = {}

        self.get_section_coords(root, result=root_coords)

        template = self.template()

        # Get the cell instance name - will be default prefix
        dot_position = root.name.find('.')
        prefix = root.name[0:dot_position] if dot_position != -1 else ''

        bracket_pos = prefix.find('[')
        cell_class = prefix[0:bracket_pos] if bracket_pos != -1 else 'Sections'

        # Manually formatted, somewhat of a compromise between readability and space use
        rows = ""
        for sec_name in root_coords.keys():
            coords = root_coords[sec_name]
            sec_name_no_prefix = sec_name[dot_position + 1:]

            row = ""
            row += "          prefix + '" + sec_name_no_prefix + "': {" + "\n"
            row += "              'x':" + self.coords2string(coords["x"]) + "," + "\n"
            row += "              'y':" + self.coords2string(coords["y"]) + "," + "\n"
            row += "              'z':" + self.coords2string(coords["z"]) + "," + "\n"
            row += "              'diam':" + self.coords2string(coords["diam"]) + "\n"
            row += "          }," + "\n"

            rows += row + "\n"

        template = template.replace("[SECTION_COORDS]", rows)
        template = template.replace("[CELL_NAME]", cell_class)
        template = template.replace("[DEFAULT_PREFIX]", prefix)

        return template

    def coords2string(self, coord_list):
        return "[" + str.join(',',map("{0:.3f}".format, coord_list)) + "]"

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