/* Colmena — chat de directores. Sin dependencias, sin build.
   Reglas: todo texto de usuario/LLM entra al DOM via textContent (jamas
   innerHTML con datos); los botones llaman a los endpoints EXISTENTES del
   panel (/cmd/aprobar, /cmd/denegar, /cmd/deshacer) con X-CSRF. */
(function () {
  "use strict";

  const raiz = document.getElementById("colmena");
  if (!raiz) return;
  const EMPRESA = raiz.dataset.empresa;

  const $ = (id) => document.getElementById(id);
  const elChats = $("col-chats"), elMsjs = $("col-mensajes"),
        elQuien = $("col-chat-quien"), elFicha = $("col-ficha"),
        elEscribiendo = $("col-escribiendo"), elForm = $("col-form"),
        elTexto = $("col-texto"), elEnviar = $("col-enviar"),
        elAviso = $("col-aviso"), elDinero = $("col-dinero"),
        elSello = $("col-sello"), elFichaBtn = $("col-ficha-btn");

  const S = {
    agentes: [], sala: null, porSesion: {},        // sesion_id -> item
    abierta: null,                                  // sesion_id abierta
    noLeidos: {}, tarjetas: {}, lastId: 0, es: null,
    parado: false, sinClave: false,
  };

  function kzCsrf() {
    const m = document.cookie.match(/(?:^|;\s*)kz_csrf=([^;]*)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  async function post(url, cuerpo) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF": kzCsrf() },
      body: JSON.stringify(Object.assign({ quien: "operador" }, cuerpo)),
    });
    let j = {};
    try { j = await r.json(); } catch (e) { /* respuesta sin JSON */ }
    if (!r.ok || j.escudo) {
      const msg = j.escudo ? (j.por_que + " " + (j.que_puedes_hacer || ""))
                           : (j.error || j.detail || ("Error " + r.status));
      avisar(msg);
      throw new Error(msg);
    }
    return j;
  }

  let avisoTimer = null;
  function avisar(texto, fijo, boton) {
    elAviso.textContent = texto;
    if (boton) elAviso.appendChild(boton);
    elAviso.hidden = !texto;
    if (avisoTimer) clearTimeout(avisoTimer);
    if (texto && !fijo) avisoTimer = setTimeout(() => { elAviso.hidden = true; }, 8000);
  }

  function hora(ts) {
    try { return new Date(ts).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" }); }
    catch (e) { return ""; }
  }

  const NOMBRE = {};                                // cubo -> nombre visible
  function nombreDe(autorId, tipo) {
    if (tipo === "operador") return "Tu";
    if (tipo === "sistema") return "sistema";
    const cubo = autorId.replace(/^director_/, "");
    return NOMBRE[cubo] || cubo;
  }

  /* ── lista de conversaciones ── */
  function pintarLista() {
    elChats.textContent = "";
    const items = [];
    if (S.sala) items.push({ sesion: S.sala.sesion, nombre: "Sala de Reunion",
                             inicial: "☀", sala: true, ultimo: S.sala.ultimo });
    for (const a of S.agentes)
      items.push({ sesion: a.sesion, nombre: a.nombre, inicial: a.nombre[0],
                   salud: (a.salud && a.salud.estado || "").toLowerCase(),
                   ultimo: a.ultimo, agente: a });
    for (const it of items) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "col-item" + (S.abierta === it.sesion ? " activa" : "");
      b.dataset.sesion = it.sesion;

      const av = document.createElement("span");
      av.className = "col-avatar" + (it.sala ? " sala" : "");
      av.textContent = it.inicial;
      if (!it.sala) {
        const dot = document.createElement("span");
        dot.className = "col-salud " + (it.salud === "ok" ? "ok" :
          it.salud === "degradado" ? "degradado" :
          it.salud === "error" ? "error" : "");
        dot.title = "salud: " + (it.salud || "sin datos");
        av.appendChild(dot);
      }

      const centro = document.createElement("span");
      centro.className = "col-item-centro";
      const n = document.createElement("div");
      n.className = "col-item-nombre"; n.textContent = it.nombre;
      const p = document.createElement("div");
      p.className = "col-item-prev";
      p.textContent = it.ultimo ? it.ultimo.texto : "sin mensajes todavia";
      centro.append(n, p);

      const meta = document.createElement("span");
      meta.className = "col-item-meta";
      const h = document.createElement("span");
      h.className = "col-item-hora";
      h.textContent = it.ultimo ? hora(it.ultimo.ts) : "";
      meta.appendChild(h);
      const nl = S.noLeidos[it.sesion] || 0;
      if (nl > 0) {
        const bd = document.createElement("span");
        bd.className = "col-badge"; bd.textContent = nl > 99 ? "99+" : String(nl);
        meta.appendChild(bd);
      }
      b.append(av, centro, meta);
      b.addEventListener("click", () => abrir(it.sesion));
      elChats.appendChild(b);
    }
  }

  /* ── cabecera + ficha del chat abierto ── */
  function pintarCabecera() {
    const it = S.porSesion[S.abierta];
    elQuien.textContent = "";
    const n = document.createElement("div");
    n.className = "nombre";
    const d = document.createElement("div");
    d.className = "detalle";
    if (it && it.agente) {
      n.textContent = "Director/a de " + it.agente.nombre;
      d.textContent = it.agente.uid + " · autonomia " + it.agente.autonomia;
    } else {
      n.textContent = "Sala de Reunion";
      d.textContent = "los 10 directores · @cubo para dirigirte a uno";
    }
    elQuien.append(n, d);
    elFicha.hidden = true;
  }

  function pintarFicha() {
    const it = S.porSesion[S.abierta];
    elFicha.textContent = "";
    const dl = document.createElement("dl");
    const fila = (t, v, mono) => {
      const dt = document.createElement("dt"); dt.textContent = t;
      const dd = document.createElement("dd"); dd.textContent = v;
      if (mono) dd.className = "mono";
      dl.append(dt, dd);
    };
    if (it && it.agente) {
      const a = it.agente;
      fila("id unico", a.uid, true);
      fila("role_id", a.role_id, true);
      fila("mision", a.mision);
      fila("autonomia", a.autonomia + (a.nota_estado ? " — " + a.nota_estado : ""));
      fila("acciones externas declaradas",
           (a.acciones_irreversibles || []).join(", ") || "ninguna");
      fila("salud", (a.salud ? a.salud.estado + " — " + a.salud.detalle : "SIN DATOS"));
      const herr = a.herramientas || [];
      const directas = herr.filter((h) => h.clase === "LECTURA" || h.clase === "REVERSIBLE");
      const propone = herr.filter((h) => h.clase.startsWith("IRREVERSIBLE"));
      fila("regla", directas.length
        ? "ejecuta LECTURA/REVERSIBLE por si solo/a; IRREVERSIBLE-* siempre pasa por tu SI."
        : "todo lo que hace pasa por tu SI (sin herramientas directas todavia).");
      if (directas.length) {
        const dt = document.createElement("dt"); dt.textContent = "ejecuta directamente";
        const dd = document.createElement("dd");
        dd.textContent = directas.map((h) => h.nombre + " (" + h.clase + ")").join(", ");
        dl.append(dt, dd);
      }
      if (propone.length) {
        const dt = document.createElement("dt"); dt.textContent = "propone (pide tu SI)";
        const dd = document.createElement("dd");
        dd.textContent = propone.map((h) => h.nombre + " (" + h.clase + ")").join(", ");
        dl.append(dt, dd);
      }
    } else {
      fila("sala", "reunion con los 10 directores");
      fila("turnos", "solo tus mensajes abren turnos; @cubo limita quien responde");
      fila("anti-bucle", "una mencion entre directores no hace hablar a nadie");
    }
    elFicha.appendChild(dl);
  }

  /* ── mensajes ── */
  // Clasifica un mensaje de sistema por su prefijo/forma FIJA (texto que el
  // propio backend construye — nunca texto libre del LLM, por eso el patron
  // es fiable): exito (herramienta LECTURA/REVERSIBLE real), rechazo (error
  // o limite), o info (nota neutra). Antes los tres eran la misma pildora
  // gris — sin distincion visual, un rechazo se leia igual que un exito.
  function categoriaSistema(texto) {
    if (/rechazad[ao]:/.test(texto) ||
        /^techo (tenant|global) alcanzado/.test(texto) ||
        /^Limite diario de coste alcanzado/.test(texto) ||
        /no pudo responder \(/.test(texto))
      return "rechazo";
    if (/\(REVERSIBLE, dentro de Kaizen\)/.test(texto) ||
        /\(LECTURA\) para responder\.$/.test(texto))
      return "exito";
    return "info";
  }

  function pintarMensaje(m) {
    if (document.querySelector('[data-id="' + m.id + '"]')) return;   // dedupe SSE/hilo
    const caja = document.createElement("div");
    caja.dataset.id = m.id;
    caja.className = "col-msj " +
      (m.autor_tipo === "operador" ? "op" : m.autor_tipo === "sistema" ? "sis" : "dir");

    const abiertaEsSala = S.porSesion[S.abierta] && !S.porSesion[S.abierta].agente;
    if (m.autor_tipo === "director" && (abiertaEsSala || m.ap_id)) {
      const q = document.createElement("div");
      q.className = "col-quien";
      q.textContent = nombreDe(m.autor_id, m.autor_tipo);
      caja.appendChild(q);
    }

    if (m.ap_id) {
      caja.appendChild(pintarTarjeta(m));
    } else {
      const b = document.createElement("div");
      b.className = "col-burbuja" + (m.autor_tipo === "sistema"
        ? " col-sis-" + categoriaSistema(m.texto) : "");
      b.textContent = m.texto;
      caja.appendChild(b);
    }

    const pie = document.createElement("div");
    pie.className = "col-pie-msj";
    pie.textContent = hora(m.ts) +
      (m.coste_eur > 0 ? " · " + m.coste_eur.toFixed(4).replace(".", ",") + " €" : "");
    caja.appendChild(pie);
    elMsjs.appendChild(caja);
  }

  function pintarTarjeta(m) {
    const t = S.tarjetas[m.ap_id] || {};
    const div = document.createElement("div");
    div.className = "col-tarjeta";
    div.dataset.ap = m.ap_id;

    const cab = document.createElement("div");
    const acc = document.createElement("span");
    acc.className = "t-accion"; acc.textContent = t.accion || "propuesta";
    const cl = document.createElement("span");
    cl.className = "t-clase" + (t.clase === "IRREVERSIBLE-EXTERNA" ? " irrext" : "");
    cl.textContent = t.clase || "";
    cab.append(acc, cl);

    const res = document.createElement("p");
    res.className = "t-resumen"; res.textContent = m.texto;

    const est = document.createElement("div");
    est.className = "t-estado";

    const botones = document.createElement("div");
    botones.className = "t-botones";

    const consec = document.createElement("p");
    consec.className = "t-consecuencia";

    div.append(cab, res, est, botones, consec);
    actualizarTarjeta(div, m.ap_id);
    return div;
  }

  function actualizarTarjeta(div, apId) {
    const t = S.tarjetas[apId] || { estado: "SIN DATOS" };
    const est = div.querySelector(".t-estado");
    const botones = div.querySelector(".t-botones");
    const consec = div.querySelector(".t-consecuencia");
    if (t.accion) div.querySelector(".t-accion").textContent = t.accion;
    if (t.clase) {
      const cl = div.querySelector(".t-clase");
      cl.textContent = t.clase;
      cl.className = "t-clase" + (t.clase === "IRREVERSIBLE-EXTERNA" ? " irrext" : "");
    }
    botones.textContent = "";
    consec.textContent = "";
    const externa = t.clase === "IRREVERSIBLE-EXTERNA";

    if (t.estado === "PENDIENTE") {
      est.className = "t-estado pendiente";
      est.textContent = "PENDIENTE de tu decision (caduca a las 72 h)";
      consec.textContent = externa
        ? "Si dices SI: sale al mundo tras una mecha con DESHACER."
        : "Si dices SI: se aplica dentro de Kaizen.";
      const si = document.createElement("button");
      si.type = "button"; si.className = "t-si";
      si.textContent = "SI (manten pulsado)";
      armarPulsacion(si, () => decidir("aprobar", apId));
      const no = document.createElement("button");
      no.type = "button"; no.className = "t-no"; no.textContent = "NO";
      no.addEventListener("click", () => {
        // El motivo es opcional: lo que haya escrito en el cajon de texto
        // al pulsar NO se registra como motivo (sin dialogos que bloquean).
        decidir("denegar", apId, { motivo: elTexto.value.trim().slice(0, 200) });
      });
      botones.append(si, no);
    } else if (t.estado === "EN_MECHA") {
      est.className = "t-estado mecha";
      const pinta = () => {
        const s = Math.max(0, Math.round((new Date(t.dispara) - Date.now()) / 1000));
        est.textContent = "EN MECHA — se hara en " + s + " s";
      };
      pinta();
      const iv = setInterval(() => {
        if (!document.body.contains(est) ||
            !S.tarjetas[apId] || S.tarjetas[apId].estado !== "EN_MECHA")
          return clearInterval(iv);
        pinta();
      }, 1000);
      const btn = document.createElement("button");
      btn.type = "button"; btn.className = "t-deshacer"; btn.textContent = "DESHACER";
      btn.addEventListener("click", () => decidir("deshacer", apId));
      botones.appendChild(btn);
    } else {
      const bajo = (t.estado || "").toLowerCase();
      est.className = "t-estado " + (bajo === "ejecutada" || bajo === "aprobada" ? "ejecutada" : "");
      est.textContent = t.estado || "SIN DATOS";
      if (bajo === "ejecutada")
        consec.textContent = externa
          ? "Autorizada y sellada. El envio real va por el canal del cubo, con sus candados."
          : "Aplicada dentro de Kaizen.";
      if (bajo === "caducada")
        consec.textContent = "Nadie decidio en 72 h: abortada con aviso (R-13).";
    }
  }

  function refrescarTarjetas() {
    for (const div of document.querySelectorAll(".col-tarjeta"))
      actualizarTarjeta(div, div.dataset.ap);
  }

  function armarPulsacion(btn, accion) {                 // manten pulsado 800 ms
    let t0 = null;
    const empezar = () => { t0 = Date.now(); btn.classList.add("armado"); };
    const soltar = () => {
      btn.classList.remove("armado");
      if (t0 && Date.now() - t0 >= 800) accion();
      t0 = null;
    };
    btn.addEventListener("mousedown", empezar);
    btn.addEventListener("touchstart", empezar, { passive: true });
    btn.addEventListener("mouseup", soltar);
    btn.addEventListener("mouseleave", () => { btn.classList.remove("armado"); t0 = null; });
    btn.addEventListener("touchend", soltar);
  }

  async function decidir(gesto, apId, extra) {
    // La decision la ejecuta la maquinaria EXISTENTE del panel; aqui solo botones.
    const url = { aprobar: "/cmd/aprobar", denegar: "/cmd/denegar",
                  deshacer: "/cmd/deshacer" }[gesto];
    try {
      const j = await post(url, Object.assign({ empresa: EMPRESA, id: apId }, extra || {}));
      if (j.mensaje) avisar(j.mensaje);
      const r = await fetch("/api/colmena/tarjetas?empresa=" + EMPRESA);
      S.tarjetas = (await r.json()).tarjetas || {};
      refrescarTarjetas();
    } catch (e) { /* aviso ya mostrado por post() */ }
  }

  /* ── abrir conversacion ── */
  async function abrir(sesion) {
    S.abierta = sesion;
    S.noLeidos[sesion] = 0;
    try { localStorage.setItem("colmena_abierta_" + EMPRESA, String(sesion)); }
    catch (e) { /* privado */ }
    raiz.classList.add("ver-chat");
    pintarLista();
    pintarCabecera();
    elMsjs.textContent = "";
    const r = await fetch("/api/colmena/hilo?empresa=" + EMPRESA + "&sesion=" + sesion);
    const j = await r.json();
    S.tarjetas = Object.assign(S.tarjetas, j.tarjetas || {});
    for (const m of j.mensajes) pintarMensaje(m);
    elMsjs.scrollTop = elMsjs.scrollHeight;
    elTexto.focus();
  }

  /* ── envio ── */
  elForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const texto = elTexto.value.trim();
    if (!texto || !S.abierta) return;
    elEnviar.disabled = true;
    try {
      await post("/cmd/colmena/decir", { empresa: EMPRESA, sesion: S.abierta, texto: texto });
      elTexto.value = "";
      elTexto.style.height = "";
    } catch (e) { /* aviso ya mostrado */ }
    elEnviar.disabled = false;
    elTexto.focus();
  });
  elTexto.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      elForm.requestSubmit();
    }
  });
  elTexto.addEventListener("input", () => {
    elTexto.style.height = "";
    elTexto.style.height = Math.min(elTexto.scrollHeight, 144) + "px";
  });

  elFichaBtn.addEventListener("click", () => {
    if (elFicha.hidden) { pintarFicha(); elFicha.hidden = false; }
    else elFicha.hidden = true;
  });

  /* ── rio SSE ── */
  function conectarRio() {
    if (S.es) S.es.close();
    const es = new EventSource("/api/colmena/rio?empresa=" + EMPRESA + "&desde=" + S.lastId);
    S.es = es;
    es.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      S.lastId = Math.max(S.lastId, m.id);
      const it = S.porSesion[m.sesion];
      if (it) {                                  // la vista previa vive en el
        const u = { texto: (m.texto || "").slice(0, 80), ts: m.ts };
        if (it.agente) it.agente.ultimo = u;     // agente (individual)...
        else S.sala.ultimo = u;                  // ...o en la sala
      }
      if (m.sesion === S.abierta) {
        const abajo = elMsjs.scrollHeight - elMsjs.scrollTop - elMsjs.clientHeight < 60;
        pintarMensaje(m);
        if (abajo) elMsjs.scrollTop = elMsjs.scrollHeight;
      } else if (m.autor_tipo !== "operador") {
        S.noLeidos[m.sesion] = (S.noLeidos[m.sesion] || 0) + 1;
      }
      pintarLista();
    };
    es.addEventListener("meta", (ev) => {
      const meta = JSON.parse(ev.data);
      S.parado = !!meta.parado;
      elDinero.textContent = meta.dinero || "";
      const nuevos = meta.tarjetas || {};
      const cambiaron = JSON.stringify(nuevos) !== JSON.stringify(S.tarjetas);
      S.tarjetas = nuevos;
      if (cambiaron) refrescarTarjetas();
      const esc = (meta.escribiendo || {})[String(S.abierta)] || [];
      if (esc.length) {
        elEscribiendo.textContent = esc.map((c) => NOMBRE[c] || c).join(", ") +
          (esc.length > 1 ? " estan escribiendo" : " esta escribiendo");
        elEscribiendo.hidden = false;
      } else elEscribiendo.hidden = true;
      if (S.parado && !elAviso.querySelector(".t-reanudar")) {
        const rb = document.createElement("button");
        rb.type = "button"; rb.className = "t-deshacer t-reanudar";
        rb.style.marginLeft = ".7rem";
        rb.textContent = "REANUDAR (manten pulsado)";
        armarPulsacion(rb, async () => {
          try { await post("/cmd/reanudar", {}); } catch (e) { /* avisado */ }
        });
        avisar("TODO PARADO esta activo: puedes hablar, pero no se admiten " +
               "propuestas ni sale nada de Kaizen. ", true, rb);
      } else if (!S.parado && elAviso.querySelector(".t-reanudar")) {
        elAviso.hidden = true; elAviso.textContent = "";
      }
    });
    es.onerror = () => {                        // reconexion manual con cursor
      es.close();
      setTimeout(conectarRio, 2000);
    };
  }

  /* ── sello de integridad ── */
  async function comprobarSello() {
    try {
      const j = await (await fetch("/api/colmena/sello")).json();
      const ok = (j.cadena || "").startsWith("CADENA INTACTA");
      elSello.textContent = "sello: " + (ok ? "intacto" : "ROTO — revisa el cajon tecnico");
      elSello.className = ok ? "ok" : "mal";
    } catch (e) { elSello.textContent = "sello: sin comprobar"; }
  }

  /* ── boton volver (movil) ── */
  const atras = document.createElement("button");
  atras.id = "col-atras"; atras.type = "button"; atras.textContent = "←";
  atras.addEventListener("click", () => raiz.classList.remove("ver-chat"));
  document.getElementById("col-chat-cab").prepend(atras);

  /* ── arranque ── */
  (async function boot() {
    const r = await fetch("/api/colmena/agentes?empresa=" + EMPRESA);
    if (r.status === 401) { window.location = "/login"; return; }
    const j = await r.json();
    S.agentes = j.agentes; S.sala = j.sala; S.lastId = j.max_mensaje || 0;
    S.sinClave = !!j.sin_clave;
    elDinero.textContent = j.dinero || "";
    for (const a of S.agentes) {
      NOMBRE[a.cubo] = a.nombre;
      S.porSesion[a.sesion] = { sesion: a.sesion, agente: a };
    }
    S.porSesion[S.sala.sesion] = { sesion: S.sala.sesion, agente: null };
    if (S.sinClave)
      avisar("SIN CLAVE: falta ANTHROPIC_API_KEY en .env — los directores no " +
             "podran responder hasta que la configures.", true);
    pintarLista();
    let abierta = null;
    try { abierta = parseInt(localStorage.getItem("colmena_abierta_" + EMPRESA), 10); }
    catch (e) { /* privado */ }
    await abrir(S.porSesion[abierta] ? abierta : S.sala.sesion);
    if (window.matchMedia("(max-width: 720px)").matches)
      raiz.classList.remove("ver-chat");           // en movil: primero la lista
    conectarRio();
    comprobarSello();
    setInterval(comprobarSello, 60000);
  })();
})();
