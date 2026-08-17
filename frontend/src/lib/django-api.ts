const DEFAULT_DJANGO_API_URL = "http://localhost:8710";

/** Base URL of the Django API as seen from the Next.js server process. */
export function djangoApiBaseUrl(): string {
  return process.env.DJANGO_API_URL || DEFAULT_DJANGO_API_URL;
}
