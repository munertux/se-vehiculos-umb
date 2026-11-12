/* Pantalla de consulta: preguntas sucesivas con la escala de certeza y
   presentación del resultado (top 5 de hipótesis). */
(function () {
  const { api, escapar } = window.SE;
  const el = (id) => document.getElementById(id);
  const datos = JSON.parse(el("datos-consulta").textContent);
  const idAtencion = datos.id_atencion;
  const PREGUNTAS_ESTIMADAS = 15;
  const CERTEZA = { si: "1,00", probablemente_si: "0,75", no_se: "0,50", probablemente_no: "0,25", no: "0,00" };
  let numero = datos.n || 1;
  let ocupado = false;

  function mostrarError(msg) {
    const caja = el("error-consulta");
    caja.textContent = msg;
    caja.classList.toggle("oculto", !msg);
  }

  function progreso() {
    el("texto-progreso").textContent = `Pregunta ${numero}`;
    el("num-pregunta").textContent = `Pregunta ${numero}`;
    el("barra-progreso").style.width = Math.min(95, (numero / PREGUNTAS_ESTIMADAS) * 100) + "%";
  }

  function bloquear(valor) {
    ocupado = valor;
    document.querySelectorAll("#opciones-respuesta button, #btn-finalizar").forEach((b) => (b.disabled = valor));
  }

  function mostrarPregunta(pregunta) {
    el("texto-pregunta").textContent = pregunta.enunciado;
    const cont = el("opciones-respuesta");
    cont.innerHTML = "";
    pregunta.opciones.forEach((op) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.innerHTML = `${escapar(op.etiqueta)}<small>certeza ${CERTEZA[op.clave] || ""}</small>`;
      btn.onclick = () => responder(pregunta.id_pregunta, op.clave);
      cont.appendChild(btn);
    });
    progreso();
  }

  async function responder(idPregunta, clave) {
    if (ocupado) return;
    bloquear(true);
    mostrarError("");
    try {
      const r = await api(`/api/atenciones/${idAtencion}/respuestas`, {
        method: "POST",
        body: JSON.stringify({ id_pregunta: idPregunta, respuesta: clave }),
      });
      if (r.estado === "finalizado") {
        mostrarResultado(r.resultado);
      } else {
        numero += 1;
        mostrarPregunta(r.pregunta);
      }
    } catch (e) {
      mostrarError(e.message);
    } finally {
      bloquear(false);
    }
  }

  async function finalizar(sinConfirmar) {
    if (ocupado) return;
    if (sinConfirmar !== true && !confirm("¿Terminar la consulta con las respuestas dadas hasta ahora?")) return;
    bloquear(true);
    try {
      const r = await api(`/api/atenciones/${idAtencion}/finalizar`, { method: "POST", body: "{}" });
      mostrarResultado(r.resultado);
    } catch (e) {
      mostrarError(e.message);
    } finally {
      bloquear(false);
    }
  }

  function formatoProb(p) {
    return Number(p).toFixed(1).replace(".", ",") + " %";
  }

  function mostrarResultado(hipotesis) {
    el("pantalla-pregunta").classList.add("oculto");
    el("pantalla-resultado").classList.remove("oculto");
    el("advertencia").classList.toggle("oculto", !hipotesis.some((h) => h.advertencia));

    const cont = el("resultados");
    cont.innerHTML = "";
    if (!hipotesis.length) {
      cont.innerHTML = '<p class="vacio">Con las respuestas dadas no fue posible identificar una hipótesis de falla.</p>';
      return;
    }
    hipotesis.forEach((h) => {
      const reglas = (h.reglas_activadas || []).map((c) => `<span class="codigo-regla">${escapar(c)}</span>`).join("")
        || '<span class="texto-3">—</span>';
      const div = document.createElement("article");
      div.className = "resultado-item " + (h.nivel_clase || "");
      div.innerHTML = `
        <div class="resultado-cabeza">
          <h3><span class="posicion">${h.posicion}.</span>${escapar(h.nombre)}</h3>
          <div class="probabilidad">
            <div class="probabilidad-barra"><i style="width:${Math.min(100, Number(h.probabilidad) || 0)}%"></i></div>
            <strong>${formatoProb(h.probabilidad)}</strong>
          </div>
        </div>
        <div class="resultado-meta">
          <span class="nivel ${escapar(h.nivel_clase)}">${escapar(h.nivel_texto || h.nivel_atencion)}</span>
          <span>Reglas activadas: ${reglas}</span>
        </div>
        <p class="recomendacion"><strong>Recomendación:</strong> ${escapar(h.recomendacion)}</p>
        <div class="resultado-acciones"></div>`;
      const acciones = div.querySelector(".resultado-acciones");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "boton chico exito";
      btn.textContent = "Confirmar falla real";
      btn.onclick = () => confirmar(h, acciones);
      acciones.appendChild(btn);
      cont.appendChild(div);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function confirmar(h, acciones) {
    const observacion = prompt(`Confirmar «${h.nombre}» como la falla real.\nObservación del técnico (opcional):`, "");
    if (observacion === null) return;
    try {
      await api(`/api/atenciones/${idAtencion}/confirmar`, {
        method: "POST",
        body: JSON.stringify({ id_hipotesis: h.id_hipotesis, observacion }),
      });
      document.querySelectorAll(".resultado-acciones").forEach((a) => (a.innerHTML = ""));
      acciones.innerHTML = '<span class="confirmada">✓ Falla real confirmada</span>';
    } catch (e) {
      alert("No fue posible confirmar la falla: " + e.message);
    }
  }

  el("btn-finalizar").onclick = () => finalizar(false);
  if (datos.pregunta) {
    mostrarPregunta(datos.pregunta);
  } else {
    finalizar(true);
  }
})();
