"""Antecedentes con clics que se arrastran a cada consulta (v0.16.0).

El médico marca los antecedentes con clics; se guardan en el expediente (tabla patient_history, como siempre: nada se borra) y
cada nota nueva los trae ya escritos en el campo «Antecedentes» (copia del momento, editable). Solo nombres de antecedentes
frecuentes en neurología; lo que no esté se escribe en «Otro».
"""

CHIPS = {
    "personal": ["Hipertensión arterial", "Diabetes mellitus tipo 2", "Dislipidemia", "Obesidad", "Fibrilación auricular",
                 "Cardiopatía isquémica", "Insuficiencia cardiaca", "Enfermedad renal crónica", "Hipotiroidismo", "Apnea del sueño",
                 "ACV isquémico previo", "Hemorragia cerebral previa", "Ataque isquémico transitorio", "Epilepsia", "Crisis febriles en la infancia",
                 "Migraña", "Traumatismo craneoencefálico", "Meningitis o encefalitis", "Neurocisticercosis", "Enfermedad de Parkinson",
                 "Deterioro cognitivo", "Esclerosis múltiple", "Neuropatía periférica", "Depresión o ansiedad", "VIH", "Cáncer"],
    "quirurgico": ["Craneotomía", "Derivación ventrículo-peritoneal", "Cirugía de columna cervical", "Cirugía de columna lumbar",
                   "Endarterectomía carotídea", "Embolización o clip de aneurisma", "Trombectomía mecánica", "Liberación de túnel del carpo",
                   "Cirugía cardiaca", "Cesárea", "Histerectomía"],
    "familiar": ["Epilepsia", "ACV antes de los 55 años", "Aneurisma cerebral", "Demencia", "Enfermedad de Parkinson", "Esclerosis múltiple",
                 "Migraña", "Enfermedad neuromuscular hereditaria", "Diabetes", "Hipertensión"],
    "procedimiento": ["TAC de cráneo previa", "Resonancia magnética cerebral previa", "Electroencefalograma previo",
                      "EMG y neuroconducción previa", "Punción lumbar previa", "Trombólisis previa"],
}
RELATIVES = ["padre", "madre", "hermano(a)", "hijo(a)", "abuelo(a)", "tío(a)"]

# Hábitos: una sola respuesta vigente por tipo (al marcar otra, la anterior queda como no vigente)
HABITS = {
    "Tabaco": ["Nunca ha fumado", "Exfumador", "Fumador actual"],
    "Alcohol": ["No consume", "Ocasional", "Semanal", "Diario", "Exbebedor"],
    "Drogas": ["No consume", "Marihuana", "Cocaína", "Otras"],
}

ORDER = ["personal", "quirurgico", "familiar", "habito", "hospitalizacion", "procedimiento"]
SHORT = {"personal": "Patológicos", "quirurgico": "Quirúrgicos", "familiar": "Familiares", "habito": "Hábitos",
         "hospitalizacion": "Hospitalizaciones", "procedimiento": "Procedimientos previos"}


def compose_text(db, patient):
    """Resumen de antecedentes, medicamentos y alergias del expediente, para la nota."""
    pid = patient["id"]
    rows = db.execute("SELECT category, description, when_text FROM patient_history WHERE patient_id = ? AND active = 1"
                      " ORDER BY recorded_at", (pid,)).fetchall()
    lines = []
    for cat in ORDER:
        items = [r["description"] + (f" ({r['when_text']})" if r["when_text"] else "") for r in rows if r["category"] == cat]
        if items:
            lines.append(f"{SHORT[cat]}: " + "; ".join(items) + ".")
    meds = [m["name"] + (f" {m['dose']}" if m["dose"] else "") + (f" {m['frequency']}" if m["frequency"] else "")
            for m in db.execute("SELECT name, dose, frequency FROM patient_medications WHERE patient_id = ? AND status = 'activo'"
                                " ORDER BY recorded_at", (pid,))]
    if meds:
        lines.append("Medicamentos actuales: " + "; ".join(meds) + ".")
    alg = [a["substance"] for a in db.execute("SELECT substance FROM patient_allergies WHERE patient_id = ? AND active = 1", (pid,))]
    if alg:
        lines.append("Alergias: " + ", ".join(alg) + ".")
    elif patient["allergy_status"] == "sin_alergias_conocidas":
        lines.append("Alergias: sin alergias conocidas.")
    return "\n".join(lines)


class Invalid(ValueError):
    pass


def build(form):
    """De lo marcado a (categoría, descripción, época). Valida contra las listas."""
    cat = form.get("category")
    when = (form.get("when_text") or "").strip()[:80] or None
    if cat == "habito":
        kind, value = form.get("habit"), form.get("value")
        if kind not in HABITS or value not in HABITS[kind]:
            raise Invalid("Elija el hábito y su respuesta.")
        detail = (form.get("detail") or "").strip()[:120]
        return cat, f"{kind}: {value.lower()}" + (f" ({detail})" if detail else ""), when
    if cat not in CHIPS:
        raise Invalid("Tipo de antecedente no válido.")
    item = (form.get("item") or "").strip()
    other = (form.get("other") or "").strip()[:200]
    if item == "__otro__":
        if not other:
            raise Invalid("Escriba el antecedente.")
        desc = other
    elif item in CHIPS[cat]:
        desc = item
        if item == "Cáncer" and other:
            desc = f"Cáncer: {other}"
    else:
        raise Invalid("Antecedente no válido.")
    if cat == "familiar":
        rel = [r for r in form.getlist("relative") if r in RELATIVES]
        if rel:
            desc += " en " + ", ".join(rel)
    return cat, desc, when
