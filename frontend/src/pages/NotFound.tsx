import { Link } from "react-router-dom";
import { useT } from "../lib/i18n";
import { useTitle } from "../lib/useTitle";

export default function NotFound() {
  const { t } = useT();
  useTitle(t("notFound"));
  return (
    <div className="card p-10 text-center">
      <h1 className="font-display text-3xl">{t("notFound")}</h1>
      <Link to="/" className="btn-primary mt-6">
        {t("navDashboard")}
      </Link>
    </div>
  );
}
