#!/usr/bin/env python

# Copyright 2020 Johns Hopkins University (Piotr Żelasko)
#  Apache 2.0  (http://www.apache.org/licenses/LICENSE-2.0)

import re
import logging
from collections import defaultdict
from sys import stdout
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pathlib import Path
from typing import NamedTuple, Dict, Optional

from tqdm import tqdm


logger = logging.getLogger()


def main():
    parser = ArgumentParser(
        description='Prepare train/dev/eval splits for various GlobalPhone languages.',
        formatter_class=ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--gp-path', required=True,
                        help='Path to GlobalPhone directory with each language'
                        ' in a subdirectory with its corresponding codename; '
                        'e.g. on JHU grid, "/export/corpora5/GlobalPhone" has'
                        'subdirectories like S0192 (Arabic) or S0196 (Czech).')
    parser.add_argument('--output-dir', default='data/GlobalPhone', required=True,
                        help='Output root with data directories for each language and split.')
    parser.add_argument('--languages', nargs='+', required=True,
                        default='Arabic Czech French Korean Mandarin Spanish Thai'.split(),
                        help='Which languages to prepare.')
    parser.add_argument('--romanized', action='store_true',
                        help='Use "rmn" directories in GlobalPhone transcripts if available.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Turn detailed logging on for debugging.')
    args = parser.parse_args()
    gp_path = Path(args.gp_path)
    data_dir = Path(args.output_dir)
    train_languages = args.languages
    romanized = args.romanized
    if args.verbose:
        fancy_logging()

    data_dir.mkdir(parents=True, exist_ok=True)
    assert gp_path.exists()

    for lang in tqdm(train_languages, desc='Preparing per-language data dirs'):
        logging.debug(f'Preparing language {lang}')
        # We need the following files
        #   text  utt2spk  wav.scp  segments  spk2utt
        # We'll create the last two outside of the script
        dataset = parse_gp(gp_path / LANG2CODE[lang] / lang, romanized=romanized, lang=lang)
        dataset.write(data_dir)


CODE2LANG = {
    'S0192': 'Arabic',
    'S0196': 'Czech',
    'S0197': 'French',
    'S0200': 'Korean',
    'S0193': 'Mandarin',
    'S0203': 'Spanish',
    'S0321': 'Thai',
}

LANG2CODE = {l: c for c, l in CODE2LANG.items()}

LANG2SPLIT = {
    'Arabic': {
        'dev': [5, 36, 107, 164],  # TODO: +6 TBA ?
        'eval': [27, 39, 108, 137],  # TODO: + 6 TBA ?
    },
    'Czech': {  # TODO: TBA ? ; (PZ) I put just one speaker to test the recipe
        'dev': [1],
        'eval': [2],
    },
    'French': {
        'dev': [1],  # TODO: no dev? I put one spk here
        'eval': list(range(91, 99)),  # 91-98
    },
    'Korean': {
        'dev': [6, 12, 25, 40, 45, 61, 84, 86, 91, 98],
        'eval': [19, 29, 32, 42, 51, 64, 69, 80, 82, 88],
    },
    'Mandarin': {
        'dev': list(range(28, 33)) + list(range(39, 45)),  # 28-32, 39-44
        'eval': list(range(80, 90))  # 80-89
    },
    'Spanish': {
        'dev': list(range(1, 11)),  # 1-10
        'eval': list(range(11, 19)),  # 11-18
    },
    'Thai': {
        'dev': [23, 25, 28, 37, 45, 61, 73, 85],
        'eval': list(range(101, 109)),  # 101-108
    },
}


class Segment(NamedTuple):
    recording_id: str
    start_seconds: float
    end_seconds: float


class DataDir(NamedTuple):
    wav_scp: Dict[bytes, bytes]
    text: Dict[bytes, bytes]
    utt2spk: Dict[bytes, bytes]

    def write(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        with open(data_dir / 'wav.scp', 'wb') as f:
            for k, v in self.wav_scp.items():
                f.write(k + b' ' + v + b'\n')
        with open(data_dir / 'text', 'wb') as f:
            for k, v in self.text.items():
                f.write(k + b' ' + v + b'\n')
        with open(data_dir / 'utt2spk', 'wb') as f:
            for k, v in self.utt2spk.items():
                f.write(k + b' ' + v + b'\n')


class GpDataset(NamedTuple):
    train: DataDir
    dev: DataDir
    eval: DataDir
    lang: str

    def write(self, data_root: Path):
        self.train.write(data_root / f'gp_{self.lang}_train')
        self.dev.write(data_root / f'gp_{self.lang}_dev')
        self.eval.write(data_root / f'gp_{self.lang}_eval')


def parse_gp(path: Path, lang: str, romanized=True):
    def make_id(path: Path) -> str:
        try:
            stem = path.stem
            if stem.endswith('adc.'):
                stem = stem[:-4] + '.adc'
            id = stem.split('.')[0]
            parts = id.split('_')
            return f'{parts[0]}_UTT{int(parts[1]):03d}'
        except:
            logging.error(f'Can\'t parse from {path}')
            raise

    audio_paths = list((path / 'adc').rglob('*.shn'))
    if not audio_paths:
        raise ValueError(f"No recordings found for {lang}! "
                         f"(looking for extension \".shn\" here: {path / 'adc'})")
    wav_scp = {
        make_id(p).encode('utf-8'): decompressed(p).encode('utf-8')
        for p in sorted(audio_paths)
    }
    logging.debug(f'There are {len(wav_scp)} audio files')

    tr_sfx = ('rmn' if romanized else 'trl')
    transcript_paths = list((path / tr_sfx).rglob(f'*.{tr_sfx}'))
    # If nothing found and romanized version was requested, try to fall back to non-romanized
    if not transcript_paths and tr_sfx == 'rmn':
        tr_sfx = 'trl'
        transcript_paths = list((path / tr_sfx).rglob(f'*.{tr_sfx}'))
        if not transcript_paths:
            raise ValueError(f"No transcripts found for {lang}! "
                             f"(looking for extensions (rmn,trl) in: {path}/(rmn,trl))")
    logging.debug(f'There are {len(transcript_paths)} transcript files')

    # NOTE: We are using bytes instead of str because some GP transcripts have non-Unicode symbols which fail to parse

    # easy to find parsing errors, as these values should never be used
    lang_short = next(iter(wav_scp.keys()))[:2]
    text = {}
    utt2spk = {}
    utt_id: Optional[bytes] = None  # e.g. AR059_UTT003
    spk_id: Optional[bytes] = None  # e.g. AR059
    num_utts = defaultdict(int)
    for p in sorted(transcript_paths):
        with p.open('rb') as f:
            for line in map(bytes.strip, f):
                m = re.match(rb';SprecherID .*?(\d+)', line, flags=re.I)  # case-independent because "SpReChErId"...
                if m is not None:
                    spk_id = f'{lang_short.decode()}{int(m.group(1).decode()):03d}'.encode('utf-8')
                    continue
                m = re.match(rb'; (\d+):', line)
                if m is not None:
                    utt_id = f'{spk_id.decode()}_UTT{int(m.group(1).decode()):03d}'.encode('utf-8')
                    continue
                assert spk_id is not None, f"No speaker ID at line {line}"
                assert utt_id is not None, f"No utterance ID at line {line}"
                text[utt_id] = remove_special_symbols(line)
                utt2spk[utt_id] = spk_id
                num_utts[spk_id] += 1

    # Diagnostics

    logging.debug(f'There is a total of {sum(num_utts.values())} utterances.')

    no_utt_speakers = [u for u, n in num_utts.items() if n == 0]
    if no_utt_speakers:
        logging.warning(f'There are {len(no_utt_speakers)}'
                        f' speakers with 0 utterances in language {lang}.')

    missing_recordings = set(wav_scp).difference(utt2spk)
    if missing_recordings:
        logging.warning(f'There are {len(missing_recordings)} missing {lang} utterance IDs out of {len(wav_scp)} total '
                        f'in wav.scp (use -v for details)')
        logging.debug(f'The following utterance IDs are missing in wav.scp: {b" ".join(sorted(missing_recordings))}')
    missing_transcripts = set(utt2spk).difference(wav_scp)
    if missing_transcripts:
        logging.warning(f'There are {len(missing_transcripts)} missing {lang} utterance IDs out of {len(text)} total '
                        f'in text and utt2spk (use -v for details)')
        logging.debug(
            f'The following utterance IDs are missing in text and utt2spk: {b" ".join(sorted(missing_transcripts))}')

    def number_of(utt_id):
        try:
            return int(utt_id[2:5])
        except:
            logging.error(f'Can\'t extract the number of utterance id {utt_id}')
            raise

    def select(table, split):
        if split == 'train':
            selected_ids = {
                utt_id for utt_id in text
                if all(
                    number_of(utt_id) not in LANG2SPLIT[lang][split_]
                    for split_ in ('dev', 'eval')
                )
            }
        else:
            selected_ids = {
                utt_id for utt_id in text
                if number_of(utt_id) in LANG2SPLIT[lang][split]
            }
        subset = {k: v for k, v in table.items() if k in selected_ids}
        assert all(k in subset for k in selected_ids)
        return subset

    return GpDataset(
        train=DataDir(
            wav_scp=select(wav_scp, 'train'),
            utt2spk=select(utt2spk, 'train'),
            text=select(text, 'train')
        ),
        dev=DataDir(
            wav_scp=select(wav_scp, 'dev'),
            utt2spk=select(utt2spk, 'dev'),
            text=select(text, 'dev')
        ),
        eval=DataDir(
            wav_scp=select(wav_scp, 'eval'),
            utt2spk=select(utt2spk, 'eval'),
            text=select(text, 'eval')
        ),
        lang=lang
    )


def fancy_logging(level=logging.DEBUG, stream=stdout):
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
        datefmt="%H:%M:%S",
        stream=stream
    )


def decompressed(path: Path) -> str:
    return f'shorten -x {path} - | sox -t raw -r 16000 -b 16 -e signed-integer - -t wav - |'


def remove_special_symbols(utt: bytes) -> bytes:
    # TODO: I don't know why these symbols appear in GP transcripts, we should find that out eventually
    return utt.replace(b'<s>', b'').replace(b'</s>', b'')


if __name__ == '__main__':
    main()
