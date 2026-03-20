import {
  createRouter,
  createRoute,
  createRootRoute,
} from "@tanstack/react-router";
import { App } from "./App";
import { HomePage } from "./routes/index";
import { SignupPage } from "./routes/signup";
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
  tickerRoute.addChildren([tickerGraficosRoute, tickerCompararRoute]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
