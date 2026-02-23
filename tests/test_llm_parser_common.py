"""
llm/parser_common のテスト。env_int, resolve_llm_options, add_llm_common_args。
"""

import os
import sys

import pytest

from wiki_extract.llm import client as llm_client
from wiki_extract.llm import parser_common as pc


def test_env_int_unset(monkeypatch):
    """キー未設定なら default。"""
    monkeypatch.delenv('WIKI_LLM_WORKERS', raising=False)
    assert pc.env_int('WIKI_LLM_WORKERS', 4) == 4


def test_env_int_empty(monkeypatch):
    """空文字・空白なら default。"""
    monkeypatch.setenv('WIKI_LLM_WORKERS', '')
    assert pc.env_int('WIKI_LLM_WORKERS', 4) == 4
    monkeypatch.setenv('WIKI_LLM_WORKERS', '  ')
    assert pc.env_int('WIKI_LLM_WORKERS', 4) == 4


def test_env_int_valid(monkeypatch):
    """正の整数ならその値。"""
    monkeypatch.setenv('WIKI_LLM_WORKERS', '8')
    assert pc.env_int('WIKI_LLM_WORKERS', 4) == 8


def test_env_int_invalid(monkeypatch):
    """非数なら default。"""
    monkeypatch.setenv('WIKI_LLM_WORKERS', 'abc')
    assert pc.env_int('WIKI_LLM_WORKERS', 4) == 4


def test_make_llm_parser_has_options():
    """パーサに provider, model, batch-size, workers, timeout が付く。"""
    p = pc.make_llm_parser('desc', 'WIKI_LLM_FILTER_BATCH_SIZE', llm_client.DEFAULT_LLM_FILTER_BATCH_SIZE)
    assert p.parse_args(['--provider', 'ollama', '--model', 'x', '--batch-size', '10', '--workers', '2', '--timeout', '60'])
    # パースできるのでオプションは存在する
    args = p.parse_args(['--provider', 'ollama'])
    assert args.provider == 'ollama'
    assert hasattr(args, 'batch_size')
    assert hasattr(args, 'workers')
    assert hasattr(args, 'timeout')


def test_resolve_llm_options_from_args(monkeypatch):
    """args の値が使われる。"""
    monkeypatch.delenv('WIKI_LLM_PROVIDER', raising=False)
    monkeypatch.delenv('WIKI_LLM_MODEL', raising=False)
    class Args:
        provider = 'ollama'
        model = 'custom'
        batch_size = 5
        workers = 3
        timeout = 120
    got = pc.resolve_llm_options(Args())
    assert got[0] == 'ollama'
    assert got[1] == 'custom'
    assert got[2] == 5
    assert got[3] == 3
    assert got[4] == 120


def test_resolve_llm_options_from_env(monkeypatch):
    """args に無い場合は Env、model 無しならプロバイダ別既定。"""
    monkeypatch.setenv('WIKI_LLM_PROVIDER', 'gemini')
    monkeypatch.delenv('WIKI_LLM_MODEL', raising=False)
    monkeypatch.delenv('WIKI_LLM_DEFAULT_MODEL_GEMINI', raising=False)
    class Args:
        provider = None
        model = ''
        batch_size = 1
        workers = 1
        timeout = 300
    got = pc.resolve_llm_options(Args())
    assert got[0] == 'gemini'
    assert got[1] == llm_client.DEFAULT_LLM_MODEL_GEMINI


def test_resolve_llm_options_batch_size_clamped():
    """batch_size が 0 以下なら 1 になる。"""
    class Args:
        provider = 'gemini'
        model = 'm'
        batch_size = 0
        workers = 1
        timeout = 300
    got = pc.resolve_llm_options(Args())
    assert got[2] == 1


def test_resolve_llm_options_workers_clamped():
    """workers が 0 なら 1 になる。"""
    class Args:
        provider = 'gemini'
        model = 'm'
        batch_size = 1
        workers = 0
        timeout = 300
    got = pc.resolve_llm_options(Args())
    assert got[3] == 1


def test_log_llm_batch_header(capsys):
    """ログが stderr に出力される。"""
    pc.log_llm_batch_header(
        'Title', 'ollama', 'http://x/api/chat', 'm', 10, 2, 60,
        100, 5, 0, 100,
    )
    err = capsys.readouterr().err
    assert 'Title' in err
    assert 'ollama' in err
    assert 'API:' in err


def test_log_ollama_connection_refused_hint(capsys):
    """案内メッセージが出力される。"""
    pc.log_ollama_connection_refused_hint()
    err = capsys.readouterr().err
    assert 'LLM_OLLAMA_BASE_URL' in err
