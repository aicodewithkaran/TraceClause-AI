import re
from typing import List, Dict

class ChunkingEngine:
    """Semantic section/clause chunker to preserve legal context."""

    CLAUSE_PATTERN = re.compile(
        r'(?=\n(?:SECTION|Section|CLAUSE|Clause|ARTICLE|Article|\d+\.|\([a-z0-9]+\))\s+)', 
        re.MULTILINE
    )

    @classmethod
    def split_into_clauses(cls, text: str) -> List[Dict[str, str]]:
        # Remove page separators for logical chunking
        clean_text = re.sub(r'--- Page \d+ ---', '', text)
        
        # Split by regex matching contract numbering patterns
        raw_chunks = cls.CLAUSE_PATTERN.split(clean_text)
        clauses = []
        
        chunk_idx = 1
        for chunk in raw_chunks:
            cleaned = chunk.strip()
            if len(cleaned) < 30: # Skip header noise or tiny whitespace splits
                continue
            
            # Extract header title if available
            first_line = cleaned.split('\n')[0][:60]
            clauses.append({
                "clause_number": chunk_idx,
                "clause_name": first_line if len(first_line) > 5 else f"Clause {chunk_idx}",
                "text": cleaned
            })
            chunk_idx += 1

        # Fallback if text didn't contain explicit Section headers
        if not clauses:
            paragraphs = clean_text.split('\n\n')
            for idx, p in enumerate(paragraphs, 1):
                if len(p.strip()) > 30:
                    clauses.append({
                        "clause_number": idx,
                        "clause_name": f"Paragraph {idx}",
                        "text": p.strip()
                    })

        return clauses
