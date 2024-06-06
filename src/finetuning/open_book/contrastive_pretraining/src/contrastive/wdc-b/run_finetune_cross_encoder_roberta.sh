#!/bin/bash
#SBATCH --partition=gpu_8
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --time=12:00:00
#SBATCH --export=NONE

BATCH=$1
LR=$2
EPOCHS=$3

export PYTHONPATH=$(pwd)
#export CUDA_VISIBLE_DEVICES=7

python run_finetune_cross_encoder.py \
	--model_pretrained_checkpoint="roberta-base" \
    --do_train \
	--dataset_name=wdcproducts80cc20rnd050un \
    --train_file $(pwd)src/finetuning/open_book/contrastive_product_matching/data/interim/wdcproducts80cc20rnd050un/wdcproducts80cc20rnd050un-train.json.gz \
	--validation_file $(pwd)src/finetuning/open_book/contrastive_product_matching/data/interim/wdcproducts80cc20rnd050un/wdcproducts80cc20rnd050un-train.json.gz \
	--test_file $(pwd)src/finetuning/open_book/contrastive_product_matching/data/interim/wdcproducts80cc20rnd050un/wdcproducts80cc20rnd050un-gs.json.gz \
	--evaluation_strategy=epoch \
	--tokenizer="roberta-base" \
	--grad_checkpoint=False \
    --output_dir $(pwd)/reports/cross_encoder/wdcproducts80cc20rnd050un-$BATCH-$LR-$EPOCHS-roberta-base/ \
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
