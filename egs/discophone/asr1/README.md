# DiscoPhone Recipe

This recipe is based mostly on the ESPNet Babel recipe.

## Setting Up Experiments
To setup an experiment (using one or more languages in training) simply run
from this directory ...

`./setup_ipa_experiments.sh`

This will create about 20 directories next to this one, each one set up to run an experiment
from the paper [That Sounds Familiar: an Analysis of Phonetic Representations Transfer Across Languages](https://arxiv.org/abs/2005.08118).

You will need Babel and GlobalPhone corpora to run the experiments.
Babel paths should be adapted in `conf/lang.conf`.
GlobalPhone path should be adapted in `local/setup_languages.sh`.

For more details about the experiments and rationale, please read the [paper](https://arxiv.org/abs/2005.08118).
For more details about how this recipe is set up, see the [Babel recipe](https://github.com/espnet/espnet/tree/master/egs/babel/asr1).

## Running Experiments
To run the experiment do 

`cd ../expname`

If you ran `setup_ipa_experiments.sh`, then each directory will have pre-configured set of languages to use in train and test.
Assuming you have the corpora and the paths are all set up, It is sufficient to simply run:

`./run.sh`

