/* =========================================================================
   Interpelli Torino - la logica della app.
   Tutto in un file solo, senza librerie (a parte Leaflet per la mappa).

   Come e' organizzato:
     1. memoria della app
     2. aiutanti generici
     3. lettura dei dati
     4. filtri e ricerche salvate
     5. elenco
     6. mappa
     7. dettaglio
     8. pannelli (filtri, nome ricerca)
     9. viste "Ricerche" e "Info"
    10. avvio
   ========================================================================= */

'use strict';

/* ---------- 1. MEMORIA DELLA APP ---------- */

// I filtri con cui la app si apre la prima volta (e la prima ricerca salvata).
const FILTRI_DI_FABBRICA = {
  stato: ['aperto'],
  classi: ['A027'],
  corso: ['Diurno'],
  tipo: [],            // vuoto = tutti
  maxMinuti: 30,       // null = nessun limite
  ordine: 'tempo',     // 'tempo' | 'data'
};

const FILTRI_VUOTI = { stato: [], classi: [], corso: [], tipo: [], maxMinuti: null, ordine: 'tempo' };

const CHIAVI = {
  casa: 'interpelli:casa',
  casaChiesta: 'interpelli:casa-chiesta',
  ricerche: 'interpelli:ricerche',
  preferiti: 'interpelli:preferiti',
  visti: 'interpelli:visti',
  copiaDati: 'interpelli:copia-dati',
  ultimaVista: 'interpelli:ultima-vista',
};

const stato = {
  dati: null,
  filtri: null,
  filtriInModifica: null,
  ricerche: [],
  ricercaAttiva: null,      // id della ricerca salvata attualmente applicata
  preferiti: new Set(),
  visti: new Set(),
  ricerca: '',
  vista: 'lista',           // 'lista' | 'ricerche' | 'preferiti' | 'info'
  modo: 'elenco',           // 'elenco' | 'mappa'
  mappa: null,
  stratoSegnaposti: null,
  stratoTessere: null,
  segnapostoCasa: null,
  ultimaImpronta: '',
  casa: null,               // {lat, lng, indirizzo} - vive solo su questo dispositivo
  casaInAttesa: null,       // scelta fatta nel pannello ma non ancora salvata
  sceltaSullaMappa: false,  // vero mentre aspettiamo che tocchi la mappa
};

const $ = (id) => document.getElementById(id);
const elementi = {};
['titoloVista', 'sottotitolo', 'bottoneAggiorna', 'campoRicerca', 'pulisciRicerca',
 'zonaRicerca', 'barraFiltri', 'bottoneFiltri', 'contatoreFiltri', 'filtriAttivi',
 'barraRicerche', 'interruttoreVista', 'lista', 'statoVuoto', 'riepilogo', 'velo',
 'pannelloFiltri', 'pannelloDettaglio', 'corpoDettaglio', 'chiudiDettaglio',
 'applicaFiltri', 'azzeraFiltri', 'salvaRicerca', 'conteggioAnteprima',
 'conteggioPreferiti', 'conteggioRicerche', 'navBasso', 'brindisi', 'etichettaTempo',
 'contenuto', 'zonaMappa', 'mappa', 'conteggioMappa', 'pannelloNome',
 'campoNomeRicerca', 'notificheRicerca', 'confermaNome', 'annullaNome',
 'riassuntoRicerca', 'titoloPannelloNome', 'pannelloCasa', 'campoIndirizzoCasa',
 'cercaIndirizzoCasa', 'posizioneAttuale', 'scegliSullaMappa', 'esitoCasa',
 'saltaCasa', 'confermaCasa', 'istruzioneMappa', 'annullaSceltaMappa',
].forEach((nome) => { elementi[nome] = $(nome); });


/* ---------- 2. AIUTANTI GENERICI ---------- */

function leggiMemoria(chiave, valorePredefinito) {
  try {
    const grezzo = localStorage.getItem(chiave);
    return grezzo ? JSON.parse(grezzo) : valorePredefinito;
  } catch (errore) {
    return valorePredefinito;
  }
}

function scriviMemoria(chiave, valore) {
  try { localStorage.setItem(chiave, JSON.stringify(valore)); } catch (errore) { /* spazio finito */ }
}

// Crea un elemento. Il testo passa SEMPRE da textContent, mai da innerHTML:
// cosi' i dati presi dal sito non possono rompere (o alterare) la pagina.
function nuovo(tag, classe, testo) {
  const elemento = document.createElement(tag);
  if (classe) elemento.className = classe;
  if (testo !== undefined && testo !== null) elemento.textContent = testo;
  return elemento;
}

function icona(percorsi, dimensione) {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  if (dimensione) { svg.style.width = dimensione + 'px'; svg.style.height = dimensione + 'px'; }
  percorsi.forEach((d) => {
    const p = document.createElementNS(ns, 'path');
    p.setAttribute('d', d);
    svg.appendChild(p);
  });
  return svg;
}

const ICONE = {
  bus: ['M6 16.5V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v10.5M6 16.5h12M6 16.5v2M18 16.5v2M6.5 9h11M8.5 13h.01M15.5 13h.01'],
  stella: ['M12 3.6l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8L3.5 9.8l5.9-.9z'],
  esterno: ['M14 4h6v6', 'M20 4l-9 9', 'M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5'],
  avviso: ['M12 4l9 16H3z', 'M12 10v4M12 17.2v.1'],
  cestino: ['M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13'],
  matita: ['M4 20h4L20 8l-4-4L4 16z'],
  campana: ['M6 16V11a6 6 0 1 1 12 0v5l1.5 2.5h-15z', 'M10 21h4'],
};

function mostraMessaggio(testo) {
  elementi.brindisi.textContent = testo;
  elementi.brindisi.hidden = false;
  clearTimeout(mostraMessaggio.timer);
  mostraMessaggio.timer = setTimeout(() => { elementi.brindisi.hidden = true; }, 2300);
}

const MESI = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic'];
function dataBreve(iso) {
  if (!iso) return null;
  const [anno, mese, giorno] = iso.split('-').map(Number);
  const suffisso = anno === new Date().getFullYear() ? '' : ` ${String(anno).slice(2)}`;
  return `${giorno} ${MESI[mese - 1]}${suffisso}`;
}

// Il colore che riassume "quanto e' comoda": verde vicino, rosso lontano.
function coloreTempo(minuti) {
  if (minuti === null || minuti === undefined) return 'var(--bordo)';
  if (minuti <= 30) return 'var(--verde)';
  if (minuti <= 45) return 'var(--ambra)';
  return 'var(--rosso)';
}

function testoTempo(minuti) {
  if (minuti === null || minuti === undefined) return 'n.d.';
  if (minuti < 60) return `${minuti} min`;
  const ore = Math.floor(minuti / 60);
  const resto = minuti % 60;
  return resto ? `${ore}h ${resto}min` : `${ore}h`;
}

function numeroConVirgola(valore) {
  return typeof valore === 'number' ? valore.toString().replace('.', ',') : valore;
}

function primaMaiuscola(testo) {
  return testo.charAt(0).toUpperCase() + testo.slice(1);
}


/* ---------- 3. LETTURA DEI DATI ---------- */

async function caricaDati({ forzaRete = false } = {}) {
  if (!stato.dati) mostraScheletri();

  try {
    const risposta = await fetch(`./data/interpelli.json?t=${Date.now()}`, {
      cache: forzaRete ? 'reload' : 'default',
    });
    if (!risposta.ok) throw new Error('risposta ' + risposta.status);
    stato.dati = await risposta.json();
    scriviMemoria(CHIAVI.copiaDati, stato.dati);   // scorta per quando sei offline
    return true;
  } catch (errore) {
    const copia = leggiMemoria(CHIAVI.copiaDati, null);
    if (copia) {
      stato.dati = copia;
      mostraMessaggio('Sei offline: mostro i dati salvati');
      return true;
    }
    elementi.lista.replaceChildren();
    elementi.statoVuoto.hidden = false;
    elementi.statoVuoto.replaceChildren(
      nuovo('div', 'stato-vuoto__icona', '📡'),
      nuovo('h2', null, 'Dati non raggiungibili'),
      nuovo('p', null, 'Controlla la connessione e riprova.'),
    );
    return false;
  }
}

function mostraScheletri() {
  elementi.lista.replaceChildren(...Array.from({ length: 4 }, () => nuovo('div', 'scheletro')));
  elementi.statoVuoto.hidden = true;
}


/* ---------- 4. FILTRI E RICERCHE SALVATE ---------- */

function interpelliFiltrati(filtri = stato.filtri, testoCercato = stato.ricerca) {
  if (!stato.dati) return [];
  const cerca = (testoCercato || '').trim().toLowerCase();

  let elenco = stato.dati.interpelli.filter((interpello) => {
    if (filtri.stato.length && !filtri.stato.includes(interpello.stato)) return false;
    if (filtri.classi.length && !filtri.classi.includes(interpello.classe)) return false;
    if (filtri.corso.length && !filtri.corso.includes(interpello.corso)) return false;
    if (filtri.tipo.length && !filtri.tipo.includes(interpello.tipo_cattedra)) return false;
    // Il limite di tempo non nasconde mai chi non ha un tempo calcolato:
    // meglio vederlo con un "n.d." che perderselo.
    if (filtri.maxMinuti !== null && interpello.minuti !== null && interpello.minuti > filtri.maxMinuti) return false;
    if (cerca) {
      const testo = `${interpello.scuola} ${interpello.classe} ${interpello.classe_nome} ${comuneDi(interpello)}`;
      if (!testo.toLowerCase().includes(cerca)) return false;
    }
    return true;
  });

  if (filtri.ordine === 'data') {
    elenco = elenco.slice().sort((a, b) => (b.data_interpello || '').localeCompare(a.data_interpello || ''));
  }
  return elenco;
}

function scuolaDi(interpello) {
  return (stato.dati.scuole || {})[interpello.codice_scuola] || null;
}

function comuneDi(interpello) {
  const scuola = scuolaDi(interpello);
  return (scuola && scuola.sede && scuola.sede.comune) || '';
}

function nomeClasse(codice) {
  return (stato.dati.classi || {})[codice] || '';
}

function stessiFiltri(a, b) {
  return ['stato', 'classi', 'corso', 'tipo'].every(
    (campo) => JSON.stringify(a[campo].slice().sort()) === JSON.stringify(b[campo].slice().sort())
  ) && a.maxMinuti === b.maxMinuti && a.ordine === b.ordine;
}

function contaFiltriAttivi() {
  let attivi = 0;
  ['stato', 'classi', 'corso', 'tipo'].forEach((campo) => { if (stato.filtri[campo].length) attivi++; });
  if (stato.filtri.maxMinuti !== null) attivi++;
  return attivi;
}

// Descrive una ricerca a parole: "Aperti · A027 · Diurno · entro 30 min"
function descriviFiltri(filtri) {
  const pezzi = [];
  if (filtri.stato.length) pezzi.push(filtri.stato.map(primaMaiuscola).join('/'));
  if (filtri.classi.length) {
    // Con una o due classi c'e' spazio per il nome della materia; con di piu'
    // restiamo ai codici, altrimenti la riga diventa illeggibile.
    pezzi.push(filtri.classi.length <= 2
      ? filtri.classi.map((c) => `${c} ${nomeClasse(c)}`).join(', ')
      : filtri.classi.join(', '));
  }
  if (filtri.corso.length) pezzi.push(filtri.corso.join('/'));
  if (filtri.tipo.length) pezzi.push(filtri.tipo.join('/'));
  if (filtri.maxMinuti !== null) pezzi.push(`entro ${filtri.maxMinuti} min`);
  return pezzi.length ? pezzi.join(' · ') : 'Tutti gli interpelli';
}

function caricaRicerche() {
  const salvate = leggiMemoria(CHIAVI.ricerche, null);
  if (salvate && salvate.length) {
    // Se una ricerca e' stata salvata da una versione precedente della app,
    // completiamo i campi mancanti invece di andare in errore.
    return salvate.map((r) => ({ ...r, filtri: { ...FILTRI_VUOTI, ...(r.filtri || {}) } }));
  }
  // Prima apertura: creiamo una ricerca di partenza, che l'utente puo'
  // rinominare o cancellare come vuole.
  return [{
    id: 'iniziale',
    nome: 'A027 vicino a casa',
    filtri: JSON.parse(JSON.stringify(FILTRI_DI_FABBRICA)),
    notifiche: true,
    creata: new Date().toISOString(),
  }];
}

function salvaRicerche() {
  scriviMemoria(CHIAVI.ricerche, stato.ricerche);
  aggiornaNavigazione();
}

function applicaRicerca(ricerca) {
  stato.filtri = JSON.parse(JSON.stringify(ricerca.filtri));
  stato.ricercaAttiva = ricerca.id;
  stato.vista = 'lista';
  disegnaTutto();
}


/* ---------- 5. DISEGNO GENERALE ED ELENCO ---------- */

function disegnaTutto() {
  aggiornaIntestazione();
  aggiornaBarraFiltri();
  aggiornaBarraRicerche();
  aggiornaNavigazione();
  misuraIntestazione();

  const mostraMappa = stato.modo === 'mappa' && (stato.vista === 'lista' || stato.vista === 'preferiti');
  elementi.zonaMappa.hidden = !mostraMappa;
  elementi.contenuto.hidden = mostraMappa;
  document.body.classList.toggle('con-mappa', mostraMappa);

  if (stato.vista === 'info') return disegnaInfo();
  if (stato.vista === 'ricerche') return disegnaRicerche();

  const elenco = stato.vista === 'preferiti'
    ? stato.dati.interpelli.filter((i) => stato.preferiti.has(i.id))
    : interpelliFiltrati();

  if (mostraMappa) return disegnaMappa(elenco);

  elementi.lista.replaceChildren(...elenco.map(creaScheda));
  const avviso = avvisoConfigurazione();
  if (avviso) elementi.lista.prepend(avviso);
  disegnaRiepilogo(elenco);
  if (elenco.length === 0) disegnaStatoVuoto();
  else elementi.statoVuoto.hidden = true;
}

function disegnaRiepilogo(elenco) {
  if (elenco.length === 0) { elementi.riepilogo.hidden = true; return; }
  const parola = elenco.length === 1 ? 'interpello' : 'interpelli';
  const conTempo = elenco.filter((i) => i.minuti !== null);
  elementi.riepilogo.replaceChildren(
    nuovo('span', null, `${elenco.length} ${parola}`),
    nuovo('span', null, conTempo.length && stato.filtri.ordine === 'tempo'
      ? `dal più vicino (${testoTempo(conTempo[0].minuti)})` : ''),
  );
  elementi.riepilogo.hidden = false;
}

function creaScheda(interpello) {
  const scheda = nuovo('article', 'scheda');
  scheda.style.setProperty('--colore-tempo', coloreTempo(interpello.minuti));
  if (interpello.stato !== 'aperto') scheda.classList.add('scheda--attenuata');

  const alto = nuovo('div', 'scheda__alto');
  const classe = nuovo('div', 'scheda__classe');
  classe.append(
    nuovo('span', 'scheda__codice', interpello.classe),
    nuovo('span', 'scheda__materia', interpello.classe_nome),
  );
  alto.append(classe, creaStella(interpello, 'scheda__stella'));

  const scuola = nuovo('h2', 'scheda__scuola', interpello.scuola);

  const viaggio = nuovo('div', 'scheda__viaggio');
  const tempo = nuovo('span', 'viaggio__tempo');
  tempo.append(icona(ICONE.bus), nuovo('span', null, testoTempo(interpello.minuti)));
  viaggio.appendChild(tempo);

  const dettagli = [];
  if (interpello.km) dettagli.push(`${numeroConVirgola(interpello.km)} km`);
  const comune = comuneDi(interpello);
  if (comune) dettagli.push(comune);
  if (dettagli.length) viaggio.appendChild(nuovo('span', 'viaggio__dettagli', dettagli.join(' · ')));

  const etichette = nuovo('div', 'etichette');
  if (interpello.stato === 'aperto' && !stato.visti.has(interpello.id)) {
    etichette.appendChild(nuovo('span', 'etichetta etichetta--nuovo', 'nuovo'));
  }
  etichette.appendChild(nuovo('span', `etichetta etichetta--${interpello.stato}`, interpello.stato));
  if (interpello.scaduto) etichette.appendChild(nuovo('span', 'etichetta etichetta--scaduto', 'termine passato'));
  if (interpello.corso && interpello.corso !== 'Diurno') {
    etichette.appendChild(nuovo('span', 'etichetta etichetta--neutra', interpello.corso));
  }
  etichette.appendChild(nuovo('span', 'etichetta etichetta--neutra',
    interpello.tipo_cattedra === 'Spezzone' && interpello.ore_spezzone
      ? `spezzone ${interpello.ore_spezzone} h` : interpello.tipo_cattedra));

  const date = nuovo('div', 'scheda__date');
  const pubblicato = dataBreve(interpello.data_interpello) || interpello.data_interpello_testo;
  if (pubblicato) date.appendChild(nuovo('span', null, `📅 pubblicato ${pubblicato}`));
  const scadenza = dataBreve(interpello.data_scadenza) || interpello.data_scadenza_testo;
  if (scadenza) date.appendChild(nuovo('span', null, `⏳ scade ${scadenza}`));
  if (interpello.durata) date.appendChild(nuovo('span', null, `🗓 ${interpello.durata}`));

  scheda.append(alto, scuola, viaggio, etichette, date);
  scheda.addEventListener('click', () => apriDettaglio(interpello));
  return scheda;
}

function creaStella(interpello, classe) {
  const stella = nuovo('button', classe);
  stella.setAttribute('aria-label', 'Aggiungi ai preferiti');
  if (stato.preferiti.has(interpello.id)) stella.classList.add('attiva');
  stella.appendChild(icona(ICONE.stella));
  stella.addEventListener('click', (evento) => {
    evento.stopPropagation();
    cambiaPreferito(interpello.id);
    stella.classList.toggle('attiva');
  });
  return stella;
}

// Se i tempi di viaggio mancano per tutti, la app dice a voce alta cosa manca
// invece di lasciare "n.d." dappertutto senza spiegazioni.
function avvisoConfigurazione() {
  const d = stato.dati.diagnostica;
  const conteggi = stato.dati.conteggi;
  if (!d || conteggi.totale === 0) return null;
  if (conteggi.senza_tempo_di_viaggio < conteggi.totale) return null;   // qualcosa si calcola: tutto ok

  const manca = [];
  if (!d.casa_impostata) manca.push('il segreto CASA_INDIRIZZO (l’indirizzo di partenza)');
  if (!d.chiave_google) manca.push('il segreto GOOGLE_MAPS_API_KEY (la chiave di Google)');
  if (!manca.length) return null;   // c'e' tutto ma i tempi mancano: sara' il prossimo giro

  const avviso = nuovo('div', 'avviso');
  const testo = nuovo('div');
  testo.append(
    nuovo('strong', null, 'Tempi di viaggio non calcolati. '),
    document.createTextNode(`Su GitHub manca ${manca.join(' e ')}. `),
    document.createTextNode('Aggiungilo in Settings → Secrets and variables → Actions, poi lancia '
      + 'l’aggiornamento da Actions → Aggiorna interpelli → Run workflow.'),
  );
  avviso.append(icona(ICONE.avviso), testo);
  return avviso;
}

function disegnaStatoVuoto() {
  const vuoto = elementi.statoVuoto;
  vuoto.hidden = false;

  if (stato.vista === 'preferiti') {
    vuoto.replaceChildren(
      nuovo('div', 'stato-vuoto__icona', '⭐'),
      nuovo('h2', null, 'Nessun preferito'),
      nuovo('p', null, 'Tocca la stellina su un interpello per ritrovarlo qui.'),
    );
    return;
  }

  const aperti = stato.dati.conteggi.aperti;
  const azioni = nuovo('div', 'stato-vuoto__azioni');

  const storico = nuovo('button', 'bottone bottone--primario bottone--piccolo', 'Vedi lo storico completo');
  storico.addEventListener('click', () => {
    stato.filtri = { ...FILTRI_VUOTI, ordine: stato.filtri.ordine };
    stato.ricercaAttiva = null;
    disegnaTutto();
  });
  azioni.appendChild(storico);

  if (stato.filtri.maxMinuti !== null) {
    const togli = nuovo('button', 'bottone bottone--secondario bottone--piccolo',
      `Togli il limite di ${stato.filtri.maxMinuti} min`);
    togli.addEventListener('click', () => {
      stato.filtri = { ...stato.filtri, maxMinuti: null };
      stato.ricercaAttiva = null;
      disegnaTutto();
    });
    azioni.appendChild(togli);
  }

  if (stato.filtri.classi.length && stato.filtri.classi.length < Object.keys(stato.dati.classi).length) {
    const tutte = nuovo('button', 'bottone bottone--secondario bottone--piccolo', 'Mostra tutte le classi');
    tutte.addEventListener('click', () => {
      stato.filtri = { ...stato.filtri, classi: [] };
      stato.ricercaAttiva = null;
      disegnaTutto();
    });
    azioni.appendChild(tutte);
  }

  vuoto.replaceChildren(
    nuovo('div', 'stato-vuoto__icona', aperti === 0 ? '🌤️' : '🔍'),
    nuovo('h2', null, aperti === 0 ? 'Nessun interpello aperto' : 'Nessun risultato'),
    nuovo('p', null, aperti === 0
      ? 'In questo momento non c’è nessun interpello aperto in provincia di Torino per le tue classi. Di solito ricompaiono da settembre.'
      : 'Nessun interpello corrisponde ai filtri impostati.'),
    azioni,
  );
  elementi.riepilogo.hidden = true;
}

function aggiornaIntestazione() {
  const titoli = { lista: 'Interpelli', preferiti: 'Preferiti', info: 'Info', ricerche: 'Ricerche salvate' };
  const ricercaAttiva = stato.ricerche.find((r) => r.id === stato.ricercaAttiva);
  elementi.titoloVista.textContent =
    stato.vista === 'lista' && ricercaAttiva ? ricercaAttiva.nome : titoli[stato.vista];

  if (!stato.dati) { elementi.sottotitolo.textContent = 'caricamento…'; return; }

  if (stato.vista === 'info') {
    elementi.sottotitolo.textContent = 'come funziona questa app';
  } else if (stato.vista === 'ricerche') {
    elementi.sottotitolo.textContent = 'i tuoi filtri salvati e le notifiche';
  } else {
    const quando = new Date(stato.dati.aggiornato);
    const oggi = new Date().toDateString() === quando.toDateString();
    const orario = quando.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
    elementi.sottotitolo.textContent = `${stato.dati.conteggi.aperti} aperti ora · aggiornato `
      + `${oggi ? 'oggi' : quando.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' })} alle ${orario}`;
  }

  const soloElenco = stato.vista === 'info' || stato.vista === 'ricerche';
  elementi.zonaRicerca.hidden = soloElenco;
  elementi.barraFiltri.hidden = soloElenco;
  elementi.barraRicerche.hidden = soloElenco || stato.vista === 'preferiti';
  elementi.interruttoreVista.hidden = soloElenco;
}

function aggiornaNavigazione() {
  elementi.navBasso.querySelectorAll('.nav-basso__voce').forEach((voce) => {
    voce.classList.toggle('attiva', voce.dataset.vista === stato.vista);
  });
  elementi.conteggioPreferiti.hidden = stato.preferiti.size === 0;
  elementi.conteggioPreferiti.textContent = stato.preferiti.size;
  elementi.conteggioRicerche.hidden = stato.ricerche.length === 0;
  elementi.conteggioRicerche.textContent = stato.ricerche.length;
}

function aggiornaBarraFiltri() {
  const f = stato.filtri;
  const attivi = [];
  if (f.stato.length) attivi.push({ campo: 'stato', testo: f.stato.map(primaMaiuscola).join(', ') });
  if (f.classi.length) attivi.push({ campo: 'classi', testo: f.classi.join(', ') });
  if (f.corso.length) attivi.push({ campo: 'corso', testo: f.corso.join(', ') });
  if (f.tipo.length) attivi.push({ campo: 'tipo', testo: f.tipo.join(', ') });
  if (f.maxMinuti !== null) attivi.push({ campo: 'maxMinuti', testo: `entro ${f.maxMinuti} min` });

  elementi.filtriAttivi.replaceChildren(...attivi.map(({ campo, testo }) => {
    const chip = nuovo('button', 'chip chip--attivo chip--rimuovi', testo);
    chip.addEventListener('click', () => {
      stato.filtri = { ...stato.filtri, [campo]: campo === 'maxMinuti' ? null : [] };
      stato.ricercaAttiva = null;
      disegnaTutto();
    });
    return chip;
  }));

  const quanti = contaFiltriAttivi();
  elementi.contatoreFiltri.hidden = quanti === 0;
  elementi.contatoreFiltri.textContent = quanti;
}

// La striscia di "pillole" con le ricerche salvate, come le tab di un browser.
function aggiornaBarraRicerche() {
  if (!stato.dati) return;
  const barra = elementi.barraRicerche;
  const voci = stato.ricerche.map((ricerca) => {
    const attiva = ricerca.id === stato.ricercaAttiva
      || (stato.ricercaAttiva === null && stessiFiltri(ricerca.filtri, stato.filtri));
    const chip = nuovo('button', 'pillola' + (attiva ? ' pillola--attiva' : ''));
    chip.append(nuovo('span', null, ricerca.nome));
    // Il numerino verde conta quelli aperti adesso, anche se la ricerca era
    // stata salvata guardando lo storico.
    const quanti = interpelliFiltrati({ ...ricerca.filtri, stato: ['aperto'] }, '').length;
    if (quanti) chip.appendChild(nuovo('em', 'pillola__numero', String(quanti)));
    if (ricerca.notifiche) chip.appendChild(icona(ICONE.campana, 13));
    chip.addEventListener('click', () => applicaRicerca(ricerca));
    return chip;
  });

  const aggiungi = nuovo('button', 'pillola pillola--aggiungi', '+ Salva ricerca');
  aggiungi.addEventListener('click', () => apriPannelloNome());
  voci.push(aggiungi);

  barra.replaceChildren(...voci);
}


// L'intestazione cambia altezza (filtri attivi, ricerche salvate...): la
// misuriamo e la comunichiamo al CSS, cosi' la mappa comincia esattamente sotto.
function misuraIntestazione() {
  const altezza = $('intestazione').offsetHeight;
  document.documentElement.style.setProperty('--altezza-intestazione', altezza + 'px');
}


/* ---------- 5-bis. DOVE ABITI (solo su questo dispositivo) ---------- */

// La posizione di casa non arriva dal server: la scegli tu nella app e resta
// nella memoria del telefono. Serve solo per il segnaposto sulla mappa e per
// far partire da li' i percorsi di Google Maps. I minuti sono gia' calcolati.
function casaAttuale() {
  if (stato.casa && typeof stato.casa.lat === 'number') return stato.casa;
  const pubblicata = stato.dati && stato.dati.casa;
  return (pubblicata && typeof pubblicata.lat === 'number') ? pubblicata : null;
}

function apriPannelloCasa() {
  stato.casaInAttesa = null;
  elementi.campoIndirizzoCasa.value = (stato.casa && stato.casa.indirizzo) || '';
  elementi.esitoCasa.replaceChildren();
  elementi.velo.hidden = false;
  elementi.pannelloCasa.hidden = false;
  scriviMemoria(CHIAVI.casaChiesta, true);   // chiesto una volta, non insistiamo
}

function mostraEsitoCasa(testo, tipo) {
  const riga = nuovo('div', tipo === 'errore' ? 'avviso' : 'esito-casa');
  if (tipo === 'errore') riga.append(icona(ICONE.avviso), nuovo('span', null, testo));
  else riga.append(nuovo('span', null, '📍'), nuovo('span', null, testo));
  elementi.esitoCasa.replaceChildren(riga);
}

// Cerchiamo l'indirizzo con il servizio gratuito di OpenStreetMap: nessuna
// chiave, nessun costo, e la richiesta parte dal tuo telefono.
async function cercaIndirizzoCasa() {
  const testo = elementi.campoIndirizzoCasa.value.trim();
  if (!testo) return mostraEsitoCasa('Scrivi prima un indirizzo.', 'errore');

  mostraEsitoCasa('Cerco…', 'ok');
  try {
    const url = 'https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=it&q='
      + encodeURIComponent(testo);
    const risposta = await fetch(url, { headers: { 'Accept-Language': 'it' } });
    const risultati = await risposta.json();
    if (!risultati.length) {
      return mostraEsitoCasa('Non l’ho trovato. Prova ad aggiungere la città, o usa "Scegli sulla mappa".', 'errore');
    }
    stato.casaInAttesa = {
      lat: parseFloat(risultati[0].lat),
      lng: parseFloat(risultati[0].lon),
      indirizzo: testo,
    };
    mostraEsitoCasa(risultati[0].display_name.split(',').slice(0, 4).join(','), 'ok');
  } catch (errore) {
    mostraEsitoCasa('Ricerca non riuscita: sei offline? Puoi usare "Scegli sulla mappa".', 'errore');
  }
}

function usaPosizioneAttuale() {
  if (!navigator.geolocation) {
    return mostraEsitoCasa('Questo dispositivo non sa dirmi la posizione.', 'errore');
  }
  mostraEsitoCasa('Chiedo la posizione al dispositivo…', 'ok');
  navigator.geolocation.getCurrentPosition(
    (posizione) => {
      stato.casaInAttesa = {
        lat: posizione.coords.latitude,
        lng: posizione.coords.longitude,
        indirizzo: '',
      };
      mostraEsitoCasa('Posizione presa. Tocca Salva per confermare.', 'ok');
    },
    () => mostraEsitoCasa('Permesso negato o posizione non disponibile.', 'errore'),
    { enableHighAccuracy: true, timeout: 10000 }
  );
}

function iniziaSceltaSullaMappa() {
  chiudiPannelli();
  stato.sceltaSullaMappa = true;
  stato.modo = 'mappa';
  elementi.interruttoreVista.querySelectorAll('button')
    .forEach((b) => b.classList.toggle('attiva', b.dataset.modo === 'mappa'));
  elementi.istruzioneMappa.hidden = false;
  disegnaTutto();
}

function fineSceltaSullaMappa() {
  stato.sceltaSullaMappa = false;
  elementi.istruzioneMappa.hidden = true;
}

function salvaCasa(casa) {
  stato.casa = casa;
  scriviMemoria(CHIAVI.casa, casa);
  scriviMemoria(CHIAVI.casaChiesta, true);
  stato.ultimaImpronta = '';        // cosi' la mappa si reinquadra tenendo conto di casa
  disegnaTutto();
}


/* ---------- 6. MAPPA ---------- */

// Leaflet viene caricato con "defer": aspettiamo che sia pronto.
function attendiLeaflet() {
  return new Promise((risolvi, rifiuta) => {
    if (window.L) return risolvi(window.L);
    let tentativi = 0;
    const controllo = setInterval(() => {
      if (window.L) { clearInterval(controllo); risolvi(window.L); }
      else if (++tentativi > 100) { clearInterval(controllo); rifiuta(new Error('Leaflet non caricato')); }
    }, 100);
  });
}

function temaScuro() {
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
}

async function disegnaMappa(elenco) {
  let L;
  try {
    L = await attendiLeaflet();
  } catch (errore) {
    elementi.zonaMappa.hidden = true;
    elementi.contenuto.hidden = false;
    mostraMessaggio('Mappa non disponibile offline');
    stato.modo = 'elenco';
    return disegnaTutto();
  }

  if (!stato.mappa) creaMappa(L);
  aggiornaSegnapostoCasa(L);
  disegnaSegnaposti(L, elenco);

  const parola = elenco.length === 1 ? 'interpello' : 'interpelli';
  elementi.conteggioMappa.textContent = `${elenco.length} ${parola}`;
  elementi.conteggioMappa.hidden = false;
  // La mappa era nascosta: va avvisata che ora ha spazio, altrimenti resta grigia.
  setTimeout(() => stato.mappa.invalidateSize(), 60);
}

function creaMappa(L) {
  stato.mappa = L.map(elementi.mappa, {
    center: [45.0703, 7.6869],      // Torino
    zoom: 11,
    zoomControl: false,
    attributionControl: true,
  });
  L.control.zoom({ position: 'bottomright' }).addTo(stato.mappa);
  cambiaTessere(L);
  stato.stratoSegnaposti = L.layerGroup().addTo(stato.mappa);

  // Se il telefono passa da tema chiaro a scuro, cambiamo anche le mappe.
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)')
      .addEventListener('change', () => cambiaTessere(L));
  }

  // Un tocco sulla mappa vale come "casa e' qui", ma solo quando lo hai chiesto.
  stato.mappa.on('click', (evento) => {
    if (!stato.sceltaSullaMappa) return;
    fineSceltaSullaMappa();
    salvaCasa({ lat: evento.latlng.lat, lng: evento.latlng.lng, indirizzo: '' });
    mostraMessaggio('Casa impostata 🏠');
  });
}

// Il segnaposto di casa puo' cambiare (lo scegli tu), quindi lo ridisegniamo
// invece di piazzarlo una volta sola alla creazione della mappa.
function aggiornaSegnapostoCasa(L) {
  if (stato.segnapostoCasa) {
    stato.mappa.removeLayer(stato.segnapostoCasa);
    stato.segnapostoCasa = null;
  }
  const casa = casaAttuale();
  if (!casa) return;

  stato.segnapostoCasa = L.marker([casa.lat, casa.lng], {
    icon: L.divIcon({ className: 'segnaposto-casa', html: '🏠', iconSize: [34, 34], iconAnchor: [17, 17] }),
    zIndexOffset: 500,
  }).addTo(stato.mappa);

  const nome = casa.indirizzo || 'Casa';
  stato.segnapostoCasa.bindPopup(nome + (casa.approssimata ? ' (posizione indicativa)' : ''));
}

function cambiaTessere(L) {
  if (stato.stratoTessere) stato.mappa.removeLayer(stato.stratoTessere);
  const stile = temaScuro() ? 'dark_all' : 'voyager';
  stato.stratoTessere = L.tileLayer(
    `https://{s}.basemaps.cartocdn.com/rastertiles/${stile}/{z}/{x}/{y}{r}.png`,
    {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      subdomains: 'abcd',
    }
  ).addTo(stato.mappa);
  stato.stratoTessere.bringToBack();
}

function disegnaSegnaposti(L, elenco) {
  stato.stratoSegnaposti.clearLayers();

  // Piu' interpelli nella stessa scuola = un solo segnaposto con il contatore.
  const perScuola = new Map();
  elenco.forEach((interpello) => {
    const scuola = scuolaDi(interpello);
    const sede = scuola && scuola.sede;
    const viaggio = sede && sede.viaggio;
    if (!viaggio || viaggio.lat === null || viaggio.lat === undefined) return;
    const gruppo = perScuola.get(interpello.codice_scuola) || {
      scuola, sede, viaggio, interpelli: [],
    };
    gruppo.interpelli.push(interpello);
    perScuola.set(interpello.codice_scuola, gruppo);
  });

  const punti = [];
  perScuola.forEach((gruppo) => {
    const minuti = gruppo.viaggio.minuti;
    const contenuto = document.createElement('div');
    contenuto.className = 'segnaposto';
    contenuto.style.setProperty('--c', coloreTempo(minuti));
    contenuto.appendChild(nuovo('span', 'segnaposto__testo',
      minuti === null || minuti === undefined ? '?' : `${minuti}′`));
    if (gruppo.interpelli.length > 1) {
      contenuto.appendChild(nuovo('em', 'segnaposto__numero', String(gruppo.interpelli.length)));
    }
    if (gruppo.interpelli.some((i) => i.stato === 'aperto')) contenuto.classList.add('segnaposto--aperto');

    const segnaposto = L.marker([gruppo.viaggio.lat, gruppo.viaggio.lng], {
      icon: L.divIcon({
        className: '', html: contenuto.outerHTML,
        iconSize: [46, 30], iconAnchor: [23, 30], popupAnchor: [0, -28],
      }),
    });
    segnaposto.bindPopup(() => finestrellaMappa(gruppo), { maxWidth: 280, minWidth: 220 });
    segnaposto.addTo(stato.stratoSegnaposti);
    punti.push([gruppo.viaggio.lat, gruppo.viaggio.lng]);
  });

  // Inquadriamo tutti i risultati (piu' casa) solo quando cambia l'insieme.
  const impronta = punti.length + ':' + [...perScuola.keys()].sort().join(',');
  if (impronta !== stato.ultimaImpronta && punti.length) {
    const casa = casaAttuale();
    const tutti = casa ? punti.concat([[casa.lat, casa.lng]]) : punti;
    stato.mappa.fitBounds(tutti, { padding: [45, 45], maxZoom: 14 });
    stato.ultimaImpronta = impronta;
  }
}

// La schedina che compare toccando un segnaposto.
function finestrellaMappa(gruppo) {
  const contenitore = nuovo('div', 'finestrella');
  contenitore.appendChild(nuovo('h3', 'finestrella__titolo', gruppo.scuola.denominazione || ''));
  contenitore.appendChild(nuovo('p', 'finestrella__indirizzo', gruppo.sede.indirizzo || ''));

  const viaggio = gruppo.viaggio;
  const riga = nuovo('div', 'finestrella__viaggio');
  const tempo = nuovo('span', 'sede__tempo');
  tempo.style.color = coloreTempo(viaggio.minuti);
  tempo.append(icona(ICONE.bus, 15), nuovo('span', null, testoTempo(viaggio.minuti)));
  riga.appendChild(tempo);
  if (viaggio.km_strada) riga.appendChild(nuovo('span', 'viaggio__dettagli', `${numeroConVirgola(viaggio.km_strada)} km`));
  contenitore.appendChild(riga);

  gruppo.interpelli.slice(0, 4).forEach((interpello) => {
    const voce = nuovo('button', 'finestrella__voce');
    voce.append(
      nuovo('strong', null, interpello.classe),
      nuovo('span', null, `${interpello.classe_nome} · ${interpello.durata || ''}`),
      nuovo('span', `etichetta etichetta--${interpello.stato}`, interpello.stato),
    );
    voce.addEventListener('click', () => {
      stato.mappa.closePopup();
      apriDettaglio(interpello);
    });
    contenitore.appendChild(voce);
  });
  if (gruppo.interpelli.length > 4) {
    contenitore.appendChild(nuovo('p', 'viaggio__dettagli', `e altri ${gruppo.interpelli.length - 4}…`));
  }
  return contenitore;
}


/* ---------- 7. DETTAGLIO DI UN INTERPELLO ---------- */

function apriDettaglio(interpello) {
  const scuola = scuolaDi(interpello);
  const corpo = elementi.corpoDettaglio;
  corpo.replaceChildren();

  corpo.appendChild(nuovo('h2', 'dettaglio__titolo', interpello.scuola));
  corpo.appendChild(nuovo('p', 'dettaglio__sottotitolo', `${interpello.classe} · ${interpello.classe_nome}`));

  const etichette = nuovo('div', 'etichette');
  etichette.style.marginBottom = '12px';
  etichette.appendChild(nuovo('span', `etichetta etichetta--${interpello.stato}`, interpello.stato));
  if (interpello.scaduto) etichette.appendChild(nuovo('span', 'etichetta etichetta--scaduto', 'termine già passato'));
  corpo.appendChild(etichette);

  if (interpello.stato === 'cancellato' && interpello.note_cancellazione) {
    const avviso = nuovo('div', 'avviso');
    avviso.append(icona(ICONE.avviso), nuovo('span', null, `Cancellato: ${interpello.note_cancellazione}`));
    corpo.appendChild(avviso);
  }

  if (scuola && scuola.sede) {
    const riquadro = nuovo('div', 'riquadro riquadro--principale');
    riquadro.style.setProperty('--colore-tempo', coloreTempo(interpello.minuti));
    riquadro.appendChild(nuovo('h3', null, 'Da casa a scuola'));
    riquadro.appendChild(bloccoSede(scuola.sede, true));
    corpo.appendChild(riquadro);
  }

  const plessi = (scuola && scuola.plessi) || [];
  const altri = plessi.filter((p) => !scuola.sede || p.indirizzo !== scuola.sede.indirizzo);
  if (altri.length) {
    const riquadro = nuovo('div', 'riquadro');
    riquadro.appendChild(nuovo('h3', null, `Altre sedi dell’istituto (${altri.length})`));
    altri.forEach((plesso) => riquadro.appendChild(bloccoSede(plesso, false)));
    const nota = nuovo('p', 'viaggio__dettagli',
      'L’interpello non dice in quale sede si insegna: controlla sempre l’avviso della scuola.');
    nota.style.marginTop = '8px';
    riquadro.appendChild(nota);
    corpo.appendChild(riquadro);
  }

  const dettagli = nuovo('div', 'riquadro');
  dettagli.appendChild(nuovo('h3', null, 'Dettagli'));
  [
    ['Durata', interpello.durata],
    ['Tipo di cattedra', interpello.tipo_cattedra === 'Spezzone' && interpello.ore_spezzone
      ? `Spezzone di ${interpello.ore_spezzone} ore` : interpello.tipo_cattedra],
    ['Corso', interpello.corso],
    ['Pubblicato il', interpello.data_interpello_testo],
    ['Scadenza', interpello.data_scadenza_testo],
    ['Codice scuola', interpello.codice_scuola],
  ].forEach(([etichetta, valore]) => {
    if (!valore) return;
    const riga = nuovo('div', 'riga-dato');
    riga.append(nuovo('span', 'riga-dato__etichetta', etichetta), nuovo('span', 'riga-dato__valore', valore));
    dettagli.appendChild(riga);
  });
  corpo.appendChild(dettagli);

  const collegamenti = nuovo('div', 'riquadro');
  collegamenti.appendChild(nuovo('h3', null, 'Collegamenti'));
  const elenco = nuovo('div', 'colonna');
  if (scuola && scuola.sede && scuola.sede.sito) {
    elenco.appendChild(collegamentoEsterno('Sito della scuola', sistemaIndirizzoWeb(scuola.sede.sito)));
  }
  elenco.appendChild(collegamentoEsterno('Pagina ufficiale degli interpelli',
    'https://servizi.istruzionepiemonte.it/interpello2025/ric_interpello_ambito_to.php'));
  collegamenti.appendChild(elenco);
  corpo.appendChild(collegamenti);

  const stella = nuovo('button', 'bottone bottone--secondario',
    stato.preferiti.has(interpello.id) ? '★  Togli dai preferiti' : '☆  Aggiungi ai preferiti');
  stella.style.width = '100%';
  stella.style.marginBottom = '10px';
  stella.addEventListener('click', () => {
    cambiaPreferito(interpello.id);
    stella.textContent = stato.preferiti.has(interpello.id) ? '★  Togli dai preferiti' : '☆  Aggiungi ai preferiti';
    if (stato.vista === 'preferiti') disegnaTutto();
  });
  corpo.appendChild(stella);

  elementi.velo.hidden = false;
  elementi.pannelloDettaglio.hidden = false;
  corpo.scrollTop = 0;
}

function bloccoSede(sede, principale) {
  const blocco = nuovo('div', 'sede');
  blocco.appendChild(nuovo('div', 'sede__nome',
    principale ? 'Sede centrale' : (sede.nomi ? sede.nomi[0] : 'Sede')));
  blocco.appendChild(nuovo('div', 'sede__indirizzo', sede.indirizzo || 'indirizzo non disponibile'));

  const riga = nuovo('div', 'sede__riga');
  const viaggio = sede.viaggio;

  if (viaggio && viaggio.minuti !== null && viaggio.minuti !== undefined) {
    const tempo = nuovo('span', 'sede__tempo');
    tempo.style.color = coloreTempo(viaggio.minuti);
    tempo.append(icona(ICONE.bus), nuovo('span', null, testoTempo(viaggio.minuti)));
    riga.appendChild(tempo);

    const extra = [];
    if (viaggio.cambi !== null && viaggio.cambi !== undefined) {
      extra.push(viaggio.cambi === 0 ? 'diretto' : `${viaggio.cambi} cambi`);
    }
    if (viaggio.km_strada) extra.push(`${numeroConVirgola(viaggio.km_strada)} km`);
    if (viaggio.auto_minuti) extra.push(`auto ${testoTempo(viaggio.auto_minuti)}`);
    if (extra.length) riga.appendChild(nuovo('span', 'viaggio__dettagli', extra.join(' · ')));
  } else {
    riga.appendChild(nuovo('span', 'viaggio__dettagli', 'tempo di viaggio non ancora calcolato'));
  }
  blocco.appendChild(riga);

  if (viaggio && viaggio.approssimativo) {
    const nota = nuovo('div', 'sede__nota');
    nota.append(icona(ICONE.avviso, 14),
      nuovo('span', null, 'Indirizzo incompleto in anagrafica: posizione e tempi riferiti al centro del comune.'));
    blocco.appendChild(nota);
  }

  if (viaggio && viaggio.linee && viaggio.linee.length) {
    const linee = nuovo('div', 'linee');
    viaggio.linee.forEach((linea) => linee.appendChild(nuovo('span', 'linea', linea.nome)));
    blocco.appendChild(linee);
  }

  if (sede.indirizzo) {
    // La partenza e' la casa che hai impostato su questo dispositivo. Se non
    // l'hai impostata, lasciamo che Google usi la posizione attuale.
    const casa = casaAttuale();
    const partenza = casa ? (casa.indirizzo || `${casa.lat},${casa.lng}`) : '';
    const url = 'https://www.google.com/maps/dir/?api=1'
      + (partenza ? `&origin=${encodeURIComponent(partenza)}` : '')
      + `&destination=${encodeURIComponent(sede.indirizzo)}&travelmode=transit`;
    const collegamento = collegamentoEsterno(
      partenza ? 'Apri il percorso in Google Maps' : 'Apri la scuola in Google Maps', url);
    collegamento.style.marginTop = '6px';
    blocco.appendChild(collegamento);
  }
  return blocco;
}

function collegamentoEsterno(testo, url) {
  const a = document.createElement('a');
  a.className = 'collegamento';
  a.href = url;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.append(icona(ICONE.esterno), nuovo('span', null, testo));
  return a;
}

function sistemaIndirizzoWeb(sito) {
  return /^https?:\/\//i.test(sito) ? sito : 'https://' + sito;
}


/* ---------- 8. PANNELLI ---------- */

function apriFiltri() {
  stato.filtriInModifica = JSON.parse(JSON.stringify(stato.filtri));
  disegnaPannelloFiltri();
  elementi.velo.hidden = false;
  elementi.pannelloFiltri.hidden = false;
}

function chiudiPannelli() {
  elementi.velo.hidden = true;
  elementi.pannelloFiltri.hidden = true;
  elementi.pannelloDettaglio.hidden = true;
  elementi.pannelloNome.hidden = true;
  elementi.pannelloCasa.hidden = true;
}

function disegnaPannelloFiltri() {
  const f = stato.filtriInModifica;

  gruppoDiChip($('filtroStato'), [
    { valore: 'aperto', etichetta: 'Aperti' },
    { valore: 'chiuso', etichetta: 'Chiusi' },
    { valore: 'cancellato', etichetta: 'Cancellati' },
  ], f.stato, 'stato');

  // Le classi le mostriamo con il nome della materia accanto al codice:
  // "A027" da solo dice poco quando le scegli.
  gruppoDiChip($('filtroClassi'),
    Object.entries(stato.dati.classi).map(([codice, nome]) => ({
      valore: codice, etichetta: codice, descrizione: nome,
    })),
    f.classi, 'classi');

  const corsiPresenti = [...new Set(stato.dati.interpelli.map((i) => i.corso))].sort();
  gruppoDiChip($('filtroCorso'), corsiPresenti.map((c) => ({ valore: c, etichetta: c })), f.corso, 'corso');

  gruppoDiChip($('filtroTipo'), [
    { valore: 'Interna', etichetta: 'Cattedra interna' },
    { valore: 'Esterna', etichetta: 'Cattedra esterna' },
    { valore: 'Spezzone', etichetta: 'Spezzone' },
  ], f.tipo, 'tipo');

  gruppoDiChip($('filtroTempo'), [
    { valore: 15, etichetta: '15 min' },
    { valore: 30, etichetta: '30 min' },
    { valore: 45, etichetta: '45 min' },
    { valore: 60, etichetta: '1 ora' },
    { valore: null, etichetta: 'Tutti' },
  ], f.maxMinuti, 'maxMinuti', true);

  gruppoDiChip($('filtroOrdine'), [
    { valore: 'tempo', etichetta: 'Più vicini' },
    { valore: 'data', etichetta: 'Più recenti' },
  ], f.ordine, 'ordine', true);

  const quanti = interpelliFiltrati(stato.filtriInModifica).length;
  elementi.conteggioAnteprima.textContent = quanti === 0 ? '(nessuno)' : `(${quanti})`;
  elementi.etichettaTempo.textContent = f.maxMinuti === null
    ? '' : `— mezzi pubblici, arrivo ore ${stato.dati.casa.ora_arrivo}`;
}

// Disegna un gruppo di chip. Se "singolo" e' vero se ne puo' scegliere una sola.
function gruppoDiChip(contenitore, voci, selezione, campo, singolo = false) {
  contenitore.replaceChildren(...voci.map(({ valore, etichetta, descrizione }) => {
    const scelto = singolo ? selezione === valore : selezione.includes(valore);
    const chip = nuovo('button', 'chip' + (scelto ? ' chip--attivo' : ''),
      descrizione ? null : etichetta);
    if (descrizione) {
      chip.classList.add('chip--largo');
      chip.append(nuovo('strong', 'chip__codice', etichetta),
                  nuovo('span', 'chip__nome', descrizione));
    }
    chip.addEventListener('click', () => {
      const f = stato.filtriInModifica;
      if (singolo) {
        f[campo] = valore;
      } else {
        const posizione = f[campo].indexOf(valore);
        if (posizione >= 0) f[campo].splice(posizione, 1); else f[campo].push(valore);
      }
      disegnaPannelloFiltri();
    });
    return chip;
  }));

  if (!singolo && selezione.length === 0) {
    contenitore.appendChild(nuovo('span', 'viaggio__dettagli', 'niente selezionato = tutti'));
  }
}

// Pannello "dai un nome alla ricerca". Serve sia per crearne una nuova sia per
// rinominarne una esistente (in quel caso passiamo la ricerca da modificare).
function apriPannelloNome(ricercaEsistente = null) {
  const filtri = ricercaEsistente ? ricercaEsistente.filtri : (stato.filtriInModifica || stato.filtri);
  elementi.titoloPannelloNome.textContent = ricercaEsistente ? 'Modifica ricerca' : 'Salva questa ricerca';
  elementi.riassuntoRicerca.textContent = descriviFiltri(filtri);
  elementi.campoNomeRicerca.value = ricercaEsistente ? ricercaEsistente.nome : nomeSuggerito(filtri);
  elementi.notificheRicerca.checked = ricercaEsistente ? !!ricercaEsistente.notifiche : true;
  elementi.confermaNome.dataset.modifica = ricercaEsistente ? ricercaEsistente.id : '';

  elementi.velo.hidden = false;
  elementi.pannelloFiltri.hidden = true;
  elementi.pannelloNome.hidden = false;
  setTimeout(() => elementi.campoNomeRicerca.focus(), 120);
}

function nomeSuggerito(filtri) {
  const pezzi = [];
  if (filtri.classi.length) pezzi.push(filtri.classi.join('+'));
  if (filtri.maxMinuti !== null) pezzi.push(`entro ${filtri.maxMinuti}′`);
  if (filtri.corso.length === 1) pezzi.push(filtri.corso[0].toLowerCase());
  return pezzi.join(' ') || 'Tutti gli interpelli';
}

function confermaPannelloNome() {
  const nome = elementi.campoNomeRicerca.value.trim() || 'Senza nome';
  const idDaModificare = elementi.confermaNome.dataset.modifica;

  if (idDaModificare) {
    const ricerca = stato.ricerche.find((r) => r.id === idDaModificare);
    if (ricerca) {
      ricerca.nome = nome;
      ricerca.notifiche = elementi.notificheRicerca.checked;
    }
    mostraMessaggio('Ricerca aggiornata');
  } else {
    const ricerca = {
      id: 'r' + Date.now().toString(36),
      nome,
      filtri: JSON.parse(JSON.stringify(stato.filtriInModifica || stato.filtri)),
      notifiche: elementi.notificheRicerca.checked,
      creata: new Date().toISOString(),
    };
    stato.ricerche.push(ricerca);
    stato.filtri = JSON.parse(JSON.stringify(ricerca.filtri));
    stato.ricercaAttiva = ricerca.id;
    mostraMessaggio(ricerca.notifiche ? 'Ricerca salvata, ti avviserò 🔔' : 'Ricerca salvata');
  }

  salvaRicerche();
  chiudiPannelli();
  disegnaTutto();
}


/* ---------- 9. VISTE "RICERCHE" E "INFO" ---------- */

function disegnaRicerche() {
  elementi.riepilogo.hidden = true;
  elementi.statoVuoto.hidden = true;
  const contenitore = nuovo('div');

  if (stato.ricerche.length === 0) {
    contenitore.appendChild(nuovo('p', 'info-testo',
      'Non hai ancora salvato nessuna ricerca. Imposta dei filtri e tocca "Salva ricerca".'));
  }

  stato.ricerche.forEach((ricerca) => {
    // Due conteggi diversi: quanti sono aperti adesso e quanti in tutto
    // l'archivio (ignorando il filtro sullo stato, altrimenti fuori stagione
    // ogni ricerca sembrerebbe vuota).
    const aperti = interpelliFiltrati({ ...ricerca.filtri, stato: ['aperto'] }, '');
    const archivio = interpelliFiltrati({ ...ricerca.filtri, stato: [] }, '');

    const riquadro = nuovo('div', 'riquadro riquadro--ricerca');
    const testata = nuovo('div', 'ricerca-salvata__testata');
    testata.append(nuovo('h3', 'ricerca-salvata__nome', ricerca.nome));
    if (aperti.length) testata.appendChild(nuovo('span', 'etichetta etichetta--aperto', `${aperti.length} aperti`));
    riquadro.appendChild(testata);
    riquadro.appendChild(nuovo('p', 'ricerca-salvata__filtri', descriviFiltri(ricerca.filtri)));
    riquadro.appendChild(nuovo('p', 'viaggio__dettagli',
      `${aperti.length} aperti ora · ${archivio.length} in archivio`));

    const interruttore = nuovo('label', 'riga-interruttore');
    const testo = nuovo('span');
    testo.append(nuovo('strong', null, 'Notifiche Telegram'),
                 nuovo('em', null, ricerca.notifiche ? 'attive per questa ricerca' : 'disattivate'));
    const casella = document.createElement('input');
    casella.type = 'checkbox';
    casella.checked = !!ricerca.notifiche;
    casella.addEventListener('change', () => {
      ricerca.notifiche = casella.checked;
      salvaRicerche();
      disegnaRicerche();
    });
    interruttore.append(testo, casella);
    riquadro.appendChild(interruttore);

    const azioni = nuovo('div', 'ricerca-salvata__azioni');
    const apri = nuovo('button', 'bottone bottone--primario bottone--piccolo', 'Apri');
    apri.addEventListener('click', () => applicaRicerca(ricerca));

    const rinomina = nuovo('button', 'bottone bottone--secondario bottone--piccolo', 'Modifica');
    rinomina.addEventListener('click', () => apriPannelloNome(ricerca));

    const elimina = nuovo('button', 'bottone bottone--secondario bottone--piccolo', 'Elimina');
    elimina.addEventListener('click', () => {
      stato.ricerche = stato.ricerche.filter((r) => r.id !== ricerca.id);
      if (stato.ricercaAttiva === ricerca.id) stato.ricercaAttiva = null;
      salvaRicerche();
      disegnaRicerche();
      mostraMessaggio('Ricerca eliminata');
    });

    azioni.append(apri, rinomina, elimina);
    riquadro.appendChild(azioni);
    contenitore.appendChild(riquadro);
  });

  contenitore.appendChild(riquadroSincronizzazione());
  elementi.lista.replaceChildren(contenitore);
}

// Le ricerche vivono sul telefono, ma il robot delle notifiche gira su GitHub:
// questo riquadro genera il testo da incollare una volta sola.
function riquadroSincronizzazione() {
  const riquadro = nuovo('div', 'riquadro');
  riquadro.appendChild(nuovo('h3', null, 'Sincronizza le notifiche'));
  riquadro.appendChild(nuovo('p', 'info-testo',
    'Le ricerche restano su questo telefono. Per far sapere al robot quali devono avvisarti, '
    + 'copia il testo qui sotto e incollalo nel file ricerche.json su GitHub (una volta sola, '
    + 'e ogni volta che cambi le notifiche).'));

  const contenuto = JSON.stringify({
    ricerche: stato.ricerche.filter((r) => r.notifiche)
      .map((r) => ({ nome: r.nome, notifiche: true, filtri: r.filtri })),
  }, null, 1);

  const area = document.createElement('textarea');
  area.className = 'campo-testo campo-testo--codice';
  area.readOnly = true;
  area.rows = 7;
  area.value = contenuto;
  riquadro.appendChild(area);

  const azioni = nuovo('div', 'ricerca-salvata__azioni');
  const copia = nuovo('button', 'bottone bottone--primario bottone--piccolo', 'Copia');
  copia.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(contenuto);
      mostraMessaggio('Copiato negli appunti');
    } catch (errore) {
      area.select();
      mostraMessaggio('Seleziona e copia a mano');
    }
  });
  azioni.appendChild(copia);

  const repo = stato.dati.github && stato.dati.github.repo;
  if (repo) {
    const link = document.createElement('a');
    link.className = 'bottone bottone--secondario bottone--piccolo';
    link.href = `https://github.com/${repo}/edit/main/docs/data/ricerche.json`;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = 'Apri il file su GitHub';
    azioni.appendChild(link);
  }
  riquadro.appendChild(azioni);
  return riquadro;
}

function disegnaInfo() {
  elementi.riepilogo.hidden = true;
  elementi.statoVuoto.hidden = true;
  const d = stato.dati;
  const contenitore = nuovo('div');

  const comeFunziona = nuovo('div', 'riquadro');
  comeFunziona.appendChild(nuovo('h3', null, 'Come funziona'));
  const testo = nuovo('div', 'info-testo');
  [
    ['Da dove arrivano i dati', 'Dalla pagina ufficiale degli interpelli dell’Ufficio Scolastico del Piemonte (ambito di Torino), riletta automaticamente più volte al giorno.'],
    ['Cosa vedi', `Solo le ${Object.keys(d.classi).length} classi di concorso che ti interessano: ${Object.keys(d.classi).join(', ')}.`],
    ['I minuti', `Percorso con i mezzi pubblici da ${d.casa.etichetta}, calcolato per arrivare a scuola entro le ${d.casa.ora_arrivo} di un giorno feriale.`],
    ['I chilometri', 'Sono i km di strada (percorso in auto), non la distanza in linea d’aria.'],
    ['Le sedi', 'Il segnaposto e i minuti si riferiscono alla sede centrale: nel dettaglio trovi tutte le altre sedi dell’istituto con i rispettivi tempi.'],
  ].forEach(([titolo, corpo]) => {
    const p = nuovo('p');
    p.append(nuovo('strong', null, titolo + ': '), document.createTextNode(corpo));
    testo.appendChild(p);
  });
  comeFunziona.appendChild(testo);
  contenitore.appendChild(comeFunziona);

  // Il segnaposto di casa: impostato qui, salvato solo qui.
  const casa = nuovo('div', 'riquadro');
  casa.appendChild(nuovo('h3', null, 'Il tuo segnaposto 🏠'));
  const attuale = stato.casa;
  casa.appendChild(nuovo('p', 'info-testo', attuale
    ? (attuale.indirizzo || `Punto scelto sulla mappa (${attuale.lat.toFixed(4)}, ${attuale.lng.toFixed(4)})`)
    : 'Non ancora impostato: sulla mappa non c’è il segnaposto di casa.'));
  casa.appendChild(nuovo('p', 'viaggio__dettagli',
    'Resta su questo dispositivo e non viene inviato a nessuno. I minuti di viaggio '
    + 'non dipendono da questa impostazione: sono già calcolati.'));
  const cambia = nuovo('button', 'bottone bottone--secondario', attuale ? 'Cambia posizione' : 'Imposta ora');
  cambia.style.width = '100%';
  cambia.style.marginTop = '10px';
  cambia.addEventListener('click', apriPannelloCasa);
  casa.appendChild(cambia);
  contenitore.appendChild(casa);

  const legenda = nuovo('div', 'riquadro');
  legenda.appendChild(nuovo('h3', null, 'Colori'));
  const elencoLegenda = nuovo('div', 'legenda');
  [['var(--verde)', 'fino a 30 minuti da casa'],
   ['var(--ambra)', 'da 31 a 45 minuti'],
   ['var(--rosso)', 'oltre 45 minuti'],
   ['var(--bordo)', 'tempo non ancora calcolato'],
  ].forEach(([colore, descrizione]) => {
    const voce = nuovo('div', 'legenda__voce');
    const quadratino = nuovo('span', 'legenda__colore');
    quadratino.style.background = colore;
    voce.append(quadratino, nuovo('span', null, descrizione));
    elencoLegenda.appendChild(voce);
  });
  legenda.appendChild(elencoLegenda);
  contenitore.appendChild(legenda);

  const numeri = nuovo('div', 'riquadro');
  numeri.appendChild(nuovo('h3', null, 'Situazione'));
  [
    ['Interpelli in archivio', String(d.conteggi.totale)],
    ['Aperti in questo momento', String(d.conteggi.aperti)],
    ['Ultimo aggiornamento', new Date(d.aggiornato).toLocaleString('it-IT')],
    ['Dato del sito aggiornato al', d.aggiornato_sito ? dataBreve(d.aggiornato_sito) : '—'],
    ['Ricerche salvate', String(stato.ricerche.length)],
    ['Preferiti salvati', String(stato.preferiti.size)],
  ].forEach(([etichetta, valore]) => {
    const riga = nuovo('div', 'riga-dato');
    riga.append(nuovo('span', 'riga-dato__etichetta', etichetta), nuovo('span', 'riga-dato__valore', valore));
    numeri.appendChild(riga);
  });
  contenitore.appendChild(numeri);

  const nota = nuovo('p', 'info-testo');
  nota.style.fontSize = '12.5px';
  nota.textContent = 'App non ufficiale, a uso personale. Prima di candidarti verifica sempre l’avviso pubblicato dalla scuola: questa app può contenere errori o dati non aggiornati.';
  contenitore.appendChild(nota);

  elementi.lista.replaceChildren(contenitore);
}


/* ---------- 10. PREFERITI, "VISTI", AVVIO ---------- */

function cambiaPreferito(id) {
  if (stato.preferiti.has(id)) {
    stato.preferiti.delete(id);
    mostraMessaggio('Rimosso dai preferiti');
  } else {
    stato.preferiti.add(id);
    mostraMessaggio('Salvato nei preferiti ⭐');
  }
  scriviMemoria(CHIAVI.preferiti, [...stato.preferiti]);
  aggiornaNavigazione();
}

function segnaComeVisti() {
  if (!stato.dati) return;
  stato.dati.interpelli.filter((i) => i.stato === 'aperto').forEach((i) => stato.visti.add(i.id));
  scriviMemoria(CHIAVI.visti, [...stato.visti]);
}

function collegaEventi() {
  elementi.bottoneFiltri.addEventListener('click', apriFiltri);
  elementi.velo.addEventListener('click', chiudiPannelli);
  elementi.chiudiDettaglio.addEventListener('click', chiudiPannelli);
  elementi.annullaNome.addEventListener('click', chiudiPannelli);
  elementi.confermaNome.addEventListener('click', confermaPannelloNome);

  // Pannello "dove abiti"
  elementi.cercaIndirizzoCasa.addEventListener('click', cercaIndirizzoCasa);
  elementi.campoIndirizzoCasa.addEventListener('keydown', (evento) => {
    if (evento.key === 'Enter') { evento.preventDefault(); cercaIndirizzoCasa(); }
  });
  elementi.posizioneAttuale.addEventListener('click', usaPosizioneAttuale);
  elementi.scegliSullaMappa.addEventListener('click', iniziaSceltaSullaMappa);
  elementi.saltaCasa.addEventListener('click', chiudiPannelli);
  elementi.annullaSceltaMappa.addEventListener('click', fineSceltaSullaMappa);
  elementi.confermaCasa.addEventListener('click', () => {
    if (!stato.casaInAttesa) {
      return mostraEsitoCasa('Cerca prima l’indirizzo, o usa uno degli altri due modi.', 'errore');
    }
    salvaCasa(stato.casaInAttesa);
    chiudiPannelli();
    mostraMessaggio('Casa impostata 🏠');
  });

  elementi.campoNomeRicerca.addEventListener('keydown', (evento) => {
    if (evento.key === 'Enter') confermaPannelloNome();
  });

  elementi.applicaFiltri.addEventListener('click', () => {
    stato.filtri = stato.filtriInModifica;
    const uguale = stato.ricerche.find((r) => stessiFiltri(r.filtri, stato.filtri));
    stato.ricercaAttiva = uguale ? uguale.id : null;
    chiudiPannelli();
    disegnaTutto();
  });

  elementi.azzeraFiltri.addEventListener('click', () => {
    stato.filtriInModifica = JSON.parse(JSON.stringify(FILTRI_VUOTI));
    disegnaPannelloFiltri();
  });

  elementi.salvaRicerca.addEventListener('click', () => apriPannelloNome());

  elementi.bottoneAggiorna.addEventListener('click', async () => {
    elementi.bottoneAggiorna.classList.add('gira');
    await caricaDati({ forzaRete: true });
    elementi.bottoneAggiorna.classList.remove('gira');
    disegnaTutto();
    mostraMessaggio('Dati aggiornati');
  });

  elementi.campoRicerca.addEventListener('input', (evento) => {
    stato.ricerca = evento.target.value;
    elementi.pulisciRicerca.hidden = !stato.ricerca;
    disegnaTutto();
  });

  elementi.pulisciRicerca.addEventListener('click', () => {
    elementi.campoRicerca.value = '';
    stato.ricerca = '';
    elementi.pulisciRicerca.hidden = true;
    disegnaTutto();
  });

  elementi.interruttoreVista.querySelectorAll('button').forEach((bottone) => {
    bottone.addEventListener('click', () => {
      stato.modo = bottone.dataset.modo;
      elementi.interruttoreVista.querySelectorAll('button')
        .forEach((b) => b.classList.toggle('attiva', b === bottone));
      scriviMemoria(CHIAVI.ultimaVista, stato.modo);
      disegnaTutto();
    });
  });

  elementi.navBasso.querySelectorAll('.nav-basso__voce').forEach((voce) => {
    voce.addEventListener('click', () => {
      stato.vista = voce.dataset.vista;
      window.scrollTo({ top: 0 });
      disegnaTutto();
    });
  });

  document.addEventListener('keydown', (evento) => {
    if (evento.key === 'Escape') chiudiPannelli();
  });

  document.addEventListener('visibilitychange', async () => {
    if (document.visibilityState === 'visible' && stato.dati) {
      const passati = Date.now() - new Date(stato.dati.aggiornato).getTime();
      if (passati > 10 * 60 * 1000) {
        await caricaDati({ forzaRete: true });
        disegnaTutto();
      }
    }
  });
}

async function avvia() {
  stato.ricerche = caricaRicerche();
  stato.casa = leggiMemoria(CHIAVI.casa, null);
  stato.preferiti = new Set(leggiMemoria(CHIAVI.preferiti, []));
  stato.visti = new Set(leggiMemoria(CHIAVI.visti, []));
  stato.modo = leggiMemoria(CHIAVI.ultimaVista, 'elenco');

  // All'apertura applichiamo la prima ricerca salvata.
  const prima = stato.ricerche[0];
  stato.filtri = prima ? JSON.parse(JSON.stringify(prima.filtri)) : { ...FILTRI_DI_FABBRICA };
  stato.ricercaAttiva = prima ? prima.id : null;

  elementi.interruttoreVista.querySelectorAll('button')
    .forEach((b) => b.classList.toggle('attiva', b.dataset.modo === stato.modo));

  collegaEventi();

  if (!await caricaDati()) return;

  disegnaTutto();
  setTimeout(segnaComeVisti, 4000);   // lasciamo il tempo di vedere le etichette "nuovo"

  // Primo avvio: chiediamo dove abiti, una volta sola. Se rispondi "non adesso"
  // non te lo richiediamo piu': lo trovi comunque in Info.
  if (!stato.casa && !leggiMemoria(CHIAVI.casaChiesta, false)) {
    setTimeout(apriPannelloCasa, 900);
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js').catch(() => { /* pazienza */ });
  }
}

avvia();
