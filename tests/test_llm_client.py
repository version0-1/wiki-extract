"""
llm/client のテスト。resolve_ollama_chat_url, _resolve_gemini_api_url, load_prompt。
"""

import os

import pytest

from wiki_extract.llm import client as llm_client


def test_resolve_ollama_chat_url_unset(monkeypatch):
    """LLM_OLLAMA_BASE_URL 未設定なら既定 URL + /api/chat。"""
    monkeypatch.delenv('LLM_OLLAMA_BASE_URL', raising=False)
    got = llm_client.resolve_ollama_chat_url()
    assert got.endswith('/api/chat')
    assert 'host.docker.internal' in got or '11434' in got


def test_resolve_ollama_chat_url_set(monkeypatch):
    """設定時はそのベース + /api/chat。"""
    monkeypatch.setenv('LLM_OLLAMA_BASE_URL', 'http://localhost:11434')
    got = llm_client.resolve_ollama_chat_url()
    assert got == 'http://localhost:11434/api/chat'


def test_resolve_ollama_chat_url_trailing_slash(monkeypatch):
    """末尾スラッシュは重複しない。"""
    monkeypatch.setenv('LLM_OLLAMA_BASE_URL', 'http://localhost:11434/')
    got = llm_client.resolve_ollama_chat_url()
    assert got == 'http://localhost:11434/api/chat'


def test_resolve_gemini_api_url():
    """返り URL に model と key= が含まれる。"""
    got = llm_client._resolve_gemini_api_url('gemini-2', 'my-key')
    assert 'gemini-2' in got
    assert 'key=my-key' in got or 'key=' in got


def test_resolve_gemini_api_url_env_base(monkeypatch):
    """LLM_GEMINI_BASE_URL が設定されていればそのベース。"""
    monkeypatch.setenv('LLM_GEMINI_BASE_URL', 'https://custom.example.com')
    got = llm_client._resolve_gemini_api_url('m', 'k')
    assert 'custom.example.com' in got
    assert '/v1/publishers/google/models/m:generateContent' in got


def test_load_prompt_missing():
    """存在しないプロンプト名は空文字。"""
    got = llm_client.load_prompt('nonexistent_prompt_xyz')
    assert got == ''


def test_load_prompt_exists(tmp_path, monkeypatch):
    """data/prompts にファイルがあればその内容。"""
    prompts_dir = tmp_path / 'prompts'
    prompts_dir.mkdir()
    (prompts_dir / 'filter_system.txt').write_text('system prompt', encoding='utf-8')
    monkeypatch.setattr(llm_client, '_PROMPTS_DIR', prompts_dir)
    got = llm_client.load_prompt('filter_system')
    assert 'system prompt' in got
