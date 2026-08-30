/**
 * Minimal robots.txt matcher, enough to test our own file against the
 * paths that matter.
 *
 * Follows RFC 9309 as Google and X apply it: `*` matches any run of
 * characters, `$` anchors the end, and when several rules match a path the
 * longest one wins, with Allow beating Disallow on a tie. Only the
 * `User-agent: *` group is read, which is the only group we publish.
 */

interface RobotsRule {
  allow: boolean;
  pattern: string;
}

function parseRules(robotsTxt: string): RobotsRule[] {
  const rules: RobotsRule[] = [];
  let inWildcardGroup = false;
  for (const rawLine of robotsTxt.split("\n")) {
    const line = rawLine.replace(/#.*$/, "").trim();
    if (!line) continue;
    const [field, ...rest] = line.split(":");
    const value = rest.join(":").trim();
    const key = field.trim().toLowerCase();
    if (key === "user-agent") {
      inWildcardGroup = value === "*";
    } else if (inWildcardGroup && (key === "allow" || key === "disallow") && value) {
      rules.push({ allow: key === "allow", pattern: value });
    }
  }
  return rules;
}

function patternToRegExp(pattern: string): RegExp {
  const anchored = pattern.endsWith("$");
  const body = (anchored ? pattern.slice(0, -1) : pattern)
    .split("*")
    .map((literal) => literal.replace(/[.+?^${}()|[\]\\]/g, "\\$&"))
    .join(".*");
  return new RegExp(`^${body}${anchored ? "$" : ""}`);
}

export function isPathAllowedByRobots(robotsTxt: string, pathname: string): boolean {
  const matching = parseRules(robotsTxt).filter((rule) => patternToRegExp(rule.pattern).test(pathname));
  if (matching.length === 0) return true;
  const longest = Math.max(...matching.map((rule) => rule.pattern.length));
  const winners = matching.filter((rule) => rule.pattern.length === longest);
  return winners.some((rule) => rule.allow);
}
