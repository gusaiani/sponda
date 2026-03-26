import Link from "next/link";

export default function TickerNotFound() {
  return (
    <div className="pe10-card" style={{ textAlign: "center", padding: "3rem 1rem" }}>
      <h2>Ticker não encontrado</h2>
      <p style={{ marginTop: "0.5rem", color: "var(--text-secondary)" }}>
        O código informado não corresponde a nenhuma ação listada na B3.
      </p>
      <Link href="/" style={{ marginTop: "1rem", display: "inline-block" }}>
        Voltar para a página inicial
      </Link>
    </div>
  );
}
