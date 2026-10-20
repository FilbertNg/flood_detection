/** Short visible attribution plus the full licence text; must stay reachable on every map screen. */
export function Credits() {
  return (
    <div className="credits">
      <p>© OpenStreetMap contributors · JPS Public Infobanjir · MET Malaysia · Open-Meteo · FABDEM (Univ. of Bristol, CC BY-NC-SA) · ESA WorldCover</p>
      <details className="credits-full">
        <summary>Sources</summary>
        <p>
          © OpenStreetMap contributors · Data: JPS Public Infobanjir, MET Malaysia, Open-Meteo · Terrain: Copernicus GLO-30, FABDEM (Univ. of Bristol, CC BY-NC-SA 4.0), © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium (CC BY 4.0)
        </p>
      </details>
    </div>
  );
}
