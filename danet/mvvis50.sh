#!/usr/bin/env bash
CUDA_VISIBLE_DEVICES=4,5 python mvdanet_test.py --dataset cityscapes --model mvdanet --resume-dir cityscapes/mvdanet_model/mvdanet50 --base-size 2048 --crop-size 768 --workers 1 --backbone resnet50 --multi-grid --multi-dilation 4 8 16