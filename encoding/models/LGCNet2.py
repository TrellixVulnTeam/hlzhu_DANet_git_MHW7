###########################################################################
# Created by: CASIA IVA
# Email: jliu@nlpr.ia.ac.cn
# Copyright (c) 2018
###########################################################################
from __future__ import division
import os
import numpy as np
import torch
import torch.nn as nn
from torch.nn.functional import upsample, normalize
from ..nn import PAM_Module, topk_PAM_Module
from ..nn import CAM_Module , SE_CAM_Module, selective_aggregation_ASPP_Module, reduce_PAM_Module
from ..models import BaseNet
from ..nn import ASPP_Module

__all__ = ['LGCNet2', 'get_lgcnet2']


class LGCNet2(BaseNet):
    r"""Fully Convolutional Networks for Semantic Segmentation

    Parameters
    ----------
    nclass : int
        Number of categories for the training dataset.
    backbone : string
        Pre-trained dilated backbone network type (default:'resnet50'; 'resnet50',
        'resnet101' or 'resnet152').
    norm_layer : object
        Normalization layer used in backbone network (default: :class:`mxnet.gluon.nn.BatchNorm`;


    Reference:

        Long, Jonathan, Evan Shelhamer, and Trevor Darrell. "Fully convolutional networks
        for semantic segmentation." *CVPR*, 2015

    """

    def __init__(self, nclass, backbone, aux=False, se_loss=False, norm_layer=nn.BatchNorm2d, **kwargs):
        super(LGCNet2, self).__init__(nclass, backbone, aux, se_loss, norm_layer=norm_layer, **kwargs)
        self.head = LGCNet2Head(2048, nclass, norm_layer)

    def forward(self, x):
        imsize = x.size()[2:]
        _, _, c3, c4 = self.base_forward(x)

        x = self.head(c4)
        x = list(x)
        x[0] = upsample(x[0], imsize, **self._up_kwargs)
        x[1] = upsample(x[1], imsize, **self._up_kwargs)
        x[2] = upsample(x[2], imsize, **self._up_kwargs)
        # x[3] = upsample(x[3], imsize, **self._up_kwargs)
        # x[4] = upsample(x[4], imsize, **self._up_kwargs)

        outputs = [x[0]]
        outputs.append(x[1])
        outputs.append(x[2])
        # outputs.append(x[3])
        # outputs.append(x[4])
        return tuple(outputs)


class LGCNet2Head(nn.Module):
    def __init__(self, in_channels, out_channels, norm_layer):
        super(LGCNet2Head, self).__init__()
        inter_channels = in_channels // 4


        self.conv5a = nn.Sequential(nn.Conv2d(in_channels, inter_channels, 3, padding=1, bias=False),
                                    norm_layer(inter_channels),
                                    nn.ReLU())

        self.conv5c = nn.Sequential(nn.Conv2d(in_channels, inter_channels, 3, padding=1, bias=False),
                                    norm_layer(inter_channels),
                                    nn.ReLU())

        self.sa = topk_PAM_Module(inter_channels, 256, inter_channels, 10)
        self.sc = SE_CAM_Module(inter_channels)
        self.sca = SE_CAM_Module(inter_channels)

        self.conv51 = nn.Sequential(nn.Conv2d(inter_channels, inter_channels, 3, padding=1, bias=False),
                                    norm_layer(inter_channels),
                                    nn.ReLU())
        self.conv52 = nn.Sequential(nn.Conv2d(inter_channels, inter_channels, 3, padding=1, bias=False),
                                    norm_layer(inter_channels),
                                    nn.ReLU())
        self.conv53 = nn.Sequential(nn.Conv2d(inter_channels, inter_channels, 3, padding=1, bias=False),
                                    norm_layer(inter_channels),
                                    nn.ReLU())
        # self.conv54 = nn.Sequential(nn.Conv2d(inter_channels*3, inter_channels, 1, padding=0, bias=False),
        #                             norm_layer(inter_channels),
        #                             nn.ReLU())
        self.conv54 = nn.Sequential(nn.Conv2d(inter_channels * 2, inter_channels, 1, padding=0, bias=False),
                                    norm_layer(inter_channels),
                                    nn.ReLU())

        self.conv5 = nn.Sequential(nn.Dropout2d(0.1), nn.Conv2d(512, out_channels, 1))
        self.conv6 = nn.Sequential(nn.Dropout2d(0.1), nn.Conv2d(512, out_channels, 1))
        self.conv7a = nn.Sequential(nn.Dropout2d(0.1), nn.Conv2d(512, out_channels, 1))
        self.conv7 = nn.Sequential(nn.Dropout2d(0.1), nn.Conv2d(512, out_channels, 1))
        self.conv8 = nn.Sequential(nn.Dropout2d(0.1), nn.Conv2d(512, out_channels, 1))

        self.aspp = selective_aggregation_ASPP_Module(in_channels, inner_features=256, out_features=512, dilations=(12, 24, 36))

        self.bottleneck = nn.Sequential(
            nn.Conv2d(256 * 5, 512, kernel_size=1, padding=0, dilation=1, bias=False),
            nn.BatchNorm2d(512), nn.ReLU(),
        )
    def forward(self, x):
        feat1, cat1 = self.aspp(x)
        # cat1 = self.bottleneck(cat1)
        # aspp_output = self.conv5(cat1)
        # aspp_output = self.conv5(feat1)
        # feat1 = self.conv5a(x)

        #sa
        sa_feat = self.sa(feat1)
        sa_conv = self.conv51(sa_feat)
        sa_output = self.conv6(sa_conv)

        #sc
        # feat2 = self.conv5c(x)
        # sca_feat = self.sca(feat1)
        # sca_conv = self.conv52(sca_feat)
        # sca_output = self.conv7a(sca_conv)

        # output = [sa_output]
        #sec
        feat2 = self.conv5c(x)
        sc_feat = self.sc(feat2)
        sc_conv = self.conv53(sc_feat)
        sc_output = self.conv7(sc_conv)

        feat_sum = sa_conv + sc_conv
        # feat_sum = torch.cat((sa_conv, sc_conv, sca_conv), 1)
        # feat_sum = torch.cat((sa_conv, sc_conv), 1)

        # feat_sum = self.conv54(feat_sum)
        sasc_output = self.conv8(feat_sum)

        output = [sasc_output]
        output.append(sa_output)
        output.append(sc_output)
        # output.append(aspp_output)
        # output.append(sca_output)

        return tuple(output)


def get_lgcnet2(dataset='pascal_voc', backbone='resnet50', pretrained=False,
              root='./pretrain_models', **kwargs):
    r"""DANet model from the paper `"Dual Attention Network for Scene Segmentation"
    <https://arxiv.org/abs/1809.02983.pdf>`
    """
    acronyms = {
        'pascal_voc': 'voc',
        'pascal_aug': 'voc',
        'pcontext': 'pcontext',
        'ade20k': 'ade',
        'cityscapes': 'cityscapes',
    }
    # infer number of classes
    from ..datasets import datasets, VOCSegmentation, VOCAugSegmentation, ADE20KSegmentation
    model = LGCNet2(datasets[dataset.lower()].NUM_CLASS, backbone=backbone, root=root, **kwargs)
    if pretrained:
        from .model_store import get_model_file
        model.load_state_dict(torch.load(
            get_model_file('fcn_%s_%s' % (backbone, acronyms[dataset]), root=root)),
            strict=False)
    return model


