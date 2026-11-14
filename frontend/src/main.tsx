import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import "./index.css";
import { I18nProvider } from "./lib/i18n";
import Analysis from "./pages/Analysis";
import Dashboard from "./pages/Dashboard";
import Editor from "./pages/Editor";
import ExportPage from "./pages/Export";
import FeedbackPage from "./pages/Feedback";
import NewProject from "./pages/NewProject";
import NotFound from "./pages/NotFound";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="new" element={<NewProject />} />
            <Route path="projects/:id" element={<Analysis />} />
            <Route path="projects/:id/editor" element={<Editor />} />
            <Route path="projects/:id/export" element={<ExportPage />} />
            <Route path="feedback" element={<FeedbackPage />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </I18nProvider>
  </StrictMode>,
);
