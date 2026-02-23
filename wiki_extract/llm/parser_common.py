"""
LLM 利用コマンド用の共通 argparse ヘルパー。
"""

import argparse
import os

from wiki_extract.llm.client import (
    DEFAULT_LLM_FILTER_BATCH_SIZE,
    DEFAULT_LLM_MODEL_GEMINI,
    DEFAULT_LLM_MODEL_OLLAMA,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_SPLIT_BATCH_SIZE,
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_LLM_WORKERS,
)


def env_int(key: str, default: int) -> int:
    """環境変数を int で返す。未設定・不正時は default。"""
    v = os.environ.get(key)
    if v is None or not str(v).strip():
        return default
    try:
        return int(v)
    except ValueError:
        return default


def add_llm_common_args(
    parser,
    *,
    batch_size_env: str = 'WIKI_LLM_FILTER_BATCH_SIZE',
    batch_size_default: int = DEFAULT_LLM_FILTER_BATCH_SIZE,
    include_provider: bool = True,
    include_workers: bool = True,
) -> None:
    """
    ArgumentParser に LLM 共通オプションを追加する。
    batch_size_env / batch_size_default で filter 用・split 用を切り替え。
    """
    if include_provider:
        parser.add_argument(
            '--provider',
            type=str,
            default=os.environ.get('WIKI_LLM_PROVIDER') or DEFAULT_LLM_PROVIDER,
            choices=('ollama', 'gemini'),
            help='LLM プロバイダ。既定: WIKI_LLM_PROVIDER または gemini',
        )
    parser.add_argument(
        '--model',
        type=str,
        default=os.environ.get('WIKI_LLM_MODEL', ''),
        help='モデル名。既定: WIKI_LLM_MODEL またはプロバイダ別（WIKI_LLM_DEFAULT_MODEL_OLLAMA / WIKI_LLM_DEFAULT_MODEL_GEMINI）',
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=env_int(batch_size_env, batch_size_default),
        help=f'1回のAPIに渡す件数。既定: {batch_size_env}',
    )
    if include_workers:
        parser.add_argument(
            '--workers',
            type=int,
            default=env_int('WIKI_LLM_WORKERS', DEFAULT_LLM_WORKERS),
            help='並列LLM呼び出し数。既定: WIKI_LLM_WORKERS',
        )
    parser.add_argument(
        '--timeout',
        type=int,
        default=env_int('WIKI_LLM_TIMEOUT', DEFAULT_LLM_TIMEOUT),
        help='API タイムアウト秒。既定: WIKI_LLM_TIMEOUT',
    )


def make_llm_parser(
    description: str,
    batch_size_env: str,
    batch_size_default: int,
) -> argparse.ArgumentParser:
    """
    description で ArgumentParser を作成し、LLM 共通オプション（provider, model, batch-size, workers, timeout）を追加して返す。
    split / filter の parse_args で利用する。
    """
    p = argparse.ArgumentParser(description=description)
    add_llm_common_args(
        p,
        batch_size_env=batch_size_env,
        batch_size_default=batch_size_default,
        include_provider=True,
        include_workers=True,
    )
    return p


def resolve_llm_options(
    args,
    *,
    default_provider: str = DEFAULT_LLM_PROVIDER,
    default_workers: int = DEFAULT_LLM_WORKERS,
) -> tuple[str, str, int, int, int]:
    """
    parse_args の結果から provider, model, batch_size, workers, timeout を解決する。
    args に provider / workers がない場合は default_* を使用。
    返り値: (provider, model, batch_size, workers, timeout)
    """
    provider = (getattr(args, 'provider', None) or os.environ.get('WIKI_LLM_PROVIDER') or default_provider).lower()
    model = (getattr(args, 'model', '') or os.environ.get('WIKI_LLM_MODEL') or '').strip()
    if not model:
        model = (
            (os.environ.get('WIKI_LLM_DEFAULT_MODEL_GEMINI') or DEFAULT_LLM_MODEL_GEMINI)
            if provider == 'gemini'
            else (os.environ.get('WIKI_LLM_DEFAULT_MODEL_OLLAMA') or DEFAULT_LLM_MODEL_OLLAMA)
        )
    batch_size = max(1, getattr(args, 'batch_size', 1))
    workers = max(1, getattr(args, 'workers', default_workers))
    timeout = max(1, getattr(args, 'timeout', DEFAULT_LLM_TIMEOUT))
    return (provider, model, batch_size, workers, timeout)


def log_llm_batch_header(
    title_line: str,
    provider: str,
    api_url: str,
    model: str,
    batch_size: int,
    workers: int,
    timeout: int,
    total_rows: int,
    num_batches_total: int,
    skipped_count: int,
    rows_to_do_count: int,
) -> None:
    """LLM バッチ処理開始時の共通ログ（split / filter 用）を出力する。"""
    from wiki_extract.util.log import log
    log(title_line)
    log(f'  provider: {provider}, model: {model}, batch_size: {batch_size}, workers: {workers}, timeout: {timeout}s')
    if provider == 'ollama':
        log(f'  API: {api_url}')
    log(f'  入力: {total_rows} 行, バッチ数: {num_batches_total}')
    if skipped_count:
        log(f'  再開: 先頭 {skipped_count} 行は完了済み、最後のバッチから再実行（残り {rows_to_do_count} 行）')


def log_ollama_connection_refused_hint() -> None:
    """Docker 内で Ollama に接続できないときの案内を log に出力する。"""
    from wiki_extract.util.log import log
    log('  → Docker 内では LLM_OLLAMA_BASE_URL でホストの Ollama を指定してください（既定: host.docker.internal）。')
    log('    Linux の場合は、docker-compose_linux.yml を渡して起動してください（例: docker compose -f docker-compose.yml -f docker-compose_linux.yml up -d）。')
