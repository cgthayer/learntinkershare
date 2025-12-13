#!/usr/bin/env python3

import chromadb
from chromadb.utils import embedding_functions
import numpy as np


def main():
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"  # Sentence transformer model
    )
    data = ["I like to walk", "I like to run", "I like to hike"]
    embeddings = embedding_fn(data[:3])
    print("Pairwise sentences (cosine):")
    for i in range(3):
        for j in range(3):
            sim = cosine_similarity(embeddings[i], embeddings[j])
            print(f"* {data[i]:>20} <-> {data[j]:<20}: {sim:.4f}")

    unexpected = "I like to sprint"
    print(f"Similarity to \"{unexpected}\":")
    uvec = embedding_fn([unexpected])[0]  # unexpected vector (embedding)
    data = ["I like to walk", "I like to run", "I like to hike"]
    for i in range(3):
        sim = cosine_similarity(uvec, embeddings[i])
        print(f"* {data[i]}: {sim:.2f}")


def cosine_similarity(vec1, vec2):
    dot_product = np.dot(vec1, vec2)
    norm_product = np.linalg.norm(vec1) * np.linalg.norm(vec2)
    return dot_product / norm_product


if __name__ == "__main__":
    main()
