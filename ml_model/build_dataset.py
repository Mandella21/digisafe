"""
DigiSafe - Training Corpus Builder
===================================
Section 3.3.6 / 3.12.3 - Machine Learning Text Classification Module.

Builds the labelled corpus used to train the harassment-detection classifier.

IMPORTANT - HONEST DECLARATION OF DATA PROVENANCE
-------------------------------------------------
This is a CURATED, SYNTHETICALLY-EXPANDED corpus, not scraped production data.
It was authored for this project by combining hand-written seed messages
(reflecting harassment patterns documented in the Chapter 2 literature review
and localised to a Ghanaian context) with template-based combinatorial
expansion. This is consistent with the project scope declared in Section 6 of
the proposal, which states the prototype is "developed and demonstrated within
an academic environment using sample and simulated data".

Accuracy figures obtained on this corpus therefore measure how well the model
separates THESE classes of message. They must NOT be presented as real-world
harassment-detection accuracy. See ml_model/metrics.json for the caveat that
should accompany any figure quoted in the report.

Label schema
------------
seed_id   : identifier of the hand-written seed sentence a row was expanded
            from. Rows sharing a seed_id are surface variants of the SAME
            underlying message, so the train/test split MUST be grouped on
            this column - otherwise a variant of a test sentence appears in
            training and the reported accuracy is inflated. See train_model.py.
label     : 1 = abusive, 0 = non-abusive  (binary target)
category  : one of
            - Physical Violence / Life Threat
            - Blackmail / Non-Consensual Extortion
            - Cyberstalking / Intimidation
            - Severe Harassment / Defamation / Hate Speech
            - Non-Abusive                     (multiclass target)

Run:  python ml_model/build_dataset.py
"""

import csv
import itertools
import random
from pathlib import Path

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

DATA_DIR = Path(__file__).resolve().parent / "dataset"
OUTPUT_CSV = DATA_DIR / "harassment_dataset.csv"

CAT_VIOLENCE = "Physical Violence / Life Threat"
CAT_BLACKMAIL = "Blackmail / Non-Consensual Extortion"
CAT_STALKING = "Cyberstalking / Intimidation"
CAT_HARASSMENT = "Severe Harassment / Defamation / Hate Speech"
CAT_CLEAN = "Non-Abusive"


# ---------------------------------------------------------------------------
# 1. ABUSIVE SEED MESSAGES
# ---------------------------------------------------------------------------
# Hand-written seeds. Each is a realistic single message of the kind a victim
# would screenshot and submit as evidence.

VIOLENCE_SEEDS = [
    "i will kill you tonight",
    "you are going to die and nobody will find your body",
    "i swear i will beat you until you cannot walk again",
    "when i catch you i will break your legs",
    "i will slit your throat you useless thing",
    "i am coming to your hostel with a knife",
    "you will not see the end of this week alive",
    "i will burn your house down with you inside",
    "i will shoot you the day i see you in town",
    "keep talking and i will bury you myself",
    "i will smash your face until your own mother cannot recognise you",
    "watch your back because i am coming for you",
    "you will regret being born when i get my hands on you",
    "i will make sure you end up in the grave",
    "one more word and i will finish you completely",
    "i will hurt you so badly you will beg me to stop",
    "i will strangle you with my bare hands",
    "you are a dead person walking",
    "i will pour acid on your face",
    "i will deal with you until you learn your lesson permanently",
    "i will break your neck if you report me",
    "prepare your funeral because i am coming",
    "i will destroy you and everyone in your family",
    "your days on this earth are numbered",
    "i will stab you in front of everyone",
]

BLACKMAIL_SEEDS = [
    "send me money or i will leak your nudes",
    "pay me 2000 cedis by tomorrow or everyone sees your pictures",
    "i still have the videos and i will post them online",
    "if you block me i will send your photos to your father",
    "give me what i want or your whole church will see these images",
    "i will expose your private pictures to the whole campus",
    "cooperate with me or i will ruin your reputation forever",
    "i saved everything and i will share it with your employer",
    "your family will receive these videos if you do not reply",
    "i will post your private chats on facebook for everyone to read",
    "send more pictures or i release the ones i already have",
    "meet me tonight or the pictures go public",
    "i will tag your pastor in the photos if you ignore me",
    "you will pay me every month or i keep posting",
    "i am uploading your videos to telegram if you do not answer",
    "your scholarship will be gone when they see what i have",
    "do what i say or i will send this to your fiance",
    "i will share your private moments with your classmates",
    "transfer the money now or i publish everything tonight",
    "i have screenshots of everything and i will use them against you",
    "deny me again and your whole family sees the video",
    "i will destroy your marriage with these pictures",
]

STALKING_SEEDS = [
    "i know where you live and i am watching you",
    "i saw you at the junction today wearing the blue dress",
    "i followed you home yesterday and you did not even notice",
    "you cannot hide from me anywhere in this country",
    "i am outside your gate right now",
    "i know your lecture timetable and where you sit",
    "i have your new number even after you changed it",
    "i will find you no matter how many times you block me",
    "i know your mother works at the market on fridays",
    "i am tracking everywhere you go",
    "you changed your route today but i still saw you",
    "i will never leave you alone until you talk to me",
    "i have been watching your hostel window every night",
    "i know which trotro you take every morning",
    "you can run but i will always know where you are",
    "i created new accounts because you blocked the old ones",
    "i am counting the hours until i see you in person",
    "i took pictures of you today without you knowing",
    "your new address will not save you from me",
    "i will show up wherever you are until you respond",
]

HARASSMENT_SEEDS = [
    "you are a useless worthless whore",
    "nobody will ever love a disgusting pig like you",
    "you are stupid and everyone in class laughs at you",
    "you should just kill yourself and save everyone the trouble",
    "you are a shameless slut who sleeps with everyone",
    "you are the ugliest thing i have ever seen in my life",
    "you deserve to die alone you filthy animal",
    "everyone knows you are a liar and a fraud",
    "you disgust me you worthless piece of trash",
    "go and die somewhere nobody wants you here",
    "you are a stupid idiot who cannot do anything right",
    "i will tell everyone what a cheap girl you are",
    "you are a disgrace to your family and your tribe",
    "you are mentally retarded and should not be in university",
    "nobody respects you because you are a common prostitute",
    "you are trash and you will always be trash",
    "i will spread the rumour until nobody talks to you again",
    "you are a dirty liar and a thief",
    "shut up you brainless fool nobody asked you",
    "you are worthless and your existence is a mistake",
    "everyone in the hall thinks you are a joke",
    "you are a shameless disgusting creature",
]

# ---------------------------------------------------------------------------
# 2. NON-ABUSIVE SEED MESSAGES
# ---------------------------------------------------------------------------
# Ordinary, benign messages.

CLEAN_ORDINARY = [
    "please send me the lecture notes when you get a chance",
    "are we still meeting at the library at four",
    "happy birthday i hope you have a wonderful day",
    "the assignment deadline was moved to next friday",
    "i will be a bit late for the group meeting",
    "thank you so much for your help yesterday",
    "did you understand what the lecturer said about pointers",
    "can you send me the link to the recording",
    "let us meet at the department after the quiz",
    "i have submitted my project proposal today",
    "the exam timetable has been released on the portal",
    "please remind me to bring my student id tomorrow",
    "i really enjoyed the seminar this morning",
    "congratulations on passing your defence",
    "the bus to campus leaves at seven thirty",
    "i am travelling to kumasi this weekend for a wedding",
    "could you please review my code before i submit",
    "the wifi in the lab is very slow today",
    "let me know when you are free to discuss the report",
    "i finished reading chapter two of the textbook",
    "we should start revising for the mid semester exams",
    "please confirm whether you received my email",
    "the football match starts at eight tonight",
    "i will pay the hostel fees on monday",
    "good morning hope you slept well",
    "see you at church on sunday",
    "the printer in the office is out of toner",
    "i need to buy a new laptop charger",
    "my supervisor approved my chapter three",
    "the results will be published next month",
]

# Hard negatives: negative sentiment, conflict, or sadness, but NOT abuse.
# These stop the model from simply learning "negative words = abusive".
CLEAN_HARD_NEGATIVES = [
    "i am really angry about how the meeting went today",
    "i hate this course it is so difficult and stressful",
    "i am disappointed that you did not tell me the truth",
    "i think we should stop talking to each other for a while",
    "this is the worst service i have ever received",
    "i do not want to be in this relationship anymore",
    "you hurt my feelings when you said that in front of everyone",
    "i am frustrated because my code keeps crashing",
    "that was a terrible decision and i disagree completely",
    "i failed the quiz and i feel awful about it",
    "please stop calling me i need some space",
    "i am upset that my laptop was stolen last night",
    "the film was violent and disturbing and i did not enjoy it",
    "we had a serious argument and i said things i regret",
    "i am tired of always being the one who apologises",
    "my landlord is threatening to increase the rent again",
    "i reported the theft to the police this morning",
    "she was crying because she failed her exam",
    "the news said a man was killed in an accident on the highway",
    "i am studying criminal law including offences against the person",
    "our lecturer discussed cyberbullying and harassment in class today",
    "the article explains how victims of blackmail can get help",
    "i am writing my project on detecting abusive messages online",
    "the counsellor gave a talk about domestic violence awareness",
    "the horror movie had a scene where someone gets stabbed",
    "i deleted the game because it was too aggressive",
    "he shouted at the referee during the match",
    "the security officer warned us about people following students at night",
    "please report any suspicious person watching the hostel",
    "the seminar covered how to preserve digital evidence of threats",
    "i do not like him but i would never wish him harm",
    "we are debating whether the death penalty should be abolished",
    "my sister is annoying me but i still love her",
    "the boss criticised my presentation quite harshly",
    "the team lost badly and everyone was upset",
]


# ---------------------------------------------------------------------------
# 3. TEMPLATE-BASED EXPANSION
# ---------------------------------------------------------------------------
# Realistic surface variation: prefixes, suffixes, and light noise that mirror
# how these messages actually appear in chat logs.

ABUSIVE_PREFIXES = [
    "", "", "", "listen to me ", "i am telling you ", "hey ", "stupid girl ",
    "you better understand ", "for the last time ", "i swear to god ",
    "am warning you ", "look here ", "idiot ",
]

ABUSIVE_SUFFIXES = [
    "", "", "", " you hear me", " and i mean it", " idiot", " foolish girl",
    " so watch yourself", " and nobody can save you", " stupid",
    " and that is final", " you will see",
]

CLEAN_PREFIXES = [
    "", "", "", "hi ", "hello ", "good morning ", "please ", "hey ",
    "just checking in ", "quick question ", "by the way ",
]

CLEAN_SUFFIXES = [
    "", "", "", " thanks", " please", " let me know", " ok", " cheers",
    " talk soon", " have a good day", " god bless",
]


def expand(seeds, prefixes, suffixes, target_count, category, label, tag):
    """Expand seed messages into `target_count` labelled variants.

    Every row carries the `seed_id` of the sentence it was derived from so that
    training can hold out whole seeds rather than individual variants.
    """
    seed_ids = {seed: f"{tag}-{i:03d}" for i, seed in enumerate(seeds)}
    combos = list(itertools.product(seeds, prefixes, suffixes))
    random.shuffle(combos)

    rows, seen = [], set()
    for seed, pre, suf in combos:
        if len(rows) >= target_count:
            break
        text = f"{pre}{seed}{suf}".strip()
        text = " ".join(text.split())
        if text in seen:
            continue
        seen.add(text)
        rows.append({
            "text": text,
            "label": label,
            "category": category,
            "seed_id": seed_ids[seed],
        })
    return rows


def build():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    # Abusive classes - roughly balanced across the four categories.
    rows += expand(VIOLENCE_SEEDS, ABUSIVE_PREFIXES, ABUSIVE_SUFFIXES, 320, CAT_VIOLENCE, 1, "VIO")
    rows += expand(BLACKMAIL_SEEDS, ABUSIVE_PREFIXES, ABUSIVE_SUFFIXES, 320, CAT_BLACKMAIL, 1, "BLK")
    rows += expand(STALKING_SEEDS, ABUSIVE_PREFIXES, ABUSIVE_SUFFIXES, 300, CAT_STALKING, 1, "STK")
    rows += expand(HARASSMENT_SEEDS, ABUSIVE_PREFIXES, ABUSIVE_SUFFIXES, 320, CAT_HARASSMENT, 1, "HAR")

    # Non-abusive: ordinary messages plus a substantial block of hard negatives.
    rows += expand(CLEAN_ORDINARY, CLEAN_PREFIXES, CLEAN_SUFFIXES, 640, CAT_CLEAN, 0, "CLN")
    rows += expand(CLEAN_HARD_NEGATIVES, CLEAN_PREFIXES, CLEAN_SUFFIXES, 620, CAT_CLEAN, 0, "HRD")

    random.shuffle(rows)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["text", "label", "category", "seed_id"])
        writer.writeheader()
        writer.writerows(rows)

    abusive = sum(r["label"] for r in rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_CSV}")
    print(f"  abusive     : {abusive}")
    print(f"  non-abusive : {len(rows) - abusive}")
    print("  category breakdown:")
    for cat in (CAT_VIOLENCE, CAT_BLACKMAIL, CAT_STALKING, CAT_HARASSMENT, CAT_CLEAN):
        print(f"    {cat:45s} {sum(1 for r in rows if r['category'] == cat)}")


if __name__ == "__main__":
    build()
