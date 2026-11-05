"""Plantillas de hallazgos por patología (v0.26.0).

Textos tomados del documento de Word del Dr. Lainez («Endo NIC»): notas predeterminadas para cada situación diagnóstica de la endoscopia
alta y la colonoscopia. En el informe aparecen como un menú desplegable en cada segmento; al elegir una, el texto se escribe en ese
segmento (y, si la plantilla trae conclusión, se agrega a la conclusión). El médico revisa y edita: son SUS textos, no los inventa el
programa. Los «…» del original quedan para que él complete (cara, curvatura, tamaño).

Secciones: las del informe (esofago, ueg, estomago, duodeno, colon, rectosigmoides) y «recomendaciones».
"""
import json

from .db import new_id, utcnow, write_tx

KINDS = {"eda": "Endoscopia digestiva alta", "colonoscopia": "Colonoscopia", "rectosigmoidoscopia": "Rectosigmoidoscopia"}
SECTIONS = {
    "eda": [("esofago", "Esófago"), ("ueg", "Unión esofagogástrica"), ("estomago", "Estómago"), ("duodeno", "Duodeno"),
            ("recomendaciones", "Recomendaciones")],
    "colonoscopia": [("colon", "Colonoscopia"), ("recomendaciones", "Recomendaciones")],
    "rectosigmoidoscopia": [("rectosigmoides", "Rectosigmoidoscopia"), ("recomendaciones", "Recomendaciones")],
}

# (tipo, sección, título, texto, conclusión sugerida)
SEED = [
    # ---------------- Endoscopia alta · esófago
    ("eda", "esofago", "Várices esofágicas F1",
     "En H se observa un cordón varicoso, recto, que desaparece a la insuflación máxima del equipo.", ""),
    ("eda", "esofago", "Várices esofágicas F2",
     "En H se observa cordón varicoso, moderadamente dilatado y tortuoso que ocupa menos de un tercio de la luz, y no desaparece a la "
     "insuflación máxima del equipo, no presencia de puntos rojos en su superficie.", ""),
    ("eda", "esofago", "Várices esofágicas F3",
     "En H se observa cordón varicoso, dilatado, tortuoso que ocupa más de un tercio de la luz, y no desaparece a la insuflación máxima "
     "del equipo, no presencia de puntos rojos en su superficie.", ""),
    ("eda", "esofago", "Ligadura de várices esofágicas",
     "Esófago distal: en H3 se realiza succión de cordón varicoso F3 y liberación secuencial de banda elástica de forma helicoidal "
     "ascendente, logrando estrangulación efectiva de 1 banda. En H9 se observa cordón varicoso, moderadamente dilatado y tortuoso que "
     "ocupa menos de un tercio de la luz, resto del órgano sin alteración.", ""),
    ("eda", "esofago", "Dilatación esofágica (Savary 7 y 9 mm)",
     "Previa sedación con propofol y midazolam se introduce el equipo y a los 20 cm de la arcada dentaria se observa una estenosis "
     "concéntrica, regular, de aspecto benigno, que no permite el paso del equipo, se procede a pasar guía atraumática bajo visión "
     "fluoroscópica introduciendo dilatadores Savary de 7 y 9 mm sin presentar complicaciones. Posteriormente se procede a introducir "
     "endoscopio, logrando pasar estenosis, con sangrado autolimitado y desgarro de la mucosa a nivel de la estenosis.\n"
     "Se procede a visualizar la mucosa gástrica de características normales, mucosa del bulbo y segunda porción de duodeno se observa "
     "de características normales.", "Estenosis de esófago proximal grado III"),
    ("eda", "esofago", "Dilatación esofágica (Savary 9 a 15 mm, dos anillos)",
     "Previa sedación con propofol y midazolam se introduce el equipo de 10 mm en su extremo distal hasta los 40 cm de la arcada dentaria "
     "donde se observan dos anillos con estenosis concéntrica, regular, de aspecto benigno, que no permite el paso del equipo, se procede "
     "a pasar guía atraumática, se procede a introducir dilatador de Savary de 15 mm el cual no vence la estenosis, por lo que se "
     "introducen dilatadores Savary de 9 mm, 11 mm, 13 mm y 15 mm sin complicaciones. Posteriormente se procede a introducir endoscopio "
     "de 10 mm de diámetro en su extremo distal, logrando vencer la estenosis con sangrado autolimitado y desgarro de la mucosa a nivel "
     "de la estenosis.", ""),
    ("eda", "esofago", "Acalasia",
     "Al introducir el equipo se observa esófago dilatado (de aspecto sigmoideo) con presencia de abundante contenido líquido claro el "
     "cual se aspira en su totalidad exponiendo una mucosa de aspecto normal. Se avanza hasta el tercio distal donde existe a nivel del "
     "EEI estenosis puntiforme concéntrica, fruncida, donde los pliegues convergen, la cual se vence después de maniobrar con el equipo "
     "y se logra el paso del mismo hacia el estómago con sensación de caída al vacío. Existe ausencia de la peristalsis.", ""),
    ("eda", "esofago", "Tumor de esófago (24 cm)",
     "Se introduce el equipo hasta los 24 cm de la arcada dentaria donde se observa una lesión que estenosa la luz del órgano e impide "
     "el paso del equipo, de aspecto infiltrativo con fondo de necrosis en su superficie, mamelonante, a la cual se le toman múltiples "
     "muestras para biopsias las cuales desprenden por arrancamiento con sangrado autolimitado.", ""),
    ("eda", "esofago", "Neoplasia de esófago (20 cm)",
     "Se introduce equipo hasta los 20 cm en donde se observa una lesión esofágica de aspecto tumoral, de aproximadamente 5 cm de "
     "diámetro, polilobulada, de bordes irregulares, con mucosa friable al paso del equipo, que obstruye casi por completo la luz "
     "esofágica; posteriormente se logra pasar equipo hasta los 30 cm pero a partir de ahí presenta resistencia y ya no es posible "
     "avanzar el equipo. Se toma biopsia de la lesión la cual es por arrancamiento, con sangrado autolimitado y sin complicaciones.", ""),
    ("eda", "esofago", "Metaplasia esofágica (lengüetas)",
     "Permeable en toda su extensión, en la mucosa del tercio distal se observan en H2 y H6 dos lengüetas de color rojizo con cambios "
     "glandulares en su superficie que impresionan sospecha de metaplasia intestinal de aproximadamente 1 cm de longitud, de las cuales "
     "se toman biopsias con sangrado mínimo autolimitado, además la mucosa se observa con discreto eritema, la peristalsis del órgano se "
     "observa disminuida. Contenido normal.", ""),
    ("eda", "esofago", "Anillo de Schatzki (incompleto)",
     "A nivel de tercio distal inmediatamente sobre la línea Z se observa un área fibrosa que ocupa toda la circunferencia sin llegar "
     "totalmente a la formación anular (incompleto).", ""),
    # ---------------- unión esofagogástrica
    ("eda", "ueg", "Posible incompetencia del EEI",
     "El esfínter esofágico inferior se observa abierto durante toda la exploración.", ""),
    # ---------------- estómago
    ("eda", "estomago", "Gastropatía hipertensiva",
     "La mucosa gástrica se observa congestiva, de forma difusa, eritematosa, con patrón reticular en forma de piel de víbora, que "
     "separa áreas edematosas de mucosa gástrica. A nivel de cuerpo pliegues engrosados.", ""),
    ("eda", "estomago", "Várices gástricas",
     "A la maniobra de retroversión se observa presencia de cordones varicosos, rectos, que provienen del esófago y se continúan hacia "
     "la curvatura…", ""),
    ("eda", "estomago", "Úlcera",
     "En la cara … hacia curvatura … se observa una lesión ulcerosa de aproximadamente 3 mm de diámetro, estrellada, lineal, profunda, "
     "de bordes regulares, bien definidos, con mucosa circundante de aspecto normal, fondo cubierto de fibrina, de la cual se toma "
     "biopsia.", ""),
    ("eda", "estomago", "GIST (lesión submucosa)",
     "Hacia cara … y curvatura … se observa una lesión tumoral de aspecto submucoso de aproximadamente 3 cm de diámetro, que protruye "
     "hacia la luz, con superficie lisa y mucosa rosada que es similar a la circundante.", "GIST de …"),
    ("eda", "estomago", "Metaplasia intestinal gástrica",
     "Píloro simétrico, central, que deja el paso del equipo sin dificultad. En antro e incisura angular se observan áreas "
     "ligeramente sobreelevadas, de color blanquecino grisáceo, distribuidas en parches, con patrón mucoso afelpado; a la evaluación "
     "con NBI se observa patrón tubulovelloso con cresta azul clara (light blue crest). Se toman biopsias según el protocolo de Sídney "
     "(antro, incisura angular y cuerpo, en frascos separados), con sangrado autolimitado. Lago gástrico claro y escaso. En maniobra de "
     "retroversión fundus y cardias de características normales.",
     "Hallazgos endoscópicos sugestivos de metaplasia intestinal gástrica, pendiente de histología"),
    ("eda", "estomago", "Tumor gástrico",
     "Píloro simétrico, central, que deja el paso del equipo sin dificultad. Desde el área prepilórica se observa lesión de aspecto "
     "tumoral, mamelonante e infiltrativa, con múltiples lesiones ulcerosas de bordes mal definidos, confluentes sobre su superficie, "
     "cubiertas con fibrina. La lesión se extiende hasta cuerpo medio abarcando toda la circunferencia del órgano, que a la toma de "
     "biopsia desprende por arrancamiento. Lago gástrico claro y escaso. En maniobra de retroversión fundus y cardias de "
     "características normales.", ""),
    ("eda", "estomago", "Metaplasia gástrica",
     "Píloro simétrico, central, que deja el paso del equipo sin dificultad. Mucosa antral eritematosa, con extensas áreas ligeramente "
     "sobreelevadas de color blanquecino y patrón afelpado. En cuerpo y fundus la mucosa se muestra pálida, con visualización del patrón "
     "vascular submucoso a su través, ausencia de pliegues gástricos a la insuflación, además lesiones elevadas, sésiles, de 2 a 3 mm en "
     "cuerpo y fundus, eritematosas, sin cambio del patrón glandular a luz blanca y NBI. Lago gástrico claro y escaso. En maniobra de "
     "retroversión fundus y cardias de características normales.", ""),
    ("eda", "estomago", "Estómago operado",
     "Se introduce el equipo hasta visualizar dos bocas anastomóticas, la mucosa del remanente gástrico se observa congestiva en toda su "
     "extensión con abundante líquido verde amarillento de aspecto biliar; a nivel del estoma se visualizan dos lesiones "
     "pseudopolipoideas, con superficie eritematosa, con presencia de erosiones y en su base se observan hilos de sutura. Se toma "
     "biopsia, con sangrado autolimitado y sin complicaciones.", ""),
    ("eda", "estomago", "Billroth II",
     "Se introduce equipo hasta visualizar cavidad gástrica observándose mucosa de fundus y remanente de cuerpo con marcado edema, "
     "eritema, bañada por abundante reflujo de líquido amarillo verdoso de aspecto bilioso, observándose dos neobocas; se explora a "
     "través del asa aferente y aproximadamente a los 5 cm se observa estenosis circular regular blanquecina que no permite la "
     "progresión del equipo a pesar de múltiples intentos, se procede a toma de biopsia de la misma con elasticidad disminuida y "
     "sangrado autolimitado. Se intenta explorar neoboca eferente y se observa marcado eritema y edema con disminución del calibre de la "
     "luz que no permite la progresión del equipo, tomándose muestras de biopsia de la misma con elasticidad disminuida y sangrado "
     "autolimitado.", ""),
    ("eda", "estomago", "Pangastritis erosiva hemorrágica (EII)",
     "Píloro lateralizado hacia la derecha, simétrico y permeable. Estómago de dimensiones normales que distiende sin dificultad. La "
     "mucosa gástrica se observa eritematosa en toda su extensión. En antro y cuerpo se observa presencia de múltiples erosiones planas, "
     "de aproximadamente 3 a 4 mm de diámetro, algunas con presencia de restos hemáticos oxidados en su superficie, y otras del mismo "
     "tamaño, un poco más profundas, con fibrina en su superficie. La mucosa se observa irregular y con áreas de fibrosis. Se procede a "
     "la toma de biopsia, con sangrado autolimitado y sin complicaciones. A la maniobra de retroversión se observa fundus y cardias de "
     "aspecto normal. Lago gástrico con presencia de líquido verde amarillento de aspecto biliar. Luz, pliegues y peristalsis sin "
     "alteraciones.", "Pangastritis eritematosa erosiva hemorrágica moderada"),
    ("eda", "estomago", "Angiodisplasia gástrica (APC)",
     "Píloro central y permeable. La mucosa gástrica se observa eritematosa y congestiva en toda su extensión con patrón reticular fino "
     "que le confiere un patrón en mosaico. En antro gástrico se observan varias lesiones arboriformes de tipo vascular de "
     "aproximadamente 3 a 5 mm de predominio en curvatura mayor y en región prepilórica. Se aplica APC de forma satisfactoria. Lago "
     "gástrico claro y escaso. A la maniobra de retroversión no se observan alteraciones en fundus ni en cardias bajo visualización "
     "directa.", ""),
    ("eda", "estomago", "Ectasias vasculares antrales (aspecto en sandía)",
     "Píloro central y permeable. Se observan múltiples lesiones elevadas, rojizas, arboriformes de origen vascular que ocupan el 80% de "
     "la mucosa antral, que le confieren un aspecto en sandía, observándose cicatrices de sesión anterior. Lago gástrico claro y escaso. "
     "En maniobra de retroversión fundus y cardias de características normales.", ""),
    ("eda", "estomago", "Inyectoterapia",
     "Lesión … en donde se aplica inyectoterapia con epinefrina 1:10000 satisfactoriamente.", ""),
    ("eda", "estomago", "Toma de biopsia (frase)",
     "de la cual se toma muestra para biopsia con elasticidad conservada y sangrado autolimitado.", ""),
    ("eda", "estomago", "Gastrostomía endoscópica percutánea (PEG)",
     "Píloro simétrico, central, que deja el paso del equipo sin dificultad. Cámara gástrica de dimensiones normales, que distiende sin "
     "dificultad, con peristaltismo adecuado, la mucosa del antro ligeramente eritematosa de forma difusa, lago gástrico escaso, fundus "
     "de características normales, por lo que se procede a iluminar hacia cara anterior de cuerpo gástrico, donde se punciona con "
     "trocar, se retira aguja y se introduce guía hacia cámara gástrica. Se agarra con el asa de polipectomía, retirando el equipo. Se "
     "procede a introducir sonda de gastrostomía con ayuda de la guía, hasta su salida por pared abdominal. Se introduce equipo "
     "endoscópico donde se visualiza adecuada colocación, y se infla sonda con agua destilada, con adecuada salida. Se fija sonda.", ""),
    ("eda", "estomago", "Retiro de PEG",
     "Píloro simétrico, central, que deja el paso del equipo sin dificultad. Cámara gástrica de dimensiones normales, que distiende sin "
     "dificultad, con peristaltismo adecuado, la mucosa del antro ligeramente eritematosa de forma difusa, lago gástrico escaso, fundus "
     "de características normales, por lo que se procede a iluminar hacia cara anterior de cuerpo gástrico, donde se agarra con el asa "
     "de polipectomía el PEG, retirando el equipo. Se introduce equipo endoscópico donde se visualiza adecuada colocación de sonda "
     "Foley, y se infla sonda con agua destilada, con adecuada salida. Se fija sonda.", ""),
    # ---------------- duodeno
    ("eda", "duodeno", "Úlcera gigante deformante de bulbo y antro",
     "El bulbo duodenal se encuentra deformado; hacia cara … y curvatura … se observa una lesión ulcerosa de gran tamaño, extendiéndose "
     "hacia cara … del antro gástrico, de aproximadamente 3 cm de diámetro, profunda, con bordes elevados, fondo cubierto con exudado "
     "blanquecino. La luz se encuentra casi totalmente ocluida, que permite el paso del equipo con dificultad. Se procede a toma de "
     "biopsia la cual conserva su elasticidad. Peristalsis conservada.",
     "Úlcera gigante de antro gástrico y bulbo duodenal\nEstenosis incompleta del bulbo duodenal"),
    ("eda", "duodeno", "Divertículo de bulbo (cirugía previa)",
     "Se introduce el equipo hasta visualizar la segunda porción del duodeno observándose una mucosa de características normales. En el "
     "bulbo se observa una cicatriz por cirugía previa y la formación de un orificio diverticular hacia curvatura menor de pequeño "
     "tamaño sin signos de inflamación. Luz y peristalsis normales.", ""),
    ("eda", "duodeno", "Duodenitis nodular atrófica severa",
     "Se introduce el equipo hasta visualizar la mucosa de la segunda porción de duodeno la cual se observa pálida en toda su extensión, "
     "con pliegues duodenales distanciados, con algo de nodularidad, pérdida del patrón velloso (o vellosidades acortadas de forma "
     "uniforme).", ""),
    ("eda", "duodeno", "Lesión elevada de bulbo",
     "Se observa en cara … hacia curvatura … una lesión elevada de bordes irregulares, de aproximadamente 5 mm de diámetro, en su "
     "superficie se observan cambios glandulares, de la cual se toma biopsia conservando su elasticidad, presentando sangrado "
     "autolimitado y sin complicaciones.", ""),
    ("eda", "duodeno", "Linfangiectasia duodenal",
     "Se introduce equipo hasta visualizar la mucosa de la segunda porción de duodeno la cual se observa con patrón velloso de diferente "
     "grosor y de color blanquecino que da aspecto de nevado a todo el marco duodenal, observándose trayectos con ausencia de "
     "vellosidades de forma lineal; se tomaron muestras de biopsia con elasticidad conservada y sangrado autolimitado. La mucosa del "
     "bulbo duodenal se observa de características similares. Luz y peristalsis sin alteraciones.", ""),
    # ---------------- recomendaciones (endoscopia alta)
    ("eda", "recomendaciones", "Cuidados post ligadura de várices",
     "Cuidados post ligadura de várices esofágicas:\n1. Dieta líquida hoy.\n2. Dieta blanda licuada las siguientes 24 horas.\n"
     "3. Si toma medicamentos, deben ser triturados antes de tomarlos.\n4. No realizar esfuerzo físico por 72 horas.\n"
     "5. Reevaluación endoscópica en 4 semanas.", ""),
    ("eda", "recomendaciones", "Cuidados post gastrostomía (PEG)",
     "Se recomienda antibioterapia por 7 días.\n"
     "Cuidados de la alimentación:\n• Inicio de alimentación 4 horas después del implante.\n"
     "• Antes de cada ingesta comprobar que la sonda esté bien colocada.\n"
     "• El paciente deberá estar sentado o incorporado en la cama unos 45º.\n"
     "• Después de cada nutrición o administración de medicamentos infundir 50 ml de agua.\n"
     "• Formas de administración de la alimentación: 1. Gravedad. 2. Jeringa. 3. Bomba.\n"
     "Cuidados del estoma:\n• Comprobar si existe inflamación, dolor, etc.\n"
     "• Los primeros 15 días lavar con agua tibia y jabón. Secar, aplicar antiséptico y colocar una gasa estéril.\n"
     "• A partir de la tercera semana es suficiente con limpiar el estoma con agua y jabón.\n"
     "Cuidados de la sonda:\n• Limpiar la sonda con agua tibia y jabón.\n• Diariamente girar ligeramente la sonda.\n"
     "• Cerrar el tapón cuando no se usa.\n• Procurar que el soporte externo no haga presión sobre la piel.", ""),
    # ---------------- Colonoscopia
    ("colonoscopia", "colon", "Ileocolonoscopia normal en paciente operado (ostomía)",
     "Previa sedación con propofol y midazolam se introduce el equipo por ostomía cabo proximal hasta visualizar el fondo de ciego y "
     "orificio apendicular, válvula ileocecal de características normales, la cual se procede a traspasar y se exploran aproximadamente "
     "10 cm de mucosa de íleon, que se observa rosada de características normales. En exploración retrógrada se observa luz, mucosa, "
     "peristalsis, patrón vascular, pliegues y haustras de características normales.\nPosteriormente se introduce equipo por canal anal "
     "hasta los 30 cm del margen anal donde se observa asa ciega de anastomosis quirúrgica; en exploración retrógrada se observa luz, "
     "mucosa, peristalsis, patrón vascular, pliegues y haustras de características normales.", ""),
    ("colonoscopia", "colon", "Diverticulitis",
     "Previa sedación con propofol y midazolam se introduce el equipo hasta visualizar la mucosa de fondo de ciego, válvula ileocecal y "
     "orificio apendicular de características normales. En la exploración retrógrada se observa luz, peristalsis, patrón vascular, "
     "mucosa, pliegues y haustras de características normales hasta colon sigmoides y recto donde se observan orificios diverticulares "
     "de pequeño tamaño con presencia de parchado congestivo en región peridiverticular, observándose un orificio diverticular en el "
     "sigmoides con presencia de pus en su interior y cuello congestivo.", ""),
    ("colonoscopia", "colon", "Divertículos de sigmoides sin inflamación",
     "Previa sedación con propofol y midazolam se introduce el equipo hasta visualizar la mucosa de fondo de ciego, válvula ileocecal y "
     "orificio apendicular los cuales se observan de características normales. Se procede a traspasar válvula y se exploran "
     "aproximadamente 10 cm de mucosa de íleon la cual se observa rosada de características normales. En exploración retrógrada se "
     "observa luz, mucosa, peristalsis, patrón vascular, pliegues y haustras de características normales hasta colon sigmoides donde se "
     "visualizan varios orificios saculares de pequeño, mediano y uno de ellos de gran tamaño sin signos de inflamación, resto de "
     "características normales hasta el margen anal.", ""),
    ("colonoscopia", "colon", "Divertículos en todo el colon",
     "Previa sedación con propofol y midazolam se introduce el equipo hasta visualizar la mucosa de fondo de ciego, válvula ileocecal y "
     "orificio apendicular de características normales. Se procede a traspasar la válvula ileocecal explorándose aproximadamente 20 cm "
     "de mucosa, la cual se observa rosada de características normales. Durante toda la exploración se observan orificios "
     "diverticulares de pequeño y mediano tamaño, sin signos inflamatorios. En exploración retrógrada se observa luz, peristalsis, patrón "
     "vascular, mucosa, pliegues y haustras de características normales hasta el margen anal.", ""),
    ("colonoscopia", "colon", "Pólipo pediculado de sigmoides y lesión de recto",
     "Previa sedación con propofol y midazolam se introduce el equipo hasta visualizar la mucosa de fondo de ciego, válvula ileocecal y "
     "orificio apendicular de características normales. Se traspasa la válvula y se exploran aproximadamente 5 cm de íleon terminal de "
     "características normales. En la exploración retrógrada se observa luz, peristalsis, patrón vascular, mucosa, pliegues y haustras "
     "de características normales hasta colon sigmoides donde se visualiza a los 35 cm aproximadamente del borde anal un pólipo con "
     "pedículo corto de 5 mm de diámetro, de superficie lisa, con mucosa que lo recubre similar a la mucosa que lo circunda, "
     "vascularizado sin definir patrón, al cual se realiza resección con asa de diatermia sin visualizar complicaciones inmediatas. En "
     "recto medio, aproximadamente a los 5 cm de la línea pectínea, se visualiza una lesión sobreelevada, blanquecina, de 4 mm de "
     "diámetro, de superficie lisa; se realiza resección con pinza de biopsia en su totalidad con sangrado autolimitado. Resto del "
     "estudio de características normales hasta el margen anal.", ""),
    ("colonoscopia", "colon", "Pólipos y divertículos",
     "Previa sedación con propofol y midazolam se introduce el equipo hasta visualizar la mucosa de fondo de ciego, válvula ileocecal y "
     "orificio apendicular de características normales. Se traspasa la válvula y se exploran 5 cm de íleon terminal de características "
     "normales. En la exploración retrógrada se observa luz, peristalsis, patrón vascular, mucosa, pliegues y haustras de "
     "características normales hasta colon transverso donde se observa una lesión polipoidea sésil de 3 mm de diámetro, con mucosa que "
     "la recubre similar a la mucosa que la circunda, la cual se extirpa con pinza de biopsia en su totalidad. Colon descendente de "
     "características normales; en colon sigmoides se observa una lesión polipoidea sésil de 3 mm de diámetro, con mucosa que la "
     "recubre similar a la mucosa que la circunda, la cual se extirpa con pinza de biopsia en su totalidad. En colon transverso y "
     "sigmoides se observan saculaciones diverticulares de gran tamaño, ocupadas con material fecal, sin datos de inflamación, de forma "
     "aislada. Resto del estudio de características normales hasta el margen anal donde se observa papila hipertrófica. Durante todo el "
     "procedimiento se toman múltiples biopsias.", ""),
    ("colonoscopia", "colon", "Pólipos múltiples (asa de diatermia)",
     "Previa sedación con propofol y midazolam se introduce el equipo hasta visualizar la mucosa de fondo de ciego, válvula ileocecal y "
     "orificio apendicular de características normales. En exploración retrógrada se visualiza en unión ceco-ascendente una lesión de "
     "crecimiento lateral de aproximadamente 2 mm de diámetro con bordes regulares y cambio de patrón mucoso en su superficie de la cual "
     "se toma biopsia. Se continúa explorando hasta ángulo esplénico donde se visualiza un pólipo sésil de aproximadamente 3 mm de "
     "diámetro con borde regular y superficie con cambio en el patrón mucoso, el cual se extirpa con asa de diatermia. En colon "
     "sigmoides se visualizan dos pólipos pediculados; uno de ellos de diámetro aproximado de 1 cm con bordes irregulares, cambios en el "
     "patrón mucoso en su superficie, al cual se le realiza inyectoterapia y se extirpa con asa de diatermia. El otro pólipo de diámetro "
     "aproximado de 2 cm con bordes irregulares y superficie con cambio del patrón mucoso, se le realiza inyectoterapia y se extirpa con "
     "asa de diatermia produciéndose un sangrado autolimitado el cual se logra controlar con inyección de epinefrina 1:10000 y "
     "polidocanol 1.5%. Se continúa explorando hasta el canal anal donde en maniobra de retroflexión y en visión directa se visualiza "
     "una lesión tumoral que sobresale del canal anal, de bordes irregulares, con superficie irregular y cambio en el patrón mucoso, "
     "dicha lesión ya era conocida.", ""),
    ("colonoscopia", "colon", "Pólipos con inyectoterapia",
     "Previa sedación con propofol y midazolam se introduce el equipo hasta visualizar la mucosa de fondo de ciego, válvula ileocecal y "
     "orificio apendicular de características normales aunque tapizado por materia fecal. En exploración retrógrada la mucosa, luz, "
     "peristalsis y contenido son normales hasta colon descendente cerca del ángulo esplénico donde se observan 2 pólipos sésiles de "
     "aproximadamente 1 cm de diámetro con bordes regulares y superficie con cambio en el patrón mucoso, los cuales se extirpan con asa "
     "de diatermia, con sangrado autolimitado. En colon sigmoides se visualiza una lesión polipoidea pediculada de aproximadamente "
     "2.5 cm de diámetro con bordes irregulares, multilobulada, con cambios en el patrón mucoso en su superficie, a la cual se le "
     "realiza inyectoterapia en su base y se extirpa con asa de diatermia, produciéndose un sangrado autolimitado el cual se logra "
     "controlar con inyección de epinefrina 1:10000. Además se observan múltiples orificios diverticulares de pequeño tamaño sin signos "
     "de inflamación. Durante la exploración la mucosa se encontraba tapizada de material fecal que dificultaba la correcta "
     "visualización de la misma. Resto de exploración normal.", ""),
    ("colonoscopia", "colon", "Pólipos neoplásicos",
     "Previa sedación con propofol y midazolam se introduce el equipo hasta visualizar la mucosa de fondo de ciego, válvula ileocecal y "
     "orificio apendicular de características normales. En ciego se observa lesión polipoidea sésil de 2 mm aproximadamente con cambios "
     "en el patrón glandular la cual se extirpa con pinza de biopsia. En exploración retrógrada se observa luz, peristalsis, patrón "
     "vascular, mucosa, pliegues y haustras de características normales hasta colon descendente donde se observa lesión polipoidea de "
     "3 mm sésil con cambios del patrón glandular la cual se extirpa con pinza de biopsia. A los 15 cm del canal anal se observa lesión "
     "polipoidea de pedículo ancho, de aspecto infiltrante al igual que el resto de la lesión, irregular, multilobulada, con bordes mal "
     "definidos, que ocluye más de 2/3 de la luz y permite el paso del equipo con dificultad, de la cual se toman múltiples muestras de "
     "biopsia que se desprenden de forma fragmentada, de consistencia y elasticidad disminuidas y con sangrado autolimitado; además a "
     "nivel de colon sigmoides se observan algunos orificios diverticulares de pequeño tamaño sin signos de inflamación.", ""),
    ("colonoscopia", "colon", "Pólipos y lesión vascular violácea de recto",
     "Previa sedación con propofol y midazolam se introduce equipo hasta visualizar la mucosa de fondo de ciego, válvula ileocecal y "
     "orificio apendicular los cuales se observan de características normales. En exploración retrógrada mucosa, haustras, peristalsis "
     "y patrón vascular de características normales hasta los 50 cm desde el margen anal donde se observa un pólipo de 5 mm de "
     "diámetro, de color rosado, sésil, superficie lisa, bordes regulares, el cual se extirpa con pinza de biopsia. A nivel de mucosa de "
     "recto se observa una lesión de color violáceo que toma circunferencialmente el órgano, de aspecto vascular; además se observa "
     "sobre esta mucosa un pólipo sésil de aproximadamente 7 mm de color rojo con superficie lisa y bordes regulares el cual se extirpa "
     "con pinza de biopsia.", ""),
    ("colonoscopia", "colon", "Neoplasia de colon sigmoides (18 cm) con pólipo",
     "Previa sedación con propofol y midazolam se introduce el equipo; a los 18 cm del borde anal se observa lesión tumoral, vegetante, "
     "ulcerada, que crece hacia la luz, que ocupa más de las 3 partes de la misma, con imagen en desfiladero, no permitiendo el paso del "
     "equipo a pesar de las maniobras realizadas, de superficie irregular con extensas áreas de necrosis, muy vascularizada, friable al "
     "contacto y a la toma de muestra la cual se produce por arrancamiento. A los 16 cm se observa un pólipo sésil de 4 mm con patrón "
     "muy vascularizado el cual se extrae con pinza de biopsia. Margen anal normal.", ""),
    ("colonoscopia", "colon", "Neoplasia de colon sigmoides (22 cm)",
     "Previa sedación con propofol y midazolam se introduce el equipo; a los 22 cm del borde anal se observa lesión tumoral, vegetante, "
     "ulcerada, que crece hacia la luz, que ocupa más de las 3 partes de la misma, no permitiendo el paso del equipo a pesar de las "
     "maniobras realizadas, de superficie irregular, mamelonante, con extensas áreas de necrosis y ulceraciones, muy vascularizada, "
     "friable al contacto y a la toma de muestra la cual se produce por arrancamiento. Margen anal normal.", ""),
    ("colonoscopia", "colon", "Neoplasia (masa) de ángulo hepático con divertículos",
     "Previa sedación con propofol y midazolam se introduce el equipo visualizándose en colon sigmoides y descendente gran cantidad de "
     "saculaciones diverticulares de gran tamaño, ocupadas con material fecal, sin datos de inflamación. Se pasa ángulo hepático e "
     "inmediatamente se visualiza masa tumoral, irregular, multilobulada, con bordes mal definidos, con áreas de necrosis central que "
     "ocupa la totalidad de la luz, que no deja pasar el equipo; se toma biopsia que desprende de forma fragmentada. En la exploración "
     "retrógrada se observa luz, peristalsis, patrón vascular, mucosa, pliegues y haustras de características normales hasta colon "
     "descendente y sigmoides, con lesiones ya mencionadas. Resto del estudio de características normales hasta el margen anal.", ""),
    ("colonoscopia", "colon", "Neoplasia de ángulo hepático (preparación deficiente)",
     "Previa sedación con propofol y midazolam se introduce el equipo hasta ángulo hepático donde se observa una lesión de aspecto "
     "infiltrativo y mamelonante, ulcerada, con áreas de necrosis, que ocupa más del 75% de la luz y que impide el paso del equipo. Se "
     "toma muestra para biopsia por arrancamiento, con sangrado autolimitado. En exploración retrógrada se observa la luz tapizada con "
     "abundante materia fecal, que impide la correcta exploración de la mucosa hasta el margen anal.", ""),
    ("colonoscopia", "colon", "Neoplasia infiltrante de sigmoides",
     "Previa sedación con propofol y midazolam se introduce el equipo hasta visualizar la mucosa de fondo de ciego, válvula ileocecal y "
     "orificio apendicular de características normales. En la exploración retrógrada se observa luz, peristalsis, patrón vascular, "
     "mucosa, pliegues y haustras de características normales hasta colon sigmoides donde se observa lesión tumoral que estenosa la luz, "
     "friable, con áreas necróticas, que ocupa más de 2/3 de la luz, que se extiende desde los 35 cm del borde anal hasta los 25 cm; se "
     "toma biopsia que desprende de forma fragmentada. Resto de la exploración sin alteración hasta el margen anal.", ""),
    ("colonoscopia", "colon", "Colitis ulcerosa",
     "Previa sedación con propofol y midazolam se introduce el equipo hasta visualizar la mucosa de fondo de ciego, válvula ileocecal y "
     "orificio apendicular. Se traspasa la válvula y se exploran 15 cm de íleon terminal de características normales. En la exploración "
     "retrógrada se observa luz, peristalsis, pliegues y haustras de características normales, mucosa eritematosa, edematosa, "
     "granujienta, con disminución del patrón vascular, desde colon ascendente hasta recto; en localización más distal se hacen más "
     "llamativas las lesiones, con presencia de algunas áreas con erosiones y friabilidad leve, hasta el margen anal.", ""),
    ("colonoscopia", "colon", "Ectasias vasculares de recto (APC)",
     "Previa sedación con propofol y midazolam se introduce el equipo hasta visualizar la mucosa de fondo de ciego, válvula ileocecal y "
     "orificio apendicular de características normales. En la exploración retrógrada se observa luz, peristalsis, patrón vascular, "
     "mucosa, pliegues y haustras de características normales hasta el recto donde se observan lesiones planas eritematosas de aspecto "
     "arboriforme de color rojo con presencia de sangrado espontáneo compatibles con ectasias vasculares, a las cuales se les aplica "
     "APC. Dichas lesiones alternan con zonas de mucosa de características normales.", ""),
    ("colonoscopia", "colon", "Ostomía: colitis actínica y por derivación",
     "Previa sedación con propofol y midazolam se introduce el equipo por ostomía cabo proximal hasta visualizar el fondo de ciego y "
     "orificio apendicular, válvula ileocecal de características normales. En la exploración retrógrada se observan algunas áreas de la "
     "mucosa tapizada con materia fecal, además se observan lesiones arboriformes, rojas, sugestivas de ectasias vasculares.\nSe pasa "
     "por cabo distal y se exploran 20 cm, se observan lesiones arboriformes, rojas, sugestivas de ectasias vasculares, no "
     "continuándose por presencia de asa ciega.\nSe introduce el equipo por el ano y se avanza hasta los 20 cm de sus márgenes; aquí se "
     "observa estenosis concéntrica fibrótica a ese nivel, que permite ver la luz pero impide el paso del equipo; resto de la mucosa "
     "pálida con pérdida de la vascularización y de las haustras, con friabilidad, que sangra espontáneamente y con el paso del equipo, "
     "hasta el margen anal.", ""),
    ("colonoscopia", "colon", "Lesión en saco ciego del cabo distal y colitis por derivación",
     "Previa sedación con propofol y midazolam se introduce el equipo por ostomía cabo proximal hasta visualizar fondo de ciego, "
     "orificio apendicular y válvula ileocecal de características normales. Se procede a traspasar válvula ileocecal explorándose "
     "aproximadamente 40 cm de mucosa de íleon, la cual se observa rosada de características normales. En la exploración retrógrada se "
     "observa luz, mucosa, peristalsis, haustras y patrón vascular de características normales. Se procede a introducir equipo por "
     "recto hasta saco ciego, observándose una lesión que protruye hacia la luz de aproximadamente 1.5 cm de diámetro, de bordes "
     "regulares, con mucosa de las mismas características que la circundante, de la cual se procede a toma de biopsia que conserva su "
     "elasticidad. En exploración retrógrada se observa la mucosa eritematosa en toda su extensión, pliegues, haustras y peristalsis de "
     "características normales hasta el margen del ano.", ""),
    ("colonoscopia", "colon", "Angioma / melanosis (lesión rectal)",
     "Previa sedación con propofol y midazolam se introduce el equipo hasta visualizar la mucosa de fondo de ciego, orificio "
     "apendicular y válvula ileocecal, los cuales son de características normales. Se pasa la válvula y se exploran aproximadamente "
     "40 cm de mucosa de íleon terminal, de aspecto normal. Durante toda la exploración se observa en todo el marco colónico luz, "
     "mucosa, haustras, patrón vascular y peristalsis normales hasta los 15 cm del canal anal donde se observa mucosa eritematosa con "
     "aspecto granujiento, existiendo una úlcera que abarca prácticamente la totalidad de la superficie de la misma, con áreas de "
     "sangrado submucoso. Existen áreas de color violáceo oscuro, casi negro, que ofrecen dificultades para diferenciar entre una "
     "melanosis coli y hemangioma.", ""),
    # ---------------- Rectosigmoidoscopia
    ("rectosigmoidoscopia", "rectosigmoides", "Hemorroides y fisura",
     "Al tacto rectal en la zona perianal se observa plexo hemorroidal cubierto de piel, dilatado hacia H5, sin datos de trombosis, y "
     "fisura hacia H12. Se introduce el equipo hasta los 40 cm del margen anal; en la exploración retrógrada se observa luz, "
     "peristalsis, patrón vascular, mucosa, pliegues y haustras de características normales hasta el margen anal; por encima de la "
     "línea pectínea se observan plexos hemorroidales dilatados, sin datos de trombosis.", ""),
]


def seed_key(kind, title) -> str:
    return f"{kind}:{title}"


def ensure_seed(db, org_id) -> int:
    """Carga las plantillas del programa que la clínica todavía no tiene (la primera vez, todas; después, solo las nuevas que se
    agreguen en una actualización). Nunca toca las que el médico ya editó o quitó del menú."""
    have = {r[0] for r in db.execute("SELECT seed_key FROM endo_templates WHERE org_id = ? AND seed_key IS NOT NULL", (org_id,))}
    missing = [(i, x) for i, x in enumerate(SEED) if seed_key(x[0], x[2]) not in have]
    if not missing:
        return 0
    now = utcnow()
    with write_tx(db):
        for i, (kind, sec, title, body, concl) in missing:
            db.execute("INSERT INTO endo_templates(id, org_id, kind, section, title, body, conclusion, position, active, created_at,"
                       " updated_at, seed_key) VALUES (?,?,?,?,?,?,?,?,1,?,?,?)",
                       (new_id(), org_id, kind, sec, title, body, concl or None, i, now, now, seed_key(kind, title)))
    return len(missing)


def for_kind(db, org_id, kind):
    """Plantillas activas de un tipo de estudio, agrupadas por sección: {sección: [fila, …]}."""
    ensure_seed(db, org_id)
    out = {}
    for r in db.execute("SELECT * FROM endo_templates WHERE org_id = ? AND kind = ? AND active = 1 ORDER BY position, title",
                        (org_id, kind)):
        out.setdefault(r["section"], []).append(r)
    return out


def as_json(groups) -> str:
    return json.dumps({r["id"]: {"t": r["title"], "b": r["body"], "c": r["conclusion"] or ""} for rows in groups.values() for r in rows},
                      ensure_ascii=False)
