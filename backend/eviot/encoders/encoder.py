import os
import torch
from openai import OpenAI

class Encoder:
    def __init__(self, model_name="text-embedding-3-small", device=None):
        """
        Drop-in replacement for the HuggingFace BGE encoder.
        Requires the OPENAI_API_KEY environment variable to be set.
        """
        self.model_name = model_name
        # The device parameter is kept for compatibility with older code,
        # but OpenAI handles the compute remotely.
        self.device = device 
        
        # Initialize the synchronous OpenAI client
        self.client = OpenAI()

    def encode(self, texts):
        # OpenAI expects a list, even for a single string
        if isinstance(texts, str):
            texts = [texts]
            
        # Call the OpenAI API
        response = self.client.embeddings.create(
            input=texts,
            model=self.model_name
        )
        
        # Extract the embeddings (1536 dimensions for text-embedding-3-small)
        embeddings = [data.embedding for data in response.data]
        
        # Return exactly what eviot math expects: a PyTorch tensor on the CPU
        return torch.tensor(embeddings, dtype=torch.float32)