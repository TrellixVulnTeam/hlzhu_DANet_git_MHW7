#!/usr/bin/env bash
CUDA_VISIBLE_DEVICES=2,3 python test.py --dataset cityscapes --model danet --resume-dir cityscapes/danet_model/danet50 --base-size 2048 --crop-size 768 --workers 1 --backbone resnet50 --multi-grid --multi-dilation 4 8 16