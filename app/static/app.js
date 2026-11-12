const estado = { idAtencion: null, idArea: null };

const el = (id) => document.getElementById(id);

async function api(ruta, opciones) {
  const resp = await fetch(ruta, opciones);
  if (!resp.ok) {
    const cuerpo = await resp.json().catch(() => ({}));
    throw new Error(cuerpo.error || `Error ${resp.status}`);
  }
  return resp.json();
}

async function cargarSalud() {
  try {
    const datos = await api("/api/salud");
    const c = datos.base_de_conocimiento || {};
    el("salud").textContent =
      `Base de conocimiento: ${c.Areas ?? "?"} áreas · ${c.Preguntas ?? "?"} preguntas · ${c.Hipotesis ?? "?"} hipótesis · ${c.Reglas ?? "?"} reglas`;
  } catch (e) {
    el("salud").textContent = "No fue posible conectar con la base de conocimiento.";
  }
}

async function cargarAreas() {
  const cont = el("areas");
  try {
    const areas = await api("/api/areas");
    cont.innerHTML = "";
    areas.forEach((a) => {
      const btn = document.createElement("button");
      btn.className = "area-btn";
      btn.textContent = a.nombre;
      btn.onclick = () => iniciarConsulta(a.id_area);
      cont.appendChild(btn);
    });
  } catch (e) {
    cont.textContent = "No se pudieron cargar las áreas: " + e.message;
  }
}

function mostrar(pantalla) {
  ["pantalla-inicio", "pantalla-pregunta", "pantalla-resultado"].forEach((id) => {
    el(id).classList.toggle("oculto", id !== pantalla);
  });
}

async function iniciarConsulta(idArea) {
  estado.idArea = idArea;
  const datos = await api("/api/atenciones", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_area: idArea }),
  });
  estado.idAtencion = datos.id_atencion;
  mostrar("pantalla-pregunta");
  actualizarProgreso(1);
  mostrarPregunta(datos.pregunta);
}

function actualizarProgreso(numPregunta) {
  const pct = Math.min(100, (numPregunta / 15) * 100);
  el("barra-progreso").style.width = pct + "%";
}

function mostrarPregunta(pregunta) {
  el("texto-pregunta").textContent = pregunta.enunciado;
  const cont = el("opciones-respuesta");
  cont.innerHTML = "";
  pregunta.opciones.forEach((op) => {
    const btn = document.createElement("button");
    btn.textContent = op.etiqueta;
    btn.onclick = () => responder(pregunta.id_pregunta, op.clave);
    cont.appendChild(btn);
  });
}

let contadorPreguntas = 1;

async function responder(idPregunta, clave) {
  const datos = await api(`/api/atenciones/${estado.idAtencion}/respuestas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_pregunta: idPregunta, respuesta: clave }),
  });
  contadorPreguntas += 1;
  if (datos.estado === "finalizado") {
    mostrarResultado(datos.resultado);
  } else {
    actualizarProgreso(contadorPreguntas);
    mostrarPregunta(datos.pregunta);
  }
}

function claseNivel(nivel) {
  return "nivel-" + nivel.toLowerCase()
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function mostrarResultado(hipotesis) {
  mostrar("pantalla-resultado");
  contadorPreguntas = 1;

  const advertencia = el("advertencia");
  const riesgosa = hipotesis.find((h) => h.advertencia);
  if (riesgosa) {
    advertencia.classList.remove("oculto");
    advertencia.textContent =
      "⚠ Atención: una de las hipótesis indica que el vehículo no debe seguir usándose. Detenga el vehículo de forma segura y solicite una revisión especializada.";
  } else {
    advertencia.classList.add("oculto");
  }

  const cont = el("resultados");
  cont.innerHTML = "";
  hipotesis.forEach((h) => {
    const div = document.createElement("div");
    div.className = "resultado-item " + claseNivel(h.nivel_atencion);
    div.innerHTML = `
      <div class="resultado-cabeza">
        <h3>${h.posicion}. ${h.nombre}</h3>
        <span class="probabilidad">${h.probabilidad}%</span>
      </div>
      <span class="nivel-tag">${h.nivel_atencion}</span>
      <p class="recomendacion"><strong>Recomendación:</strong> ${h.recomendacion}</p>
    `;
    cont.appendChild(div);
  });
}

el("btn-reiniciar").onclick = () => {
  contadorPreguntas = 1;
  mostrar("pantalla-inicio");
};
el("btn-nueva-consulta").onclick = () => {
  contadorPreguntas = 1;
  mostrar("pantalla-inicio");
};

cargarSalud();
cargarAreas();
