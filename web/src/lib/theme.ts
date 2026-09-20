// Tema: segue o sistema até a pessoa clicar no botão; a escolha fica no navegador dela.
// Os tokens escuros vivem em `.dark` (mesmo esquema do studio).

export type Theme = "light" | "dark";

const KEY = "jev-theme";
const system = window.matchMedia("(prefers-color-scheme: dark)");

/** localStorage pode estar bloqueado (aba privada, política do navegador): sem escolha salva, segue o sistema. */
function stored(): Theme | null {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

export function currentTheme(): Theme {
  return stored() ?? (system.matches ? "dark" : "light");
}

function apply(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.style.colorScheme = theme;
}

export function setTheme(theme: Theme): void {
  try {
    window.localStorage.setItem(KEY, theme);
  } catch {
    // sem storage a escolha vale só pra esta visita
  }
  apply(theme);
}

/** Aplica o tema inicial e acompanha o sistema enquanto não houver escolha salva. */
export function initTheme(): void {
  apply(currentTheme());
  system.addEventListener("change", () => {
    if (stored() === null) apply(currentTheme());
  });
}
