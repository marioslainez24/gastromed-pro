"""Hojas de preparación y de consentimiento por tipo de estudio (v0.13.0).

Los textos los escribe y aprueba el médico (Endoscopia → Hojas de preparación y consentimiento). Se ofrece un BORRADOR inicial sin
productos, dosis, horarios ni riesgos específicos (los pone el médico); no se puede imprimir hasta que el médico lo revise y guarde.
Los datos entre llaves se llenan con los del paciente y la cita.
"""
import json

PLACEHOLDERS = {
    "{paciente}": "Nombre completo del paciente", "{identidad}": "Número de identidad", "{expediente}": "Número de expediente",
    "{edad}": "Edad", "{procedimiento}": "Nombre del estudio", "{fecha_cita}": "Fecha de la cita", "{hora_cita}": "Hora de la cita",
    "{medico}": "Su nombre profesional", "{direccion}": "Dirección del consultorio", "{telefono}": "Teléfonos del consultorio",
    "{fecha_hoy}": "Fecha de hoy",
}

DRAFT_PREP = """Paciente: {paciente}
Estudio: {procedimiento}
Fecha de su cita: {fecha_cita} a las {hora_cita}
Lugar: {direccion}

PREPARACIÓN
[Escriba aquí la dieta, el producto de preparación, los horarios y el ayuno que usted indica para este estudio.]

MEDICAMENTOS
[Escriba aquí qué hacer con anticoagulantes, antiagregantes, insulina, hierro u otros medicamentos.]

EL DÍA DEL ESTUDIO
Traiga su identidad, sus estudios previos y la lista de medicamentos que toma.
[Escriba aquí si debe venir acompañado y cualquier otra indicación.]

Si tiene dudas, llámenos: {telefono}"""

DRAFT_CONSENT = """Yo, {paciente}, con identidad {identidad}, expediente {expediente}, declaro que {medico} me explicó en palabras que entiendo:

• En qué consiste el estudio ({procedimiento}) y para qué se realiza.
• Los beneficios esperados y las alternativas disponibles.
• Los riesgos y posibles complicaciones, incluidos los de la sedación: [escriba aquí los riesgos que usted explica para este estudio].
• Que durante el estudio puede ser necesario tomar biopsias o realizar tratamientos.

Tuve la oportunidad de hacer preguntas y fueron respondidas. Sé que puedo retirar este consentimiento antes del procedimiento.

Autorizo la realización del estudio.

Firma del paciente o representante: ______________________________   Fecha: {fecha_hoy}

Nombre del representante (si aplica): ______________________________   Parentesco: ______________

Firma y sello del médico: ______________________________

Testigo: ______________________________"""


def load(settings_json):
    try:
        return json.loads(settings_json) if settings_json else {}
    except ValueError:
        return {}


def text_for(sheets, kind, doc):
    """(texto, aprobado). Si el médico no lo ha guardado, devuelve el borrador y aprobado=False."""
    t = (sheets.get(kind) or {}).get(doc)
    if t:
        return t, True
    return (DRAFT_PREP if doc == "prep" else DRAFT_CONSENT), False


def fill(text, values):
    for k, v in values.items():
        text = text.replace(k, v or "__________")
    return text
