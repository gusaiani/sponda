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

const tickerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/$ticker",
  component: TickerPage,
});

const routeTree = rootRoute.addChildren([indexRoute, signupRoute, tickerRoute]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
