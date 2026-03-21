/**
 * Extract the Django CSRF token from the cookie.
 * Django sets the cookie name as 'csrftoken' by default.
 */
export function getCSRFToken(): string {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : "";
}

/**
 * Headers to include in mutating requests (POST, PUT, DELETE)
 * that use Django session authentication.
 */
export function csrfHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-CSRFToken": getCSRFToken(),
  };
}
