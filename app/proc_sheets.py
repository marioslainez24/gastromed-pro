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


_HEAD = """Paciente: {paciente}
Estudio: {procedimiento}
Fecha de su cita: {fecha_cita} a las {hora_cita}
Lugar: {direccion}

"""

# v0.18.0: hoja del Dr. Lainez (transcrita de su documento de Word, sin cambios de contenido).
PREP_COLONOSCOPIA = _HEAD + """PREPARACIÓN PARA COLONOSCOPÍA

MEDICAMENTO
Fortrans en sobre.

INDICACIONES GENERALES
Debe comprar 4 sobres de Fortrans.

UN DÍA ANTES DEL EXAMEN
1. Puede desayunar y almorzar normalmente (evitar comidas pesadas o grasosas).
2. Después del almuerzo debe iniciar la preparación.
3. Disolver cada sobre de Fortrans en 1 litro de agua (total 4 litros).
4. Iniciar tomando la preparación poco a poco: tomar un vaso cada 20 a 30 minutos.
5. Durante la tarde debe tomar 3 litros de la preparación (3 sobres ya disueltos).
6. Después de iniciar el medicamento, comenzará con evacuaciones líquidas. Esto es normal y esperado.

DIETA ESE DÍA
Debe llevar dieta líquida durante todo el día después de iniciar la preparación.
Puede consumir:
• Sopas o caldos colados
• Jugos naturales colados
• Agua
• Gelatina sin color rojo
No debe consumir:
• Arroz
• Verduras
• Pan
• Tortillas
• Alimentos sólidos
Importante: no consumir nada de color rojo.

EL DÍA DEL EXAMEN
1. A las 5 de la mañana debe tomar el último litro de la preparación (el cuarto sobre).
2. Después de esto, debe permanecer en ayuno completo, sin comer ni beber nada.
3. Debe presentarse a la hora indicada para el procedimiento.

INDICACIONES IMPORTANTES
• Si es diabético, debe suspender sus medicamentos el día previo al examen, según indicación médica.
• No olvidar llevar su orden médica el día del estudio.

En caso de dudas comunicarse al: {telefono}"""

# v0.18.0: PROPUESTA en el mismo formato de la hoja de colonoscopía, para que el médico la revise y apruebe. Solo ayuno y medidas
# generales; sin productos ni dosis.
PREP_EDA = _HEAD + """PREPARACIÓN PARA ENDOSCOPÍA DIGESTIVA ALTA

INDICACIONES GENERALES
No necesita comprar ningún medicamento para la preparación.

UN DÍA ANTES DEL EXAMEN
1. Puede comer normalmente durante el día (evitar comidas pesadas o grasosas).
2. La cena debe ser ligera. Después de la cena no debe comer nada más.

EL DÍA DEL EXAMEN
1. Debe venir en ayuno completo de al menos 8 horas: sin comer ni beber nada (tampoco agua, café, chicle ni caramelos).
2. Debe presentarse a la hora indicada para el procedimiento.
3. Debe venir acompañado por un adulto: por la sedación no podrá manejar ni regresar solo a su casa.

INDICACIONES IMPORTANTES
• Si es diabético, no debe tomar ni aplicarse sus medicamentos para el azúcar la mañana del examen, según indicación médica.
• Si toma medicamentos para «adelgazar la sangre» (anticoagulantes o antiagregantes), avise antes del estudio para indicarle qué hacer.
• Si usa prótesis dental removible, tráigala; se la retirará antes del estudio.
• Traiga sus endoscopías o biopsias anteriores y la lista de medicamentos que toma.
• No olvidar llevar su orden médica el día del estudio.

En caso de dudas comunicarse al: {telefono}"""

PREP_BY_KIND = {"colonoscopia": PREP_COLONOSCOPIA, "eda": PREP_EDA}
# Aviso que ve el médico en el editor mientras la hoja no está aprobada
DRAFT_NOTE = {"colonoscopia": "Texto tomado de su hoja de Word. Revíselo y pulse «Guardar y aprobar».",
              "eda": "Propuesta escrita con el mismo formato de su hoja de colonoscopía: ayuno y medidas generales. Revísela, "
                     "ajústela a su práctica y pulse «Guardar y aprobar»."}


def draft_for(kind, doc):
    if doc == "prep":
        return PREP_BY_KIND.get(kind, DRAFT_PREP)
    return DRAFT_CONSENT


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
    return draft_for(kind, doc), False


def fill(text, values):
    for k, v in values.items():
        text = text.replace(k, v or "__________")
    return text
