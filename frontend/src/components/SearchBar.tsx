import { useState, FormEvent } from "react";
import "../styles/search.css";

interface SearchBarProps {
  onSearch: (ticker: string) => void;
  isLoading: boolean;
}

export function SearchBar({ onSearch, isLoading }: SearchBarProps) {
  const [input, setInput] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const ticker = input.trim().toUpperCase();
    if (ticker) {
      onSearch(ticker);
    }
  }

  return (
    <div className="search-container">
      <form className="search-form" onSubmit={handleSubmit}>
        <input
          type="text"
          className="search-input"
          placeholder="Digite o ticker, ex: PETR4"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button
          type="submit"
          className="search-button"
          disabled={isLoading || !input.trim()}
        >
          {isLoading ? "Buscando..." : "Buscar"}
        </button>
      </form>
    </div>
  );
}
