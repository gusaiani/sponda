import { AI_ACCESS_INTRO, AI_ACCESS_SECTIONS, AI_ACCESS_TITLE } from "../../../lib/ai-access-copy";

const CODE_FENCE = "```";

/**
 * The "For AI agents" article, server-rendered.
 *
 * Deliberately free of hooks and of a client boundary. The whole audience for
 * this page is software reading the HTML, and every other content block on a
 * company page is behind `dynamic(..., { ssr: false })`, which is the reason
 * the markdown twins had to exist in the first place. This one page has to be
 * in the document.
 */
export function AiAccessArticle() {
  return (
    <article className="ai-access">
      <h1>{AI_ACCESS_TITLE}</h1>
      <p>{AI_ACCESS_INTRO}</p>

      {AI_ACCESS_SECTIONS.map((section) => (
        <section key={section.heading}>
          <h2>{section.heading}</h2>
          {section.body.map((block, index) =>
            block.startsWith(CODE_FENCE) ? (
              <pre key={index}>
                <code>{block.slice(CODE_FENCE.length, -CODE_FENCE.length).trim()}</code>
              </pre>
            ) : (
              <p key={index}>{block}</p>
            ),
          )}
        </section>
      ))}
    </article>
  );
}
