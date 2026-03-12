import { useQuota } from "../hooks/useQuota";
import "../styles/auth.css";

export function QuotaAlert() {
  const { data } = useQuota();

  if (!data || data.remaining > 0) return null;

  return (
    <div className="quota-alert">
      <p className="quota-alert-text">
        Você atingiu o limite de {data.limit} consultas diárias.{" "}
        <a href="/signup" className="quota-alert-link">
          Crie uma conta
        </a>{" "}
        para continuar.
      </p>
    </div>
  );
}
