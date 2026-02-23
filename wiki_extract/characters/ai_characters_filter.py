"""
① 登場人物候補CSVからキャラクター名（固有名詞）だけをLLMで判定し、対象/除外の2種CSVを出力する。
"""

import csv
import json
import os
import re
import sys
from pathlib import Path

from wiki_extract.characters.extract_character_candidates import clean_wiki_content, is_excluded_name
from wiki_extract.llm.batch_runner import run_llm_batch_loop, stagger_batch_start
from wiki_extract.llm.client import (
    call_llm_chat,
    load_prompt,
    resolve_ollama_chat_url,
    DEFAULT_LLM_FILTER_BATCH_SIZE,
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_LLM_WORKERS,
)
from wiki_extract.llm.parser_common import log_llm_batch_header, log_ollama_connection_refused_hint, make_llm_parser, resolve_llm_options
from wiki_extract.util.csv_util import finalize_output_with_sort, prepare_resume_by_rows
from wiki_extract.util.log import format_elapsed, log, log_progress, Timer
from wiki_extract.util.path_util import progress_path_for, resolve_output_path, validate_input_file

# ブラックリストの既定パス（Env WIKI_EXCLUDE_LIST 未設定時はパッケージ内 data/excluded_names.json）
_DEFAULT_EXCLUDE_LIST_PATH = Path(__file__).resolve().parent.parent / 'data' / 'excluded_names.json'


def _resolve_exclude_list_path(args: object) -> Path:
    """args と環境変数から除外ブラックリストのパスを返す。"""
    if getattr(args, 'exclude_list', None) is not None:
        return Path(args.exclude_list)
    default = (os.environ.get('WIKI_EXCLUDE_LIST') or '').strip()
    return Path(default) if default else _DEFAULT_EXCLUDE_LIST_PATH


def _get_filter_system_prompt() -> str:
    """data/prompts/filter_system.txt の内容を返す。"""
    return load_prompt('filter_system')


def should_force_exclude(name: str) -> bool:
    """
    役割・回次表記など、固有名詞でなく除外すべき名前なら True。
    「〇〇の△」は excluded_names.json の suffix で判定するためここでは扱わない。
    """
    if not name or len(name) < 2:
        return False
    if re.match(r'^\d+回（最終回）$', name):
        return True
    if re.match(r'^\d+回.*最終回', name):
        return True
    return False


def looks_like_sentence_fragment(name: str) -> bool:
    """
    文の断片（名前でない）なら True。該当する場合は target にせず除外する。
    """
    if not name or len(name) < 3:
        return False
    if '。' in name:
        return True
    # 長くて「、」が複数ある場合は説明文の切れ端の可能性が高い
    if len(name) > 50 and name.count('、') >= 2:
        return True
    if len(name) > 60:
        return True
    return False


def looks_like_proper_noun(name: str) -> bool:
    """
    LLM が exclude にした名前が固有名詞らしければ True。
    名前とみなせる表記は target に回すため。
    """
    if not name or len(name) > 50:
        return False
    # 漢字が1字でもあれば固有名詞の可能性が高い
    if re.search(r'[\u4e00-\u9fff]', name):
        return True
    # カタカナとひらがなの混在（例: 汀マリア）は名前らしい
    if re.search(r'[\u30a0-\u30ff]', name) and re.search(r'[\u3040-\u309f]', name):
        return True
    # スペースで区切られた「姓 名」形式（かなのみでも）
    if ' ' in name and 2 <= len(name) <= 25:
        return True
    # 中黒「・」を含む（デュナン・ナッツ、姓・名 など）
    if '・' in name and 2 <= len(name) <= 30:
        return True
    # ラテン文字を含む（ファング（A-10） など）
    if re.search(r'[a-zA-Z]', name):
        return True
    # カタカナのみ（・ー スペース可）2〜25文字はキャラ名の可能性が高い（スドオ、マグス、モートン など）
    if 2 <= len(name) <= 25 and re.fullmatch(r'[\u30a0-\u30ff・ー\s]+', name):
        return True
    return False


def load_excluded_set(path: Path | None) -> tuple[set[str], set[str]]:
    """
    除外ブラックリストを読み込む。JSON の exact のみ使用。
    完全一致と「の」+ exact の末尾一致で判定。返り値: (exact_set, exact_set)。
    """
    if path is None or not Path(path).is_file():
        return (set(), set())
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    exact_set = set(data.get('exact', []))
    return (exact_set, exact_set)


def _call_filter_llm(
    provider: str,
    api_url: str,
    model: str,
    user_input: str,
    timeout: int,
    system_prompt: str,
    api_key: str | None = None,
) -> str:
    """filter 用: 1 回の LLM 呼び出しで JSON テキストを取得。"""
    return call_llm_chat(
        provider, api_url, model, system_prompt, user_input, timeout, api_key=api_key,
    )


def load_input_list(list_path: Path) -> list[dict]:
    """登場人物候補CSVを読み、[ {page_title, names}, ... ] の形で返す（ページ単位）。"""
    from collections import defaultdict
    by_page: dict[str, list[str]] = defaultdict(list)
    with open(list_path, encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            page_title, name = row[0].strip(), row[1].strip()
            if not name:
                continue
            by_page[page_title].append(name)
    return [{'page_title': k, 'names': v} for k, v in by_page.items()]


def load_input_rows(list_path: Path) -> list[tuple[str, str]]:
    """登場人物候補CSVを読み、(page_title, name) のリストで返す。件数ペースでバッチする用。"""
    rows: list[tuple[str, str]] = []
    with open(list_path, encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            page_title, name = row[0].strip(), row[1].strip()
            if not name:
                continue
            rows.append((page_title, name))
    return rows


def _strip_json_code_block(text: str) -> str:
    """先頭・末尾の ``` で囲まれたコードブロックを除去する。"""
    text = text.strip()
    if not text.startswith('```'):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith('```'):
        lines = lines[1:]
    if lines and lines[-1].strip() == '```':
        lines = lines[:-1]
    return '\n'.join(lines)


def _normalize_status(s: str) -> str:
    """'target' または 'exclude' 以外は 'target' に正規化する。"""
    return s if s in ('target', 'exclude') else 'target'


def parse_filter_response(response: str, names: list[str]) -> list[tuple[str, str]]:
    """
    LLM の JSON レスポンスをパースし、(name, status) のリストを返す。
    status は "target" または "exclude"。パースに失敗した場合は入力順で target とする。
    """
    text = _strip_json_code_block(response)
    try:
        arr = json.loads(text)
    except json.JSONDecodeError:
        return [(n, 'target') for n in names]
    if not isinstance(arr, list):
        return [(n, 'target') for n in names]

    by_name = {
        item.get('name', ''): _normalize_status(item.get('status', 'target'))
        for item in arr
        if isinstance(item, dict)
    }
    return [(n, by_name.get(n, 'target')) for n in names]


def _resolve_filter_status(
    name: str,
    llm_status: str,
    exact_set: set[str],
    suffix_set: set[str],
) -> tuple[str, str]:
    """1 行分: 名前を正規化し、ブラックリスト・強制除外・固有名詞で status を確定する。(clean_name, status) を返す。"""
    clean_name = clean_wiki_content(name).strip() or name
    if is_excluded_name(clean_name, exact_set, suffix_set):
        return (clean_name, 'exclude')
    if should_force_exclude(clean_name):
        return (clean_name, 'exclude')
    if llm_status == 'exclude' and looks_like_proper_noun(clean_name):
        return (clean_name, 'target')
    return (clean_name, llm_status if llm_status in ('target', 'exclude') else 'target')


def _process_one_batch(
    batch_start: int,
    batch_rows: list[tuple[str, str]],
    provider: str,
    api_url: str,
    model: str,
    timeout: int,
    system_prompt: str,
    exact_set: set[str],
    suffix_set: set[str],
    *,
    batch_size: int = 1,
    workers: int = 1,
) -> tuple[int, list[tuple[str, str, str]]]:
    """
    1バッチ分のLLM呼び出しと判定を行い、(page_title, clean_name, status) のリストを返す。
    """
    stagger_batch_start(batch_start, batch_size, workers)
    batch_names = [name for _, name in batch_rows]
    user_input = '次の名前を target / exclude に分類してください:\n' + '\n'.join(batch_names)
    response = _call_filter_llm(
        provider, api_url, model, user_input, timeout, system_prompt
    )
    results = parse_filter_response(response, batch_names)

    out: list[tuple[str, str, str]] = []
    for idx, (page_title, name) in enumerate(batch_rows):
        llm_status = results[idx][1] if idx < len(results) else 'target'
        clean_name, status = _resolve_filter_status(name, llm_status, exact_set, suffix_set)
        out.append((page_title, clean_name, status))
    return (batch_start, out)


def _prepare_resume_filter(
    target_path: Path,
    excluded_path: Path,
    rows: list[tuple[str, str]],
    batch_size: int,
) -> tuple[list[tuple[str, str]], int, bool]:
    """再開時: 進捗を読み、最後のバッチ分を両CSVから削除してから再実行する対象を返す。"""
    return prepare_resume_by_rows(
        progress_path_for(target_path, 'filter'), rows, batch_size, [target_path, excluded_path]
    )


def _run_filter_batches(
    target_path: Path,
    excluded_path: Path,
    progress_path: Path,
    file_has_data: bool,
    rows_to_do: list[tuple[str, str]],
    batch_size: int,
    skipped_count: int,
    total_rows: int,
    provider: str,
    api_url: str,
    model: str,
    timeout: int,
    exact_set: set[str],
    suffix_set: set[str],
    workers: int,
    total_timer: Timer,
) -> tuple[int, int, int, int]:
    """バッチループを実行し、(errors, target_count, excluded_count, processed_count) を返す。"""
    state: dict[str, int] = {'target': 0, 'excluded': 0, 'processed': skipped_count}

    def on_success(
        _batch_start: int,
        _batch_rows: list,
        result: tuple,
        processed_count_after: int,
    ) -> None:
        state['processed'] = processed_count_after
        _, rows_with_status = result
        batch_target = 0
        batch_excluded = 0
        for page_title, clean_name, status in rows_with_status:
            if looks_like_sentence_fragment(clean_name):
                status = 'exclude'
            if status == 'target':
                wt.writerow([page_title, clean_name])
                state['target'] += 1
                batch_target += 1
            else:
                we.writerow([page_title, clean_name])
                state['excluded'] += 1
                batch_excluded += 1
        try:
            with open(progress_path, 'w', encoding='utf-8') as pf:
                pf.write(f'{batch_target},{batch_excluded},{processed_count_after}\n')
        except OSError:
            pass

    system_prompt = _get_filter_system_prompt()
    with open(target_path, 'a' if file_has_data else 'w', encoding='utf-8', newline='') as ft, \
         open(excluded_path, 'a' if file_has_data else 'w', encoding='utf-8', newline='') as fe:
        wt = csv.writer(ft)
        we = csv.writer(fe)
        if not file_has_data:
            wt.writerow(['ページ名', '名前'])
            we.writerow(['ページ名', '名前'])
            ft.flush()
            fe.flush()

        def flush_both() -> None:
            ft.flush()
            fe.flush()

        errors = run_llm_batch_loop(
            rows_to_do,
            batch_size,
            _process_one_batch,
            {
                'provider': provider,
                'api_url': api_url,
                'model': model,
                'timeout': timeout,
                'system_prompt': system_prompt,
                'exact_set': exact_set,
                'suffix_set': suffix_set,
                'batch_size': batch_size,
                'workers': workers,
            },
            workers,
            total_timer,
            'ai-characters-filter: rows processed',
            skipped_count,
            total_rows,
            on_success,
            on_after_batch=flush_both,
        )

    return (errors, state['target'], state['excluded'], state['processed'])


def _finalize_filter_output(
    progress_path: Path,
    processed_count: int,
    total_rows: int,
    target_path: Path,
    excluded_path: Path,
    target_count: int,
    excluded_count: int,
) -> None:
    """完了時にソートと進捗ファイル削除を行う。"""
    finalize_output_with_sort(
        progress_path,
        processed_count,
        total_rows,
        paths_to_sort=[target_path, excluded_path],
        sort_log_message='  出力CSVを ページ名・名前 でソートしています…',
        has_output=(target_count + excluded_count) > 0,
    )


def parse_args() -> object:
    p = make_llm_parser(
        '登場人物候補CSVをLLMで対象/除外に分類し、2種のCSVを出力する',
        'WIKI_LLM_FILTER_BATCH_SIZE',
        DEFAULT_LLM_FILTER_BATCH_SIZE,
    )
    p.add_argument('--input-list', type=Path, default=Path('out/character_candidates.csv'),
                   help='登場人物候補CSV（extract-character-candidates の出力）。既定: out/character_candidates.csv')
    p.add_argument('--output-target', type=Path, default=None,
                   help='対象CSV（既定: <inputの同dir>/characters_target.csv）')
    p.add_argument('--output-excluded', type=Path, default=None,
                   help='除外CSV（既定: <inputの同dir>/characters_excluded.csv）')
    p.add_argument('--exclude-list', type=Path, default=None,
                   help='除外対象ブラックリスト（JSON）。既定: WIKI_EXCLUDE_LIST または data/excluded_names.json')
    return p.parse_args()


def main() -> None:
    args = parse_args()
    list_path = Path(args.input_list)
    validate_input_file(
        list_path,
        f'Error: 登場人物候補CSVが見つかりません: {list_path} （--input-list でパスを指定するか、既定の out/character_candidates.csv を用意してください）',
    )
    target_path = resolve_output_path(list_path, args.output_target, 'characters_target.csv')
    excluded_path = resolve_output_path(list_path, args.output_excluded, 'characters_excluded.csv')

    provider, model, batch_size, workers, timeout = resolve_llm_options(args)
    api_url = resolve_ollama_chat_url()
    exclude_list_path = _resolve_exclude_list_path(args)
    exact_set, suffix_set = load_excluded_set(exclude_list_path)
    if exact_set:
        log(f'  除外ブラックリスト: {exclude_list_path} 完全一致＆「の」+exact末尾一致 {len(exact_set)}語')

    rows = load_input_rows(list_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    excluded_path.parent.mkdir(parents=True, exist_ok=True)
    rows_to_do, skipped_count, file_has_data = _prepare_resume_filter(
        target_path, excluded_path, rows, batch_size
    )
    total_rows = len(rows)
    num_batches_total = (len(rows_to_do) + batch_size - 1) // batch_size if rows_to_do else 0

    log_llm_batch_header(
        'ai-characters-filter: 対象/除外をLLMで判定（CSV件数ペースでバッチ）',
        provider, api_url, model, batch_size, workers, timeout,
        total_rows, num_batches_total, skipped_count, len(rows_to_do),
    )
    progress_path = progress_path_for(target_path, 'filter')

    with Timer() as total_timer:
        errors, target_count, excluded_count, processed_count = _run_filter_batches(
            target_path,
            excluded_path,
            progress_path,
            file_has_data,
            rows_to_do,
            batch_size,
            skipped_count,
            total_rows,
            provider,
            api_url,
            model,
            timeout,
            exact_set,
            suffix_set,
            workers,
            total_timer,
        )
        _finalize_filter_output(
            progress_path,
            processed_count,
            total_rows,
            target_path,
            excluded_path,
            target_count,
            excluded_count,
        )
        log(f'  対象: {target_path}, 除外: {excluded_path}, 今回 対象={target_count}, 除外={excluded_count}, エラー数={errors}')

    log('')
    log(f'  実行時間: {format_elapsed(total_timer.elapsed)} ({total_timer.elapsed:.1f}秒)')


if __name__ == '__main__':
    main()
    sys.exit(0)
