"use client";

import { use, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "../../../../i18n";
import type { SpondPayload } from "../../../../hooks/useProfile";
import { SpondThread } from "../../../../components/social/SpondThread";

interface Props {
  params: Promise<{ locale: string; id: string }>;
}

interface ThreadResponse {
  spond: SpondPayload;
  replies: SpondPayload[];
}

async function fetchThread(id: string): Promise<ThreadResponse | null> {
  const r = await fetch(`/api/social/sponds/${id}/`, { credentials: "include" });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error("thread_fetch_failed");
  return r.json();
}

export default function SpondPermalinkPage({ params }: Props) {
  const { id } = use(params);
  const { t } = useTranslation();
  const [refresh, setRefresh] = useState(0);
  // Set when the visitor clicked Reply on a card without an inline
  // composer (and possibly logged in on the way here).
  const wantsToReply = useSearchParams().get("reply") === "1";

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["social-thread", id, refresh],
    queryFn: () => fetchThread(id),
    staleTime: 5_000,
  });

  useEffect(() => {
    refetch();
  }, [refresh, refetch]);

  if (isLoading) {
    return (
      <div style={{ maxWidth: "640px", margin: "32px auto", padding: "0 16px", color: "#666" }}>
        {t("common.loading")}
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ maxWidth: "640px", margin: "32px auto", padding: "0 16px", color: "#666" }}>
        404
      </div>
    );
  }

  return (
    <>
      <meta name="robots" content="noindex,follow" />
      <div style={{ maxWidth: "640px", margin: "32px auto", padding: "0 16px" }}>
        <SpondThread
          spond={data.spond}
          replies={data.replies}
          inlineReply
          startReplying={wantsToReply}
          onChanged={() => setRefresh((n) => n + 1)}
        />
      </div>
    </>
  );
}
