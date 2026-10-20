import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ProductionIdentityProvider } from "./components/IdentitySwitcher";
import "./styles.css";

const DevIdentityProvider = __REVIEW_DEV_IDENTITY__
  ? lazy(() => import("./components/DevIdentityProvider"))
  : null;

const app = (
  <BrowserRouter>
    {DevIdentityProvider ? (
      <Suspense fallback={<p>加载本地开发身份入口…</p>}>
        <DevIdentityProvider>
          <App />
        </DevIdentityProvider>
      </Suspense>
    ) : (
      <ProductionIdentityProvider>
        <App />
      </ProductionIdentityProvider>
    )}
  </BrowserRouter>
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>{app}</StrictMode>,
);
