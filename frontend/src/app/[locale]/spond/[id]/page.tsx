"use client";

import { use, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "../../../../i18n";
import { useAuth } from "../../../../hooks/useAuth";
import type { SpondPayload } from "../../../../hooks/useProfile";
import { SpondCard } from "../../../../components/social/SpondCard";
import { SpondComposer } from "../../../../components/social/SpondComposer";

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
  const { isAuthenticated } = useAuth();
  const [refresh, setRefresh] = useState(0);

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
        <SpondCard spond={data.spond} />
        {isAuthenticated && (
          <SpondComposer
            parentId={data.spond.id}
            parentHandle={data.spond.author.handle}
            onSubmitted={() => setRefresh((n) => n + 1)}
          />
        )}
        {data.replies.length > 0 && (
          <div style={{ marginTop: "16px" }}>
            {data.replies.map((reply) => <SpondCard key={reply.id} spond={reply} />)}
          </div>
        )}
      </div>
    </>
  );
}
