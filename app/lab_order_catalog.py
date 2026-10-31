"""Catálogo de la solicitud de análisis clínicos (v0.9.0).

Transcrito de la hoja de solicitud de laboratorio que usa el Dr. Lainez (fotografías del 31-oct-2026, hoja con
«Fecha de modificación: abril 2024»). Son solo los NOMBRES de las pruebas y su agrupación, para marcar casillas
como en el papel; no incluye precios, rangos ni datos del laboratorio.

`RESULT_CODE` enlaza algunas pruebas de un solo valor con el catálogo de resultados (tabla lab_tests) para que la orden
cambie sola a «resultado recibido». Las pruebas compuestas (hemograma, perfiles…) se cierran a mano.
"""
import re
import unicodedata

SECTIONS = [
    ("Hematología", [
        "Hemograma Completo", "Células Falciformes (Drepanocitos)", "Coombs Directo", "Coombs Indirecto", "Crioaglutininas",
        "Electroforesis de Hemoglobina", "Eritrosedimentación (VES)", "Frotis de Sangre Periférica (FSP)", "Grupo Sanguíneo y Rh",
        "Hematozoario (Plasmodium spp.)", "Reticulocitos", "Eosinófilos"]),
    ("Coagulación", [
        "Anticoagulante Lúpico", "Dímero-D", "Fibrinógeno", "Proteína C", "Proteína S", "Retracción del Coágulo",
        "Tiempo de Coagulación", "Tiempo de Protrombina (TP)", "Tiempo de Sangrado", "Tiempo de Tromboplastina Parcial (TPT)",
        "Antitrombina III"]),
    ("Química en sangre", [
        "Ácido Úrico", "Aldolasa", "Amilasa", "Amonio Sérico", "Bilirrubinas Totales y Fraccionadas", "Calcio",
        "Capacidad de Captación de Hierro", "Cloruro (Cl)", "CO2", "Colesterol HDL", "Colesterol LDL", "Colesterol Total",
        "Colinesterasa", "CPK (Creatin Fosfoquinasa)", "CPK-MB", "Creatinina", "Tolerancia Oral a la Glucosa 2 Horas",
        "Curva Tolerancia 2 h Glucosa Gestacional 75 g", "Curva Tolerancia 3 h Glucosa Gestacional 100 g",
        "Curva Tolerancia de Glucosa 2 Horas", "Curva Tolerancia de Glucosa 3 Horas", "Curva Tolerancia de Glucosa 4 Horas",
        "Curva Tolerancia de Glucosa 5 Horas", "Deshidrogenasa Láctica (LDH)", "Electroforesis de Proteínas", "Fosfatasa Alcalina",
        "Fósforo", "Gamma Glutamil Transpeptidasa (GGT)", "Glucosa en Ayunas", "Glucosa Post-Prandial",
        "Hemoglobina Glicosilada (HbA1c)", "Hierro Sérico", "Homocisteína", "Lipasa", "Litio", "Magnesio (Mg)",
        "Proteína C Reactiva (PCR)", "PCR Ultrasensible (PCR-us)", "Potasio (K)", "Proteínas Totales y Fraccionadas", "Sodio (Na)",
        "Sullivan 50 g (2 muestras)", "TGO (Aspartato)", "TGP (Alanino)", "Triglicéridos", "Troponina I", "Urea Nitrogenada (BUN)",
        "Investigación Hemoglobina S (HPLC)", "Osmolaridad Plasmática"]),
    ("Química en orina", [
        "17 Cetoesteroides Orina 24 Horas", "17 Hidroxiesteroides Orina 24 Horas", "Ácido Úrico / 24 Horas",
        "Ácido Vanilmandélico Orina 24 Horas", "Calcio / 24 Horas", "Creatinina / 24 Horas", "Índice Proteína-Creatinina en Orina",
        "Cociente Albúmina-Creatinina en Orina", "Depuración de Creatinina / 24 Horas", "Fósforo / 24 Horas", "Magnesio / 24 Horas",
        "Microalbuminuria", "Proteínas Totales / 24 Horas", "Tasa de Filtrado Glomerular", "Cortisol Libre en Orina / 24 Horas"]),
    ("Orina", ["Porfobilinógeno / Urobilinógeno", "General de Orina", "Prueba de Embarazo en Orina"]),
    ("Heces", [
        "Calprotectina Fecal", "Citología de Moco Fecal", "General de Heces", "Sangre Oculta en Heces", "Wright en Heces",
        "Helicobacter pylori en Heces (Cualitativo)", "Helicobacter pylori en Heces (Cuantitativo)", "Cripto-Giardia",
        "Rotavirus en Heces", "Clostridium difficile Toxina A+B", "Coloración de Cryptosporidium (Apicomplexa)",
        "Adenovirus en Heces", "Sudán III", "Sudán IV"]),
    ("Hormonas · reproductoras", [
        "17 OH-Progesterona", "BHCG (Gonadotropina Coriónica Humana, Fracción Beta)", "DHEA-S", "Estradiol",
        "Examen de Embarazo en Sangre", "FSH (Hormona Folículo Estimulante)", "LH (Hormona Luteinizante)", "Progesterona",
        "Prolactina (PRL)", "SHBG", "Testosterona", "Índice de Testosterona Libre", "Hormona Antimulleriana", "Androstenediona"]),
    ("Hormonas · tiroides", [
        "Anticuerpos Antitiroideos (Anti-TPO / Anti-TG)", "Ac. Antiperoxidasa (Anti-TPO)", "Ac. Antitiroglobulina (TG)", "T3 Libre",
        "T3 Triyodotironina Total", "T4 Libre / Tiroxina Libre", "T4 Tiroxina Total", "T4-Uptake", "Tiroglobulina",
        "TSH (Hormona Estimulante del Tiroides)"]),
    ("Hormonas · endocrinas y otras", [
        "ACTH", "Cortisol a.m.", "Cortisol p.m.", "Curva de Insulina", "Insulina", "Insulina Post-Prandial",
        "Hormona del Crecimiento", "IGF-1", "IGFBP3", "PTH (Paratohormona)"]),
    ("Drogas de abuso y fármacos", [
        "Anfetaminas", "Cocaína", "Etanol", "Marihuana", "Nicotina", "Set de 2 Drogas", "Set de 4 Drogas", "Set de 7 Drogas",
        "Set de 12 Drogas", "Ácido Valproico", "Carbamazepina", "Digoxina", "Fenitoína", "Fenobarbital"]),
    ("Inmunología", [
        "Ácido Fólico", "Anti CCP (Péptido Citrulinado)", "Células LE", "Complemento Sérico C3", "Complemento Sérico C4",
        "Factor Reumatoideo", "Ferritina", "Inmunoglobulina A", "Inmunoglobulina G", "Inmunoglobulina M", "Inmunoglobulina E",
        "Interleucina 6 (IL-6)", "NT Pro BNP", "Panel Alergia Alimentos", "Panel Alergia Inhalantes", "Procalcitonina",
        "Quantiferon TB-Gold", "Troponina T Ultrasensible", "Vitamina B12", "Vitamina D (25-OH)"]),
    ("Enfermedades autoinmunes", [
        "Anti Centrómero B", "Anti Gliadina IgA", "Anti Gliadina IgG", "Anti Jo-1", "Anti La / SSB", "Anti Músculo Liso",
        "Anti RNP / Sm", "Anti Ro / SSA", "Anti Scl-70", "Anticuerpos Anti DNA / IFI", "Anticuerpos Anti DNA / ELISA",
        "Anticuerpos ANCA P ELISA", "Anticuerpos ANCA C ELISA", "ANA 18 Max", "Panel Miositis",
        "Anticuerpos Antimitocondriales (AMA)", "Anticuerpos Anti Membrana Basal Glomerular IgG",
        "Anticuerpos Anti Neutrófilos Totales (ANCA) - IFI", "Anticuerpos Anti Neutrófilos Totales (ANCA) - ELISA",
        "Anticuerpos ANA 9 Line", "Anticuerpos ENA", "Anticuerpos Antifosfolípidos IgG", "Anticuerpos Antifosfolípidos IgM",
        "Anticuerpos Antinucleares (ANA) - IFI", "Anticuerpos Antinucleares (ANA) - ELISA", "Anticuerpos Antitransglutaminasa IgA",
        "Anticuerpos Antitransglutaminasa IgG", "Anticuerpos Anticardiolipinas IgG", "Anticuerpos Anticardiolipinas IgM",
        "Anti Beta 2 Glicoproteína I IgG", "Anti Beta 2 Glicoproteína I IgM"]),
    ("Enfermedades infecciosas", [
        "Adenovirus Respiratorio", "Anticuerpos VIH 1 y 2, P24", "Anticuerpos Chlamydia trachomatis IgG",
        "Anticuerpos Chlamydia trachomatis IgM", "Anticuerpos Cisticercosis IgG, IgM", "Anticuerpos contra el Antígeno de Superficie (HBs Ac)",
        "Ag. Cryptococcus neoformans", "Ag. Strepto A", "Antígeno de Superficie (Australia) HBs Ag", "Anticuerpos Dengue y Antígeno NS1",
        "Anticuerpos Estreptolisina «O» (ASO)", "Anticuerpos Helicobacter pylori Totales IgG, IgM, IgA", "Anticuerpos Hepatitis A IgG",
        "Anticuerpos Hepatitis A IgM", "Anticuerpos Hepatitis B Core Totales", "Anticuerpos Hepatitis B Core IgM",
        "Anticuerpos Hepatitis C", "Anticuerpos Mononucleosis (Monotest)", "Anticuerpos Rubéola IgG", "Anticuerpos Rubéola IgM",
        "Anticuerpos Zika IgG", "Anticuerpos Zika IgM", "Anticuerpos Chikungunya IgG", "Anticuerpos Chikungunya IgM",
        "Anticuerpos Toxoplasmosis IgG", "Anticuerpos Toxoplasmosis IgM", "Anticuerpo Treponema (Sífilis TP)",
        "Antígeno Influenza A y B", "Antígenos Febriles", "Citomegalovirus IgG, IgM", "Epstein Barr Virus IgG (Cápside)",
        "Epstein Barr Virus IgM (Cápside)", "Epstein Barr Virus Nuclear (EBNA)", "Linfocitos CD4", "Prueba de Tuberculina", "RPR",
        "VDRL", "Virus Sincitial Respiratorio"]),
    ("Marcadores tumorales", [
        "PSA Libre", "PSA Total", "AFP", "CEA", "Ca 19-9 (Páncreas, Vesícula)", "Ca 15-3 (Mama)", "Ca 125 (Ovario)",
        "HE4 (Proteína Epididimal Humana 4, Ovario)", "Algoritmo ROMA (Ovario)"]),
    ("COVID-19", [
        "Anticuerpo COVID-19 (Prueba Rápida)", "Antígeno SARS-CoV-2", "Panel Respiratorio + COVID-19", "PCR SARS-CoV-2",
        "Xpert SARS-CoV-2/FLU/RSV (PCR)", "Ag. COVID-19 + Influenza A y B", "LIAT SARS-CoV-2/FLU (PCR)"]),
    ("Microbiología · líquidos (incluye Gram, Wright, citoquímica y cultivo)", [
        "Líquido Articular (Sinovial)", "Líquido Cefalorraquídeo (LCR)", "Líquido Peritoneal (Ascítico)", "Líquido Pleural"]),
    ("Microbiología · tinciones", [
        "KOH", "Giemsa", "Tinta China", "Coloración de Gram", "Coloración de Wright", "Coloración de Ziehl-Neelsen",
        "Examen en Fresco Solución Salina", "Citología de Moco Nasal", "Leishmaniasis"]),
    ("Microbiología · cultivos", [
        "Cultivo Bacteriológico", "Urocultivo", "Coprocultivo", "Espermocultivo (Líquido Seminal)", "Exudado Faríngeo",
        "Cribado Streptococcus agalactiae (Betahemolítico)", "Cultivo de Expectoración", "Cultivo por Hongos",
        "Cultivo Neisseria gonorrhoeae", "Cultivo por Micobacterias", "Espermograma"]),
    ("Biología molecular", [
        "Prueba de Paternidad", "BRCA 1 y 2", "PCR HIV", "Carga Viral VIH", "Carga Viral Hepatitis B", "Carga Viral Hepatitis C",
        "Carga Viral Citomegalovirus", "PCR para Citomegalovirus", "PCR para Epstein Barr", "PCR para Herpes I y II",
        "PCR para Toxoplasma", "Panel de Meningitis/Encefalitis", "PCR para Varicela Zóster", "Panel Dengue-Zika-Chikungunya",
        "PCR para Complejo Mycobacterium tuberculosis", "PCR para Mycobacterium tuberculosis Resistente a RIF",
        "PCR Virus Papiloma Humano (VPH) 14 Genotipos", "PCR Virus Papiloma Humano (VPH) 24 Genotipos",
        "PCR para Chlamydia trachomatis / Neisseria gonorrhoeae", "Panel Neumonía", "Panel ITS (Enfermedades de Transmisión Sexual)",
        "Xpert Carba R"]),
]

# Perfiles: cada componente es el nombre exacto de una prueba del catálogo; si no está en el catálogo, se imprime como texto.
PROFILES = [
    ("Pre-operatorio", ["Hemograma Completo", "General de Orina", "General de Heces", "Grupo Sanguíneo y Rh", "Tiempo de Protrombina (TP)",
                        "Tiempo de Tromboplastina Parcial (TPT)", "Tiempo de Sangrado", "Tiempo de Coagulación", "Glucosa en Ayunas",
                        "Urea Nitrogenada (BUN)", "Creatinina", "TGO (Aspartato)", "TGP (Alanino)", "Fosfatasa Alcalina", "RPR",
                        "Anticuerpos VIH 1 y 2, P24"]),
    ("Hepático", ["Deshidrogenasa Láctica (LDH)", "Albúmina", "Proteínas Totales y Fraccionadas", "Tiempo de Tromboplastina Parcial (TPT)",
                  "TGO (Aspartato)", "TGP (Alanino)", "Fosfatasa Alcalina", "Gamma Glutamil Transpeptidasa (GGT)",
                  "Tiempo de Protrombina (TP)", "Bilirrubinas Totales y Fraccionadas"]),
    ("Anemias", ["Hemograma Completo", "Frotis de Sangre Periférica (FSP)", "Ferritina", "Vitamina B12", "Ácido Fólico",
                 "Capacidad de Captación de Hierro"]),
    ("Bioquímico (metabólico)", ["Glucosa en Ayunas", "Calcio", "Proteínas Totales y Fraccionadas", "Sodio (Na)", "Potasio (K)", "CO2",
                                 "Cloruro (Cl)", "Urea Nitrogenada (BUN)", "Creatinina", "TGO (Aspartato)", "TGP (Alanino)",
                                 "Fosfatasa Alcalina", "Bilirrubinas Totales y Fraccionadas"]),
    ("Lipídico", ["Colesterol Total", "Colesterol HDL", "Colesterol LDL", "Triglicéridos"]),
    ("Diabético", ["Hemograma Completo", "Glucosa en Ayunas", "Hemoglobina Glicosilada (HbA1c)", "Microalbuminuria"]),
    ("Menores de 35 años", ["Hemograma Completo", "Eritrosedimentación (VES)", "Glucosa en Ayunas", "Ácido Úrico", "General de Orina",
                            "General de Heces", "Tiempo de Protrombina (TP)", "Tiempo de Tromboplastina Parcial (TPT)", "TGO (Aspartato)",
                            "TGP (Alanino)", "Triglicéridos", "Colesterol Total", "Colesterol LDL", "Colesterol HDL", "Creatinina",
                            "Urea Nitrogenada (BUN)"]),
    ("Mayores de 35 años", ["Hemograma Completo", "Eritrosedimentación (VES)", "Glucosa en Ayunas", "Glucosa Post-Prandial", "Ácido Úrico",
                            "General de Orina", "General de Heces", "RPR", "Tiempo de Protrombina (TP)", "Tiempo de Tromboplastina Parcial (TPT)",
                            "Calcio", "TGO (Aspartato)", "TGP (Alanino)", "Urea Nitrogenada (BUN)", "Creatinina", "Colesterol Total",
                            "Colesterol LDL", "Colesterol HDL", "Triglicéridos", "PCR Ultrasensible (PCR-us)", "PSA Total (masculino)",
                            "TSH (Hormona Estimulante del Tiroides)"]),
    ("Febril", ["Proteína C Reactiva (PCR)", "Anticuerpos Estreptolisina «O» (ASO)", "General de Heces", "Eritrosedimentación (VES)",
                "General de Orina", "Urocultivo", "Hemograma Completo", "Hematozoario (Plasmodium spp.)", "Antígenos Febriles"]),
    ("Reumático", ["Anti CCP (Péptido Citrulinado)", "Hemograma Completo", "Eritrosedimentación (VES)", "Ácido Úrico",
                   "Anticuerpos Estreptolisina «O» (ASO)", "Proteína C Reactiva (PCR)", "Factor Reumatoideo"]),
    ("Tiroideo (1)", ["TSH (Hormona Estimulante del Tiroides)", "T4 Libre / Tiroxina Libre"]),
    ("Tiroideo (2)", ["TSH (Hormona Estimulante del Tiroides)", "T3 Triyodotironina Total", "T4-Uptake", "T4 Tiroxina Total",
                      "T4 Libre / Tiroxina Libre", "Ac. Antiperoxidasa (Anti-TPO)", "Ac. Antitiroglobulina (TG)"]),
    ("Hormonal mujeres > 40", ["TSH (Hormona Estimulante del Tiroides)", "T3 Triyodotironina Total", "T4 Tiroxina Total",
                               "LH (Hormona Luteinizante)", "FSH (Hormona Folículo Estimulante)", "Estradiol", "Prolactina (PRL)", "Insulina",
                               "Progesterona"]),
    ("Cardiovascular", ["TGP (Alanino)", "TGO (Aspartato)", "CPK (Creatin Fosfoquinasa)", "CPK-MB", "Deshidrogenasa Láctica (LDH)",
                        "NT Pro BNP", "Hemograma Completo", "Glucosa en Ayunas", "Hemoglobina Glicosilada (HbA1c)", "Colesterol Total",
                        "Colesterol HDL", "Colesterol LDL", "Triglicéridos", "Creatinina", "Urea Nitrogenada (BUN)", "PCR Ultrasensible (PCR-us)"]),
    ("Renal 1", ["Cociente Albúmina-Creatinina en Orina", "General de Orina", "Creatinina", "Urea Nitrogenada (BUN)"]),
    ("Renal 2", ["General de Orina", "Urea Nitrogenada (BUN)", "Creatinina / 24 Horas", "Depuración de Creatinina / 24 Horas",
                 "Proteínas Totales / 24 Horas", "Microalbuminuria en 24 horas", "Sodio (Na)", "Potasio (K)", "Cloruro (Cl)", "Calcio",
                 "Fósforo", "CO2"]),
    ("Prostático", ["PSA Total", "PSA Libre", "Relación PSA libre / PSA total"]),
    ("Óseo", ["PTH (Paratohormona)", "Vitamina D (25-OH)", "Calcio", "Fósforo"]),
    ("Obstétrico (1)", ["Hemograma Completo", "Grupo Sanguíneo y Rh", "General de Orina", "Glucosa en Ayunas", "RPR",
                        "Anticuerpos VIH 1 y 2, P24"]),
    ("Obstétrico (2)", ["Coombs Indirecto", "Tiempo de Protrombina (TP)", "Tiempo de Tromboplastina Parcial (TPT)", "Fibrinógeno",
                        "Toxo avidez", "Anticuerpos Antifosfolípidos IgG", "Anticuerpos Antifosfolípidos IgM", "Hemograma Completo",
                        "General de Orina", "General de Heces", "Glucosa en Ayunas", "RPR", "Anticuerpos VIH 1 y 2, P24",
                        "Grupo Sanguíneo y Rh", "Herpes II IgM, IgG", "Anticuerpos Anticardiolipinas IgG", "Anticuerpos Anticardiolipinas IgM",
                        "Anticuerpos Rubéola IgG", "Anticuerpos Rubéola IgM", "Citomegalovirus IgG, IgM", "Anticuerpos Toxoplasmosis IgG",
                        "Anticuerpos Toxoplasmosis IgM"]),
    ("COVID-19", ["Hemograma Completo", "Eritrosedimentación (VES)", "Ferritina", "Proteína C Reactiva (PCR)", "Deshidrogenasa Láctica (LDH)",
                  "TGO (Aspartato)", "TGP (Alanino)"]),
    ("Recién nacido < 1 mes", ["Hemograma Completo", "Grupo Sanguíneo y Rh", "TSH (Hormona Estimulante del Tiroides)",
                               "T4 Libre / Tiroxina Libre"]),
    ("Niño sano 1", ["Hemograma Completo", "General de Orina", "General de Heces", "Glucosa en Ayunas"]),
    ("Niño sano 2", ["Hemograma Completo", "General de Orina", "General de Heces", "Grupo Sanguíneo y Rh", "Frotis de Sangre Periférica (FSP)",
                     "Ácido Úrico", "Proteínas Totales y Fraccionadas", "Colesterol Total", "Triglicéridos", "Creatinina",
                     "Urea Nitrogenada (BUN)", "Glucosa en Ayunas", "TGO (Aspartato)", "TGP (Alanino)", "Fosfatasa Alcalina",
                     "Bilirrubinas Totales y Fraccionadas", "Calcio"]),
]

# Pruebas de un solo valor enlazadas con el catálogo de resultados (lab_tests.code).
RESULT_CODE = {
    "Creatinina": "creat", "Urea Nitrogenada (BUN)": "bun", "Sodio (Na)": "na", "Potasio (K)": "k", "Glucosa en Ayunas": "glu",
    "Hemoglobina Glicosilada (HbA1c)": "hba1c", "Colesterol Total": "col", "Triglicéridos": "tg", "Amilasa": "amilasa", "Lipasa": "lipasa",
    "Proteína C Reactiva (PCR)": "pcr", "Eritrosedimentación (VES)": "vsg", "Calprotectina Fecal": "calpro", "AFP": "afp", "CEA": "cea",
    "Ca 19-9 (Páncreas, Vesícula)": "ca199", "Antígeno de Superficie (Australia) HBs Ag": "hbsag",
    "Anticuerpos Hepatitis B Core Totales": "anti_hbc", "Anticuerpos Hepatitis C": "anti_hcv", "Anticuerpos VIH 1 y 2, P24": "vih",
    "Sangre Oculta en Heces": "sangre_oculta", "TSH (Hormona Estimulante del Tiroides)": "tsh", "Ferritina": "ferritina",
    "Hierro Sérico": "hierro", "Vitamina B12": "b12", "Ácido Fólico": "folato", "TGO (Aspartato)": "ast", "TGP (Alanino)": "alt",
    "Fosfatasa Alcalina": "fa", "Gamma Glutamil Transpeptidasa (GGT)": "ggt", "Tiempo de Protrombina (TP)": "tp",
    "Helicobacter pylori en Heces (Cualitativo)": "hp_ag_heces",
}


def slug(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:80]


TESTS = {}          # clave -> (sección, nombre)
for _sec, _names in SECTIONS:
    for _n in _names:
        _k = slug(_n)
        assert _k not in TESTS, f"clave repetida: {_k}"
        TESTS[_k] = (_sec, _n)
BY_NAME = {n: k for k, (_, n) in TESTS.items()}
PROFILE_KEYS = {slug("perfil " + name): (name, comps) for name, comps in PROFILES}


def profile_components(comps):
    """[(clave o None, nombre)] — la clave existe si el componente está en el catálogo."""
    return [(BY_NAME.get(c), c) for c in comps]
