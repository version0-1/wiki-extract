"""
Ollama / Gemini 共通の LLM 呼び出しとプロンプト読み込み。
"""

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

# デフォルト値（.env で未設定・コメントアウト時はこれらをソース側で使用）
DEFAULT_LLM_OLLAMA_BASE_URL = 'http://host.docker.internal:11434'  # Env にはベース URL のみ。/api/chat はコードで付与
DEFAULT_LLM_GEMINI_BASE_URL = 'https://us-central1-aiplatform.googleapis.com'  # Vertex AI 既定リージョン
DEFAULT_LLM_PROVIDER = 'gemini'
DEFAULT_LLM_MODEL_OLLAMA = 'gemma3:4b'
DEFAULT_LLM_MODEL_GEMINI = 'gemini-2.5-flash-lite'
DEFAULT_LLM_FILTER_BATCH_SIZE = 30
DEFAULT_LLM_SPLIT_BATCH_SIZE = 30
DEFAULT_LLM_WORKERS = 1
DEFAULT_LLM_TIMEOUT = 300
DEFAULT_GEMINI_RETRY_ATTEMPTS = 3
DEFAULT_GEMINI_RETRY_BACKOFF = 2.0

# Vertex AI の一時的な 404/429/503 用リトライ（Env で上書き可）
_GEMINI_RETRY_CODES = (404, 429, 500, 503)


def _gemini_retry_attempts() -> int:
    return max(1, int(os.environ.get('GEMINI_RETRY_ATTEMPTS') or DEFAULT_GEMINI_RETRY_ATTEMPTS))


def _gemini_retry_backoff() -> float:
    return max(0.5, float(os.environ.get('GEMINI_RETRY_BACKOFF') or DEFAULT_GEMINI_RETRY_BACKOFF))

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / 'data' / 'prompts'


def resolve_ollama_chat_url() -> str:
    """
    Ollama の /api/chat エンドポイント URL を返す。
    環境変数 LLM_OLLAMA_BASE_URL（ベース URL のみ。/api/chat は書かない）を参照し、
    未設定時は http://host.docker.internal:11434。末尾に /api/chat を付与して返す。
    """
    base = (os.environ.get('LLM_OLLAMA_BASE_URL') or '').strip() or DEFAULT_LLM_OLLAMA_BASE_URL
    return base.rstrip('/') + '/api/chat'


def _resolve_gemini_api_url(model: str, api_key: str) -> str:
    """
    Gemini（Vertex AI）の generateContent API の URL を返す。
    環境変数 LLM_GEMINI_BASE_URL を参照。未設定時は Vertex AI のデフォルト（us-central1）を使用。
    """
    base = (os.environ.get('LLM_GEMINI_BASE_URL') or '').strip() or DEFAULT_LLM_GEMINI_BASE_URL
    base = base.rstrip('/')
    return f'{base}/v1/publishers/google/models/{model}:generateContent?key={api_key}'


def load_prompt(name: str) -> str:
    """
    プロンプトを data/prompts/{name}.txt から読み込む。
    見つからない場合は空文字を返す。
    """
    path = _PROMPTS_DIR / f'{name}.txt'
    if not path.is_file():
        return ''
    return path.read_text(encoding='utf-8').strip()


def call_llm(
    provider: str,
    api_url: str,
    model: str,
    messages: list[dict],
    timeout: int,
    *,
    api_key: str | None = None,
) -> str:
    """
    共通 LLM 呼び出し。provider は 'ollama' または 'gemini'。
    messages は [ {"role": "system"|"user"|"assistant", "content": "..." }, ... ]。
    Gemini（Vertex AI）の場合は GEMINI_API_KEY または GOOGLE_API_KEY を設定すること。
    """
    if provider.lower() == 'gemini':
        return _call_gemini(model=model, messages=messages, timeout=timeout, api_key=api_key)
    return _call_ollama(api_url=api_url, model=model, messages=messages, timeout=timeout)


def call_llm_chat(
    provider: str,
    api_url: str,
    model: str,
    system_content: str,
    user_content: str,
    timeout: int,
    *,
    few_shot: list[dict] | None = None,
    api_key: str | None = None,
) -> str:
    """
    system + 任意の few_shot（user/assistant のリスト）+ user でメッセージを組み立てて call_llm する。
    split（few-shot あり）や filter（few-shot なし）で共通利用。
    """
    messages = [{'role': 'system', 'content': system_content}]
    if few_shot:
        messages.extend(few_shot)
    messages.append({'role': 'user', 'content': user_content})
    return call_llm(provider, api_url, model, messages, timeout, api_key=api_key)


def _call_ollama(api_url: str, model: str, messages: list[dict], timeout: int) -> str:
    """Ollama 互換 API（/api/chat）に POST。"""
    body = {
        'model': model,
        'messages': messages,
        'stream': False,
        'options': {'temperature': 0},
    }
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    api_key = os.environ.get('OLLAMA_API_KEY') or os.environ.get('WIKI_LLM_API_KEY')
    if api_key and ('ollama.com' in api_url or 'ollama.com' in api_url.split('//')[-1].split('/')[0]):
        headers['Authorization'] = f'Bearer {api_key}'
    req = urllib.request.Request(api_url, data=data, method='POST', headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        result = json.loads(res.read().decode('utf-8'))
    msg = result.get('message', {})
    content = msg.get('content')
    if content is None:
        raise RuntimeError(f'Ollama エラー: {result.get("error", "不明なエラー")}')
    return content


def _call_gemini(
    model: str,
    messages: list[dict],
    timeout: int,
    api_key: str | None = None,
) -> str:
    """Vertex AI Gemini generateContent API を呼び出し。接続先は LLM_GEMINI_BASE_URL で指定。"""
    key = (api_key or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY') or os.environ.get('WIKI_LLM_API_KEY') or '').strip()
    if not key:
        raise RuntimeError(
            'Vertex AI 利用には環境変数 GEMINI_API_KEY または GOOGLE_API_KEY を設定してください。'
            ' .env に記載し、docker-compose の env_file で渡すこと。'
        )
    url = _resolve_gemini_api_url(model=model, api_key=key)

    system_parts = [m['content'] for m in messages if m.get('role') == 'system']
    system_instruction = system_parts[0] if system_parts else None
    rest = [m for m in messages if m.get('role') != 'system']

    contents = []
    for m in rest:
        role = m.get('role', 'user')
        content = m.get('content', '')
        gemini_role = 'model' if role in ('model', 'assistant') else 'user'
        contents.append({'role': gemini_role, 'parts': [{'text': content}]})

    body = {
        'contents': contents,
        'generationConfig': {'temperature': 0},
    }
    if system_instruction:
        body['systemInstruction'] = {'parts': [{'text': system_instruction}]}

    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    last_error: Exception | None = None
    for attempt in range(_gemini_retry_attempts()):
        try:
            req = urllib.request.Request(url, data=data, method='POST', headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as res:
                result = json.loads(res.read().decode('utf-8'))
            break
        except urllib.error.HTTPError as e:
            if e.code == 400:
                try:
                    body = e.read().decode('utf-8', errors='replace')
                    err_detail = json.loads(body) if body.strip() else {}
                    err_obj = err_detail.get('error') if isinstance(err_detail.get('error'), dict) else {}
                    msg = err_obj.get('message', body[:500] if body else str(e))
                except Exception:
                    msg = str(e)
                raise RuntimeError(
                    f'Vertex AI 400 Bad Request: {msg}. '
                    '入力が長すぎる場合は --batch-size を小さく（例: 20）してください。'
                ) from e
            if e.code == 401:
                raise RuntimeError(
                    'Vertex AI 401 Unauthorized: API キーが無効か未設定です。'
                    ' .env の GEMINI_API_KEY（または GOOGLE_API_KEY）を確認し、'
                    ' Google Cloud コンソールでキー発行・Vertex AI API 有効化をしてください。'
                ) from e
            if e.code in _GEMINI_RETRY_CODES and attempt < _gemini_retry_attempts() - 1:
                time.sleep(_gemini_retry_backoff() * (2**attempt))
                last_error = e
                continue
            raise
    else:
        if last_error is not None:
            raise last_error
        raise RuntimeError('Vertex AI: リトライが予期せず終了しました')
    cands = result.get('candidates')
    if not cands:
        raise RuntimeError(f'Vertex AI エラー: {result.get("error", result)}')
    parts = cands[0].get('content', {}).get('parts', [])
    if not parts:
        return ''
    return parts[0].get('text', '')
