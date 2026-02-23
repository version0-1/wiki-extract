"""
config のテスト。_env_path と parse_args（環境変数・オプション）。
"""

import importlib
import sys
from pathlib import Path

import pytest

from wiki_extract.util import config


def test_env_path_unset(monkeypatch):
    """環境変数未設定なら default の Path。"""
    monkeypatch.delenv('WIKI_DATA_DIR', raising=False)
    assert config._env_path('WIKI_DATA_DIR', '/data') == Path('/data')


def test_env_path_set(monkeypatch):
    """環境変数設定時はその Path。"""
    monkeypatch.setenv('WIKI_DATA_DIR', '/custom/data')
    assert config._env_path('WIKI_DATA_DIR', '/data') == Path('/custom/data')


def test_env_path_blank_uses_default(monkeypatch):
    """空白のみのときは default。"""
    monkeypatch.setenv('WIKI_DATA_DIR', '   ')
    assert config._env_path('WIKI_DATA_DIR', '/data') == Path('/data')


def test_parse_args_defaults(monkeypatch):
    """オプションなしなら Env または既定の Path、workers は None。"""
    monkeypatch.delenv('WIKI_DATA_DIR', raising=False)
    monkeypatch.delenv('WIKI_OUTPUT_DIR', raising=False)
    importlib.reload(config)
    monkeypatch.setattr(sys, 'argv', ['prog'])
    args = config.parse_args()
    assert args.data_dir == Path('/data')
    assert args.output_dir == Path('/out')
    assert args.workers is None


def test_parse_args_data_dir_from_cli(monkeypatch, tmp_path):
    """--data-dir で上書き。"""
    monkeypatch.setattr(sys, 'argv', ['prog', '--data-dir', str(tmp_path)])
    args = config.parse_args()
    assert args.data_dir == tmp_path


def test_parse_args_output_dir_and_workers(monkeypatch, tmp_path):
    """--output-dir と --workers を指定。"""
    out = tmp_path / 'out'
    monkeypatch.setattr(sys, 'argv', ['prog', '--output-dir', str(out), '--workers', '4'])
    args = config.parse_args()
    assert args.output_dir == out
    assert args.workers == 4
