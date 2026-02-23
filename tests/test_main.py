"""
__main__ のテスト。サブコマンド分岐と exit コード。
"""

import sys
from unittest.mock import MagicMock

import pytest


def test_main_no_subcommand_exits_one_and_prints_usage(capsys):
    """サブコマンドなしは使用法を stderr に出力して exit(1)。"""
    import wiki_extract.__main__ as main_mod
    orig_argv = sys.argv
    sys.argv = ['prog']
    try:
        with pytest.raises(SystemExit) as exc_info:
            main_mod.main()
        assert exc_info.value.code == 1
    finally:
        sys.argv = orig_argv
    err = capsys.readouterr().err
    assert 'extract-pages' in err
    assert 'ai-characters-filter' in err


def test_main_extract_pages_calls_main(monkeypatch):
    """extract-pages で main_extract_pages が呼ばれ exit(0)。"""
    import wiki_extract.__main__ as main_mod
    mock_extract = MagicMock()
    monkeypatch.setattr(main_mod, 'main_extract_pages', mock_extract)
    orig_argv = sys.argv
    sys.argv = ['prog', 'extract-pages']
    try:
        with pytest.raises(SystemExit) as exc_info:
            main_mod.main()
        assert exc_info.value.code == 0
    finally:
        sys.argv = orig_argv
    mock_extract.assert_called_once()


def test_main_extract_character_candidates_calls_main(monkeypatch):
    """extract-character-candidates で main_extract_character_candidates が呼ばれ exit(0)。"""
    import wiki_extract.__main__ as main_mod
    mock_candidates = MagicMock()
    monkeypatch.setattr(main_mod, 'main_extract_character_candidates', mock_candidates)
    orig_argv = sys.argv
    sys.argv = ['prog', 'extract-character-candidates']
    try:
        with pytest.raises(SystemExit) as exc_info:
            main_mod.main()
        assert exc_info.value.code == 0
    finally:
        sys.argv = orig_argv
    mock_candidates.assert_called_once()


def test_main_ai_characters_filter_calls_main(monkeypatch):
    """ai-characters-filter で main_ai_characters_filter が呼ばれ exit(0)。"""
    import wiki_extract.__main__ as main_mod
    mock_filter = MagicMock()
    monkeypatch.setattr(main_mod, 'main_ai_characters_filter', mock_filter)
    orig_argv = sys.argv
    sys.argv = ['prog', 'ai-characters-filter']
    try:
        with pytest.raises(SystemExit) as exc_info:
            main_mod.main()
        assert exc_info.value.code == 0
    finally:
        sys.argv = orig_argv
    mock_filter.assert_called_once()


def test_main_ai_characters_split_calls_main(monkeypatch):
    """ai-characters-split で main_ai_characters_split が呼ばれ exit(0)。"""
    import wiki_extract.__main__ as main_mod
    mock_split = MagicMock()
    monkeypatch.setattr(main_mod, 'main_ai_characters_split', mock_split)
    orig_argv = sys.argv
    sys.argv = ['prog', 'ai-characters-split']
    try:
        with pytest.raises(SystemExit) as exc_info:
            main_mod.main()
        assert exc_info.value.code == 0
    finally:
        sys.argv = orig_argv
    mock_split.assert_called_once()
