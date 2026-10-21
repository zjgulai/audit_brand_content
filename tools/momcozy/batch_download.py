#!/usr/bin/env python3
# tools/momcozy/batch_download.py
#
# 批量下载某个商品目录下 product.json 中所有 images[].source_url。
# 用法:
#   python3 tools/momcozy/batch_download.py <product_dir>
#   MOMCOZY_CATALOG_ROOT=~/audit-data/momcozy-catalog \
#     python3 tools/momcozy/batch_download.py ~/audit-data/momcozy-catalog/breast-pump
#
# 行为:
#   - 读 <product_dir>/product.json
#   - 逐张调用 image_download.download_one 落盘到 <product_dir>/images/
#   - manifest 追加到 <product_dir>/../_logs/images-manifest.jsonl
#   - 回填 product.json 的 local_filename/sha256/bytes + download 汇总
#   - 失败重试 2 次(间隔 2s)
#
# ★★ 2026-10-21：**落盘根必须在仓外**。
#   本仓是**公开**仓（AGENTS.md §2.6），而这里下载的是客户产品图。
#   原来 README 与注释都写「产物落到 PMO/audit/momcozy-catalog/」（仓内），
#   靠 `.gitignore` 挡着 —— 而 DG-2 的整条立论正是「`.gitignore` **不是**边界，
#   `git add -f` 照样能进」。那种写法与红线直接冲突。
#   现在：`<product_dir>` 由调用方给，默认走 `~/audit-data/momcozy-catalog/`；
#   下面 `_assert_outside_repo()` 会**硬拒**仓内路径（退 2，不是静默继续）。
#
# 注意(Python 实读校验,不用 shasum/stat —— 规避 +4096 填充态假失败):
#   校验用 open().read() 算 sha256,与 download_one 的 sha 同源。

import json
import os
import sys
import time
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import image_download as img

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CATALOG_ROOT = os.path.expanduser('~/audit-data/momcozy-catalog')


def assert_outside_repo(path: str) -> str:
    """落盘根必须在**仓外**。仓内直接拒（退 2）。

    ★ 为什么是硬拒而不是警告：本仓公开（AGENTS.md §2.6），而这里写的是客户产品图。
      靠 `.gitignore` 挡不住 `git add -f` —— DG-2 的整条立论就是这个。
      一个「警告后继续写进仓内」的实现，等于把红线交给读日志的人。
    """
    real = os.path.realpath(path)
    repo = os.path.realpath(REPO)
    if real == repo or real.startswith(repo + os.sep):
        print(f'[拒] 落盘根经 realpath 解析后在仓内：{real}\n'
              f'     本仓是公开仓，客户素材不许写入（AGENTS.md §2.6）。\n'
              f'     用 MOMCOZY_CATALOG_ROOT 指到仓外，默认是 {DEFAULT_CATALOG_ROOT}',
              file=sys.stderr)
        sys.exit(2)
    return real


def main():
    if len(sys.argv) < 2:
        print('usage: batch_download.py <product_dir>', file=sys.stderr)
        sys.exit(2)
    product_dir = assert_outside_repo(sys.argv[1])
    pj = os.path.join(product_dir, 'product.json')
    dest = os.path.join(product_dir, 'images')
    os.makedirs(dest, mode=0o700, exist_ok=True)

    d = json.load(open(pj, encoding='utf-8'))
    handle = d['handle']
    imgs = d.get('images', [])

    # manifest 路径：<catalog_root>/<series>/_logs/images-manifest.jsonl
    # ★ 与 dest 同一条纪律：必须在仓外。product_dir 已由 assert_outside_repo 核过，
    #   这里的 mf 由它推导出来，因此同为仓外。
    mf = None
    probe = os.path.abspath(product_dir)
    while probe != '/':
        cand = os.path.join(probe, '_logs', 'images-manifest.jsonl')
        if os.path.isdir(os.path.join(probe, '_logs')):
            mf = cand
            break
        probe = os.path.dirname(probe)
    if mf is None:
        mf = os.path.join(os.path.dirname(product_dir), '_logs', 'images-manifest.jsonl')
    assert_outside_repo(os.path.dirname(mf))
    os.makedirs(os.path.dirname(mf), mode=0o700, exist_ok=True)

    results = []
    for i, im in enumerate(imgs, 1):
        url = im['source_url']
        r = img.download_one(url, dest)
        tries = 1
        while not r.get('saved') and tries < 3:
            time.sleep(2)
            r = img.download_one(url, dest)
            tries += 1
        r['product_handle'] = handle
        r['image_index'] = i
        r['attempts'] = tries
        results.append(r)
        status = 'OK' if r.get('saved') else 'FAIL ' + str(r.get('fail_reason'))
        print(f'[{i:02d}/{len(imgs)}] {status} {os.path.basename(url.split("?")[0])[:45]}', flush=True)

    with open(mf, 'a', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    # 回填 product.json(Python 实读校验)
    by_url = {r['source_url']: r for r in results if r.get('saved')}
    updated = 0
    bad = 0
    for im in d['images']:
        e = by_url.get(im['source_url'])
        if not e:
            bad += 1
            continue
        p = os.path.join(dest, e['local_filename'])
        if not os.path.exists(p):
            bad += 1
            continue
        h = hashlib.sha256(open(p, 'rb').read()).hexdigest()
        if h != e['sha256'] or os.path.getsize(p) != e['bytes']:
            bad += 1
            continue
        im['local_filename'] = e['local_filename']
        im['sha256'] = e['sha256']
        im['bytes'] = e['bytes']
        updated += 1

    d['download'] = {
        'status': 'complete' if updated == len(d['images']) else 'partial',
        'downloaded': updated,
        'total': len(d['images']),
        'manifest': mf,
        'completed_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    with open(pj, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write('\n')

    ok = sum(1 for r in results if r.get('saved'))
    print(f'--- {handle}: {ok} ok / {len(results)-ok} fail / {len(results)} total')
    sys.exit(0 if ok == len(results) else 1)


if __name__ == '__main__':
    main()
