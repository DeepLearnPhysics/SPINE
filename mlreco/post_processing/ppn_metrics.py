import numpy as np
from scipy.spatial.distance import cdist
import scipy
import os
from mlreco.utils import CSVData

def ppn_metrics(cfg, data_blob, res, logdir, iteration):
    # UResNet prediction
    if not 'segmentation' in res: return
    if not 'points' in res: return

    method_cfg = cfg['post_processing']['ppn_metrics']

    index        = data_blob['index']
    segmentation = res['segmentation']
    points       = res['points']
    attention    = res['mask_ppn2']
    input_data   = data_blob.get('input_data' if method_cfg is None else method_cfg.get('input_data', 'input_data'), None)
    segment_label = data_blob.get('segment_label' if method_cfg is None else method_cfg.get('segment_label', 'segment_label'), None)
    num_classes = 5 if method_cfg is None else method_cfg.get('num_classes', 5)
    points_label = data_blob.get('particles_label' if method_cfg is None else method_cfg.get('particles_label', 'particles_label'), None)

    store_per_iteration = True
    if method_cfg is not None and method_cfg.get('store_method',None) is not None:
        assert(method_cfg['store_method'] in ['per-iteration','per-event'])
        store_per_iteration = method_cfg['store_method'] == 'per-iteration'
    fout=None
    if store_per_iteration:
        fout_gt=CSVData(os.path.join(logdir, 'ppn-metrics-gt-iter-%07d.csv' % iteration))
        fout_pred=CSVData(os.path.join(logdir, 'ppn-metrics-pred-iter-%07d.csv' % iteration))

    for data_idx, tree_idx in enumerate(index):

        if not store_per_iteration:
            fout_gt=CSVData(os.path.join(logdir, 'ppn-metrics-gt-event-%07d.csv' % tree_idx))
            fout_pred=CSVData(os.path.join(logdir, 'ppn-metrics-pred-event-%07d.csv' % tree_idx))

        # UResNet output
        predictions = np.argmax(segmentation[data_idx],axis=1)
        label = segment_label[data_idx][:, -1]

        ppn_voxels = points[data_idx][:, :3] + 0.5 + input_data[data_idx][:, :3]
        ppn_score  = scipy.special.softmax(points[data_idx][:, 3:5], axis=1)[:, 1]
        ppn_type   = scipy.special.softmax(points[data_idx][:, 5:], axis=1)

        ppn_mask = (attention[data_idx][:, 0]==1) & (ppn_score > 0.5)

        ppn_voxels = ppn_voxels[ppn_mask]
        ppn_score  = ppn_score[ppn_mask]
        ppn_type   = ppn_type[ppn_mask]

        # Metrics now
        # Distance to closest true point (regardless of type)
        d = cdist(ppn_voxels, points_label[data_idx][:, :3])
        distance_to_closest_true_point = d.min(axis=1)

        distance_to_closest_true_point_type = []
        distance_to_closest_true_pix_type = []
        distance_to_closest_pred_pix_type = []
        for c in range(num_classes):
            true_mask = points_label[data_idx][:, -1] == c
            d = cdist(ppn_voxels, points_label[data_idx][true_mask][:, :3])
            if d.shape[1] > 0:
                distance_to_closest_true_point_type.append(d.min(axis=1))
            else:
                distance_to_closest_true_point_type.append(-1 * np.ones(ppn_voxels.shape[0],))
            d = cdist(ppn_voxels, input_data[data_idx][segment_label[data_idx][:, -1] == c][:, :3])
            if d.shape[1] > 0:
                distance_to_closest_true_pix_type.append(d.min(axis=1))
            else:
                distance_to_closest_true_pix_type.append(-1 * np.ones(ppn_voxels.shape[0],))
            d = cdist(ppn_voxels, input_data[data_idx][predictions == c][:, :3])
            if d.shape[1] > 0:
                distance_to_closest_pred_pix_type.append(d.min(axis=1))
            else:
                distance_to_closest_pred_pix_type.append(-1 * np.ones(ppn_voxels.shape[0],))
        distance_to_closest_true_point_type = np.array(distance_to_closest_true_point_type)
        distance_to_closest_true_pix_type = np.array(distance_to_closest_true_pix_type)
        distance_to_closest_pred_pix_type = np.array(distance_to_closest_pred_pix_type)

        for i in range(ppn_voxels.shape[0]):
            fout_pred.record(('idx', 'distance_to_closest_true_point', 'score') + tuple(['distance_to_closest_true_point_type_%d' % c for c in range(num_classes)]) + tuple(['score_type_%d' % c for c in range(num_classes)]) + tuple(['distance_to_closest_true_pix_type_%d' % c for c in range(num_classes)]) + tuple(['distance_to_closest_pred_pix_type_%d' % c for c in range(num_classes)]), (tree_idx, distance_to_closest_true_point[i], ppn_score[i]) + tuple(distance_to_closest_true_point_type[:, i]) + tuple(ppn_type[i]) + tuple(distance_to_closest_true_pix_type[:, i]) + tuple(distance_to_closest_pred_pix_type[:, i]))
            fout_pred.write()

        # Distance to closest pred point (regardless of type)
        d = cdist(ppn_voxels, points_label[data_idx][:, :3])
        distance_to_closest_pred_point = d.min(axis=0)
        score_of_closest_pred_point = ppn_score[d.argmin(axis=0)]
        types_of_closest_pred_point = ppn_type[d.argmin(axis=0)]
        #print(score_of_closest_pred_point.shape, types_of_closest_pred_point.shape)

        one_pixel = 2.
        for i in range(points_label[data_idx].shape[0]):
            # Whether this point is already missed in mask_ppn2 or not
            is_in_attention = cdist(input_data[data_idx][ppn_mask][:, :3], [points_label[data_idx][i, :3]]).min(axis=0) < one_pixel
            fout_gt.record(('idx', 'distance_to_closest_pred_point', 'type', 'score_of_closest_pred_point',
                            'attention') + tuple(['type_of_closest_pred_point_%d' % c for c in range(num_classes)]),
                    (tree_idx, distance_to_closest_pred_point[i], points_label[data_idx][i, -1], score_of_closest_pred_point[i],
                            int(is_in_attention)) + tuple(types_of_closest_pred_point[i]))
            fout_gt.write()



        if not store_per_iteration:
            fout_gt.close()
            fout_pred.close()

    if store_per_iteration:
        fout_gt.close()
        fout_pred.close()
