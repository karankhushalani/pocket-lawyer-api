import base64
import io
import re

import pdfplumber
from openai import AsyncOpenAI

from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def extract_text_from_pdf(file_bytes: bytes) -> str:
    text_pages: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                cleaned = _clean_page(page_text)
                text_pages.append(cleaned)
    return "\n\n".join(text_pages)


def _clean_page(text: str) -> str:
    lines = text.splitlines()
    filtered: list[str] = []
    for line in lines:
        stripped = line.strip()
        if re.fullmatch(r'\d+', stripped):
            continue
        if re.fullmatch(r'Page \d+ of \d+', stripped, re.IGNORECASE):
            continue
        filtered.append(line)
    result = '\n'.join(filtered)
    result = re.sub(r' {2,}', ' ', result)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


async def extract_text_from_image(file_bytes: bytes) -> str:
    b64 = base64.b64encode(file_bytes).decode('utf-8')
    data_url = f'data:image/png;base64,{b64}'
    response = await client.chat.completions.create(
        model='gpt-4o',
        messages=[
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'text',
                        'text': (
                            'Extract all text from this legal document image. '
                            'Preserve formatting, section numbers, and clause structure.'
                        ),
                    },
                    {
                        'type': 'image_url',
                        'image_url': {'url': data_url},
                    },
                ],
            },
        ],
        max_tokens=4096,
    )
    return response.choices[0].message.content or ''


async def chunk_text(
    text: str, chunk_size: int = 800, overlap: int = 150
) -> list[str]:
    paragraphs = re.split(r'\n\s*\n', text.strip())
    chunks: list[str] = []
    buffer = ''

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(buffer) + len(para) <= chunk_size:
            buffer = (buffer + '\n\n' + para).strip() if buffer else para
            continue

        if buffer:
            chunks.append(buffer)
            buffer = _overlap_tail(buffer, overlap)

        sentences = re.split(r'(?<=[.!?])\s+', para)
        for sent in sentences:
            if not sent.strip():
                continue
            if len(buffer) + len(sent) <= chunk_size:
                buffer = (buffer + ' ' + sent).strip() if buffer else sent
            else:
                if buffer:
                    chunks.append(buffer)
                buffer = _overlap_tail(buffer, overlap) if buffer else ''
                sent_words = sent.split()
                for i in range(0, len(sent_words), chunk_size):
                    word_group = ' '.join(sent_words[i : i + chunk_size])
                    chunks.append(word_group)
                buffer = ''

    if buffer:
        chunks.append(buffer)

    return chunks


def _overlap_tail(text: str, overlap: int) -> str:
    words = text.split()
    if len(words) <= overlap:
        return text
    return ' '.join(words[-overlap:])


