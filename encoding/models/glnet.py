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
from ..nn import PAM_Module
from ..nn import pool_CAM_Module
from ..nn import reduce_CAM_Module
from ..nn import SE_ASPP_Module
from ..nn import PAM_Module_gaussmask, PRI_CAM_Module
from .convmtx_mask_generater import *

from ..models import BaseNet

__all__ = ['GLNet', 'get_glnet']


class GLNet(BaseNet):
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

    def __init__(self, nclass, backbone, mviews=25, aux=False, se_loss=False, norm_layer=nn.BatchNorm2d, **kwargs):
        super(GLNet, self).__init__(nclass, backbone, aux, se_loss, norm_layer=norm_layer, **kwargs)
        self.head = GLNetHead(2048, nclass, norm_layer, mask=convmtx2_bf2MV_gaussian(mviews, M=int(kwargs['crop-size'] // 8), N=int(kwargs['crop-size'] // 8)))
        # self.head = GLNetHead(2048, nclass, norm_layer)

    def forward(self, x):
        imsize = x.size()[2:]
        _, _, c3, c4 = self.base_forward(x)

        x = self.head(c4)
        x = list(x)
        x[0] = upsample(x[0], imsize, **self._up_kwargs)
        x[1] = upsample(x[1], imsize, **self._up_kwargs)
        x[2] = upsample(x[2], imsize, **self._up_kwargs)

        outputs = [x[0]]
        outputs.append(x[1])
        outputs.append(x[2])
        return tuple(outputs)


class GLNetHead(nn.Module):
    def __init__(self, in_channels, out_channels, norm_layer, mask):
        super(GLNet, self).__init__()
        inter_channels = in_channels//4
        self.conv5a = nn.Sequential(nn.Conv2d(in_channels, inter_channels, 3, padding=1, bias=False),
                                    norm_layer(inter_channels),
                                    nn.ReLU(inplace=True))

        self.conv5c = nn.Sequential(nn.Conv2d(in_channels, inter_channels, 1, padding=0, bias=False),
                                    norm_layer(inter_channels),
                                    nn.ReLU(inplace=True))


        self.rcm = reduce_CAM_Module(in_channels,inter_channels)
        self.pmg = PAM_Module_gaussmask(inter_channels, inter_rate=64, mask=mask)
        self.pcm = PRI_CAM_Module(inter_channels)

        self.conv6 = nn.Sequential(nn.Dropout2d(0.1, False), nn.Conv2d(inter_channels, out_channels, 1))
        self.conv7 = nn.Sequential(nn.Dropout2d(0.1, False), nn.Conv2d(inter_channels, out_channels, 1))
        self.conv8 = nn.Sequential(nn.Dropout2d(0.1, False), nn.Conv2d(256, out_channels, 1))

    def forward(self, x):
        # n,c,h,w = x.size()

        rcm_feat = self.rcm(x)
        rcm_output = self.conv6(rcm_feat)

        rcm_feat_conv = self.conv(rcm_feat)
        pmg_feat = self.pmg(rcm_feat_conv)
        pmg_feat = pmg_feat + rcm_feat_conv
        pmg_output = self.conv7(pmg_feat)

        pcm_feat = self.pcm(pmg_feat)
        pcm_output = self.conv8(pcm_feat)

        output = [pcm_output]
        output.append(rcm_output)
        output.append(pmg_output)
        return tuple(output)


def get_glnet(dataset='pascal_voc', backbone='resnet50', pretrained=False,
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
    model = GLNet(datasets[dataset.lower()].NUM_CLASS, backbone=backbone, root=root, **kwargs)
    if pretrained:
        from .model_store import get_model_file
        model.load_state_dict(torch.load(
            get_model_file('fcn_%s_%s' % (backbone, acronyms[dataset]), root=root)),
            strict=False)
    return model

