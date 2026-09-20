import { useState } from "react";
import { currentTheme, setTheme, type Theme } from "../lib/theme";

const SUN =
  "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm0-10.5a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1A.75.75 0 0 1 8 .5zm0 12.25a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1a.75.75 0 0 1 .75-.75zM15.5 8a.75.75 0 0 1-.75.75h-1a.75.75 0 0 1 0-1.5h1a.75.75 0 0 1 .75.75zM3 8a.75.75 0 0 1-.75.75h-1a.75.75 0 0 1 0-1.5h1A.75.75 0 0 1 3 8zm10.3-5.3a.75.75 0 0 1 0 1.06l-.7.7a.75.75 0 0 1-1.06-1.06l.7-.7a.75.75 0 0 1 1.06 0zM4.46 11.54a.75.75 0 0 1 0 1.06l-.7.7a.75.75 0 0 1-1.06-1.06l.7-.7a.75.75 0 0 1 1.06 0zm8.84 1.76a.75.75 0 0 1-1.06 0l-.7-.7a.75.75 0 0 1 1.06-1.06l.7.7a.75.75 0 0 1 0 1.06zM4.46 4.46a.75.75 0 0 1-1.06 0l-.7-.7A.75.75 0 0 1 3.76 2.7l.7.7a.75.75 0 0 1 0 1.06z";
const MOON = "M6 .5a.75.75 0 0 1 .2.83A5.5 5.5 0 0 0 14.67 8.8a.75.75 0 0 1 1.03 1.03A7.5 7.5 0 1 1 5.17.3.75.75 0 0 1 6 .5z";

/** Sem escolha salva a página segue o sistema; o clique fixa claro ou escuro neste navegador. */
export function ThemeToggle() {
  const [theme, setLocal] = useState<Theme>(currentTheme);
  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      onClick={() => {
        setTheme(next);
        setLocal(next);
      }}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
        <path d={theme === "dark" ? SUN : MOON} />
      </svg>
    </button>
  );
}
