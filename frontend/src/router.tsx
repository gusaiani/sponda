import {
  createRouter,
  createRoute,
  createRootRoute,
} from "@tanstack/react-router";
import { App } from "./App";
import { HomePage } from "./routes/index";
import { SignupPage } from "./routes/signup";
import { LoginPage } from "./routes/login";
import { ForgotPasswordPage } from "./routes/forgot-password";
import { ResetPasswordPage } from "./routes/reset-password";
import { AccountPage } from "./routes/account";
import { SharedComparisonPage } from "./routes/shared";
import { GoogleCallbackPage } from "./routes/google-callback";
import { AdminDashboardPage } from "./routes/admin-dashboard";
import { TickerPage } from "./routes/$ticker";

const rootRoute = createRootRoute({
  component: App,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: HomePage,
});

const signupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/signup",
  component: SignupPage,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginPage,
});

const forgotPasswordRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/forgot-password",
  component: ForgotPasswordPage,
});

const resetPasswordRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reset-password",
  component: ResetPasswordPage,
});

const accountRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/account",
  component: AccountPage,
});

const googleCallbackRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/google/callback",
  component: GoogleCallbackPage,
});

const adminDashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin-dashboard",
  component: AdminDashboardPage,
});

const sharedComparisonRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/shared/$token",
  component: SharedComparisonPage,
});

// Layout route: renders TickerPage which reads the path to pick the active tab.
// Child routes (graficos, comparar) exist only for URL matching — TickerPage
// handles all rendering internally (no Outlet needed in TickerPage).
const tickerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/$ticker",
  component: TickerPage,
});

// Empty child routes — TickerPage detects these from location.pathname
const tickerGraficosRoute = createRoute({
  getParentRoute: () => tickerRoute,
  path: "/graficos",
});

const tickerCompararRoute = createRoute({
  getParentRoute: () => tickerRoute,
  path: "/comparar",
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  signupRoute,
  loginRoute,
  forgotPasswordRoute,
  resetPasswordRoute,
  accountRoute,
  googleCallbackRoute,
  adminDashboardRoute,
  sharedComparisonRoute,
  tickerRoute.addChildren([tickerGraficosRoute, tickerCompararRoute]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
