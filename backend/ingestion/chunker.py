import spacy

_nlp = None

def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            from spacy.cli import download
            download("en_core_web_sm")
            _nlp = spacy.load("en_core_web_sm")
    return _nlp

def chunk_into_sentences(text: str) -> list[str]:
    nlp = get_nlp()
    doc = nlp(text)
    sentences = [
        sent.text.strip()
        for sent in doc.sents
        if len(sent.text.strip()) > 20  # filter noise
    ]
    return sentences