"""Catálogo de estudios para las solicitudes de imagen y de neurofisiología (NeuroMed Pro 1.0).

Igual que en GastroMed Pro: marcar los estudios con un clic en vez de escribirlos. Son solo NOMBRES de estudios de uso habitual en
neurología (sin indicaciones, dosis ni precios). Lo que no esté se escribe en «Otros».
"""

IMAGING = [
    ("Tomografía (TAC)", [
        "TAC de cráneo simple", "TAC de cráneo con contraste", "Angio-TAC cerebral y de vasos del cuello", "TAC de perfusión cerebral",
        "TAC de columna cervical", "TAC de columna lumbar", "TAC de senos paranasales", "TAC de tórax"]),
    ("Resonancia magnética", [
        "Resonancia magnética de cerebro simple", "Resonancia magnética de cerebro simple y con gadolinio",
        "Resonancia magnética de cerebro con protocolo de epilepsia", "Resonancia magnética de cerebro con difusión (protocolo de ACV)",
        "Angio-resonancia cerebral", "Angio-resonancia de vasos del cuello", "Venorresonancia cerebral",
        "Resonancia magnética de columna cervical", "Resonancia magnética de columna dorsal", "Resonancia magnética de columna lumbosacra",
        "Resonancia magnética de órbitas", "Resonancia magnética de silla turca (hipófisis)"]),
    ("Ultrasonido vascular", [
        "Doppler carotídeo y vertebral", "Doppler transcraneal", "Doppler transcraneal con burbujas (búsqueda de cortocircuito)"]),
    ("Corazón (estudio del ACV)", [
        "Electrocardiograma", "Holter de 24 horas", "Holter de 72 horas", "Ecocardiograma transtorácico", "Ecocardiograma transesofágico"]),
    ("Radiología simple y otros", [
        "Radiografía de columna cervical", "Radiografía de columna lumbar", "Radiografía de tórax PA", "Angiografía cerebral por sustracción digital",
        "PET-CT cerebral"]),
]

NEUROPHYS = [
    ("Electroencefalografía", [
        "Electroencefalograma (EEG) de rutina", "EEG con privación de sueño", "EEG de sueño", "Video-EEG prolongado",
        "EEG continuo en paciente hospitalizado"]),
    ("Nervio y músculo", [
        "Electromiografía (EMG) y neuroconducción de 4 extremidades", "EMG y neuroconducción de miembros superiores",
        "EMG y neuroconducción de miembros inferiores", "Neuroconducción de nervio facial (blink reflex)",
        "Estimulación nerviosa repetitiva", "EMG de fibra única"]),
    ("Potenciales evocados", [
        "Potenciales evocados visuales", "Potenciales evocados auditivos de tallo cerebral", "Potenciales evocados somatosensoriales"]),
    ("Sueño y otros", [
        "Polisomnografía", "Poligrafía respiratoria domiciliaria", "Prueba de latencias múltiples del sueño", "Punción lumbar diagnóstica",
        "Evaluación neuropsicológica"]),
]

# tipo de la pantalla → (tipo guardado en la base, título impreso, catálogo, ejemplo para «Otros»)
# En NeuroMed Pro el tipo guardado «endoscopia» se muestra como «Neurofisiología» (se conserva la clave de la base de datos).
KINDS = {
    "imagen": ("imagen", None, IMAGING, "Ej.: Resonancia de plexo braquial"),
    "endoscopia": ("endoscopia", "Neurofisiología", NEUROPHYS, "Ej.: EMG de músculos paraespinales"),
}


def lookup(kind):
    """{nombre del estudio: grupo} para validar lo marcado."""
    return {name: grp for grp, names in KINDS[kind][2] for name in names}
