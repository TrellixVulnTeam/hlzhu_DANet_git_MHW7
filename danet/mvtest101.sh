#!/usr/bin/env bash
CUDA_VISIBLE_DEVICES=2,3 python test.py --dataset cityscapes --model mvdanet --resume-dir cityscapes/mvdanet_model/mvdanet101 --base-size 2048 --crop-size 768 --workers 1 --backbone resnet101 --multi-grid --multi-dilation 4 8 16 --eval