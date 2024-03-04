import math
import re
from typing import List
from transformers import AutoTokenizer

class TextChunker:
    '''
    Instead of using arbitrary character limit, we use the number of tokens as the chunk size.
    This gurantees that we stay within the token limit and len() runs faster on tokenized strings.

    Args:
        text (str): The text to be chunked
        chunk_size (int): The number of tokens per chunk
        chunk_minimum (int): The minimum number of tokens per chunk
        tokenizer (str): The name of the tokenizer to be used
    '''
    def __init__(self, chunk_size=250, chunk_minimum=50, tokenizer="BAAI/bge-large-zh-v1.5"):
        self.chunk_size = chunk_size
        self.chunk_minimum = chunk_minimum
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer)


    '''
    Chunk the text into smaller chunks. Recursively split the text into smaller chunks if the text is too large.

    Args:
        text (str): The text to be chunked
        seperator (str)[]: The regex seperator to be used to split the text into smaller chunks.
    '''
    def chunk(self, text, seperators):
        chunks = self.recursive_chunk(text, seperators)

        # Post processing to remove empty chunks and combine neighboring chunks if they're below the chunk minimum
        processed_chunks = []
        for i in range(len(chunks)):
            if self._len(chunks[i]) < self.chunk_minimum:
                # If we can merge with previous chunk, merge
                # Else if, we can merge with next chunk, merge
                # Else just leave it alone

                if i > 0 and processed_chunks and self._len(processed_chunks[-1]) + self._len(chunks[i]) <= self.chunk_size:
                    processed_chunks[-1] += chunks[i]
                elif i < len(chunks) - 1 and self._len(chunks[i]) + self._len(chunks[i+1]) <= self.chunk_size:
                    chunks[i+1] = chunks[i] + chunks[i+1]
                else:
                    # Double check that the chunk is not a bunch of empty spaces or newline characters
                    if not chunks[i].isspace():
                        processed_chunks.append(chunks[i])
            else:
                processed_chunks.append(chunks[i])
        
        return processed_chunks

    def recursive_chunk(self, text, seperators: List[str]) -> List[str]:
        final_chunks = []
        if self._len(text) <= self.chunk_size:
            return [text]
        else:
            if len(seperators) == 0:
                return self.simple_chunk(text)
            # Grab the most high priority seperator at seperators[-1]
            seperator = seperators.pop()
            chunks = self._split_text_with_regex(text, seperator, True)
            for chunk in chunks:
                if self._len(chunk) <= self.chunk_size:
                    final_chunks.append(chunk)
                else:
                    final_chunks += self.recursive_chunk(chunk, seperators)
        return final_chunks

    '''
    When you can't split a text any logical way, split it into individual characters
    i.e. : aksjdniwndiqwndiqjwndiwqndjiqwndijqwndijqwndiqjwndiqjwndijqwdniqjwdnijqwndijqndijwqndwqijnqjiwd
    '''
    def simple_chunk(self, text):
        token_count = self._len(text)
        estimated_chunks = math.ceil(token_count/self.chunk_size)
        chunks = list(self.split_text_evenly(text, estimated_chunks))

        # math.ceil should help us get the right number of chunks, but in edge cases it might not
        # This should ever loop once, if ever, but just in case, we'll loop until we get the right number of chunks
        while not (self.verify_chunks(chunks)):
            estimated_chunks += 1
            chunks = list(self.split_text_evenly(text, estimated_chunks))
        
        return chunks

    def split_text_evenly(self, text, num_chunks):
        k, m = divmod(len(text), num_chunks)
        return (text[i*k+min(i, m):(i+1)*k+min(i+1, m)] for i in range(num_chunks))

    def verify_chunks(self, chunks):
        for chunk in chunks:
            if self._len(chunk) > self.chunk_size:
                return False
        return True

    def _len(self, text):
        return len(self.tokenizer.encode(text))
    
    # Credit to langchain for this helper function
    def _split_text_with_regex(
        self, text: str, separator: str, keep_separator: bool
    ) -> List[str]:
        if separator:
            if keep_separator:
                _splits = re.split(f"({separator})", text)
                splits = [_splits[i] + _splits[i + 1] for i in range(1, len(_splits), 2)]
                if len(_splits) % 2 == 0:
                    splits += _splits[-1:]
                splits = [_splits[0]] + splits
            else:
                splits = re.split(separator, text)
        else:
            splits = list(text)
        return [s for s in splits if s != ""]