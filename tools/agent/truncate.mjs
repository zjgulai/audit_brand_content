/**
 * 截断守卫 —— 防止「半句话」被当成完整回答发出去。
 *
 * 为什么需要这个文件（真实事故，2026-09-16）：
 *   守衡发出的一条 779 字回复，结尾停在「这条也算那份记录里「未做」——
 *   句子没写完，但守护进程日志记的是「✓ 已发送」，没有任何报错。
 *   用户看到的就是一条断掉的回答，而他无从知道它是断的。
 *
 * 根因不是飞书（实测飞书 text 消息能收 8000 字），而是：
 *   DeepSeek 的 max_tokens 同时覆盖思维链和正文。配置成 1600 时，
 *   reasoning_tokens 可以把整个额度吃光，finish_reason='length'，
 *   正文被腰斩甚至为 0 字。而 agent.mjs 拿到了 finishReason 却从没检查。
 *
 * 设计原则：截断**必须可见**。宁可显式告诉用户「这条被截断了，我重发」，
 * 也不能把半句话伪装成完整回答 —— 后者会让人以为那就是全部内容。
 */

/** 认得出「句子已经说完」的结尾字符 */
const SENTENCE_END = /[。！？；：…」』】）)\]}"'`*|~～]/;

/** 结尾若是这些，句子显然没说完 */
const DANGLING_END = /[，、,;：（(\[【「『《“‘\-—]+$/;

/** 段落中续行（表格行、列表项）结尾没有标点时，不算悬空 */
const INCOMPLETE_LINE_END = /[，、,;：:（(\[【「『《“‘\-—]$/;

/** 结尾是拉丁字母/数字/URL 时无法判断，不报（宁漏勿误伤） */
const AMBIGUOUS_TAIL = /[A-Za-z0-9/.:_=%&#?+-]$/;

/** 最长保留多少字再截（一篇长回答的合理上限，避免刷屏） */
const DEFAULT_MAX_CHARS = 3000;

/**
 * 判断一次模型回复是否被截断 —— finish_reason 优先。
 *
 * @param {object} opts
 * @param {string} opts.finishReason  LLM 返回的 finish_reason
 * @param {string} opts.text          正文
 * @returns {{cut: boolean, reason: string|null}}
 */
export function detectTruncation({ finishReason, text } = {}) {
  const t = String(text ?? '').trim();

  // 1) finish_reason 是权威信号，优先于任何文本启发式
  if (finishReason === 'length') {
    return { cut: true, reason: 'finish_reason=length（额度耗尽）' };
  }
  if (finishReason === 'content_filter') {
    return { cut: true, reason: 'finish_reason=content_filter（被内容策略拦截）' };
  }
  if (finishReason && finishReason !== 'stop' && finishReason !== 'tool_calls') {
    return { cut: true, reason: `finish_reason=${finishReason}（非正常收尾）` };
  }

  // 2) 文本启发式：空回复本身就是一种失败
  if (!t) return { cut: true, reason: '正文为空' };

  // 3) 悬空标点（以逗号/顿号/左括号等收尾）
  if (DANGLING_END.test(t)) {
    return { cut: true, reason: '结尾是悬空标点，句子未完成' };
  }

  // 4) 结尾是「未闭合的中文句子」。
  //    聊天回答里，正文以中文汉字收尾、却没有句末标点，说明话没说完。
  //    真实事故的结尾是「…这条也算那份记录里「未做」—— 没有悬空标点，
  //    单靠标点规则抓不到，必须看「最后一个字是不是汉字且无终结符」。
  //    拉丁字母/数字/URL 结尾一律放过（那些本来就常不带中文标点）。
  if (!SENTENCE_END.test(t.slice(-1)) && !AMBIGUOUS_TAIL.test(t)) {
    const lines = t.split('\n').filter((l) => l.trim());
    const lastLine = (lines[lines.length - 1] ?? '').trim();
    const isTableLike = /^\|/.test(lastLine) || /^[-*+]\s/.test(lastLine) || /^\d+[.、)]\s/.test(lastLine);

    // 短回复（「好」「收到」）本来就不带句号，不能误报。
    // 阈值 12 字：实线上短答普遍在这个量级以下，而真正的腰斩远长于此。
    if (t.length >= 12 && !isTableLike && /[\u4e00-\u9fff]$/.test(lastLine) && !INCOMPLETE_LINE_END.test(lastLine)) {
      return { cut: true, reason: '结尾是未闭合的中文句子，缺句末标点' };
    }

    // 长文本完全没有句末标点 —— 整体被腰斩的特征
    if (t.length > 200 && !SENTENCE_END.test(t.slice(-8))) {
      return { cut: true, reason: '长回复结尾无句末标点' };
    }
  }

  return { cut: false, reason: null };
}

/**
 * 把被截断的文本修剪到最后一个完整句子，并附上明确的截断标记。
 *
 * @param {string} text
 * @param {object} opts
 * @param {number} [opts.maxChars]
 * @param {string} [opts.reason] 截断原因，写进提示里便于排查
 * @returns {string}
 */
export function annotateTruncation(text, { maxChars = DEFAULT_MAX_CHARS, reason = null } = {}) {
  let t = String(text ?? '').trim();

  // 超长先硬截，避免单条消息刷屏
  if (t.length > maxChars) {
    t = t.slice(0, maxChars);
  }

  // 回退到最后一个完整句子结尾，别把半句话留在那儿
  const lastEnd = Math.max(
    t.lastIndexOf('。'), t.lastIndexOf('！'), t.lastIndexOf('？'),
    t.lastIndexOf('\n'), t.lastIndexOf('；'),
  );
  if (lastEnd >= 0 && lastEnd < t.length - 1) {
    t = t.slice(0, lastEnd + 1).trimEnd();
  }

  const why = reason ? `（${reason}）` : '';
  return `${t}\n\n---\n⚠️ 这条回答被长度上限截断了${why}，上面是不完整的。你可以让我「接着说」，或者把问题拆小一点再问。`;
}

/**
 * 一句话摘要，给日志用。
 * @param {string} text
 */
export function tailOf(text, n = 40) {
  const t = String(text ?? '').trim();
  return t.length <= n ? t : `…${t.slice(-n)}`;
}
