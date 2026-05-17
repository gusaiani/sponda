"use client";

import { SpondComposer } from "./SpondComposer";
import { SpondFeed } from "./SpondFeed";

interface Props {
  ticker: string;
}

export function SpondsTab({ ticker }: Props) {
  return (
    <div style={{ maxWidth: "640px", margin: "16px auto", padding: "0 16px" }}>
      <SpondComposer lockedTicker={ticker} />
      <SpondFeed kind="company" ticker={ticker} />
    </div>
  );
}
