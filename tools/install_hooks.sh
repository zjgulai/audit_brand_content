#!/usr/bin/env bash
# tools/install_hooks.sh —— T-411：把 pre-push 验收钩子装到当前 clone
#
# ## 为什么需要一个脚本，而不是在 README 里写一行命令
#
# `git config core.hooksPath tools/githooks` 是**本地仓库配置**，
# 它不在版本控制里。也就是说：**这个仓的每一个 clone 都要各做一次**，
# 而「没做」在盘上的表现是——什么都没有。
#
# 实测过的三种失败形态（都不是红的）：
#
#   1. 有人 clone 下来直接推 → 钩子不跑，CI 才会拦（慢一轮）
#   2. 有人以为 `tools/githooks/pre-push` 存在就等于装好了
#      （`git ls-files` 里确实有它）→ 但 git 根本不看那个路径
#   3. `core.hooksPath` 被别的工具改成 `.husky` 之类 → 我们的钩子静默失效，
#      而 `git config core.hooksPath` 仍然返回一个**非空值**，
#      看起来像「已经配了」
#
# 所以这个脚本做三件事：**装**、**验**、**报告现在是哪一种状态**。
# 它不假装能替别人装 —— 那是做不到的，写清楚比装作做到了强。
#
# ## 用法
#
#     bash tools/install_hooks.sh            # 装 + 验
#     bash tools/install_hooks.sh --check    # 只报告状态（退 0/1，不改配置）
#     bash tools/install_hooks.sh --uninstall
#
# ## 退出码
#
#   0 已安装且指向本仓的 tools/githooks
#   1 未安装 / 指向别处（--check 下也是 1）
#   2 不是 git 仓库 / 读不出配置
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WANT="tools/githooks"
HOOK_FILE="${ROOT}/${WANT}/pre-push"

cd "${ROOT}" || {
  echo "✗ 进不到仓库根：${ROOT}" >&2
  exit 2
}

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "⚠ 未测：这不是一个 git 仓库（${ROOT}）" >&2
  exit 2
fi

# ★ 用 `git config --get`，不用 `git config <key>`：
#   后者在未设置时退 1 但不打印，前者同理；用 --get 更明确。
CURRENT="$(git config --get core.hooksPath 2>/dev/null)"
CUR_RC=$?

state() {
  if [ "${CUR_RC}" -ne 0 ] || [ -z "${CURRENT}" ]; then
    echo "未安装"
  elif [ "${CURRENT}" = "${WANT}" ]; then
    echo "已安装（指向 ${CURRENT}）"
  else
    echo "指向别处（${CURRENT}）"
  fi
}

case "${1:-}" in
  --check)
    echo "core.hooksPath = ${CURRENT:-（未设置）}"
    echo "钩子文件存在 = $([ -f "${HOOK_FILE}" ] && echo 是 || echo 否)"
    S="$(state)"
    echo "状态 = ${S}"
    if [ "${S}" = "已安装（指向 ${WANT}）" ]; then
      echo "✓ 本 clone 的 pre-push 会跑验收执行器"
      exit 0
    fi
    echo "✗ 本 clone 的 pre-push **不会**跑验收执行器 —— 这就是 T-411 的「不可入库」那一半" >&2
    echo "  修法：bash tools/install_hooks.sh" >&2
    exit 1
    ;;
  --uninstall)
    git config --unset core.hooksPath 2>/dev/null || true
    echo "已卸载（core.hooksPath 不再设置）"
    exit 0
    ;;
  "" )
    ;;
  *)
    echo "未知参数：$1" >&2
    echo "用法：bash tools/install_hooks.sh [--check|--uninstall]" >&2
    exit 2
    ;;
esac

if [ ! -f "${HOOK_FILE}" ]; then
  echo "✗ 找不到钩子文件：${HOOK_FILE}" >&2
  echo "  这是个真缺陷（文件本该在版本控制里）—— 不是安装问题。" >&2
  exit 1
fi

if [ ! -x "${HOOK_FILE}" ]; then
  # ★ 只读权限不够：git 会因为「不可执行」**静默跳过**这个钩子。
  #   静默跳过比报错更难查，所以这里显式补上。
  chmod +x "${HOOK_FILE}" 2>/dev/null || true
  echo "· 已给 pre-push 补上可执行位（git 会静默跳过不可执行的钩子）"
fi

git config core.hooksPath "${WANT}"
CURRENT="$(git config --get core.hooksPath 2>/dev/null)"
CUR_RC=$?
S="$(state)"
echo "core.hooksPath = ${CURRENT}"
echo "状态 = ${S}"

if [ "${S}" = "已安装（指向 ${WANT}）" ]; then
  echo "✓ 装好了。之后 git push 会先跑 tools/verify_acceptance_run.py"
  echo "  跳过（明知会红但要先推）：SKIP_ACCEPTANCE=1 git push —— 会写进 .git/SKIP-ACCEPTANCE.log"
  exit 0
fi

echo "✗ 装完但读回来不一致（期望 ${WANT}，实得 ${CURRENT:-空}）" >&2
exit 1
