#!/bin/bash

# Copyright 2020 Johns Hopkins University (Piotr Żelasko)
# Copyright 2018 Johns Hopkins University (Matthew Wiesner)
#  Apache 2.0  (http://www.apache.org/licenses/LICENSE-2.0)

. ./path.sh || exit 1;
. ./cmd.sh || exit 1;

# general configuration
phone_tokens=false  # when true, it will use ['a', ':']; when false, it will use ['a:']
backend=pytorch
stage=0        # start from 0 if you need to start from data preparation
stop_stage=100
ngpu=1         # number of gpus ("0" uses cpu, otherwise use gpu)
seed=1
debugmode=1
dumpdir=dump   # directory to dump full features
N=0            # number of minibatches to be used (mainly for debugging). "0" uses all minibatches.
verbose=0      # verbose option
resume=        # Resume the training from snapshot

# feature configuration
do_delta=false

train_config=conf/train_li10.yaml
lm_config=conf/lm.yaml
decode_config=conf/decode_li10.yaml

# rnnlm related
use_lm=false
lm_resume=        # specify a snapshot file to resume LM training
lmtag=            # tag for managing LMs

# decoding parameter
recog_model=model.acc.best # set a model to be used for decoding: 'model.acc.best' or 'model.loss.best'

# exp tag
tag="" # tag for managing experiments.

# Generate configs with local/prepare_experiment_configs.py
langs_config=

if [ $langs_config ]; then
  # shellcheck disable=SC1090
  source $langs_config
else
  # BABEL TRAIN:
  # Amharic - 307
  # Bengali - 103
  # Cantonese - 101
  # Javanese - 402
  # Vietnamese - 107
  # Zulu - 206
  # Dutch (CGN) Fake Babel Code - 505
  # BABEL TEST:
  # Georgian - 404
  # Lao - 203
  babel_langs="307 103 101 402 107 206 505"
  babel_recog="${babel_langs} 404 203"
  gp_langs="Czech French Mandarin Spanish Thai"
  gp_recog="${gp_langs}"
  mboshi_train=false
  mboshi_recog=true
  gp_romanized=false
  ipa_transcript=false
fi

. utils/parse_options.sh || exit 1;

# Set bash to 'debug' mode, it will exit on :
# -e 'error', -u 'undefined variable', -o ... 'error in pipeline', -x 'print commands',
set -e
set -u
set -o pipefail

# Train Directories
train_set=train
train_dev=dev

# LM Directories
if [ -z ${lmtag} ]; then
    lmtag=$(basename ${lm_config%.*})
fi
lmexpname=train_rnnlm_${backend}_${lmtag}
lmexpdir=exp/${lmexpname}
lm_train_set=data/local/train.txt
lm_valid_set=data/local/dev.txt

recog_set=""
for l in ${babel_recog} ${gp_recog}; do
  recog_set="eval_${l} ${recog_set}"
done
recog_set=${recog_set%% }

phone_token_opt='--phones'
if [ $phone_tokens = true ]; then
  phone_token_opt='--phone-tokens'
fi

# This step will create the data directories for GlobalPhone and Babel languages.
# It's also going to use LanguageNet G2P models to convert text into phonetic transcripts.
# Depending on the settings, it will either transcribe into phones, e.g. ([m], [i:], [t]), or
# phonetic tokens, e.g. (/m/, /i/, /:/, /t/).
# The Kaldi "text" file will consist of these phonetic sequences, as we're trying to build
# a universal IPA recognizer.
# The lexicons are created separately for each split as an artifact from the ESPnet setup.
if ((stage <= 0)); then
  echo "stage 0: Setting up individual languages"
  local/setup_languages.sh \
    --langs "${babel_langs}" \
    --recog "${babel_recog}" \
    --gp-langs "${gp_langs}" \
    --gp-recog "${gp_recog}" \
    --mboshi-train "${mboshi_train}" \
    --mboshi-recog "${mboshi_recog}" \
    --gp-romanized "${gp_romanized}" \
    --phone_token_opt "${phone_token_opt}" \
    --multilang true
  for x in ${train_set} ${dev_set} ${recog_set}; do
    sed -i.bak -e "s/$/ sox -R -t wav - -t wav - rate 16000 dither | /" data/${x}/wav.scp
  done
fi



feat_tr_dir=${dumpdir}/${train_set}/delta${do_delta}; mkdir -p ${feat_tr_dir}
feat_dt_dir=${dumpdir}/${train_dev}/delta${do_delta}; mkdir -p ${feat_dt_dir}
if [ ${stage} -le 1 ] && [ ${stop_stage} -ge 1 ]; then
  echo "stage 1: Feature extraction"
  fbankdir=fbank
  # Generate the fbank features; by default 80-dimensional fbanks with pitch on each frame
  for x in ${train_set} ${train_dev} ${recog_set}; do
    steps/make_fbank_pitch.sh --cmd "$train_cmd" --nj 80 --write_utt2num_frames true \
        data/${x} exp/make_fbank/${x} ${fbankdir}
    utils/fix_data_dir.sh data/${x}
  done

  mv data/${train_set} data/${train_set}_org
  mv data/${train_dev} data/${train_dev}_org
  remove_longshortdata.sh --maxframes 3000 --maxchars 400 data/${train_set}_org data/${train_set}
  remove_longshortdata.sh --maxframes 3000 --maxchars 400 data/${train_dev}_org data/${train_dev}

  # compute global CMVN
  compute-cmvn-stats scp:data/${train_set}/feats.scp data/${train_set}/cmvn.ark
  utils/fix_data_dir.sh data/${train_set}

  exp_name=$(basename $PWD)
  # dump features for training
  if [[ $(hostname -f) == *.clsp.jhu.edu ]] && [ ! -d ${feat_tr_dir}/storage ]; then
  utils/create_split_dir.pl \
      /export/b{10,11,12,13}/${USER}/espnet-data/egs/babel/${exp_name}/dump/${train_set}/delta${do_delta}/storage \
      ${feat_tr_dir}/storage
  fi
  if [[ $(hostname -f) == *.clsp.jhu.edu ]] && [ ! -d ${feat_dt_dir}/storage ]; then
  utils/create_split_dir.pl \
      /export/b{10,11,12,13}/${USER}/espnet-data/egs/babel/${exp_name}/dump/${train_dev}/delta${do_delta}/storage \
      ${feat_dt_dir}/storage
  fi
  dump.sh --cmd "$train_cmd" --nj 20 --do_delta ${do_delta} \
      data/${train_set}/feats.scp data/${train_set}/cmvn.ark exp/dump_feats/train ${feat_tr_dir}
  dump.sh --cmd "$train_cmd" --nj 10 --do_delta ${do_delta} \
      data/${train_dev}/feats.scp data/${train_set}/cmvn.ark exp/dump_feats/dev ${feat_dt_dir}
  for rtask in ${recog_set}; do
      feat_recog_dir=${dumpdir}/${rtask}/delta${do_delta}; mkdir -p ${feat_recog_dir}
      dump.sh --cmd "$train_cmd" --nj 10 --do_delta ${do_delta} \
            data/${rtask}/feats.scp data/${train_set}/cmvn.ark exp/dump_feats/recog/${rtask} \
            ${feat_recog_dir}
  done
fi

dict=data/lang_1char/${train_set}_units.txt
nlsyms=data/lang_1char/non_lang_syms.txt

trans_type="phn"
if $phone_tokens; then
    trans_type="char"
fi

echo "dictionary: ${dict}"
if [ ${stage} -le 2 ] && [ ${stop_stage} -ge 2 ]; then
    ### Task dependent. You have to check non-linguistic symbols used in the corpus.
    echo "stage 2: Dictionary and Json Data Preparation"
    mkdir -p data/lang_1char/

    echo "make a non-linguistic symbol list"
    # The grep trick prevents grep from returning non-zero value when no special symbol is found,
    # which would have prematurely ended the script.
    cut -f 2- -d' ' data/${train_set}/text | tr " " "\n" | sort | uniq | { grep "<" || true; } > ${nlsyms}
    cat ${nlsyms}

    echo "make a dictionary"
    echo "<unk> 1" > ${dict} # <unk> must be 1, 0 will be used for "blank" in CTC
    text2token.py -t ${trans_type} -s 1 -n 1 -l ${nlsyms} data/${train_set}/text | cut -f 2- -d" " | tr " " "\n" \
    | sort | uniq | grep -v -e '^\s*$' | grep -v '<unk>' | awk '{print $0 " " NR+1}' >> ${dict}
    wc -l ${dict}

    echo "make json files"
    data2json.sh --feat ${feat_tr_dir}/feats.scp --nlsyms ${nlsyms} \
         data/${train_set} ${dict} > ${feat_tr_dir}/data.json
    data2json.sh --feat ${feat_dt_dir}/feats.scp --nlsyms ${nlsyms} \
         data/${train_dev} ${dict} > ${feat_dt_dir}/data.json
    for rtask in ${recog_set}; do
        feat_recog_dir=${dumpdir}/${rtask}/delta${do_delta}
        data2json.sh --feat ${feat_recog_dir}/feats.scp \
            --nlsyms ${nlsyms} data/${rtask} ${dict} > ${feat_recog_dir}/data.json
    done
fi


if ${use_lm}; then
  lm_train_set=data/local/train.txt
  lm_valid_set=data/local/dev.txt

  # Make train and valid
  text2token.py -t ${trans_type} \
                 --nchar 1 \
                --space "<space>" \
                --non-lang-syms data/lang_1char/non_lang_syms.txt \
                <(cut -d' ' -f2- data/${train_set}/text | head -100) \
                > ${lm_train_set}

  text2token.py -t ${trans_type} \
                --nchar 1 \
                --space "<space>" \
                --non-lang-syms data/lang_1char/non_lang_syms.txt \
                <(cut -d' ' -f2- data/${train_dev}/text | head -100) \
                > ${lm_valid_set}

  ${cuda_cmd} --gpu ${ngpu} ${lmexpdir}/train.log \
          lm_train.py \
          --config ${lm_config} \
          --ngpu ${ngpu} \
          --backend ${backend} \
          --verbose 1 \
          --outdir ${lmexpdir} \
          --tensorboard-dir tensorboard/${lmexpname} \
          --train-label ${lm_train_set} \
          --valid-label ${lm_valid_set} \
          --resume ${lm_resume} \
          --dict ${dict}
fi


if [ -z ${tag} ]; then
    expname=${train_set}_${backend}_$(basename ${train_config%.*})
    if ${do_delta}; then
        expname=${expname}_delta
    fi
else
    expname=${train_set}_${backend}_${tag}
fi
expdir=exp/${expname}
mkdir -p ${expdir}

if [ ${stage} -le 3 ] && [ ${stop_stage} -ge 3 ]; then
    echo "stage 3: Network Training"

    ${cuda_cmd} --gpu ${ngpu} ${expdir}/train.log \
        asr_train.py \
        --config ${train_config} \
        --ngpu ${ngpu} \
        --backend ${backend} \
        --outdir ${expdir}/results \
        --tensorboard-dir tensorboard/${expname} \
        --debugmode ${debugmode} \
        --dict ${dict} \
        --debugdir ${expdir} \
        --minibatches ${N} \
        --verbose ${verbose} \
        --resume ${resume} \
        --seed ${seed} \
        --train-json ${feat_tr_dir}/data.json \
        --valid-json ${feat_dt_dir}/data.json
fi


if [ ${stage} -le 4 ] && [ ${stop_stage} -ge 4 ]; then
    echo "stage 4: Decoding"
    nj=32

    extra_opts=""
    if ${use_lm}; then
      extra_opts="--rnnlm ${lmexpdir}/rnnlm.model.best ${extra_opts}"
    fi

    pids=() # initialize pids
    for rtask in ${recog_set}; do
    (
        decode_dir=decode_${rtask}_$(basename ${decode_config%.*})
        if ${use_lm}; then
            decode_dir=${decode_dir}_rnnlm_${lmtag}
        fi
        feat_recog_dir=${dumpdir}/${rtask}/delta${do_delta}

        # split data
        splitjson.py --parts ${nj} ${feat_recog_dir}/data.json

        #### use CPU for decoding
        ngpu=0

        ${decode_cmd} JOB=1:${nj} ${expdir}/${decode_dir}/log/decode.JOB.log \
            asr_recog.py \
            --config ${decode_config} \
            --ngpu ${ngpu} \
            --backend ${backend} \
            --recog-json ${feat_recog_dir}/split${nj}utt/data.JOB.json \
            --result-label ${expdir}/${decode_dir}/data.JOB.json \
            --model ${expdir}/results/${recog_model}  \
            ${extra_opts}

        score_sclite.sh --wer true --nlsyms ${nlsyms} ${expdir}/${decode_dir} ${dict}

    ) &
    pids+=($!) # store background pids
    done
    i=0; for pid in "${pids[@]}"; do wait ${pid} || ((++i)); done
    [ ${i} -gt 0 ] && echo "$0: ${i} background jobs are failed." && false
    echo "Finished"
fi
