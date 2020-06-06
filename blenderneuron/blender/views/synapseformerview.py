from abc import ABCMeta, abstractmethod
from math import acos, pi, floor
from random import random
from mathutils import Euler, Vector, Matrix
from blenderneuron.blender.views.objectview import ViewAbstract
from blenderneuron.blender.views.cellobjectview import CellObjectView
import bpy
import bpy, mathutils
from heapq import *
import fnmatch
from functools import total_ordering
import json
from blenderneuron.blender.utils import make_safe_filename

class SynapseTerminal:
    def __init__(self, loc, radius, section_name, point_index, x, seg_i):
        self.loc = loc
        self.radius = radius
        self.section_name = section_name
        self.point_index = point_index
        self.x = x
        self.segment_index = seg_i


@total_ordering
class SynapsePair:
    def __init__(self, source, dest, length):
        self.source = source
        self.dest = dest
        self.length = length

    # These are needed for pair heap - minimally implemented
    def __lt__(self, other):
        return True

    def __eq__(self, other):
        return False

class SynapseFormerView(CellObjectView):
    def __init__(self, source_group, dest_group):
        super(SynapseFormerView, self).__init__(source_group, closed_ends=False)

        self.dest_group = dest_group

        self.synapse_container_name = None
        self.synapse_pairs = None

    def show(self):

        self.dest_group.show(CellObjectView, closed_ends=False)

        super(SynapseFormerView, self).show()

    def remove(self):
        if self.dest_group.view is not None:
            self.dest_group.view.remove()

        super(SynapseFormerView, self).remove()

        if self.synapse_container_name is not None:
            syn_container = bpy.data.objects.get(self.synapse_container_name)

            if syn_container is not None:
                curve_name = syn_container.data.name

                bpy.data.objects.remove(syn_container)

                bpy.data.curves.remove(bpy.data.curves[curve_name])

    def save_synapses(
            self,
            file_name,
            synapse_set_name,
            synapse_name_dest,
            synapse_params_dest,
            conduction_velocity,
            synaptic_delay,
            initial_weight,
            threshold,
            is_reciprocal,
            synapse_name_source,
            synapse_params_source,
            create_spines,
            neck_diameter,
            head_diameter,
            spine_prefix):

        syn_dict = self.create_synapse_entry_dict(
            conduction_velocity,
            synaptic_delay,
            create_spines,
            head_diameter,
            initial_weight,
            is_reciprocal,
            neck_diameter,
            spine_prefix,
            synapse_name_dest,
            synapse_name_source,
            synapse_params_dest,
            synapse_params_source,
            synapse_set_name,
            threshold
        )

        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(syn_dict, f)

    def create_synapses(
            self,
            synapse_set_name,
            synapse_name_dest,
            synapse_params_dest,
            conduction_velocity,
            synaptic_delay,
            initial_weight,
            threshold,
            is_reciprocal,
            synapse_name_source,
            synapse_params_source,
            create_spines,
            neck_diameter,
            head_diameter,
            spine_prefix):

        syn_dict = self.create_synapse_entry_dict(
            conduction_velocity,
            synaptic_delay,
            create_spines,
            head_diameter,
            initial_weight,
            is_reciprocal,
            neck_diameter,
            spine_prefix,
            synapse_name_dest,
            synapse_name_source,
            synapse_params_dest,
            synapse_params_source,
            synapse_set_name,
            threshold
        )

        self.group.node.client.create_synapses(syn_dict)

    def create_synapse_entry_dict(
            self,
            conduction_velocity,
            synaptic_delay,
            create_spines,
            head_diameter,
            initial_weight,
            is_reciprocal,
            neck_diameter,
            spine_prefix,
            synapse_name_dest,
            synapse_name_source,
            synapse_params_dest,
            synapse_params_source,
            synapse_set_name,
            threshold):

        syn_set = {
            'name': make_safe_filename(synapse_set_name),
            'entries': [],
        }

        for pair in self.synapse_pairs:
            # Compute the delay based on syn distance
            if not create_spines:
                propagation_delay = pair.length / (conduction_velocity * 1000.0)  # 1m/s = 1000um/ms

            # When creating spines, prop. delay is emergent
            else:
                propagation_delay = 0

            delay = propagation_delay + synaptic_delay

            from_term = pair.source
            to_term = pair.dest

            head_start = None
            head_end = None
            neck_start = None
            neck_end = None

            if create_spines:
                spine_vec = (to_term.loc - from_term.loc).normalized()

                head_end = to_term.loc - spine_vec * to_term.radius
                head_start = head_end - spine_vec * head_diameter

                neck_length = max(0, pair.length - head_diameter)

                if neck_length > 0:
                    neck_start = from_term.loc + spine_vec * from_term.radius
                    neck_end = head_start

            # Create an entry to source->dest synapse
            entry_forward = self.create_syn_entry(
                from_term, to_term,
                synapse_name_dest,
                synapse_params_dest,
                delay, initial_weight, threshold,
                create_spines, spine_prefix,
                head_start, head_end, head_diameter,
                neck_start, neck_end, neck_diameter,
                is_reciprocal, synapse_name_source, synapse_params_source
            )

            syn_set['entries'].append(entry_forward)

        return syn_set

    def create_syn_entry(self, from_term, to_term, syn_class, syn_params,
                         delay, initial_weight, threshold,
                         create_spine=False, spine_prefix=None,
                         head_start=None, head_end=None, head_diameter=None,
                         neck_start=None, neck_end=None, neck_diameter=None,
                         is_reciprocal=False, syn_class_source=None, syn_params_source=None):

        entry = {
            'source_section': from_term.section_name,
            'source_x': float(from_term.x),
            'source_seg_i': from_term.segment_index,

            'dest_section': to_term.section_name,
            'dest_x': float(to_term.x),
            'dest_seg_i': to_term.segment_index,

            'dest_syn': syn_class,
            'dest_syn_params': syn_params,

            'delay': delay,
            'weight': initial_weight,
            'threshold': threshold,

            'create_spine': create_spine,
            'is_reciprocal': is_reciprocal,
        }

        if is_reciprocal:
            entry['source_syn'] = syn_class_source
            entry['source_syn_params'] = syn_params_source

        if create_spine:
            entry['prefix'] = spine_prefix

            entry['head_start'] = list(head_start)
            entry['head_end'] = list(head_end)
            entry['head_diameter'] = head_diameter

            entry['neck_start'] = None

            if neck_start is not None:
                entry['neck_start'] = list(neck_start)
                entry['neck_end'] = list(neck_end)
                entry['neck_diameter'] = neck_diameter

        return entry

    def get_synapse_locations(self, max_dist, use_radii, max_syns_per_pt,
                              section_pattern_source, section_pattern_dest):

        # Build a kd-tree for efficient distance searches
        dest_group_tree, dest_node2synterm, dest_max_radius = \
            self.build_tree(self.dest_group.view, section_pattern_dest)

        # Find the pairs using the kd-tree
        syn_pairs = self.find_pairs(
            self,
            section_pattern_source,
            self.dest_group.view,
            dest_group_tree,
            dest_node2synterm,
            max_dist,
            use_radii,
            dest_max_radius,
            max_syns_per_pt
        )

        # Draw the pairs as line segments
        bez = bpy.data.objects.new("SynapsePreview", self.make_curve())

        for pair in syn_pairs:
            spline = bez.data.splines.new('BEZIER')
            bez_pts = spline.bezier_points

            bez_pts.add(1)  # comes with 1pt by default
            bez_pts[0].co = pair.source.loc
            bez_pts[1].co = pair.dest.loc

        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.scene.objects.link(bez)
        bpy.context.scene.update()

        bez.select = True
        bpy.context.scene.objects.active = bez

        # Set handles to make splines straight
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.curve.select_all(action='SELECT')
        bpy.ops.curve.handle_type_set(type='AUTOMATIC')
        bpy.ops.object.mode_set(mode='OBJECT')

        self.synapse_container_name = bez.name
        self.synapse_pairs = syn_pairs

        return syn_pairs

    def make_curve(self):
        curve = bpy.data.curves.new("SynapsePreviewCurve", type='CURVE')
        curve.dimensions = '3D'
        curve.resolution_u = 0
        curve.fill_mode = 'FULL'
        curve.bevel_depth = 0.0
        curve.show_normal_face = False
        curve.show_handles = False

        return curve

    @staticmethod
    def build_tree(group_view, pattern):

        # Pre-allocate the KDTree
        size = 0
        for container in group_view.containers.values():
            splines = container.object.data.splines
            for spline_index, spline in enumerate(splines):
                section_name = container.spline_index2section[spline_index].name
                if fnmatch.fnmatch(section_name, pattern):
                    size += len(spline.bezier_points)

        tree = mathutils.kdtree.KDTree(size)

        # Set up a map of tree node -> (section, pt, radius)
        # This will make it easy to find point section/cell
        node2terminal = {}

        # Keep track of maximum radius
        # Used when radii are used for distance evaluations
        max_radius = 0
        node_id = 0

        for container in group_view.containers.values():
            cell_obj = container.object
            splines = cell_obj.data.splines

            # Will convert all points to global coordinates
            mw = cell_obj.matrix_world

            for spline_id, spline in enumerate(splines):
                section = container.spline_index2section[spline_id]
                section_name = section.name

                if fnmatch.fnmatch(section_name, pattern):

                    arc_lengths = section.arc_lengths()
                    tot_length = arc_lengths[-1]

                    for pt_id, pt in enumerate(spline.bezier_points):
                        loc = (mw * pt.co).copy().freeze()

                        # Compute section fraction along i.e. NEURON sec(x)
                        x = arc_lengths[pt_id] / tot_length
                        seg_i = min(floor(section.nseg * x), section.nseg-1)

                        # Insert points into the tree
                        tree.insert(loc, node_id)

                        # Insert into node->syn terminal map
                        node2terminal[node_id] = SynapseTerminal(loc, pt.radius, section_name, pt_id, x, seg_i)

                        # Update max radius
                        radius = pt.radius
                        if radius > max_radius:
                            max_radius = radius

                        node_id += 1

        # Balance the tree - necessary for spatial searches
        tree.balance()

        return tree, node2terminal, max_radius

    @staticmethod
    def find_pairs(group_view1, view1_pattern, group_view2, group2_tree, group2_node2synterm,
                   max_dist, use_radii, max_radius, max_syns_per_pt):

        # Keep track of pair distances in a heap
        # The pairs with the shortest distances will be added first
        pair_heap = []

        search_dist = max_dist

        # Allow for an extra search margin when utilizing radii
        if use_radii:
            search_dist += max_radius

        containers2 = group_view2.containers

        for container1 in group_view1.containers.values():
            cell_obj = container1.object
            mw = cell_obj.matrix_world

            for spline1_id, spline1 in enumerate(cell_obj.data.splines):
                section = container1.spline_index2section[spline1_id]
                section_name = section.name

                if fnmatch.fnmatch(section_name, view1_pattern):
                    arc_lengths = section.arc_lengths()
                    tot_length = arc_lengths[-1]

                    for pt1_id, pt1 in enumerate(spline1.bezier_points):

                        # Convert to global coordinates
                        # Freeze it so it can be stored in a dict
                        pt_glob = (mw * pt1.co.copy()).freeze()

                        # Find points in the other group that are within the search
                        # distance of current point
                        matches = group2_tree.find_range(
                            pt_glob,
                            search_dist + (pt1.radius if use_radii else 0)
                        )

                        if len(matches) > 0:
                            # Compute section along fraction i.e. NEURON sec(x)
                            # and section segment index
                            x = arc_lengths[pt1_id] / tot_length
                            seg_i = min(floor(section.nseg * x), section.nseg - 1)

                        # Add found points to the pair heap
                        for pt2_glob, node2_id, dist in matches:

                            # Create a terminal for source end
                            term1 = SynapseTerminal(pt_glob, pt1.radius, section_name, pt1_id, x, seg_i)

                            # Get the original terminal from dest group
                            term2 = group2_node2synterm[node2_id]

                            # Create the pair
                            pair = SynapsePair(term1, term2, dist)

                            if use_radii:
                                # The range search uses distance between 3D points
                                # The radii are subtracted to obtain the approx. true distance between
                                # the section points
                                true_dist = dist - pt1.radius - term2.radius

                                # This distance must still be less than the maximum search distance
                                if true_dist <= max_dist:

                                    # Update the true pair distance
                                    pair.length = true_dist

                                    # Add to the pair heap only when this is the case
                                    heappush(pair_heap, (true_dist, pair))

                            else:
                                # When not using radii, all matches will be less than search distance
                                heappush(pair_heap, (dist, pair))



        # Keep track of how many times each point has been used
        # This allows control over how many synapses can be formed with a given point
        used_pt_counts = {}

        # The pairs of points with the locations for synapses
        result_pairs = []

        while len(pair_heap) > 0:
            # Pop the next smallest distance pair from the heap
            dist, pair = heappop(pair_heap)
            pt1, pt2 = pair.source.loc, pair.dest.loc

            pt1_count = used_pt_counts.get(pt1, 0)
            pt2_count = used_pt_counts.get(pt2, 0)

            # Skip if used too much
            if pt1_count >= max_syns_per_pt or pt2_count >= max_syns_per_pt:
                continue

            # Otherwise, record use
            used_pt_counts[pt1] = pt1_count + 1
            used_pt_counts[pt2] = pt2_count + 1

            # Use it
            result_pairs.append(pair)

        return result_pairs
