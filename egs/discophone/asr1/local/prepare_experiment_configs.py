#!/usr/bin/env python
from pathlib import Path

CONF_DIR = Path("conf/experiments")
BABEL_LANGS_OF_INTEREST = frozenset("101 103 107 203 206 307 402 404".split())
GLOBALPHONE_LANGS_OF_INTEREST = frozenset(
    "Czech French Mandarin Spanish Thai".split()
)

CONF_TEMPLATE = """
# BABEL TRAIN:
# Amharic - 307
# Bengali - 103
# Cantonese - 101
# Javanese - 402
# Vietnamese - 107
# Zulu - 206
# BABEL TEST:
# Georgian - 404
# Lao - 203
babel_langs="{BABEL_LANGS}"
babel_recog="{BABEL_RECOG_LANGS}"
gp_langs="{GLOBALPHONE_LANGS}"
gp_recog="{GLOBALPHONE_RECOG_LANGS}"
mboshi_train={MBOSHI_TRAIN}
mboshi_recog={MBOSHI_RECOG}
gp_romanized=false
phone_tokens={PHONE_TOKENS}
"""

CONF_DIR.mkdir(parents=True, exist_ok=True)

for phone_tokens in ("true", "false"):
    phn = "phonetokens" if phone_tokens == "true" else "phones"
    # Monolingual schemes
    for babel_lang in BABEL_LANGS_OF_INTEREST:
        config = CONF_TEMPLATE.format(
            BABEL_LANGS=babel_lang,
            BABEL_RECOG_LANGS=babel_lang,
            GLOBALPHONE_LANGS="",
            GLOBALPHONE_RECOG_LANGS="",
            MBOSHI_TRAIN="false",
            MBOSHI_RECOG="false",
            PHONE_TOKENS=phone_tokens,
        )
        (CONF_DIR / f"monolingual-{babel_lang}-{phn}.conf").write_text(config)
    for gp_lang in GLOBALPHONE_LANGS_OF_INTEREST:
        config = CONF_TEMPLATE.format(
            BABEL_LANGS="",
            BABEL_RECOG_LANGS="",
            GLOBALPHONE_LANGS=gp_lang,
            GLOBALPHONE_RECOG_LANGS=gp_lang,
            MBOSHI_TRAIN="false",
            MBOSHI_RECOG="false",
            PHONE_TOKENS=phone_tokens,
        )
        (CONF_DIR / f"monolingual-{gp_lang}-{phn}.conf").write_text(config)
    # MBOSHI
    #config = CONF_TEMPLATE.format(
    #    BABEL_LANGS="",
    #    BABEL_RECOG_LANGS="",
    #    GLOBALPHONE_LANGS="",
    #    GLOBALPHONE_RECOG_LANGS="",
    #    MBOSHI_TRAIN="true",
    #    MBOSHI_RECOG="true",
    #    USE_IPA="true",
    #)
    #(CONF_DIR / f"monolingual-mboshi-ipa.conf").write_text(config)

    # Leave-one-out schemes
    for babel_lang in BABEL_LANGS_OF_INTEREST:
        config = CONF_TEMPLATE.format(
            BABEL_LANGS=" ".join(BABEL_LANGS_OF_INTEREST - {babel_lang}),
            BABEL_RECOG_LANGS=babel_lang,
            GLOBALPHONE_LANGS=" ".join(GLOBALPHONE_LANGS_OF_INTEREST),
            GLOBALPHONE_RECOG_LANGS="",
            MBOSHI_TRAIN="false",
            MBOSHI_RECOG="false",
            PHONE_TOKENS=phone_tokens,
        )
        (CONF_DIR / f"oneout-{babel_lang}-{phn}.conf").write_text(config)
    for gp_lang in GLOBALPHONE_LANGS_OF_INTEREST:
        config = CONF_TEMPLATE.format(
            BABEL_LANGS=" ".join(BABEL_LANGS_OF_INTEREST),
            BABEL_RECOG_LANGS="",
            GLOBALPHONE_LANGS=" ".join(GLOBALPHONE_LANGS_OF_INTEREST - {gp_lang}),
            GLOBALPHONE_RECOG_LANGS=gp_lang,
            MBOSHI_TRAIN="false",
            MBOSHI_RECOG="false",
            PHONE_TOKENS=phone_tokens,
        )
        (CONF_DIR / f"oneout-{gp_lang}-{phn}.conf").write_text(config)
    # MBOSHI
    #config = CONF_TEMPLATE.format(
    #    BABEL_LANGS=" ".join(BABEL_LANGS_OF_INTEREST),
    #    BABEL_RECOG_LANGS="",
    #    GLOBALPHONE_LANGS=" ".join(GLOBALPHONE_LANGS_OF_INTEREST),
    #    GLOBALPHONE_RECOG_LANGS="",
    #    MBOSHI_TRAIN="false",
    #    MBOSHI_RECOG="true",
    #    USE_IPA="true",
    #)
    #(CONF_DIR / f"oneout-mboshi-ipa.conf").write_text(config)

    # Train-all-test-all scheme
    config = CONF_TEMPLATE.format(
        BABEL_LANGS=" ".join(BABEL_LANGS_OF_INTEREST),
        BABEL_RECOG_LANGS=" ".join(BABEL_LANGS_OF_INTEREST),
        GLOBALPHONE_LANGS=" ".join(GLOBALPHONE_LANGS_OF_INTEREST),
        GLOBALPHONE_RECOG_LANGS=" ".join(GLOBALPHONE_LANGS_OF_INTEREST),
        MBOSHI_TRAIN="false",
        MBOSHI_RECOG="false",
        PHONE_TOKENS=phone_tokens,
    )
    (CONF_DIR / f"all-{phn}.conf").write_text(config)
