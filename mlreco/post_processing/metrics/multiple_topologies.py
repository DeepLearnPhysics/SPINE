
import numpy as np
import scipy

from mlreco.post_processing import post_processing
from mlreco.utils.gnn.cluster import get_cluster_label
from mlreco.utils.vertex import predict_vertex, get_vertex
from mlreco.utils.groups import type_labels

from mlreco.analysis.ui import FullChainEvaluator
from mlreco.analysis.particle import NullInteraction, match_particles_fn
from pprint import pprint


@post_processing(['topologies'],
                ['input_data', 'seg_label', 'clust_data', 'particles_asis', 'kinematics'],
                ['segmentation', 'inter_group_pred', 'particles', 'particles_seg', 'node_pred_type', 'node_pred_vtx'])
def multiple_topologies(cfg, module_cfg, data_blob, res, logdir, iteration,
                data_idx=None, input_data=None, clust_data=None, particles_asis=None, kinematics=None,
                inter_group_pred=None, particles=None, particles_seg=None,
                node_pred_type=None, node_pred_vtx=None, clust_data_noghost=None, **kwargs):

    row_names, row_values = [], []
    predictor = FullChainEvaluator(None, data_blob, res, cfg)
    matches, _, _ = predictor.match_interactions(data_idx, min_overlap_count=10)
    index = predictor.index[data_idx]
    for pair in matches:
        pred_int, true_int = pair[0], pair[1]
        if isinstance(true_int, NullInteraction):
            continue
        parts, true_parts = pair[0].particles, pair[1].particles
        vtx, true_vtx = pair[0].vertex, pair[1].vertex
        pred_counter = pair[0].particle_counts
        true_counter = pair[1].particle_counts

        pprint(parts)

        pprint(true_parts)

        matched_particles, _, _ = match_particles_fn(parts, true_parts, 
            primaries=True, min_overlap_count=10)

        pred_inter_names, pred_inter_values = pred_int.get_names_and_values()

        true_inter_names, true_inter_values = true_int.get_names_and_values()

        for ppair in matched_particles:

            pred_p, true_p = ppair[0], ppair[1]

            pred_particle_names, pred_particle_values = pred_p.get_names_and_values()
            true_particle_names, true_particle_values = true_p.get_names_and_values()

            row_names.append(
                tuple(['Index']
                + pred_inter_names + true_inter_names \
                + pred_particle_names + true_particle_names))

            row_values.append(
                tuple([index]
                 + pred_inter_values + true_inter_values \
                 + pred_particle_values + true_particle_values))
    for i in range(len(row_names[0])):
        print(row_names[0][i], row_values[0][i])
    return row_names, row_values
