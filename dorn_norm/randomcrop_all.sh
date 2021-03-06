#!/bin/bash
uname -a
#date
#env
export PYTHONBUFFERED="True"
NETWORK='dorn'
SAVE_DIR='./outputs_val/' 
DATA_DIRECTORY='/data/liuyx/nyuv2'
DATA_LIST_PATH='/data/liuyx/nyuv2/nyu_depth_v2_train_fill_all/train_rgb.txt'
##RESTORE_FROM='./pretrained/resnet50-imagenet.pth'
#RESTORE_FROM='./basedorn.batch8_polyfixbnconv1e-4/nyu_24400.pth'
RESTORE_FROM='./dataset/MS_DeepLab_resnet_pretrained_COCO_init.pth'
#SNAPSHOT_DIR='./snapshots_train_eval/'
LR=1e-4
SNAPSHOT_DIR='../events/'$NETWORK'.allrandomcrop'$LR
BATCHSIZE=8
STEPS=250000   # 20 epoch
SAVE_PRED_EVERY=100
GPU_IDS='1'
INPUT_SIZE='257,353'
NUM_CLASSES=160 
STARTITERS=0
 
python base_fixconv.py --data-dir ${DATA_DIRECTORY} \
                          --data-list ${DATA_LIST_PATH} \
                          --input-size ${INPUT_SIZE} \
                          --num-classes ${NUM_CLASSES} \
                          --random-mirror \
                          --random-scale \
                          --gpu ${GPU_IDS} \
                          --learning-rate ${LR} \
                          --batch-size ${BATCHSIZE} \
                          --num-steps ${STEPS} \
                          --start-iters ${STARTITERS}\
                          --restore-from ${RESTORE_FROM} \
                          --snapshot-dir ${SNAPSHOT_DIR} \
                          --save-pred-every ${SAVE_PRED_EVERY}\
		                  --network ${NETWORK}
