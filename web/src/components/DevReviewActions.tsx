import type { CaseDetail } from "../api/client";
import ReviewActions from "./ReviewActions";

interface Props {
  detail: CaseDetail;
  refresh: () => Promise<CaseDetail | null>;
}

/**
 * 开发验收写动作入口（与生产版共用同一套完整复核与草稿交接状态机）。
 */
export default function DevReviewActions({ detail, refresh }: Props) {
  return <ReviewActions detail={detail} refresh={refresh} mode="dev" />;
}
