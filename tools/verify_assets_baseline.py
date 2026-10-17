#!/usr/bin/env python3
"""verify_assets_baseline.py — momcozy-assets 基线恒等校验

判据(AGENTS.md §2.4:写进文档的每个上限必须指得出哪一行在拦它):

  A1  manifest 可解析 / schema_version 正确 / files_count == len(files)
  A2  每条 entry 的目标文件存在
  A3  内容 sha256(Python open().read(),**不用 stat/shasum**) == manifest.dst_sha256
  A4  内容 size == manifest.dst_size
  A5  盘上没有"manifest 未登记"的多余文件(排除 manifest 自身 / _logs / _quarantine / .DS_Store)
  A6  license_status 全部 unknown(策略:不因"品牌资产"默认可公开)
  A7  汇总字段自洽(by_kind 求和 == files 数;all_sha256_match 必须为 true)
  A8  非 generated 条目:src_sha256 == dst_sha256(证明"就是那一份")

退出码:
  0 = 全绿
  1 = 有红
  2 = 未测(manifest 读不出 / 根目录不存在 / 目标根不存在) —— 与通过、红都不同

反向对照:
  python3 tools/verify_assets_baseline.py --controls
  7 项离线对照,全部在 mktemp 临时目录里跑,不碰真基线(§2.4.4)。

填充态说明(ENV-001):本机 stat/wc -c/macOS shasum 会虚报 +4096B,
本工具一律用 Python 读真内容 —— 这是 A3/A4 的全部理由。
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile

EXIT_OK, EXIT_RED, EXIT_UNTESTED = 0, 1, 2
SCHEMA = 'momcozy-assets/1.0'


def sha_of(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def size_of(path):
    with open(path, 'rb') as f:
        return len(f.read())


def check(root, manifest_path):
    """返回 (exit_code, errors[])。errors 为空表示全绿。"""
    if not os.path.isdir(root):
        return EXIT_UNTESTED, [f'UNTESTED: root 不存在: {root}']
    if not os.path.exists(manifest_path):
        return EXIT_UNTESTED, [f'UNTESTED: manifest 不存在: {manifest_path}']
    try:
        with open(manifest_path, encoding='utf-8') as f:
            m = json.load(f)
    except Exception as e:  # noqa: BLE001 —— 读不出就是未测,不许当成绿
        return EXIT_UNTESTED, [f'UNTESTED: manifest 读不出: {e}']

    errors = []

    # A1
    if m.get('schema_version') != SCHEMA:
        errors.append(f"A1 schema_version = {m.get('schema_version')!r}, 期望 {SCHEMA!r}")
    files = m.get('files')
    if not isinstance(files, list) or not files:
        errors.append('A1 files[] 为空或不是数组')
        return EXIT_RED, errors
    if m.get('files_count') != len(files):
        errors.append(f"A1 files_count={m.get('files_count')} != len(files)={len(files)}")

    expected = set()
    # A2 / A3 / A4 / A8
    for e in files:
        rel = e.get('dst_path')
        if not rel:
            errors.append('A2 entry 缺 dst_path')
            continue
        expected.add(rel)
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            errors.append(f'A2 缺文件: {rel}')
            continue
        disk_sha = sha_of(p)
        disk_size = size_of(p)
        if disk_sha != e.get('dst_sha256'):
            errors.append(
                f"A3 sha 不符: {rel} manifest={str(e.get('dst_sha256'))[:12]} disk={disk_sha[:12]}"
            )
        if disk_size != e.get('dst_size'):
            errors.append(f"A4 size 不符: {rel} manifest={e.get('dst_size')} disk={disk_size}")
        if not e.get('generated') and e.get('src_sha256'):
            if e['src_sha256'] != disk_sha:
                errors.append(f"A8 src != dst: {rel}")

    # A5 多余文件(只扫目标根,不是全仓库)
    target_root = m.get('target_root') or 'PMO/audit/momcozy-assets'
    assets_root = os.path.join(root, target_root)
    if not os.path.isdir(assets_root):
        return EXIT_UNTESTED, [f'UNTESTED: target_root 不存在: {assets_root}']
    manifest_abs = os.path.abspath(manifest_path)
    extras = []
    for dirpath, dirnames, filenames in os.walk(assets_root):
        dirnames[:] = [d for d in dirnames if d not in ('_logs', '_quarantine')]
        for fn in filenames:
            if fn == '.DS_Store':
                continue
            ap = os.path.abspath(os.path.join(dirpath, fn))
            if ap == manifest_abs:
                continue
            rel = os.path.relpath(ap, root)
            if rel not in expected:
                extras.append(rel)
    if extras:
        shown = ', '.join(sorted(extras)[:5])
        more = ' …' if len(extras) > 5 else ''
        errors.append(f'A5 多余文件({len(extras)}): {shown}{more}')

    # A6
    bad_lic = [e.get('dst_path') for e in files if e.get('src_license_status') != 'unknown']
    if bad_lic:
        errors.append(
            f'A6 license 非 unknown({len(bad_lic)}): ' + ', '.join(str(x) for x in bad_lic[:3])
        )

    # A7
    kind_sum = sum(m.get('by_kind', {}).values())
    if kind_sum != len(files):
        errors.append(f"A7 by_kind 求和 {kind_sum} != files {len(files)}")
    if m.get('all_sha256_match') is not True:
        errors.append('A7 all_sha256_match 不为 true')

    return (EXIT_OK if not errors else EXIT_RED), errors


# ── 反向对照 ──────────────────────────────────────────────────────────
def _run_child(root, manifest):
    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), '--root', root, '--manifest', manifest],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _make_case(base, content=b'hello baseline\n', schema=SCHEMA):
    d = tempfile.mkdtemp(dir=base)
    assets = os.path.join(d, 'PMO/audit/momcozy-assets')
    os.makedirs(assets, exist_ok=True)
    fp = os.path.join(assets, 'a.txt')
    with open(fp, 'wb') as f:
        f.write(content)
    manifest = {
        'schema_version': schema,
        'files_count': 1,
        'target_root': 'PMO/audit/momcozy-assets',
        'all_sha256_match': True,
        'by_kind': {'rules': 1},
        'files': [{
            'dst_path': 'PMO/audit/momcozy-assets/a.txt',
            'dst_sha256': hashlib.sha256(content).hexdigest(),
            'dst_size': len(content),
            'src_sha256': hashlib.sha256(content).hexdigest(),
            'src_license_status': 'unknown',
            'generated': False,
        }],
    }
    mp = os.path.join(d, 'manifest.json')
    with open(mp, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False)
    return d, mp, fp


def run_controls():
    base = tempfile.mkdtemp(prefix='assets_verify_ctl_')
    passed = failed = 0

    def report(ok, name, detail=''):
        nonlocal passed, failed
        if ok:
            print(f'PASS: {name}')
            passed += 1
        else:
            print(f'FAIL: {name} {detail}', file=sys.stderr)
            failed += 1

    # B1 正例:合法基线必须绿(否则后面所有反例恒真)
    d, mp, fp = _make_case(base)
    rc, out = _run_child(d, mp)
    report(rc == 0, 'B1 合法基线 → 0', f'rc={rc} out={out.strip()[:120]}')

    # B2 内容被改 → A3 红
    with open(fp, 'ab') as f:
        f.write(b'tampered')
    rc, out = _run_child(d, mp)
    report(rc == 1 and 'A3' in out, 'B2 内容篡改 → A3 红', f'rc={rc}')

    # B3 文件被删 → A2 红
    d3, mp3, fp3 = _make_case(base)
    os.unlink(fp3)
    rc, out = _run_child(d3, mp3)
    report(rc == 1 and 'A2' in out, 'B3 文件缺失 → A2 红', f'rc={rc}')

    # B4 多一个未登记文件 → A5 红
    d4, mp4, fp4 = _make_case(base)
    with open(os.path.join(d4, 'PMO/audit/momcozy-assets', 'extra.txt'), 'wb') as f:
        f.write(b'extra')
    rc, out = _run_child(d4, mp4)
    report(rc == 1 and 'A5' in out, 'B4 多余文件 → A5 红', f'rc={rc}')

    # B5 manifest 读不出 → 未测(2),不是绿
    rc, out = _run_child(d4, os.path.join(base, 'no-such-manifest.json'))
    report(rc == 2, 'B5 manifest 缺失 → 2(未测)', f'rc={rc}')

    # B6 schema_version 错 → A1 红
    d6, mp6, _ = _make_case(base, schema='wrong/0.0')
    rc, out = _run_child(d6, mp6)
    report(rc == 1 and 'A1' in out, 'B6 schema 错 → A1 红', f'rc={rc}')

    # B7 license 非 unknown → A6 红
    d7, mp7, _ = _make_case(base)
    m = json.load(open(mp7, encoding='utf-8'))
    m['files'][0]['src_license_status'] = 'public'
    json.dump(m, open(mp7, 'w', encoding='utf-8'), ensure_ascii=False)
    rc, out = _run_child(d7, mp7)
    report(rc == 1 and 'A6' in out, 'B7 license 非 unknown → A6 红', f'rc={rc}')

    print('----------------------------------------')
    if failed == 0:
        print(f'✅ {passed}/7 全过')
        return EXIT_OK
    print(f'❌ {passed} passed, {failed} failed', file=sys.stderr)
    return EXIT_RED


def main():
    ap = argparse.ArgumentParser(description='momcozy-assets 基线恒等校验')
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument('--manifest', default=None)
    ap.add_argument('--controls', action='store_true', help='跑 7 项离线反向对照')
    args = ap.parse_args()

    if args.controls:
        sys.exit(run_controls())

    manifest = args.manifest or os.path.join(
        args.root, 'PMO/audit/momcozy-assets/manifest.json'
    )
    rc, errors = check(args.root, manifest)

    print('=' * 72)
    print('momcozy-assets 基线恒等校验')
    print('=' * 72)
    if rc == EXIT_UNTESTED:
        for e in errors:
            print(f'⚠ {e}')
        sys.exit(EXIT_UNTESTED)
    if rc == EXIT_OK:
        print('✅ 基线恒等:A1–A8 全过')
        sys.exit(EXIT_OK)
    for e in errors:
        print(f'❌ {e}')
    sys.exit(EXIT_RED)


if __name__ == '__main__':
    main()