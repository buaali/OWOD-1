import pdb
import torch
import torch.nn.functional as F
def gcn_adaptive_loss(pooled_feat, cls_prob, rois, batch_size, gp, epsilon = 1e-6):
    #pdb.set_trace()

    margin = 1
    #cls_prob = cls_prob.squeeze()
    # get the feature embedding of every class for source and target domains wiith GCN
    #pooled_feat = pooled_feat.view(batch_size, pooled_feat.size(0) // batch_size, pooled_feat.size(1))
    #cls_prob = cls_prob.view(batch_size, cls_prob.size(0) // batch_size, cls_prob.size(1))


    num_classes = cls_prob.size(2)
    class_feat = list()

    #pdb.set_trace()
    for i in range(num_classes):
        tmp_cls_prob = cls_prob[:, :, i].view(cls_prob.size(0), cls_prob.size(1), 1)
        #pdb.set_trace()
        tmp_class_feat = pooled_feat * tmp_cls_prob
        tmp_feat = list()
        tmp_weight = list()

        for j in range(batch_size):
            tmp_batch_feat_ = tmp_class_feat[j, :, :]
            tmp_batch_weight_ = tmp_cls_prob[j, :, :]
            tmp_batch_adj = get_adj(rois[j, :, :])

            # graph-based aggregation
            tmp_batch_feat = torch.mm(tmp_batch_adj, tmp_batch_feat_)
            tmp_batch_weight = torch.mm(tmp_batch_adj, tmp_batch_weight_)

            tmp_feat.append(tmp_batch_feat)
            tmp_weight.append(tmp_batch_weight)

        tmp_class_feat_ = torch.stack(tmp_feat, dim = 0)
        tmp_class_weight = torch.stack(tmp_weight, dim = 0)
        tmp_class_feat = torch.sum(torch.sum(tmp_class_feat_, dim=1), dim = 0) / (torch.sum(tmp_class_weight) + epsilon)
        class_feat.append(tmp_class_feat)


    class_feat = torch.stack(class_feat, dim = 0)
    #update gp,tgp
    for c in range(0, num_classes):
        if (gp[c] == 0).all():
            gp[c] = class_feat[c]
            continue
        alpha = (F.cosine_similarity(gp[c], class_feat[c], dim=0).item() + 1) / 2.0
        gp[c] = (1.0 - alpha) * gp[c] + alpha * class_feat[c]
    
    # get the intra-class and inter-class adaptation loss
    inter_loss = 0

    for i in range(gp.size(0)):
        tmp_src_feat_1 = gp[i, :]

        for j in range(i+1, gp.size(0)):
            tmp_src_feat_2 = gp[j, :]
            inter_loss = inter_loss + torch.pow(
                (margin - torch.sqrt(distance(tmp_src_feat_1, tmp_src_feat_2))) / margin,
                2) * torch.pow(
                torch.max(margin - torch.sqrt(distance(tmp_src_feat_1, tmp_src_feat_2)),
                          torch.tensor(0).float().cuda()), 2.0)

    inter_loss = inter_loss / (gp.size(0) - 1) * gp.size(0)
    return gp, inter_loss

def distance( src_feat, tgt_feat):

    output = torch.pow(src_feat - tgt_feat, 2.0).mean()
    return output

def get_adj(rois, epsilon = 1e-6):
    # compute the area of every bbox
    area = (rois[:, 2] - rois[:, 0]) * (rois[:, 3] - rois[:, 1])
    area = area + (area == 0).float() * epsilon

    # compute iou
    x_min = rois[:,0]
    x_min_copy = torch.stack([x_min] * rois.size(0), dim=0)
    x_min_copy_ = x_min_copy.permute((1,0))
    x_min_matrix = torch.max(torch.stack([x_min_copy, x_min_copy_], dim=-1), dim=-1)[0]
    x_max = rois[:,2]
    x_max_copy = torch.stack([x_max] * rois.size(0), dim=0)
    x_max_copy_ = x_max_copy.permute((1, 0))
    x_max_matrix = torch.min(torch.stack([x_max_copy, x_max_copy_], dim=-1), dim=-1)[0]
    y_min = rois[:,1]
    y_min_copy = torch.stack([y_min] * rois.size(0), dim=0)
    y_min_copy_ = y_min_copy.permute((1, 0))
    y_min_matrix = torch.max(torch.stack([y_min_copy, y_min_copy_], dim=-1), dim=-1)[0]
    y_max = rois[:,3]
    y_max_copy = torch.stack([y_max] * rois.size(0), dim=0)
    y_max_copy_ = y_max_copy.permute((1, 0))
    y_max_matrix = torch.min(torch.stack([y_max_copy, y_max_copy_], dim=-1), dim=-1)[0]
    
    w = torch.max(torch.stack([(x_max_matrix - x_min_matrix), torch.zeros_like(x_min_matrix)], dim = -1), dim = -1)[0]
    h = torch.max(torch.stack([(y_max_matrix - y_min_matrix), torch.zeros_like(y_min_matrix)], dim = -1), dim = -1)[0]
    intersection = w * h
    area_copy = torch.stack([area] * rois.size(0), dim = 0)
    area_copy_ = area_copy.permute((1,0))
    area_sum = area_copy + area_copy_
    union = area_sum - intersection
    iou = intersection / union

    return iou