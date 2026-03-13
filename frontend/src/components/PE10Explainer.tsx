import { useState } from "react";
import "../styles/card.css";

export function PE10Explainer() {
  const [open, setOpen] = useState(false);

  return (
    <div className="pe10-explainer-wrapper">
      <button
        className="pe10-explainer-toggle"
        onClick={() => setOpen(!open)}
      >
        {open ? "Ocultar" : "O que é o PE10?"}
        <span
          className={`pe10-explainer-chevron ${open ? "pe10-explainer-chevron-open" : ""}`}
        >
          &#9662;
        </span>
      </button>

      {open && (
        <div className="pe10-explainer">
          <p>
            O <strong>PE10</strong> (também conhecido como <strong>CAPE</strong>)
            é o índice preço/lucro calculado sobre a média dos lucros reais
            (ajustados pela inflação) dos últimos 10 anos.
          </p>
          <p>
            Ao suavizar oscilações cíclicas de curto prazo, o PE10 oferece uma
            visão mais estável de quanto o mercado está pagando por cada real de
            lucro. Valores elevados sugerem que o ativo pode estar caro em
            relação ao seu histórico de rentabilidade, enquanto valores baixos
            podem indicar oportunidades.
          </p>
          <p>
            <strong>Atenção:</strong> para empresas em forte crescimento ou
            declínio, o PE10 pode levar a conclusões equivocadas, já que a média
            de 10 anos não reflete a trajetória recente dos lucros. Use-o como
            um dos fatores da análise, não como critério único.
          </p>
        </div>
      )}
    </div>
  );
}
