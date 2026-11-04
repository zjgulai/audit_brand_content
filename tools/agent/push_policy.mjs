/**
 * push_policy.mjs —— 定时巡检与主动总结推送的唯一目标群闸门
 *
 * 委托方 2026-11-04 明确裁定：
 * 「定时任务暂时先只在测试群推送，等稳定了再来定夺」
 *
 * 执行点：任何定时任务或主动总结卡片发送前必须调 assertTestGroupTarget(chatId)，
 * 非测试群（oc_49a7cfb2861cffa4365ca8491f398d32）一律硬拒绝抛出异常。
 */

export const TEST_GROUP_CHAT_ID = 'oc_49a7cfb2861cffa4365ca8491f398d32';
export const TEST_GROUP_CHAT_NAME = '内容治理-守衡Agent-测试';

export function scheduledPushTarget() {
  return TEST_GROUP_CHAT_ID;
}

export function assertTestGroupTarget(chatId) {
  const target = String(chatId ?? '').trim();
  if (target !== TEST_GROUP_CHAT_ID) {
    throw new Error(
      `拒绝定时推送：当前仅允许推送到测试群「${TEST_GROUP_CHAT_NAME}」（${TEST_GROUP_CHAT_ID}），收到目标=${target || '(空)'}`,
    );
  }
  return TEST_GROUP_CHAT_ID;
}
