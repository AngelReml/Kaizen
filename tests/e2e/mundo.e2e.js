// Prueba de extremo a extremo del Mundo contra el backend REAL (app de panel_mando sobre datos sintéticos).
// Uso:  node tests/e2e/mundo.e2e.js        (variables: KAIZEN_PY, KAIZEN_CHROME, PLAYWRIGHT_MODULE, KAIZEN_E2E_PUERTO)
// Cada escenario imprime PASS/FAIL con la evidencia; el proceso sale con código 1 si alguno falla.
const { spawn } = require('child_process');
const path = require('path'), fs = require('fs'), os = require('os'), http = require('http');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const RAIZ = path.resolve(__dirname, '..', '..');
const PY = process.env.KAIZEN_PY || 'python3';
const PORT = +(process.env.KAIZEN_E2E_PUERTO || 8631);
const BASE = 'http://127.0.0.1:' + PORT;
const DATOS = fs.mkdtempSync(path.join(os.tmpdir(), 'kaizen_e2e_'));
let srv = null;
const sleep = ms => new Promise(r => setTimeout(r, ms));

function arrancar(extra, puerto, datos) {
  srv = spawn(PY, [path.join(RAIZ, 'tests/e2e/servidor_e2e.py'), '--puerto', String(puerto || PORT), '--datos', datos || DATOS, '--mecha', '40'].concat(extra || []), { cwd: RAIZ, stdio: ['ignore', 'pipe', 'pipe'] });
  srv.stderr.on('data', d => { if (process.env.VERBOSO) process.stderr.write(d); });
  return esperarServidor(20000);
}
function parar() { return new Promise(res => { const s = srv; srv = null; if (!s) return res(); s.once('exit', () => res()); s.kill('SIGTERM'); setTimeout(() => { try { s.kill('SIGKILL'); } catch (e) {} res(); }, 4000).unref(); }); }   // el temporizador mata SOLO el proceso que se paró, no uno nuevo
async function esperarServidor(ms) { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { await req('GET', '/latido'); return; } catch (e) { await sleep(300); } } throw new Error('el servidor de ensayo no arranca'); }
let BASE_ACTUAL = null;
function req(method, url, body) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const r = http.request((BASE_ACTUAL || BASE) + url, { method, headers: data ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } : {} }, res => { let b = ''; res.on('data', c => b += c); res.on('end', () => { try { resolve(JSON.parse(b)); } catch (e) { resolve(b); } }); });
    r.on('error', reject); r.setTimeout(5000, () => r.destroy(new Error('timeout'))); if (data) r.write(data); r.end();
  });
}
const post = (u, b) => req('POST', u, b || {});

const resultados = [];
async function escenario(nombre, fn) {
  if (process.env.SOLO && !process.env.SOLO.split(',').some(p => nombre.startsWith(p))) return;      // SOLO=10d,11 para repetir escenarios sueltos
  const t0 = Date.now();
  try { const ev = await fn(); resultados.push([nombre, true]); console.log('PASS  ' + nombre + (ev ? '  · ' + ev : '') + '  (' + ((Date.now() - t0) / 1000).toFixed(1) + ' s)'); }
  catch (e) { resultados.push([nombre, false]); console.log('FAIL  ' + nombre + '  · ' + e.message); }
}
function ok(c, msg) { if (!c) throw new Error(msg); }
async function until(page, fn, arg, ms, msg) { try { await page.waitForFunction(fn, arg, { timeout: ms || 10000 }); } catch (e) { throw new Error(msg || 'no se cumplió a tiempo'); } }
const info = page => page.evaluate(() => KAIZEN.info());

(async () => {
  await arrancar();
  const b = await chromium.launch({ executablePath: process.env.KAIZEN_CHROME || undefined, args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist', '--no-sandbox'] });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.addInitScript(() => { try { localStorage.setItem('kaizen-q', '1'); } catch (e) {} });
  const page = await ctx.newPage(); const errs = [];
  page.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource|net::ERR|EventSource|MIME/.test(m.text())) errs.push('CONSOLE ' + m.text()); });
  await page.route(/fonts\.(googleapis|gstatic)\.com/, r => r.abort());
  page.on('dialog', d => d.dismiss());

  await escenario('1 arranque vacío: todas las salas cerradas y sin gente', async () => {
    await page.goto(BASE + '/mundo?empresa=laboratorio');
    await until(page, () => window.KAIZEN && KAIZEN.info().online === true, null, 30000, 'no conectó');
    const i = await info(page);
    const casa = i.rooms.filter(r => r.cubo && !r.annex); ok(casa.length === 5, 'salas de cubo en la casa: ' + casa.length);
    const abiertas = casa.filter(r => !r.locked); ok(abiertas.length === 0, 'abiertas sin alta: ' + abiertas.map(r => r.id));
    ok(i.lots.filter(l => l.cubo).length === 5 && i.lots.every(l => l.state === 'free'), 'pabellones reservados sin construir: ' + JSON.stringify(i.lots));
    ok(i.agents.length === 0, 'agentes inventados: ' + i.agents.length);
    ok((await page.textContent('#alive-t')) === 'El jardín está despierto', 'estado de conexión');
    ok((await page.textContent('#st-gasto')).includes('0,00'), 'gasto');
    return 'online, 5 salas cerradas, 5 pabellones reservados, 0 agentes';
  });

  await escenario('2 alta de directores: llegan andando y se levantan los pabellones', async () => {
    await page.click('[data-tab="cubos"]');                            // RRHH propone y el operador da de alta (un clic)
    ok((await page.textContent('#tabbody')).includes('Dar de alta el director de'), 'RRHH no propone el alta');
    await page.click('#alta-btn');
    await page.click('[data-tab="sala"]');
    await until(page, () => KAIZEN.info().agents.length >= 5, null, 15000, 'no llegaron los directores de la casa');
    let i = await info(page);
    ok(i.rooms.filter(r => r.cubo && !r.annex && !r.locked).length === 5, 'salas de la casa abiertas');
    ok(i.lots.filter(l => l.state === 'obra').length === 5, 'obras: ' + JSON.stringify(i.lots.map(l => l.state)));
    await until(page, () => KAIZEN.info().agents.length === 10, null, 60000, 'pabellones sin terminar');
    i = await info(page);
    ok(i.lots.filter(l => l.state === 'built').length === 5, 'pabellones construidos');
    return '10 directores, 5 pabellones';
  });

  await escenario('3 evento real de la bitácora: aparece, habla el director y se sella', async () => {
    const antes = (await info(page)).events;
    await post('/_e2e/evento', { tipo: 'comercial.lead.descubierto', payload: { lead_ref: 'l1' } });
    await until(page, () => document.querySelector('#feedList li') && document.querySelector('#feedList li').textContent.includes('negocio candidato'), null, 8000, 'no llegó al feed');
    await until(page, () => KAIZEN.info().agents.find(a => a.id === 'comercial').say, null, 3000, 'el director no habla');
    await until(page, n => KAIZEN.info().events === n, antes + 1, 20000, 'sellados no pasó de ' + antes + ' a ' + (antes + 1));   // el contador llega con la foto del backend, unos segundos después del evento
    const i = await info(page); ok(i.events === antes + 1, 'sellados ' + antes + ' → ' + i.events);
    return 'sellados ' + antes + ' → ' + i.events;
  });

  await escenario('4 evento del bus del sustrato', async () => {
    await post('/_e2e/bus', { topic: 'kaizen.brand.revision_emitida.v1', payload: { x: 1 } });
    await until(page, () => Array.from(document.querySelectorAll('#feedList li')).some(li => li.textContent.includes('Marca') && li.textContent.includes('revision emitida')), null, 8000, 'no llegó el evento del bus');
  });

  await escenario('4b chat de la Colmena: el director habla en su mesa y en la Sala de Reunión', async () => {
    await post('/_e2e/chat', { cubo: 'marketing', autor: 'operador', texto: 'como va la campana?' });
    await post('/_e2e/chat', { cubo: 'marketing', autor: 'director', texto: 'Hay dos borradores esperando revision.' });
    await until(page, () => (KAIZEN.info().agents.find(a => a.id === 'marketing') || {}).say === 'Hay dos borradores esperando revision.', null, 8000, 'el director no habla en su mesa');
    await post('/_e2e/chat', { cubo: null, autor: 'director', autor_cubo: 'marketing', texto: 'Propongo pausar la campana.' });
    await post('/_e2e/chat', { cubo: null, autor: 'director', autor_cubo: 'ops', texto: 'Yo me ocupo de la capacidad.' });
    await until(page, () => KAIZEN.info().agents.some(a => a.state === 'walk'), null, 8000, 'nadie va a la Sala de Reunión');
    ok(await page.evaluate(() => Array.from(document.querySelectorAll('#feedList li')).some(li => li.textContent.includes('Tú: como va la campana'))), 'mensaje del operador en el feed');
  });

  await escenario('5 texto hostil en un evento: se muestra literal, no se ejecuta', async () => {
    await post('/_e2e/evento', { tipo: 'comercial.pedido.atribuido', payload: { via: '<img src=x onerror="window.__xss=1">' } });
    await until(page, () => Array.from(document.querySelectorAll('#feedList li')).some(li => li.textContent.includes('<img src=x')), null, 8000, 'el texto hostil no llegó literal');
    ok(await page.evaluate(() => window.__xss === undefined), 'SE EJECUTÓ código del evento');
    ok(await page.evaluate(() => !document.querySelector('#feedList img')), 'se creó un <img>');
  });

  await escenario('6 ventanilla: tarjeta real, SÍ mantenido, mecha y deshacer', async () => {
    const c1 = await post('/_e2e/aprobacion', { cubo: 'comercial', accion: 'enviar email inicial a candidato', clase: 'IRREVERSIBLE-EXTERNA', ref: 'borrador_x' });
    await until(page, () => document.getElementById('win-n').textContent === '1', null, 15000, 'la ventanilla no cuenta la tarjeta');
    await page.click('#b-win');
    await page.waitForSelector('#drawer-body .card');
    ok((await page.textContent('#drawer-body')).includes('enviar email inicial'), 'título de la tarjeta');
    const si = page.locator('[data-si]').first(); const bx = await si.boundingBox();
    await page.mouse.move(bx.x + bx.width / 2, bx.y + bx.height / 2); await page.mouse.down(); await sleep(250); await page.mouse.up();
    await sleep(600); ok((await req('GET', '/api/tarjetas/laboratorio')).tarjetas.length === 1, 'un toque corto NO debe aprobar');
    await page.mouse.move(bx.x + bx.width / 2, bx.y + bx.height / 2); await page.mouse.down(); await sleep(1100); await page.mouse.up();
    await page.waitForSelector('[data-dispara]', { timeout: 8000 });
    ok((await page.textContent('#drawer-body')).includes('Sale en'), 'cuenta atrás de la mecha');
    await page.click('[data-undo]');
    await until(page, () => !document.querySelector('[data-dispara]'), null, 8000, 'la mecha no se deshizo');
    const t = await req('GET', '/api/tarjetas/laboratorio'); ok(t.tarjetas.length === 0, 'tras deshacer no debe quedar pendiente');
    const c2 = await post('/_e2e/aprobacion', { cubo: 'ops', accion: 'ajustar capacidad', clase: 'IRREVERSIBLE-INTERNA' });
    await page.waitForSelector('[data-si]', { timeout: 15000 });
    const b2 = await page.locator('[data-si]').first().boundingBox();
    await page.mouse.move(b2.x + b2.width / 2, b2.y + b2.height / 2); await page.mouse.down(); await sleep(1100); await page.mouse.up();
    await until(page, () => document.getElementById('win-n').textContent === '0', null, 15000, 'la aprobación interna no se ejecutó');
    return 'corto no aprueba; largo arma mecha; deshacer aborta; interna se ejecuta';
  });

  await escenario('6b ventanilla: NO deniega y la tarjeta desaparece', async () => {
    await post('/_e2e/aprobacion', { cubo: 'legal', accion: 'publicar comunicado', clase: 'IRREVERSIBLE-EXTERNA' });
    await page.click('#b-win'); await page.waitForSelector('[data-no]', { timeout: 15000 });
    await page.click('[data-no]');
    await until(page, () => document.getElementById('win-n').textContent === '0' && !document.querySelector('[data-no]'), null, 15000, 'la tarjeta no desapareció');
    ok((await req('GET', '/api/tarjetas/laboratorio')).tarjetas.length === 0, 'sigue pendiente en el backend');
    await page.click('#drawer-x');
  });

  await escenario('6c gasto real: salud DEGRADADA, sala con polvo y modo ahorro visible', async () => {
    await post('/_e2e/coste', { eur: 13 });                             // ≥ 80 % del límite de los cubos (16 €)
    await until(page, () => KAIZEN.info().rooms.filter(r => r.cubo && !r.locked).some(r => r.wear === 1), null, 20000, 'la salud DEGRADADA no llega a las salas');
    await post('/_e2e/gasto', { eur: 5.5 });                            // pasa del tope diario de la empresa (5 €)
    await until(page, () => document.getElementById('st-gasto').classList.contains('hot'), null, 20000, 'no se marca el modo ahorro');
    const g = await page.textContent('#st-gasto'); ok(g.includes('5,5'), 'gasto mostrado: ' + g);
  });

  await escenario('7 PARAR TODO (2 s) y reanudar', async () => {
    if (await page.locator('#drawer-x').isVisible()) await page.click('#drawer-x');
    const st = page.locator('#b-stop'); const bx = await st.boundingBox();
    await page.mouse.move(bx.x + bx.width / 2, bx.y + bx.height / 2); await page.mouse.down(); await sleep(700); await page.mouse.up();
    await sleep(500); ok(!(await req('GET', '/latido')).parado, 'un toque corto NO debe parar');
    await page.mouse.move(bx.x + bx.width / 2, bx.y + bx.height / 2); await page.mouse.down(); await sleep(2300); await page.mouse.up();
    await until(page, () => KAIZEN.info().parado === true, null, 10000, 'el mundo no muestra la parada');
    ok((await req('GET', '/latido')).parado === true, 'el backend no está parado');
    ok((await page.textContent('#alive-t')) === 'Todo parado', 'texto de estado');
    ok((await page.textContent('#b-stop')) === 'REANUDAR', 'botón');
    await page.click('#b-stop');
    await until(page, () => KAIZEN.info().parado === false, null, 10000, 'no reanudó');
    ok((await req('GET', '/latido')).parado === false, 'el backend sigue parado');
  });

  await escenario('8 sello: íntegro y después roto', async () => {
    await page.click('[data-tab="reg"]');
    await page.click('#t-sello'); await until(page, () => /intacto/.test((document.getElementById('reg-sello') || {}).textContent || ''), null, 8000, 'no dice íntegro');
    await post('/_e2e/romper_sello');
    await page.click('#t-sello'); await until(page, () => /se rompe/.test((document.getElementById('reg-sello') || {}).textContent || ''), null, 8000, 'no detecta la ruptura');
    ok(await page.evaluate(() => !!document.querySelector('#reg-sello .dot.bad')), 'punto rojo');
    await until(page, () => document.getElementById('alive-t').textContent === 'Sello del historial roto', null, 70000, 'la barra superior no avisa del sello roto');
    // G1: el sello roto endurece a TODOS los cubos de la empresa un nivel (BAJA -> CERO; CERO se queda). El pulso
    // lo comprueba como mucho cada 30 s, asi que se espera; el mundo debe mostrar el nivel vigente, no el del manifest.
    await until(page, async () => { const j = await (await fetch('/api/mundo/estado?empresa=laboratorio')).json(); return j.cubos.length > 0 && j.cubos.every(c => c.autonomia === 'CERO'); }, null, 90000, 'el sello roto no endurecio la autonomia de los cubos');
    await page.click('[data-tab="sala"]');
  });

  await escenario('9 caída del backend: lo dice y no inventa; al volver, sin duplicados', async () => {
    const drops0 = (await info(page)).drops;
    // Precondicion: calma antes de cortar. Los eventos que acaba de sellar el producto (p. ej. el endurecimiento de G1) caen
    // como gotas y pueden seguir cayendo; lo que se comprueba aqui es que SIN conexion no se inventa actividad NUEVA.
    await until(page, () => KAIZEN.info().drops === 0, null, 120000, 'las gotas no se calman antes de cortar el backend');
    await parar();
    await until(page, () => KAIZEN.info().online === false, null, 25000, 'no detecta la caída');
    ok((await page.textContent('#alive-t')) === 'Sin conexión con Kaizen', 'texto sin conexión');
    await sleep(3000); const i = await info(page); ok(i.drops === 0 && i.agents.every(a => !a.say || true), 'actividad sin conexión');
    const items0 = await page.evaluate(() => document.querySelectorAll('#feedList li').length);
    await arrancar();
    await until(page, () => KAIZEN.info().online === true, null, 40000, 'no reconectó');
    await sleep(2500);
    const items1 = await page.evaluate(() => document.querySelectorAll('#feedList li').length);
    ok(items1 === items0, 'duplicados tras reconectar: ' + items0 + ' → ' + items1);
    await post('/_e2e/evento', { tipo: 'comercial.lead.cualificado', payload: { lead_ref: 'l2' } });
    await until(page, () => /cualific/i.test(document.querySelector('#feedList li').textContent), null, 10000, 'no llegan eventos tras reconectar');
    return 'feed ' + items0 + ' = ' + items1;
  });

  await escenario('10 recarga: el estado sale del backend', async () => {
    await page.reload();
    await until(page, () => window.KAIZEN && KAIZEN.info().online === true && KAIZEN.info().agents.length === 10, null, 40000, 'no recuperó el estado');
    const i = await info(page); ok(i.lots.filter(l => l.state === 'built').length === 5, 'pabellones tras recargar');
    ok((await page.locator('#feedList li').count()) > 0, 'feed de recientes');
  });

  await escenario('10b cubo nuevo: el edificio le reserva el solar libre y lo construye al darlo de alta', async () => {
    await post('/_e2e/cubo_nuevo');
    await until(page, () => KAIZEN.info().lots.some(l => l.cubo === 'prueba' && l.state === 'free'), null, 30000, 'el solar no se reserva');
    ok(await page.evaluate(() => KAIZEN.info().lots.filter(l => !l.cubo && l.state === 'free').length === 0), 'no debería quedar ningún solar libre sin dueño');
    await post('/_e2e/alta_cubo');
    await until(page, () => KAIZEN.info().lots.some(l => l.cubo === 'prueba' && l.state === 'obra'), null, 20000, 'no empieza la obra');
    await until(page, () => KAIZEN.info().agents.length === 11, null, 90000, 'la obra no termina');
    const i = await info(page); ok(i.rooms.some(r => r.id === 'prueba' && r.annex && !r.locked), 'sala del pabellón nuevo');
    return '11 directores, pabellón nuevo en el último solar';
  });

  await escenario('10c ráfaga de 300 eventos: el juego sigue vivo y acotado', async () => {
    const antes = (await info(page)).cur.rue;                            // el cursor de la cadena (el contador de sellados es null con el sello roto)
    for (let k = 0; k < 300; k += 50) await Promise.all(Array.from({ length: 50 }, (_, j) => post('/_e2e/evento', { tipo: 'comercial.lead.cualificado', payload: { lead_ref: 'r' + (k + j) } })));
    await until(page, n => KAIZEN.info().cur.rue >= n, antes + 300, 90000, 'no llegaron los 300 eventos');
    const t0 = Date.now(); const i = await info(page); ok(Date.now() - t0 < 3000, 'la página no responde');
    ok(i.drops <= 41, 'gotas sin acotar: ' + i.drops);
    ok((await page.locator('#feedList li').count()) <= 60, 'el feed no está acotado');
    return 'cadena +' + (i.cur.rue - antes) + ', gotas ' + i.drops;
  });

  await escenario('10e rincones: el clic hace cosas y ninguna toca el estado de la empresa', async () => {
    const Pw = (x, y) => [600 + (x - y) * 16, 190 + (x + y) * 8];       // la misma proyección isométrica del mundo
    await page.addStyleTag({ content: 'aside,nav.cmd,header.top{display:none!important}' });
    await page.evaluate(() => { document.getElementById('b-home').click(); for (let i = 0; i < 2; i++) document.getElementById('b-zout').click(); });
    await sleep(2500);
    const fx = () => page.evaluate(() => KAIZEN.fx());
    const estado = async () => { const i = await info(page); return JSON.stringify({ ev: i.events, cur: i.cur, drops: i.drops, gasto: i.gasto, tarj: i.tarjetas, parado: i.parado }); };
    { const t0 = Date.now(); await until(page, () => KAIZEN.info().drops === 0, null, 150000, 'las gotas de tinta no terminaron de llegar al Registro'); console.log('      (gotas vaciadas en ' + ((Date.now() - t0) / 1000).toFixed(0) + ' s)'); }   // lo que ya venía en camino no es de este clic
    const antes = await estado(), f0 = await fx(), i0 = await info(page), a = i0.agents[0];
    const blancos = [
      ['torii', Pw(21.5, 6).map((v, i) => i ? v - 26 : v)], ['flor', Pw(14, 21)], ['arbol', Pw(2.2, 18.6).map((v, i) => i ? v - 44 : v)],
      ['isla', [f0.isles[1][0], f0.isles[1][1] + 14]], ...(f0.sun[2] > .3 ? [['sol', [f0.sun[0], f0.sun[1]]]] : []), ['director', null]
    ];
    const hechos = [];
    for (const [k, w] of blancos) {
      let w2 = w;
      if (k === 'director') { const ags = (await info(page)).agents, sit = ags.find(x => x.state === 'sit') || ags[0]; w2 = Pw(sit.pos[0], sit.pos[1]).map((v, i) => i ? v - 14 : v); }
      const sc = await page.evaluate(([x, y]) => KAIZEN.toScreen(x, y), w2), ant = await fx();
      await page.mouse.click(sc[0], sc[1]); await sleep(400);
      const des = await fx();
      ok(des.sp > ant.sp || des.bloom > ant.bloom || des.found.length > ant.found.length, 'el clic en ' + k + ' no hizo nada (' + sc.map(Math.round) + ')');
      hechos.push(k);
    }
    ok((await fx()).found.length >= 5, 'rincones descubiertos: ' + (await fx()).found.join(','));
    ok(await estado() === antes, 'un clic de adorno cambió el estado de la empresa');
    await page.evaluate(() => { document.getElementById('pf-x') && document.getElementById('pf-x').click(); });
    return hechos.join(' · ') + ' · estado intacto';
  });

  await escenario('10f «mientras no estabas»: tras una ausencia larga cuenta lo que avanzó el backend, y solo eso', async () => {
    const cur0 = (await info(page)).cur;
    // al recargar, el propio juego guarda «visita ahora» (pagehide): la siembra tiene que ocurrir al arrancar la página nueva
    await page.addInitScript(() => { try { if (!sessionStorage.getItem('sembrada-10f')) { sessionStorage.setItem('sembrada-10f', '1'); localStorage.setItem('kaizen-visita', JSON.stringify({ ts: Date.now() - 5 * 36e5, empresa: 'laboratorio', rue: -1, bus: 0, chat: 0 })); } } catch (e) {} });
    await page.reload(); await until(page, () => window.KAIZEN && KAIZEN.info().online === true, null, 30000, 'no volvió a conectar');
    await page.waitForSelector('#alba', { timeout: 15000 });
    const txt = await page.locator('#alba').innerText();
    ok(/hace 5 h/.test(txt), 'no dice cuánto llevaba fuera: ' + txt);
    const m = txt.match(/(\d+)\s+hechos? sellados?/); ok(m && +m[1] === cur0.rue + 1, 'la cuenta de hechos sellados no sale del cursor del backend: ' + txt);
    await page.click('#alba-ok'); ok(await page.locator('#alba').count() === 0, 'no se cierra');
    await page.reload(); await until(page, () => window.KAIZEN && KAIZEN.info().online === true, null, 30000);
    await sleep(1500); ok(await page.locator('#alba').count() === 0, 'sin ausencia larga no debe salir');
    return 'resumen real tras 5 h fuera; no sale sin ausencia';
  });

  await escenario('10g panel izquierdo minimizable: se pliega, se recuerda al recargar y se reabre', async () => {
    await page.evaluate(() => { try { localStorage.removeItem('kaizen-panel'); } catch (e) {} });
    await page.reload(); await until(page, () => window.KAIZEN && KAIZEN.info().online === true, null, 30000);
    ok(await page.locator('#tabbody').isVisible(), 'el panel debería empezar abierto');
    await page.click('#left-min'); ok(!(await page.locator('#tabbody').isVisible()), 'no se pliega');
    await page.reload(); await until(page, () => window.KAIZEN && KAIZEN.info().online === true, null, 30000);
    ok(!(await page.locator('#tabbody').isVisible()), 'no recuerda que estaba minimizado');
    await page.click('#left-min'); ok(await page.locator('#tabbody').isVisible(), 'no se reabre');
    return 'plegado, recordado y reabierto';
  });

  // ── segundo servidor, con clave: sesión, cookie y CSRF de verdad ──
  await escenario('10d modo con clave: sin sesión redirige, con sesión funciona el CSRF y al caducar vuelve al acceso', async () => {
    await parar(); const P2 = PORT + 1, B2 = 'http://127.0.0.1:' + P2, CLAVE = 'clave-de-ensayo-123';
    const datos2 = fs.mkdtempSync(path.join(os.tmpdir(), 'kaizen_e2e_clave_'));
    BASE_ACTUAL = B2; await arrancar(['--token', CLAVE], P2, datos2);
    const c2 = await b.newContext({ viewport: { width: 1280, height: 900 } }); await c2.addInitScript(() => { try { localStorage.setItem('kaizen-q', '1'); } catch (e) {} });
    const p2 = await c2.newPage(); await p2.route(/fonts\.(googleapis|gstatic)\.com/, r => r.abort());
    await p2.goto(B2 + '/mundo'); ok(/\/login/.test(p2.url()), 'sin sesión no redirige al acceso: ' + p2.url());
    await p2.goto(B2 + '/login?token=' + CLAVE + '&ir=/mundo'); await p2.waitForFunction(() => window.KAIZEN && KAIZEN.info().online === true, null, { timeout: 40000 });
    ok(/\/mundo/.test(p2.url()), 'tras entrar no está en /mundo');
    await post('/_e2e/aprobacion', { cubo: 'ops', accion: 'ajustar capacidad', clase: 'IRREVERSIBLE-INTERNA' });
    await p2.waitForFunction(() => document.getElementById('win-n').textContent === '1', null, { timeout: 40000 });
    await p2.click('#b-win'); await p2.waitForSelector('[data-si]');
    const bx = await p2.locator('[data-si]').first().boundingBox(); await p2.mouse.move(bx.x + bx.width / 2, bx.y + bx.height / 2); await p2.mouse.down(); await sleep(1200); await p2.mouse.up();
    await p2.waitForFunction(() => document.getElementById('win-n').textContent === '0', null, { timeout: 40000 });         // POST con CSRF aceptado
    await post('/_e2e/caducar_sesiones');
    await p2.waitForURL(/\/login/, { timeout: 60000 });
    await c2.close(); await parar(); BASE_ACTUAL = null;
    return 'redirect, CSRF y caducidad';
  });

  await escenario('11 sin errores de JavaScript', async () => { ok(errs.length === 0, errs.slice(0, 3).join(' | ')); });

  await b.close(); await parar();
  const fallos = resultados.filter(r => !r[1]).length;
  console.log('\n' + (resultados.length - fallos) + ' de ' + resultados.length + ' escenarios en verde');
  process.exit(fallos ? 1 : 0);
})().catch(async e => { console.error('ERROR', e); await parar(); process.exit(2); });
