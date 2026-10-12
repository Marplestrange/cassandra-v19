"""Patch d'appoint (jetable) : outils d'agent dans modeles.completer."""
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def sub(p, old, new):
    chemin = RACINE / p
    s = chemin.read_bytes().decode("utf-8")
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    assert old in s, (p, old[:70])
    s = s.replace(old, new, 1)
    chemin.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))


P = "modules/modeles/module.py"
sub(P, '''    def appel_ollama(cle_, modele, base, msgs, max_tokens, temperature, allow_reasoning, timeout, reflexion):
        """L'API NATIVE : la seule qui accepte `think` (couper la réflexion) et `num_ctx` (la fenêtre)."""''', '''    def appels_de(brut_calls):
        """Les appels d'outils d'un message, normalisés : [{id, nom, arguments (dict)}]. Des arguments illisibles sont rendus tels quels sous `_brut` : le modèle se corrige au tour suivant."""
        out = []
        for i, tc in enumerate(brut_calls or []):
            f = (tc or {}).get("function") or {}
            a = f.get("arguments")
            if isinstance(a, str):
                try:
                    a = json.loads(a) if a.strip() else {}
                except ValueError:
                    a = {"_brut": a[:2000]}
            out.append({"id": str((tc or {}).get("id") or "call_%d" % i), "nom": str(f.get("name") or ""), "arguments": a if isinstance(a, dict) else {"_brut": str(a)[:2000]}})
        return out

    def outils_openai(outils):
        return [{"type": "function", "function": {"name": t["nom"], "description": str(t.get("description") or "")[:1000], "parameters": t.get("parametres") or {"type": "object", "properties": {}}}} for t in outils]

    def messages_ollama(msgs):
        """Le format OpenAI vers le natif d'Ollama : arguments en objet, résultat d'outil avec le nom de l'outil."""
        noms, out = {}, []
        for m in msgs:
            m = dict(m)
            m["content"] = m.get("content") or ""
            if m.get("tool_calls"):
                tcs = []
                for tc in m["tool_calls"]:
                    f = dict(tc.get("function") or {})
                    noms[str(tc.get("id"))] = f.get("name", "")
                    if isinstance(f.get("arguments"), str):
                        try:
                            f["arguments"] = json.loads(f["arguments"] or "{}")
                        except ValueError:
                            f["arguments"] = {}
                    tcs.append({"function": f})
                m["tool_calls"] = tcs
            if m.get("role") == "tool":
                m["tool_name"] = noms.get(str(m.pop("tool_call_id", "")), m.get("name", ""))
            out.append(m)
        return out

    def appel_ollama(cle_, modele, base, msgs, max_tokens, temperature, allow_reasoning, timeout, reflexion, outils=None):
        """L'API NATIVE : la seule qui accepte `think` (couper la réflexion) et `num_ctx` (la fenêtre)."""''')
sub(P, '''        corps = {"model": modele, "messages": msgs, "stream": False, "options": opts, "keep_alive": "10m", "think": bool(reflexion)}''', '''        corps = {"model": modele, "messages": messages_ollama(msgs), "stream": False, "options": opts, "keep_alive": "10m", "think": bool(reflexion)}
        if outils:
            corps["tools"] = outils_openai(outils)''')
sub(P, '''        m = j.get("message") or {}
        txt = (m.get("content") or "").strip()
        fin = str(j.get("done_reason") or "")
        avert = ""
        if fin == "length":
            avert = "réponse TRONQUÉE par num_predict=%s (done_reason=length) — augmenter le budget" % max_tokens
        if not txt:''', '''        m = j.get("message") or {}
        txt = (m.get("content") or "").strip()
        fin = str(j.get("done_reason") or "")
        avert = ""
        appels = appels_de(m.get("tool_calls"))
        if fin == "length":
            avert = "réponse TRONQUÉE par num_predict=%s (done_reason=length) — augmenter le budget" % max_tokens
        if not txt and not appels:''')
sub(P, '''        return txt, avert, {"prompt_tokens": j.get("prompt_eval_count"), "completion_tokens": j.get("eval_count")}

    def appel_openai(cle, modele, base, msgs, max_tokens, temperature, allow_reasoning, timeout):''', '''        message = {"role": "assistant", "content": txt or None, "tool_calls": [{"id": a["id"], "type": "function", "function": {"name": a["nom"], "arguments": json.dumps(a["arguments"], ensure_ascii=False)}} for a in appels]} if appels else None
        return txt, avert, {"prompt_tokens": j.get("prompt_eval_count"), "completion_tokens": j.get("eval_count")}, appels, message

    def appel_openai(cle, modele, base, msgs, max_tokens, temperature, allow_reasoning, timeout, outils=None):''')
sub(P, '''        if temperature is not None:
            kw["temperature"] = float(temperature)
        rejoue, usage = False, {}''', '''        if temperature is not None:
            kw["temperature"] = float(temperature)
        if outils:
            kw["tools"] = outils_openai(outils)
        rejoue, usage = False, {}''')
sub(P, '''            if not txt and rc and not rejoue:''', '''            appels = appels_de(msg.get("tool_calls"))
            if not txt and not appels and rc and not rejoue:''')
sub(P, '''            if not txt:
                if rc and allow_reasoning:
                    txt = rc
                else:
                    avert = "contenu VIDE renvoyé par %s (finish_reason=%s) — modèle raisonneur qui a tout dépensé en réflexion ?" % (modele, fin)
            return txt, avert, usage''', '''            if not txt and not appels:
                if rc and allow_reasoning:
                    txt = rc
                else:
                    avert = "contenu VIDE renvoyé par %s (finish_reason=%s) — modèle raisonneur qui a tout dépensé en réflexion ?" % (modele, fin)
            message = {"role": "assistant", "content": txt or None, "tool_calls": msg.get("tool_calls")} if appels else None
            return txt, avert, usage, appels, message''')
sub(P, '''    def appeler(m, messages, systeme, max_tokens, temperature, allow_reasoning, timeout, reflexion, role=""):''', '''    def appeler(m, messages, systeme, max_tokens, temperature, allow_reasoning, timeout, reflexion, role="", outils=None):''')
sub(P, '''            if prov == "ollama" and all(isinstance(x.get("content"), str) for x in msgs):
                txt, avert, usage = appel_ollama(cle, nom, base, msgs, max_tokens, temperature, allow_reasoning, timeout, reflexion)
            else:
                txt, avert, usage = appel_openai(cle, nom, base, msgs, max_tokens, temperature, allow_reasoning, timeout)''', '''            if prov == "ollama" and all(isinstance(x.get("content") or "", str) for x in msgs):
                txt, avert, usage, appels, message = appel_ollama(cle, nom, base, msgs, max_tokens, temperature, allow_reasoning, timeout, reflexion, outils)
            else:
                txt, avert, usage, appels, message = appel_openai(cle, nom, base, msgs, max_tokens, temperature, allow_reasoning, timeout, outils)''')
sub(P, '''        ajouter_usage(role, m["id"], bool(txt), dt, usage)
        return {"ok": bool(txt), "texte": txt, "avertissement": avert, "erreur": "" if txt else (avert or "aucune réponse"), "secondes": dt, "modele": m["id"], "usage": {k: v for k, v in usage.items() if isinstance(v, int)}}''', '''        ajouter_usage(role, m["id"], bool(txt or appels), dt, usage)
        return {"ok": bool(txt or appels), "texte": txt, "appels": appels, "message": message, "avertissement": avert, "erreur": "" if (txt or appels) else (avert or "aucune réponse"), "secondes": dt, "modele": m["id"],
                "usage": {k: v for k, v in usage.items() if isinstance(v, int)}}''')
sub(P, '''    def completer(c, messages=None, systeme="", max_tokens=1400, temperature=None, role="", modele_id="", reflexion=False, timeout=75.0, allow_reasoning=True):''', '''    def completer(c, messages=None, systeme="", max_tokens=1400, temperature=None, role="", modele_id="", reflexion=False, timeout=75.0, allow_reasoning=True, outils=None):''')
sub(P, '''        return appeler(m, messages, systeme, mx, tp, bool(allow_reasoning), to, bool(reflexion), role)''', '''        if outils is not None and (not isinstance(outils, list) or len(outils) > 200 or not all(isinstance(t, dict) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(t.get("nom") or "")) for t in outils)):
            return {"ok": False, "erreur": "outils invalides (200 au plus, nom de 1 à 64 caractères [A-Za-z0-9_-])"}
        return appeler(m, messages, systeme, mx, tp, bool(allow_reasoning), to, bool(reflexion), role, outils or None)''')
sub("modules/modeles/manifeste.toml", 'masque = ["messages", "systeme", "texte"]', 'masque = ["messages", "systeme", "texte", "appels", "message"]')
print("ok")
