import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import LoadingRows from "../components/LoadingRows";
import { usePolling } from "../hooks/usePolling";
import { shouldSurfaceFailures } from "../hooks/polling.logic";
import {
  ApiError,
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

  // ★ ADR-0021 · W-3：收件箱轮询。
  //
  //   `loadAll` 保留原样 —— 它被写动作（标记已读/确认）复用，那需要
  //   **一次成功/失败的明确结果**；而轮询需要的是「静默刷新 + 失败计数」。
  //   两者混成一个函数会让「写后回读」也带上轮询语义（比如失败被吞掉）。
  //
  //   所以这里给轮询单独一个 loader：与 `loadAll` 拉同样的两个接口，
  //   但**抛错**（让 hook 计失败次数），并且不清空旧数据。
  const poll = usePolling(
    useCallback(async () => {
      if (devEnabled && current === null) return;
      // ★ 不用 `loadAll`：它会自己吞掉异常，`usePolling` 就永远数不到失败。
      const [notifRows, caseRows] = await Promise.all([
        reviewApi.listNotifications(),
        reviewApi.listCases(),
      ]);
      setNotifications(notifRows);
      setCases(caseRows);
      setError(null);
    }, [current, devEnabled]),
    { enabled: !(devEnabled && current === null) },
  );

  // ★ 首次加载才清空；后续刷新保留旧数据（轮询不清空是 W-3 的核心口径）。
  //
  // ★★ 这里**不能**把 `poll.phase` 放进依赖：phase 每轮都会变
  //   （initial → idle → refreshing → idle…），放进去的话
  //   「phase === initial 时清空」会在每轮首次那一帧成立 —— 列表又闪了。
  //   正确写法：清空只跟「身份/会话变了」走（那是真的换了数据源）；
  //   轮询本身从不清空。
  // ★★★ 2026-10-30：与 `QueuePage` 同一处竞态，同一个修法。
  //
  //   依赖里原来有 `current`。而 `current` 在 `/api/v1/me` 返回时会从 null
  //   变成对象 —— 那是**首屏加载过程中必然发生的一次变化**，不是「换了身份」。
  //   于是清空 effect 会在取数请求还在飞的时候跑一遍 `setXxx(null)`，
  //   谁先跑取决于两个请求的返回顺序 —— 竞态。
  //   在 QueuePage 上的实测表现是「永远停在骨架屏，等 20 秒轮询才恢复」。
  //
  //   修法：开发身份未就绪（`devEnabled && current === null`）时才清；
  //   会话真的换了（`sessionEpoch`）时也清。`current` 从 null → 对象不清。
  const devIdentityReady = devEnabled ? current !== null : true;
  useEffect(() => {
    if (!devIdentityReady) {
      setNotifications(null);
      setCases(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [devIdentityReady]);

  useEffect(() => {
    setNotifications(null);
    setCases(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionEpoch]);

  const handleNotifAction = async (id: string, kind: "read" | "ack") => {
    setActionFlash(null);
    try {
      await reviewApi.markNotification(id, kind, crypto.randomUUID());
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
          <h1 id="inbox-page-title">待办收件箱</h1>
          <p className="hint">
            集中查看分配给您的待办提醒与需品牌自决的案件。
          </p>
          {/* ★ ADR-0021 · W-3：收件箱轮询状态。
              只在刷新中 / 连续失败时出现（不占位、不清空列表）。
              轮询失败时界面上还是旧数据 —— **看起来完全正常**，
              所以这里必须说一句，否则用户会以为「没有新待办」。 */}
          {(poll.phase === "refreshing" || shouldSurfaceFailures(poll.failures)) && (
            <p className="hint" data-poll-status="" role="status" aria-live="polite">
              {poll.phase === "refreshing"
                ? "正在更新收件箱…"
                : `后台刷新失败（连续 ${poll.failures} 次），当前显示的可能不是最新数据`}
            </p>
          )}
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
        <Icon name="bell" size={13} /> 工作台通知收件箱
        {notifications !== null && `（${notifications.length} 条）`}
      </h2>
      {notifications === null ? (
        <LoadingRows rows={3} label="正在加载通知" />
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
                  <strong>{n.notification_id.slice(0, 12)}</strong>
                </span>
                <span className="badge badge--pending" data-status-badge="">
                  {n.type ?? "in_app"}
                </span>
                <span className="hint">
                  {n.unread === false ? "已读" : "未读"}
                  {n.acked_at ? `，已确认 (${n.acked_at})` : ""}
                </span>
              </div>
              {n.payload && (
                <pre className="evidence__quote font-data">
                  {JSON.stringify(n.payload, null, 2)}
                </pre>
              )}
              {(n.unread !== false || !n.acked_at) && (
                <div className="actions__row">
                  {n.unread !== false && (
                    <Button
                      variant="secondary"
                      onClick={() => void handleNotifAction(n.notification_id, "read")}
                    >
                      标记已读
                    </Button>
                  )}
                  {!n.acked_at && (
                    <Button
                      variant="secondary"
                      onClick={() => void handleNotifAction(n.notification_id, "ack")}
                    >
                      确认知悉
                    </Button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <h2>
        <Icon name="inbox" size={13} /> 待自决专区（业务自审，{" "}
        {cases === null ? "尚未读取" : `${pendingSelfCases.length} 条`}）
      </h2>
      <p className="hint">
        以下内容需业务方自行评估确认，核对后可修改重提或进入案件补充说明。
      </p>
      {cases === null ? (
        <LoadingRows rows={2} label="正在加载案件" />
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
                    {c.entry_channel ? ` ${c.entry_channel}` : ""}
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
