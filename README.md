# modellazione-3D
description: Sviluppare e dettagliare modelli BIM esistenti in Archicad 30 tramite
  il collegamento Python/JSON e Tapir già configurato. Utilizzare per
  integrare strutture, capriate, coperture, tegole, sottostrutture,
  facciate, serramenti, modanature, stratigrafie, materiali e texture,
  partendo dal modello aperto e dalle fonti disponibili nel repository,
  nei DWG, nei disegni, nelle fotografie e nella documentazione tecnica.
  Mantenere elementi modificabili, identificazione coerente,
  classificazioni, tracciabilità delle fonti e verifiche per esportazione IFC.
------
-----
# Modellazione BIM in Archicad 30

## Stato operativo già raggiunto

Il collegamento dell'agente ad Archicad tramite Tapir è già stato eseguito.
Archicad 30 è aperto e Tapir è installato.

Esiste un repository GitHub contenente informazioni e risorse utilizzate
dall'agente. Sono già state formulate prime considerazioni sul modello.

Riprendere dal lavoro documentato, senza ricominciare la configurazione.
Verificare soltanto che connessione e progetto destinatario siano ancora
quelli corretti prima di effettuare operazioni.

Non considerare una prova di collegamento come verifica di tutte
le funzionalità necessarie.

## Continuità con il repository

Prima di intervenire, leggere le istruzioni del repository, la documentazione
del progetto, lo stato delle attività e gli script pertinenti.

Distinguere nel repository:
- istruzioni operative;
- documentazione delle API;
- dati specifici dell'edificio;
- esempi e prove;
- ipotesi ancora da verificare.

Non trattare gli esempi come dati reali dell'edificio.
Non trattare il codice presente come automaticamente corretto o compatibile.

Riutilizzare funzioni e convenzioni già verificate.
Evitare script duplicati e documentazione contraddittoria.
Verificare la versione delle API rispetto all'ambiente installato.

## Ripresa delle considerazioni precedenti

Recuperare le osservazioni già formulate sul modello.
Per ciascuna distinguere:
dato letto nel modello, dato documentato, misura verificata,
deduzione, informazione mancante e anomalia da verificare.

Confermare attraverso nuove letture soltanto le informazioni necessarie
all'intervento corrente o che possono essere cambiate.

## Modalità di lavoro

Procedere per ambiti circoscritti e verificabili.

Prima di ogni lotto:
1. Identificare progetto ed elementi interessati.
2. Leggere le fonti pertinenti.
3. Verificare unità, coordinate e quote.
4. Individuare materiali, classificazioni e proprietà disponibili.
5. Preparare il piano delle modifiche.
6. Verificare la disponibilità di una copia o checkpoint recuperabile.

Eseguire prima una simulazione senza modifiche.
Applicare il lotto sulla copia di lavoro.
Rileggere gli elementi generati e confrontarli con le fonti.

Non estendere una procedura ripetitiva prima di avere verificato il campione.
Non ripetere una creazione dopo un errore senza controllare se sia già avvenuta.

## Identificazione degli elementi

Leggere e rispettare la convenzione degli ID già presente nel progetto.
Non rinumerare gli elementi esistenti indiscriminatamente.

Mantenere separati:
ID leggibile, GUID Archicad, GlobalId IFC, codice di tipo,
descrizione e classificazione.

Registrare la corrispondenza tra identificatore logico dello script
ed elemento Archicad per evitare duplicazioni nelle esecuzioni successive.

## Attendibilità della ricostruzione

Non attribuire a fotografie o immagini informazioni che non dimostrano.

Distinguere attendibilità della geometria, del materiale e della funzione.
Non inventare stratigrafie nascoste, sezioni strutturali, ferramenta,
ancoraggi o prestazioni.

Registrare fonte e stato di verifica delle informazioni utilizzate.
Presentare le ipotesi come ipotesi.

## Esito di ciascuna attività

Riportare elementi letti, creati, modificati ed esclusi.
Indicare controlli eseguiti, errori, ipotesi e informazioni mancanti.

Non dichiarare il risultato verificato soltanto perché il comando API
è terminato senza errori.
----
## Valutare le fonti

Registrare per ogni fonte nome del file o URL, data, revisione,
ambito di applicazione e limitazioni.

Distinguere sempre:
- DOCUMENTATO: informazione esplicitamente presente nei documenti;
- RILEVATO: informazione ricavata da misure verificate;
- DEDOTTO: ricostruzione motivata da evidenze indirette;
- MANCANTE: informazione non disponibile;
- DA_VERIFICARE: informazione incerta o contraddittoria.

Valutare separatamente geometria, materiale e funzione dello stesso elemento.

Non ricavare da fotografie stratigrafie nascoste, resistenze,
ancoraggi o prestazioni non dimostrate.

Utilizzare dettagli trovati sul web come riferimenti tipologici,
senza considerarli automaticamente corrispondenti all'edificio.

## Interpretare fotografie, disegni e DWG

Per i DWG verificare unità, origine, rotazione, riferimenti esterni,
layer e natura bidimensionale o tridimensionale del contenuto.

Controllare la scala mediante quote o misure indipendenti.
Non assumere che una unità del disegno equivalga a un metro o a un millimetro.

Per fotografie e immagini distinguere quote leggibili, misure ricavabili
e semplici stime. Non misurare prospettive non calibrate come se fossero
prospetti ortogonali.

Registrare la trasformazione tra coordinate delle fonti e coordinate
del modello: unità, rotazione e traslazione.

Confrontare piante, sezioni, prospetti e fotografie.
Segnalare le incongruenze prima di utilizzarle per modellare.

## Definire il dettaglio necessario

Stabilire per ciascuna categoria:
finalità, geometria necessaria, informazioni richieste, tolleranze,
fonti disponibili e verifiche di accettazione.

Distinguere le esigenze di rappresentazione, coordinamento,
computazione, costruzione e gestione.

Non generare dettagli privi di utilità rispetto alla consegna.
Non dichiarare esecutivo un dettaglio ricostruito senza dati sufficienti.

## Gestire ID e descrizioni

Rispettare la convenzione già utilizzata nel modello.

Mantenere distinti:
- ID elemento leggibile;
- GUID interno Archicad;
- GlobalId IFC;
- codice di tipo;
- descrizione;
- classificazione;
- codice dell'insieme di appartenenza.

Non scrivere GUID artificiali nel campo ID elemento.
Non utilizzare la descrizione come sostituto della classificazione.

Se manca una convenzione, proporne una prima di applicarla.
Esempio interno, da adattare al progetto:
PROGETTO-CORPO-DISCIPLINA-CATEGORIA-PROGRESSIVO.

Mantenere stabile l'ID durante gli aggiornamenti.
Conservare piano, materiale, dimensioni e stato in proprietà dedicate.

Per elementi ripetuti distinguere tipo e singola istanza.
Per una capriata associare i componenti a un codice comune di appartenenza.

Registrare la corrispondenza tra identificatore logico dello script,
ID leggibile, GUID Archicad e GlobalId IFC quando disponibile.

## Gestire proprietà e classificazioni

Riutilizzare proprietà e classificazioni esistenti quando adeguate.

Prima di creare nuove proprietà definirne:
nome, tipo di dato, unità, disponibilità e finalità.

Registrare, quando pertinenti:
descrizione, codice di tipo, insieme di appartenenza, fase,
fonte geometrica, fonte materiale, stato della verifica e revisione.

Non presentare proprietà personalizzate come proprietà IFC standard.
Verificarne la mappatura quando devono essere esportate.

Non assegnare funzione portante, classe resistente o prestazioni certificate
senza documentazione pertinente.

## Scegliere gli strumenti di modellazione

Privilegiare elementi nativi modificabili:
muri, solai, travi, pilastri, falde, shell e aperture,
quando appropriati alla geometria e alla funzione.

Usare profili complessi e oggetti parametrici per componenti ricorrenti.

Usare Morph o geometrie generiche quando necessario,
documentandone i limiti per modifica, quantità e scambio IFC.

Evitare duplicazioni tra modello esistente e dettagli aggiunti.
Verificare tagli, raccordi, connessioni e operazioni tra solidi.

## Modellare capriate e strutture

Ricostruire prima assi, appoggi, luci, quote e schema geometrico.

Distinguere, quando presenti:
catena, puntoni, monaco, saette, arcarecci, travetti e controventi.

Modellare componenti separati quando necessario per identificazione,
materiali, quantità e scambio informativo.

Verificare sezioni, orientamento, estremità, eccentricità e interferenze.

Non inventare incastri, ferramenta, ancoraggi o sezioni resistenti.
Registrare come ipotesi ciò che non è documentato.

Distinguere la ricostruzione geometrica dalla progettazione
e dalla verifica strutturale.

## Modellare coperture e tegole

Definire falde, pendenze, gronde, colmi, displuvi, compluvi,
spessori, aperture e raccordi.

Distinguere struttura, pacchetto di copertura e manto
quando richiesto dalla finalità del modello.

Rappresentare le tegole mediante superficie, moduli ripetuti
o singoli componenti in funzione del dettaglio necessario.

Controllare passo, sovrapposizione, orientamento, bordi e pezzi speciali.

Non duplicare volumi e quantità già rappresentati nella copertura.
Controllare l'impatto delle ripetizioni sulle prestazioni del modello.

## Modellare facciate e particolari

Ricostruire aperture, imbotti, davanzali, cornici, marcapiani,
cornicioni, modanature, portali, parapetti e cancellate
in base alle fonti disponibili.

Creare e verificare un campione prima di ripetere un dettaglio.

Non assumere che elementi apparentemente simili siano identici.
Distinguere tipi, varianti e irregolarità rilevate.

Non ricavare profondità e fissaggi nascosti da una sola fotografia
senza registrarli come ipotesi.

## Gestire materiali, stratigrafie e texture

Distinguere materiale da costruzione, struttura composta,
profilo complesso, superficie e texture.

Non utilizzare l'aspetto di una texture come prova del materiale reale.
Non attribuire proprietà fisiche per semplice somiglianza visiva.

Per ogni stratigrafia documentare ordine, spessore e orientamento
degli strati, nucleo e finiture.

Confrontare lo spessore complessivo con le misure disponibili.
Non usare priorità di intersezione arbitrarie per nascondere errori.

Mantenere esplicitamente non determinati i materiali sconosciuti.

Per le texture controllare scala, orientamento, provenienza,
condizioni d'uso e disponibilità dei file collegati.

## Eseguire gli script in modo controllabile

Separare lettura, interpretazione delle fonti, piano di modifica,
esecuzione e verifica.

Prevedere una modalità dry-run che elenchi le operazioni
senza modificare il modello.

Evitare duplicati mediante identificatori persistenti.
Una seconda esecuzione sugli stessi dati non deve creare nuove copie.

Ritrovare gli elementi mediante la corrispondenza registrata con i GUID.
Non identificarli soltanto dalla posizione o dalla descrizione.

Registrare input, unità, trasformazioni, versione dello script,
comandi eseguiti, risultati ed errori.

Controllare il risultato di ciascun elemento nelle operazioni collettive.

Dopo errori o timeout rileggere lo stato del modello
prima di ripetere una creazione.

Non presumere che una sequenza di comandi sia una transazione atomica.
Procedere per lotti limitati e verificabili.

## Verificare il risultato

Confrontare il modello con le fonti mediante piante, sezioni,
prospetti e viste tridimensionali pertinenti.

Controllare:
posizione, quote, dimensioni, orientamento, continuità,
interferenze, duplicazioni, parti mancanti e piani di appartenenza.

Verificare ID, classificazioni, proprietà, materiali,
stratigrafie, superfici, quantità e dipendenze di libreria.

Usare tolleranze definite per il progetto.

Distinguere errori certi, anomalie da verificare e scelte discrezionali.

## Preparare e verificare IFC

Leggere i requisiti di consegna e definire schema IFC,
contenuto richiesto e traduttore di esportazione.

Verificare struttura spaziale, coordinate, unità, classi IFC,
tipi, materiali, strati, proprietà, quantità e aperture.

Non assegnare classi IFC dal solo nome dell'elemento.
Controllare la mappatura effettiva del traduttore.

Verificare la continuità dei GlobalId tra revisioni.

Esportare un campione rappresentativo e controllarlo
con uno strumento indipendente rispetto alla sessione di modellazione.

Confrontare geometrie, elementi, identificatori, proprietà e materiali.

Non presumere che texture e superfici mantengano la stessa resa
in applicazioni diverse.

Automatizzare l'esportazione soltanto con una procedura verificata.
Se necessario, indicare i passaggi manuali ancora richiesti.

## Documentare l'esito

Per ogni lotto riportare:
ambito, fonti, elementi creati o modificati, verifiche eseguite,
errori, ipotesi e informazioni mancanti.

Indicare espressamente le verifiche non eseguite.

Non presentare come accertati dettagli ricostruiti per analogia.
Non dichiarare completo il modello per la sola riuscita dello script.
-----
