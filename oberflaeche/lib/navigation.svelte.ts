// Welche Seite offen ist, als Anker in der Adresse (#/einstellungen), damit Links und Zurück funktionieren.
export const navigation = $state({ seite: "" });

function lesen(): void {
  navigation.seite = location.hash.startsWith("#/") ? decodeURIComponent(location.hash.slice(2)) : "";
}

export function navigationStarten(): () => void {
  lesen();
  addEventListener("hashchange", lesen);
  return () => removeEventListener("hashchange", lesen);
}

export function gehe(seite: string): void {
  location.hash = `#/${encodeURIComponent(seite)}`;
}
