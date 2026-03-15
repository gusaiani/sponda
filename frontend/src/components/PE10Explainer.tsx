import { useState } from "react";
import "../styles/card.css";

export function PE10Explainer() {
  const [pe10Open, setPE10Open] = useState(false);
  const [pfcf10Open, setPFCF10Open] = useState(false);

  return (
    <div className="pe10-explainer-wrapper">
      {/* PE10 */}
      <button
        className="pe10-explainer-toggle"
        onClick={() => setPE10Open(!pe10Open)}
      >
        {pe10Open ? "Ocultar" : "O que é o PE10?"}
        <span className={`pe10-explainer-chevron ${pe10Open ? "pe10-explainer-chevron-open" : ""}`}>
          &#9662;
        </span>
      </button>

      {pe10Open && (
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

      {/* PFCF10 */}
      <button
        className="pe10-explainer-toggle"
        onClick={() => setPFCF10Open(!pfcf10Open)}
      >
        {pfcf10Open ? "Ocultar" : "O que é o PFCF10?"}
        <span className={`pe10-explainer-chevron ${pfcf10Open ? "pe10-explainer-chevron-open" : ""}`}>
          &#9662;
        </span>
      </button>

      {pfcf10Open && (
        <div className="pe10-explainer">
          <p>
            O <strong>PFCF10</strong> é o índice preço/fluxo de caixa livre
            calculado sobre a média do fluxo de caixa livre real (ajustado pela
            inflação) dos últimos 10 anos.
          </p>
          <p>
            <strong>Fluxo de caixa livre (FCF)</strong> é o caixa que a empresa
            de fato gera após seus investimentos. Aqui, definimos FCF como
            fluxo de caixa operacional + fluxo de caixa de investimento.
          </p>
          <p>
            <strong>Qual a diferença entre FCF e lucro?</strong> O lucro líquido
            é um número contábil que inclui itens não-monetários como depreciação,
            amortização e provisões. Uma empresa pode reportar lucro alto mas gerar
            pouco caixa — ou vice-versa. O FCF mostra quanto dinheiro realmente
            entrou (ou saiu) do caixa, o que é mais difícil de manipular e mais
            relevante para quem quer saber o que a empresa pode distribuir aos
            acionistas ou reinvestir.
          </p>
          <p>
            O PFCF10 complementa o PE10: comparar os dois indicadores para uma
            mesma empresa revela se os lucros reportados se traduzem em geração
            real de caixa.
          </p>
        </div>
      )}
    </div>
  );
}
