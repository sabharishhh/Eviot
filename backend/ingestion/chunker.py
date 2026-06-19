import spacy
import numpy as np
from typing import List
from sklearn.metrics.pairwise import cosine_similarity

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


def _split_large_chunk(
    text: str,
    window_size: int = 6,
    overlap: int = 2,
) -> List[str]:

    nlp = get_nlp()

    sentences = [
        s.text.strip()
        for s in nlp(text).sents
        if len(s.text.strip()) > 15
    ]

    if len(sentences) <= window_size:
        return [text]

    chunks = []
    step = max(1, window_size - overlap)

    for i in range(0, len(sentences), step):
        chunk = " ".join(sentences[i : i + window_size])

        if chunk.strip():
            chunks.append(chunk)

        if i + window_size >= len(sentences):
            break

    return chunks


def chunk_into_sentences(
    text: str,
    encoder,
    min_sentence_length: int = 20,
    min_chunk_words: int = 40,
    max_chunk_words: int = 250,
) -> List[str]:
    """
    Semantic chunker using embedding similarity.
    Usage:
        chunks = chunk_into_sentences(text, encoder)
    Returns:
        List[str]
    """

    nlp = get_nlp()
    doc = nlp(text)

    sentences = [
        sent.text.strip()
        for sent in doc.sents
        if len(sent.text.strip()) >= min_sentence_length
    ]

    if not sentences:
        return []

    if len(sentences) <= 3:
        return [" ".join(sentences)]

    sentence_embeddings = encoder.encode(sentences)
    sentence_embeddings = np.asarray(sentence_embeddings)

    similarities = []

    for i in range(len(sentence_embeddings) - 1):
        sim = cosine_similarity(
            sentence_embeddings[i].reshape(1, -1),
            sentence_embeddings[i + 1].reshape(1, -1),
        )[0][0]

        similarities.append(float(sim))

    mean_sim = np.mean(similarities)
    std_sim = np.std(similarities)

    threshold = mean_sim - std_sim
    threshold = max(0.30, min(threshold, 0.80))

    breakpoints = []

    for idx, sim in enumerate(similarities):
        if sim < threshold:
            breakpoints.append(idx)

    chunks = []
    start = 0

    for bp in breakpoints:
        chunk = " ".join(sentences[start : bp + 1])
        if chunk.strip():
            chunks.append(chunk)
        start = bp + 1

    final_chunk = " ".join(sentences[start:])

    if final_chunk.strip():
        chunks.append(final_chunk)

    merged_chunks = []
    i = 0

    while i < len(chunks):
        current = chunks[i]

        if (
            len(current.split()) < min_chunk_words
            and i + 1 < len(chunks)
        ):
            current = current + " " + chunks[i + 1]
            i += 1

        merged_chunks.append(current)
        i += 1

    final_chunks = []

    for chunk in merged_chunks:
        if len(chunk.split()) > max_chunk_words:
            final_chunks.extend(
                _split_large_chunk(
                    chunk,
                    window_size=6,
                    overlap=2,
                )
            )
        else:
            final_chunks.append(chunk)

    return final_chunks