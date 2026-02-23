"""
オプション・環境変数の組み合わせテスト。
CLI と Env の「未設定／設定／オプションで上書き」を parametrize で検証する。
"""

import sys
from pathlib import Path

import pytest

from wiki_extract import util
from wiki_extract.extract import extract_pages
from wiki_extract.llm import client as llm_client
from wiki_extract.llm import parser_common as pc


# ---- util/config (extract-pages 用の data-dir / output-dir は config と extract_pages の両方で使う) ----


def test_config_env_data_dir_set(monkeypatch, tmp_path):
    """_env_path: WIKI_DATA_DIR 設定時はその Path。"""
    monkeypatch.setenv('WIKI_DATA_DIR', str(tmp_path))
    assert util.config._env_path('WIKI_DATA_DIR', '/data') == tmp_path


def test_config_cli_overrides_env(monkeypatch, tmp_path):
    """--data-dir は Env より優先（parse_args で明示指定）。"""
    other = tmp_path / 'other'
    other.mkdir()
    monkeypatch.setattr(sys, 'argv', ['prog', '--data-dir', str(other)])
    args = util.config.parse_args()
    assert args.data_dir == other


def test_config_workers_optional(monkeypatch):
    """--workers 未指定なら None。"""
    monkeypatch.setattr(sys, 'argv', ['prog'])
    args = util.config.parse_args()
    assert args.workers is None


def test_config_workers_specified(monkeypatch, tmp_path):
    """--workers 指定時はその整数。"""
    monkeypatch.setattr(sys, 'argv', ['prog', '--data-dir', str(tmp_path), '--workers', '4'])
    args = util.config.parse_args()
    assert args.workers == 4


# ---- llm/parser_common ----


@pytest.mark.parametrize('env_value,default,expected', [
    (None, 10, 10),
    ('', 10, 10),
    ('   ', 10, 10),
    ('5', 10, 5),
    ('invalid', 10, 10),
])
def test_env_int_combinations(monkeypatch, env_value, default, expected):
    """env_int: 未設定・空・数値・不正の組み合わせ。"""
    key = 'WIKI_LLM_TEST_KEY'
    if env_value is None:
        monkeypatch.delenv(key, raising=False)
    else:
        monkeypatch.setenv(key, env_value)
    assert pc.env_int(key, default) == expected


def test_resolve_llm_options_provider_cli_overrides_env(monkeypatch):
    """--provider は WIKI_LLM_PROVIDER より優先。"""
    monkeypatch.setenv('WIKI_LLM_PROVIDER', 'gemini')
    class Args:
        provider = 'ollama'
        model = 'm'
        batch_size = 1
        workers = 1
        timeout = 300
    got = pc.resolve_llm_options(Args())
    assert got[0] == 'ollama'


def test_resolve_llm_options_model_from_env(monkeypatch):
    """model が args に無いときは WIKI_LLM_MODEL。"""
    monkeypatch.setenv('WIKI_LLM_PROVIDER', 'ollama')
    monkeypatch.setenv('WIKI_LLM_MODEL', 'custom-model')
    monkeypatch.delenv('WIKI_LLM_DEFAULT_MODEL_OLLAMA', raising=False)
    class Args:
        provider = 'ollama'
        model = ''
        batch_size = 1
        workers = 1
        timeout = 300
    got = pc.resolve_llm_options(Args())
    assert got[1] == 'custom-model'


def test_resolve_llm_options_batch_size_cli_overrides_env(monkeypatch):
    """--batch-size は WIKI_LLM_FILTER_BATCH_SIZE より優先。"""
    monkeypatch.setenv('WIKI_LLM_FILTER_BATCH_SIZE', '50')
    class Args:
        provider = 'gemini'
        model = 'm'
        batch_size = 15
        workers = 1
        timeout = 300
    got = pc.resolve_llm_options(Args())
    assert got[2] == 15


def test_resolve_llm_options_timeout_env(monkeypatch):
    """WIKI_LLM_TIMEOUT が args の default として使われる（parse_args 経由で）。"""
    monkeypatch.setenv('WIKI_LLM_TIMEOUT', '600')
    p = pc.make_llm_parser('d', 'WIKI_LLM_FILTER_BATCH_SIZE', 30)
    args = p.parse_args(['--provider', 'gemini'])
    assert args.timeout == 600


# ---- llm/client ----


def test_resolve_ollama_chat_url_unset_default(monkeypatch):
    """LLM_OLLAMA_BASE_URL 未設定なら既定ベース + /api/chat。"""
    monkeypatch.delenv('LLM_OLLAMA_BASE_URL', raising=False)
    url = llm_client.resolve_ollama_chat_url()
    assert url.endswith('/api/chat')
    assert '11434' in url


def test_resolve_ollama_chat_url_set_and_trailing_slash(monkeypatch):
    """設定かつ末尾スラッシュでも /api/chat が重複しない。"""
    monkeypatch.setenv('LLM_OLLAMA_BASE_URL', 'http://host:11434/')
    url = llm_client.resolve_ollama_chat_url()
    assert url == 'http://host:11434/api/chat'


def test_resolve_gemini_api_url_base_from_env(monkeypatch):
    """LLM_GEMINI_BASE_URL 設定時はそのベース。"""
    monkeypatch.setenv('LLM_GEMINI_BASE_URL', 'https://custom.example.com')
    url = llm_client._resolve_gemini_api_url('model-x', 'key-y')
    assert 'custom.example.com' in url
    assert 'model-x' in url
    assert 'key=key-y' in url


# ---- characters/ai_characters_filter: parse_args, _resolve_exclude_list_path ----


def test_ai_filter_parse_args_defaults(monkeypatch):
    """既定では input-list が out/character_candidates.csv。"""
    monkeypatch.delenv('WIKI_LLM_PROVIDER', raising=False)
    monkeypatch.delenv('WIKI_LLM_MODEL', raising=False)
    from wiki_extract.characters import ai_characters_filter as af
    monkeypatch.setattr(sys, 'argv', ['prog'])
    args = af.parse_args()
    assert args.input_list == Path('out/character_candidates.csv')
    assert args.output_target is None
    assert args.output_excluded is None
    assert args.exclude_list is None


def test_ai_filter_resolve_exclude_list_cli_overrides(monkeypatch, tmp_path):
    """--exclude-list 指定時はそのパス。"""
    from wiki_extract.characters import ai_characters_filter as af
    p = tmp_path / 'exclude.json'
    p.touch()
    class Args:
        exclude_list = p
    got = af._resolve_exclude_list_path(Args())
    assert got == p


def test_ai_filter_resolve_exclude_list_env(monkeypatch, tmp_path):
    """--exclude-list 未指定で WIKI_EXCLUDE_LIST ありならその Path。"""
    from wiki_extract.characters import ai_characters_filter as af
    monkeypatch.setenv('WIKI_EXCLUDE_LIST', str(tmp_path / 'env_exclude.json'))
    class Args:
        exclude_list = None
    got = af._resolve_exclude_list_path(Args())
    assert 'env_exclude' in str(got)


# ---- characters/ai_characters_split: parse_args ----


def test_ai_split_parse_args_defaults(monkeypatch):
    """既定では input-target が out/characters_target.csv。"""
    monkeypatch.delenv('WIKI_LLM_PROVIDER', raising=False)
    monkeypatch.delenv('WIKI_LLM_MODEL', raising=False)
    from wiki_extract.characters import ai_characters_split as asp
    monkeypatch.setattr(sys, 'argv', ['prog'])
    args = asp.parse_args()
    assert args.input_target == Path('out/characters_target.csv')
    assert args.output is None


def test_ai_split_parse_args_batch_size_env(monkeypatch):
    """WIKI_LLM_SPLIT_BATCH_SIZE が batch_size の default。"""
    monkeypatch.setenv('WIKI_LLM_SPLIT_BATCH_SIZE', '25')
    monkeypatch.delenv('WIKI_LLM_PROVIDER', raising=False)
    monkeypatch.delenv('WIKI_LLM_MODEL', raising=False)
    from wiki_extract.characters import ai_characters_split as asp
    monkeypatch.setattr(sys, 'argv', ['prog'])
    args = asp.parse_args()
    assert args.batch_size == 25


# ---- extract/extract_pages: parse_args ----


def test_extract_pages_parse_args_env(monkeypatch, tmp_path):
    """extract_pages の parse_args は WIKI_DATA_DIR / WIKI_OUTPUT_DIR を既定に使う。"""
    monkeypatch.setenv('WIKI_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('WIKI_OUTPUT_DIR', str(tmp_path / 'out'))
    monkeypatch.setattr(sys, 'argv', ['prog'])
    args = extract_pages.parse_args()
    assert args.data_dir == tmp_path / 'data'
    assert args.output_dir == tmp_path / 'out'


def test_extract_pages_parse_args_cli_overrides(monkeypatch, tmp_path):
    """--data-dir / --output-dir は Env より優先。"""
    d = tmp_path / 'data'
    o = tmp_path / 'out'
    d.mkdir()
    o.mkdir()
    monkeypatch.setenv('WIKI_DATA_DIR', '/default')
    monkeypatch.setenv('WIKI_OUTPUT_DIR', '/default')
    monkeypatch.setattr(sys, 'argv', ['prog', '--data-dir', str(d), '--output-dir', str(o)])
    args = extract_pages.parse_args()
    assert args.data_dir == d
    assert args.output_dir == o
