import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  request,
  reviewApi,
  type CaseSummary,
  type NotificationItem,
} from "../api/client";
import { useIdentity } from "../components/IdentitySwitcher";
import StatusBadge from "../components/StatusBadge";
import Button from "../ui/Button";
import Icon from "../ui/icon";

/**
 * 收件箱与我的内容（P-02 · Wave C 落 UJ-7 与 DP1 待自决闭环）。
 *
 * 1. 工作台内通知收件箱（消费 `GET /api/v1/notifications`）：
 *    展示失效/自动重审/租约释放/结论提交等工作台内通知，提供 `read` 与 `ack` 按钮；
 *    严格遵守 UJ-7 文案纪律：只称「已产生工作台内通知」，绝不称「外部消息已送达」。
 * 2. 待自决（DP1）与我的案件处理区：
 *    筛选出 `state === "待自决"` 的案件，引导内容提交方执行「修改后重新提交」或查看详情。
 */
export default function InboxPage() {
  const { devEnabled, current, sessionEpoch } = useIdentity();
  const [notifications, setNotifications] = useState<NotificationItem[] | null>(
    null,
  );
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionFlash, setActionFlash] = useState<string | null>(null);

  const loadAll = async () => {
    try {
      const [notifRows, caseRows] = await Promise.all([
        reviewApi.listNotifications(),
        reviewApi.listCases(),
      ]);
      setNotifications(notifRows);
      setCases(caseRows);
      setError(null);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message ?? String(e));
    }
  };

  useEffect(() => {
    if (devEnabled && current === null) {
      setNotifications(null);
      setCases(null);
      return;
    }
    void loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, devEnabled, sessionEpoch]);

  const handleNotifAction = async (id: string, kind: "read" | "ack") => {
    setActionFlash(null);
    try {
      await request(`/notifications/${encodeURIComponent(id)}/${kind}`, {
        method: "POST",
        // ★ 必须带 `notification_id`：后端 `NotificationItemBody` 把它列为必填
        //   （`api/write_api.py` 的 `_notification_command`）。改前这里发的是
        //   `body: {}` —— 于是每次点「标记已读」都拿到 **422 Unprocessable
        //   Entity**，而页面把非 501 的失败吞进 catch 后**什么都没变**：
        //   通知还是未读、也没有报错条，读起来像「按钮没反应」。
        //   这是浏览器联调抓到的第一个真实接线缺陷（`pairing_check.mjs`
        //   的 `--expect-write` 与 dev-up 的 [8/11] 都会命中它）。
        body: { notification_id: id },
        idempotencyKey: crypto.randomUUID(),
      });
      setActionFlash(`通知 ${id} 已标记为 ${kind}`);
      await loadAll();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 501) {
        setNotifications((prev) =>
          (prev ?? []).map((n) =>
            n.notification_id === id
              ? {
                  ...n,
                  unread: false,
                  ...(kind === "ack" ? { acked_at: new Date().toISOString() } : {}),
                }
              : n,
          ),
        );
        setActionFlash(
          `通知 ${id} 已在本地标记为 ${kind}（后端写端点当前为 501 占位）`,
        );
      } else {
        setActionFlash(`操作未完成：${e instanceof Error ? e.message : String(e)}`);
      }
    }
  };

  const pendingSelfCases = (cases ?? []).filter((c) => c.state === "待自决");

  return (
    <section className="cases-page" aria-labelledby="inbox-page-title">
      <div className="cases-page__head">
        <div>
          <h1 id="inbox-page-title">收件箱与我的内容（P-02）</h1>
          <p className="hint">
            失效与自动重审仅产生工作台内（In-App）通知记录，不代表飞书或个人外部消息已送达（UJ-7）。
          </p>
        </div>
        <Link to="/submit" className="btn">
          <Icon name="plus" size={12} /> 新建内容提交单
        </Link>
      </div>

      {error && (
        <div className="state state--error" role="alert">
          读取收件箱失败：{error}
        </div>
      )}

      {actionFlash && (
        <div className="state" role="status">
          {actionFlash}
        </div>
      )}

      <h2>
        <Icon name="bell" size={13} /> 工作台通知收件箱（
        {(notifications ?? []).length} 条）
      </h2>
      {notifications === null ? (
        <p className="hint">加载通知中…</p>
      ) : notifications.length === 0 ? (
        <div className="state">
          <p className="hint">当前主体暂无工作台内通知记录。</p>
        </div>
      ) : (
        <ul className="handoff-list">
          {notifications.map((n) => (
            <li key={n.notification_id} className="state">
              <div className="evidence__head">
                <span className="font-data">
                  <strong>{n.notification_id}</strong>
                </span>
                <span className="badge badge--pending" data-status-badge="">
                  {n.type ?? "in_app"}
                </span>
                <span className="hint">
                  {n.unread === false ? "已读" : "未读"}
                  {n.acked_at ? ` · 已确认 (${n.acked_at})` : ""}
                </span>
              </div>
              {n.payload && (
                <pre className="evidence__quote font-data">
                  {JSON.stringify(n.payload, null, 2)}
                </pre>
              )}
              <div className="actions__row">
                <Button
                  variant="secondary"
                  disabled={n.unread === false}
                  onClick={() => void handleNotifAction(n.notification_id, "read")}
                >
                  标记已读（Read）
                </Button>
                <Button
                  variant="secondary"
                  disabled={Boolean(n.acked_at)}
                  onClick={() => void handleNotifAction(n.notification_id, "ack")}
                >
                  确认知悉（Ack）
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <h2>
        <Icon name="inbox" size={13} /> 待自决专区（DP1 业务自审 ·{" "}
        {pendingSelfCases.length} 条）
      </h2>
      <p className="hint">
        「待自决」不等同于「通过」或「已放行」（UIUX §5.1）：请核对提示后选择修改重提或进入案件补充说明。
      </p>
      {cases === null ? (
        <p className="hint">加载案件中…</p>
      ) : pendingSelfCases.length === 0 ? (
        <div className="empty">
          <p className="empty__title">当前没有处于「待自决」状态的案件</p>
          <p>
            「待自决」是机器判不了、需要业务方自己确认的那一类，不等同于通过或已放行。
          </p>
        </div>
      ) : (
        <div className="cases-table-wrap">
          <table className="cases-table">
            <thead>
              <tr>
                <th scope="col">案件编号</th>
                <th scope="col">状态</th>
                <th scope="col">内容摘要</th>
                <th scope="col">产品线 / 渠道</th>
                <th scope="col">放行状态</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              {pendingSelfCases.map((c) => (
                <tr key={c.case_id}>
                  <td className="font-data">
                    <Link to={`/cases/${encodeURIComponent(c.case_id)}`}>
                      {c.case_id}
                    </Link>
                  </td>
                  <td>
                    <StatusBadge axis="decision" value={c.state} />
                  </td>
                  <td className="cases-table__excerpt">
                    {c.title_or_excerpt ?? "（无文本摘要）"}
                  </td>
                  <td>
                    {c.product_line ?? "未测"}
                    {c.entry_channel ? ` · ${c.entry_channel}` : ""}
                  </td>
                  <td>{c.release_status ?? "待放行"}</td>
                  <td>
                    <div className="actions__row">
                      <Link
                        to={`/cases/${encodeURIComponent(c.case_id)}`}
                        className="btn"
                      >
                        查看详情
                      </Link>
                      <Link to="/submit" className="btn">
                        修改重提
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
