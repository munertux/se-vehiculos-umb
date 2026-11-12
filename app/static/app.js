/* Utilidades comunes de la interfaz: llamadas a la API con token CSRF. */
(function () {
  const meta = document.querySelector('meta[name="csrf-token"]');
  const token = meta ? meta.getAttribute("content") : "";

  async function api(ruta, opciones = {}) {
    const metodo = (opciones.method || "GET").toUpperCase();
    const cabeceras = Object.assign({ Accept: "application/json" }, opciones.headers || {});
    if (metodo !== "GET") {
      cabeceras["X-CSRF-Token"] = token;
      if (opciones.body && !cabeceras["Content-Type"]) cabeceras["Content-Type"] = "application/json";
    }
    const resp = await fetch(ruta, Object.assign({}, opciones, { headers: cabeceras, credentials: "same-origin" }));
    if (resp.status === 401) {
      window.location.href = "/login";
      throw new Error("La sesión expiró. Ingrese de nuevo.");
    }
    const cuerpo = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(cuerpo.error || `Error ${resp.status}`);
    return cuerpo;
  }

  function escapar(texto) {
    const div = document.createElement("div");
    div.textContent = texto == null ? "" : String(texto);
    return div.innerHTML;
  }

  window.SE = { api, escapar, csrf: token };
})();
