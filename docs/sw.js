/* =========================================================================
   Service worker: il pezzo che rende la app installabile e utilizzabile
   anche senza connessione.

   Due strategie diverse:
     - la app in se' (pagina, stili, codice): prima la copia salvata, veloce;
     - i dati degli interpelli: prima la rete, cosi' vedi sempre le novita',
       e la copia salvata solo se sei offline.

   Se cambi i file della app, alza il numero di VERSIONE: il telefono
   scarichera' la nuova versione invece di riusare la vecchia.
   ========================================================================= */

const VERSIONE = 'interpelli-v8';
const CONTENITORE_APP = `${VERSIONE}-app`;
const CONTENITORE_DATI = `${VERSIONE}-dati`;

const FILE_DELLA_APP = [
  './',
  './index.html',
  './styles.css',
  './app.js',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
];

// Installazione: mettiamo da parte i file della app.
self.addEventListener('install', (evento) => {
  evento.waitUntil(
    caches.open(CONTENITORE_APP)
      // addAll fallisce tutto se un file solo non si scarica: li aggiungiamo
      // uno a uno cosi' un problema di rete non blocca l'installazione.
      .then((contenitore) => Promise.allSettled(
        FILE_DELLA_APP.map((file) => contenitore.add(file))
      ))
      .then(() => self.skipWaiting())
  );
});

// Attivazione: buttiamo via le versioni vecchie.
self.addEventListener('activate', (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((nomi) => Promise.all(
        nomi.filter((nome) => !nome.startsWith(VERSIONE)).map((nome) => caches.delete(nome))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (evento) => {
  const richiesta = evento.request;
  if (richiesta.method !== 'GET') return;

  const indirizzo = new URL(richiesta.url);

  // I dati: prima la rete (sempre aggiornati), poi la copia salvata.
  if (indirizzo.pathname.endsWith('/data/interpelli.json')) {
    evento.respondWith(
      fetch(richiesta)
        .then((risposta) => {
          const copia = risposta.clone();
          caches.open(CONTENITORE_DATI).then((c) => c.put(richiesta, copia));
          return risposta;
        })
        .catch(() => caches.match(richiesta))
    );
    return;
  }

  // Tutto il resto: prima la copia salvata, e intanto la aggiorniamo.
  evento.respondWith(
    caches.match(richiesta).then((salvata) => {
      const dallaRete = fetch(richiesta)
        .then((risposta) => {
          if (risposta.ok) {
            const copia = risposta.clone();
            caches.open(CONTENITORE_APP).then((c) => c.put(richiesta, copia));
          }
          return risposta;
        })
        .catch(() => salvata);
      return salvata || dallaRete;
    })
  );
});
