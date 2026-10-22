#!/usr/bin/env python3
"""Pilota capriata PROVVISORIA (catena + 2 puntoni). Tutti i valori sono SEGNAPOSTO DA VERIFICARE.

Predefinito: SIMULAZIONE. Per scrivere: --applica --copia-confermata (file aperto = copia di lavoro).
Idempotente: se un ID del piano esiste gia' tra le travi, l'elemento viene mantenuto, non ricreato.
Solo localhost. Usa CreateBeams / GetDetailsOfElements (Tapir) e API.GetPropertyIds / SetPropertyValuesOfElements.
"""
import argparse
import json
import math
import sys
import urllib.request
from datetime import datetime

X1, X2, Y, Z = -27.333227921, -10.828160477, -66.154156113, 3.799124889  # catena: dalla trave BER-V07-CAT-001 (dedotto)
PENDENZA_DEG = 20.0  # dal Roof BER-BASE-COP-008 (livello 2, 0.349 rad): da verificare
CATENA = (0.15, 0.16)   # segnaposto
PUNTONE = (0.14, 0.16)  # segnaposto
PREFISSO = "BER-PIL-CAP-001-"


def piano():
    xm = (X1 + X2) / 2
    a = math.radians(PENDENZA_DEG)
    return [
        ("CAT", dict(begCoordinate={"x": X1, "y": Y}, endCoordinate={"x": X2, "y": Y}, zCoordinate=Z,
                     width=CATENA[0], height=CATENA[1])),
        ("PUN-W", dict(begCoordinate={"x": X1, "y": Y}, endCoordinate={"x": xm, "y": Y}, zCoordinate=Z,
                       slantAngle=a, width=PUNTONE[0], height=PUNTONE[1])),
        ("PUN-E", dict(begCoordinate={"x": X2, "y": Y}, endCoordinate={"x": xm, "y": Y}, zCoordinate=Z,
                       slantAngle=a, width=PUNTONE[0], height=PUNTONE[1])),
    ]


def post(port, body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    if not out.get("succeeded"):
        raise RuntimeError(f"Comando fallito: {out}")
    return out["result"]


def tapir(port, name, params=None):
    return post(port, {"command": "API.ExecuteAddOnCommand", "parameters": {
        "addOnCommandId": {"commandNamespace": "TapirCommand", "commandName": name},
        "addOnCommandParameters": params or {}}})["addOnCommandResponse"]


def trova_porta():
    for p in range(19723, 19744):
        try:
            post(p, {"command": "API.IsAlive"})
            return p
        except Exception:
            continue
    sys.exit("Archicad non raggiungibile.")


def chiave(d):
    b, e = d["begCoordinate"], d["endCoordinate"]
    return tuple(round(v, 3) for v in (b["x"], b["y"], e["x"], e["y"], d["zCoordinate"], d["width"], d["height"]))


def chiave_piano(dati):
    b, e = dati["begCoordinate"], dati["endCoordinate"]
    return tuple(round(v, 3) for v in (b["x"], b["y"], e["x"], e["y"], dati["zCoordinate"], dati["width"], dati["height"]))


def leggi_travi(port):
    el = post(port, {"command": "API.GetElementsByType", "parameters": {"elementType": "Beam"}})["elements"]
    out = []
    for i in range(0, len(el), 100):
        blocco = el[i:i + 100]
        for e, d in zip(blocco, tapir(port, "GetDetailsOfElements", {"elements": blocco})["detailsOfElements"]):
            out.append({"elementId": e["elementId"], "id": d.get("id", ""), "d": d["details"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--applica", action="store_true")
    ap.add_argument("--copia-confermata", action="store_true")
    ap.add_argument("--log", default="pilota_capriata_log.json")
    a = ap.parse_args()
    if a.applica and not a.copia_confermata:
        sys.exit("Rifiutato: --applica richiede --copia-confermata.")
    port = trova_porta()
    travi = leggi_travi(port)
    azioni = []
    for sigla, dati in piano():
        eid = PREFISSO + sigla
        k = chiave_piano(dati)
        con_id = [t for t in travi if t["id"] == eid]
        senza_id = [t for t in travi if t["id"] != eid and not t["id"].startswith(PREFISSO) and chiave(t["d"]) == k]
        if len(con_id) > 1 or len(senza_id) > 1:
            sys.exit(f"Duplicati per {eid}: {len(con_id)} con ID, {len(senza_id)} senza ID. Nessuna modifica.")
        if con_id:
            azioni.append({"id": eid, "azione": "mantieni", "dati": dati})
        elif senza_id:
            azioni.append({"id": eid, "azione": "assegna_id", "guid": senza_id[0]["elementId"], "dati": dati})
        else:
            azioni.append({"id": eid, "azione": "crea", "dati": dati})
    log = {"creato": datetime.now().isoformat(timespec="seconds"),
           "modalita": "APPLICA" if a.applica else "SIMULAZIONE", "stato_dati": "SEGNAPOSTO DA VERIFICARE",
           "azioni": [{k: v for k, v in x.items() if k != "guid"} for x in azioni], "esito": "non_scritto"}
    if a.applica:
        da_creare = [x for x in azioni if x["azione"] == "crea"]
        if da_creare:
            res = tapir(port, "CreateBeams", {"beamsData": [x["dati"] for x in da_creare]})["elements"]
            if any("error" in r for r in res):
                log["esito"] = "ERRORE in CreateBeams"
                log["risposta"] = res
                da_creare = []
            else:
                for r, x in zip(res, da_creare):
                    x["guid"] = r["elementId"]
        da_id = [x for x in azioni if x["azione"] in ("crea", "assegna_id") and "guid" in x]
        if da_id:
            pid = post(port, {"command": "API.GetPropertyIds", "parameters": {"properties": [
                {"type": "BuiltIn", "nonLocalizedName": "General_ElementID"}]}})["properties"][0]["propertyId"]
            vals = [{"elementId": x["guid"], "propertyId": pid,
                     "propertyValue": {"type": "string", "status": "normal", "value": x["id"]}} for x in da_id]
            try:
                post(port, {"command": "API.SetPropertyValuesOfElements",
                            "parameters": {"elementPropertyValues": vals}})
            except RuntimeError as err:
                log["esito"] = f"ERRORE assegnazione ID (travi create ma senza ID, rieseguire): {err}"
        if log["esito"] == "non_scritto":
            dopo = {t["id"] for t in leggi_travi(port)}
            mancanti = [x["id"] for x in azioni if x["id"] not in dopo]
            log["esito"] = "OK" if not mancanti else f"ERRORE: ID non letti dopo la scrittura: {mancanti}"
    with open(a.log, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    cont = {n: sum(x["azione"] == n for x in azioni) for n in ("crea", "assegna_id", "mantieni")}
    print(json.dumps({"modalita": log["modalita"], **cont, "esito": log["esito"]}, ensure_ascii=False))
    if log["esito"].startswith("ERRORE"):
        sys.exit(1)


if __name__ == "__main__":
    main()
