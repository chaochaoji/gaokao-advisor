import re
from langchain_text_splitters import RecursiveCharacterTextSplitter


class ZhangXuefengTextSplitter:
    STRATEGIES = {
        "live_transcript": {
            "primary_separator": r"\n?(?:问|家长|同学)[：:]",
            "fallback": ["\n\n", "\n"],
            "chunk_size": 800,
            "overlap": 100,
        },
        "social_post": {
            "primary_separator": r"\n---+\n",
            "fallback": ["\n\n"],
            "chunk_size": 1500,
            "overlap": 50,
        },
        "article": {
            "primary_separator": r"\n#{1,3}\s",
            "fallback": ["\n\n", "\n"],
            "chunk_size": 600,
            "overlap": 100,
        },
        "book_chapter": {
            "primary_separator": r"第[一二三四五六七八九十\d]+[章节]",
            "fallback": ["\n\n", "\n"],
            "chunk_size": 1000,
            "overlap": 80,
        },
    }

    def split_text(self, raw_text, content_type, metadata):
        strategy = self.STRATEGIES.get(content_type, self.STRATEGIES["article"])
        safe_chunks = self._primary_split(raw_text, strategy["primary_separator"])
        splitter = RecursiveCharacterTextSplitter(
            separators=strategy["fallback"],
            chunk_size=strategy["chunk_size"],
            chunk_overlap=strategy["overlap"],
        )
        result = []
        for i, chunk in enumerate(safe_chunks):
            if len(chunk) <= strategy["chunk_size"]:
                result.append(chunk)
            else:
                result.extend(splitter.split_text(chunk))
        return [
            {"content": c, "metadata": {**metadata, "chunk_index": i}}
            for i, c in enumerate(result)
        ]

    def _primary_split(self, text, pattern):
        parts = re.split(f"({pattern})", text)
        merged = []
        i = 0
        while i < len(parts):
            if re.match(pattern, parts[i]) and i + 1 < len(parts):
                merged.append(parts[i] + parts[i + 1])
                i += 2
            else:
                if parts[i].strip():
                    merged.append(parts[i])
                i += 1
        return merged or [text]
