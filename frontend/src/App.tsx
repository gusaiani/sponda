import { Outlet } from "@tanstack/react-router";
import "./styles/global.css";

export function App() {
  return (
    <div className="app-container">
      <header className="app-header">
        <div className="app-header-inner">
          <a href="/" className="app-logo">
            Sponda
          </a>
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
