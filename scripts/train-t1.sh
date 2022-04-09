launch --gpu 8 -- python3 tools/train_net.py \
--num-gpus 8 \
--dist-url='tcp://127.0.0.1:52125' \
--resume \
--config-file ./configs/OWOD/t1/t1_train.yaml \
SOLVER.IMS_PER_BATCH 8 \
SOLVER.BASE_LR 0.01 \
OUTPUT_DIR "./output/t1"