#!/bin/bash
#SBATCH --partition=gpu_8
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --time=12:00:00
#SBATCH --export=NONE
BATCH=$1
PREBATCH=$2
LR=$3
TEMP=$4
EPOCHS=$5
PREEPOCHS=$6
AUG=$7
PREAUG=$8

export PYTHONPATH=$(pwd)
#export CUDA_VISIBLE_DEVICES=0

python run_finetune_siamese.py \
	--model_pretrained_checkpoint $(pwd)/reports/contrastive/walmart-amazon-clean-no-split-$AUG$PREBATCH-$LR-$TEMP-$PREEPOCHS-roberta-base/pytorch_model.bin \
    --do_train \
	--dataset_name=walmart-amazon \
    --train_file $(pwd)src/finetuning/open_book/contrastive_product_matching/data/interim/walmart-amazon/walmart-amazon-train.json.gz \
	--validation_file $(pwd)src/finetuning/open_book/contrastive_product_matching/data/interim/walmart-amazon/walmart-amazon-train.json.gz \
	--test_file $(pwd)src/finetuning/open_book/contrastive_product_matching/data/interim/walmart-amazon/walmart-amazon-gs.json.gz \
	--evaluation_strategy=epoch \
	--tokenizer="roberta-base" \
	--grad_checkpoint=False \
    --output_dir $(pwd)/reports/contrastive-ft-siamese/walmart-amazon-clean-no-split-$AUG$PREBATCH-$PREAUG$LR-$TEMP-$PREEPOCHS-$EPOCHS-frozen-roberta-base/ \
	--per_device_train_batch_size=$BATCH \
	--learning_rate=$LR \
	--weight_decay=0.01 \
	--num_train_epochs=$EPOCHS \
	--lr_scheduler_type="linear" \
	--warmup_ratio=0.05 \
	--max_grad_norm=1.0 \
	--fp16 \
	--metric_for_best_model=loss \
	--dataloader_num_workers=4 \
	--disable_tqdm=True \
	--save_strategy="epoch" \
	--load_best_model_at_end \
	--augment=$AUG \
	#--do_param_opt \