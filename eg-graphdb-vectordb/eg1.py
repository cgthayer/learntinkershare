"""
Simple example: Calculating embeddings and semantic distances
For developers learning about vector databases and similarity search
"""

import chromadb
from chromadb.utils import embedding_functions
import numpy as np


def main():
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="average_word_embeddings_glove.6B.300d"  # Word-optimized model
    )
    data = ["walk", "run", "hike"]
    embeddings = embedding_fn(data[:3])
    print(f"Embedding vector eg: sz={len(embeddings[0])}:\n  {embeddings[0][:5]}...\n")
    print("Pairwise cosine similarities (0-1, 1.0=same):")
    for i in range(3):
        for j in range(3):
            sim = cosine_similarity(embeddings[i], embeddings[j])
            print(f"* {data[i]:>6} <-> {data[j]:<6}: {sim:.4f}")


def cosine_similarity(vec1, vec2):
    dot_product = np.dot(vec1, vec2)
    norm_product = np.linalg.norm(vec1) * np.linalg.norm(vec2)
    return dot_product / norm_product


if __name__ == "__main__":
    main()
