"use client";

import { Suspense } from "react";
import { GoogleCallbackContent } from "./GoogleCallbackContent";

export default function GoogleCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="auth-container">
          <div className="auth-card">
            <p className="auth-success-text">Loading...</p>
          </div>
        </div>
      }
    >
      <GoogleCallbackContent />
    </Suspense>
  );
}
