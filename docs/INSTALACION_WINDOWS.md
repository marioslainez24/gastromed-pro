# Usar GastroMed Pro en su PC con Windows 11

**Un solo archivo: `GastroMedPro.exe`.** No hay que instalar Python ni ningún otro programa.
Todo se guarda en esta PC, en `C:\GastroMed`.

## Antes de empezar (recomendado)
1. **Cifrado del disco:** *Configuración → Privacidad y seguridad → Cifrado del dispositivo* (o *BitLocker*) → activado.
2. Su usuario de Windows con **contraseña o PIN** y bloqueo automático de pantalla.
3. **Wi-Fi del consultorio con contraseña**, que no sea el mismo que usan los pacientes.

## Primer uso
1. Copie `GastroMedPro.exe` al **Escritorio**.
2. Doble clic. Si aparece «Windows protegió su PC»: **Más información → Ejecutar de todas formas**
   (aparece porque el programa no tiene una firma digital comercial, que es de pago).
3. Se abre una ventana negra (el servidor) y el navegador con la **Configuración inicial**:
   escriba el nombre del consultorio, su nombre profesional, su correo y una contraseña.
4. Si Windows pregunta si permite el acceso en la red: marque **Redes privadas** y pulse **Permitir**
   (necesario para usarlo desde el celular).
5. En el escritorio aparece **«GastroMed - CLAVES …txt»**: cópielo a una USB o imprímalo, guárdelo en lugar seguro
   y **bórrelo del escritorio**. Sin esas claves no se pueden abrir los respaldos si la PC se daña.

## Uso diario
- Doble clic en `GastroMedPro.exe`. **No cierre la ventana negra** mientras use el sistema; ciérrela para apagarlo.
- **Celular:** conectado al mismo Wi-Fi, abra en Chrome la dirección **https** que muestra la ventana negra
  (por ejemplo `https://192.168.1.25:8443`) y guárdela como favorito. La primera vez dirá «La conexión no es privada»:
  toque **Configuración avanzada → Continuar**. Es normal: el certificado lo creó su propia PC (uno comercial es de pago).
  La conexión queda cifrada aunque alguien más esté en el Wi-Fi.
- Si vuelve a hacer doble clic con el programa abierto, solo se abre el navegador.

## Respaldos
- Automáticos **cada 24 horas** mientras el programa esté abierto (y al abrirlo, si el último tiene más de un día).
- Cada respaldo se verifica restaurándolo antes de darlo por bueno. Se conservan los últimos 30 en `C:\GastroMed\respaldos`.
- **Copia a disco externo:** abra `C:\GastroMed\datos\gastromed.env` con el Bloc de notas y complete
  `GASTROMED_BACKUP_COPY_DIR=E:\RespaldosGastroMed` (la letra de su disco). Cierre y abra el programa.
- Una vez por semana, lleve una copia del disco externo fuera del consultorio.

## Que se inicie solo al encender la PC (opcional)
Pulse `Windows + R`, escriba `shell:startup` y Enter. Copie allí un **acceso directo** a `GastroMedPro.exe`
(clic derecho sobre el .exe → *Mostrar más opciones → Crear acceso directo*, y mueva el acceso directo a esa carpeta).

## Actualizar
Reemplace el `GastroMedPro.exe` viejo por el nuevo (con el programa cerrado). Los datos, claves y usuarios se conservan.

## Primeros pasos dentro del sistema
1. *Ajustes → Clínica y documentos:* colegiación, dirección y teléfonos (salen en las recetas).
2. *Menú de usuario → Verificación en dos pasos:* actívela.
3. *Ajustes → Usuarios y permisos:* cree las cuentas de recepción y enfermería.
4. *Ajustes → Clínica y documentos → Logo y firma:* suba el logo y una foto de su firma.
5. *Ajustes → Horarios y vacaciones:* su horario de atención y las fechas bloqueadas.

## Recordatorios de citas (gratis)
- **Correo automático:** necesita una cuenta de Gmail del consultorio con *Verificación en dos pasos* activada.
  En myaccount.google.com/apppasswords cree una «contraseña de aplicación» (16 letras) y péguela en
  *Ajustes → Recordatorios y dictado*. Pulse «Enviar prueba». Marque «Enviar recordatorios automáticos».
- **WhatsApp:** en *Agenda → Recordatorios* toque el botón verde de cada cita; se abre WhatsApp con el mensaje escrito y usted pulsa Enviar.
- En la ficha de cada paciente elija el canal (Correo o WhatsApp) y marque que el paciente lo autorizó.
- El programa debe estar abierto para que salgan los correos automáticos.

## Dictado por voz (gratis)
*Ajustes → Recordatorios y dictado → Dictado:* lea el aviso, márquelo y active. En las notas aparece **🎤 Dictar** bajo cada campo.
Use Chrome o Edge, con internet. Diga «punto», «coma», «punto y aparte» o «nueva línea». Revise siempre el texto.

## Informes de endoscopia más rápidos
En *Hallazgos por segmento* escriba (o dicte) lo que ve en cada segmento. El botón **Normal** escribe la descripción normal de ese segmento;
**Todo normal** llena los segmentos vacíos y la conclusión. Revise siempre el texto. Para cambiar esas frases a su manera:
*Endoscopia → Textos de estudio normal*.

## Copia de seguridad en Google Drive (opcional, gratis)
1. Instale **Google Drive para computadora** e inicie sesión con su Gmail (aparece la unidad «Google Drive (G:)» con «Mi unidad»).
2. En GastroMed Pro: **Ajustes → Respaldos → Activar copia en Google Drive** (desde la PC del consultorio).
3. Pulse **Copiar ahora**. Desde entonces, cada respaldo diario se copia solo. El archivo va cifrado.
4. Imprima su **clave de respaldo** y guárdela lejos de la PC; no la suba a Drive.

## Novedades de la versión 0.14
- **Agenda:** cuando el paciente llega, «Registrar llegada»; enfermería pulsa «Signos vitales» en la sala de espera; usted pulsa **Atender →** y la nota
  se abre con esos datos. Al finalizar la nota, la cita queda «atendida».
- **Endoscopia:** «＋ Hallazgo con clics» en cada segmento; las sugerencias de diagnóstico aparecen en verde junto a la conclusión.
  Configure sus **Recomendaciones por diagnóstico** y sus **Hojas de preparación y consentimiento** en la pantalla de Endoscopia.
- **Nota:** «🖨 Imprimir todo» junta receta, órdenes y constancias del día.
- **Expediente:** el **Resumen** arriba muestra lo esencial y los cálculos con los últimos laboratorios.

## Historia de la enfermedad actual con clics
En la nota, encima de *Historia de la enfermedad actual*, abra **✍ Asistente de historia**: elija el motivo, marque lo que refiere el paciente y pulse
**Escribir en la historia**. Solo escribe lo que usted marcó; los «Niega…» salen solo si marca que interrogó los signos de alarma.

## Frases, plantillas y documentos
- *Ajustes → Frases y plantillas:* escriba sus frases (por ejemplo «Abdomen normal»). En la nota pulse **Frases** bajo el campo y elija una.
- Al terminar una nota típica, abajo use **Guardar como plantilla**. En la próxima nota elija la plantilla arriba y pulse **Aplicar**.
- Pestaña **Documentos** del paciente: incapacidad, constancia, referencia o documento libre. Revise el texto, emita e imprima para firmar.

## Límites (léalos)
- La PC debe estar encendida y el programa abierto.
- Solo funciona dentro del Wi-Fi del consultorio (fuera de él no se puede entrar, por seguridad).
- El dictado envía el audio a Google o Microsoft para convertirlo en texto; no dicte nombres, DNI ni teléfonos.
- Si algo falla, la ventana negra muestra el error: tome una foto y compártala.


## Usar GastroMed Pro en una Mac (preparado; se publica solo cuando el Dr. Lainez lo pida)

1. En la página de descargas baje **GastroMedPro-Mac-chip-Apple.zip** si su Mac tiene chip M1, M2, M3 o M4, o
   **GastroMedPro-Mac-Intel.zip** si es Intel (menú Apple  → «Acerca de esta Mac» lo dice).
2. Doble clic en el .zip: aparece una carpeta con **GastroMedPro** y **LEEME.txt**. Muévala al Escritorio o a Aplicaciones.
3. Doble clic en **GastroMedPro**. La primera vez la Mac avisa que no puede comprobar el desarrollador (el programa no tiene la firma de
   Apple, que es de pago). Vaya a **Ajustes del Sistema → Privacidad y seguridad**, baje hasta el aviso de «GastroMedPro» y pulse
   **«Abrir igualmente»**; confirme con su contraseña. Solo se hace una vez.
4. Se abre una ventana de la **Terminal** (es el servidor, como la ventana negra de Windows) y el navegador con la configuración inicial.
   No cierre la Terminal mientras use el programa; mientras está abierto, la Mac no se duerme.
5. Sus datos quedan en la carpeta **GastroMed** de su usuario (Finder → Ir → Inicio). Las claves de los respaldos se dejan en el Escritorio:
   cópielas a una USB y bórrelas del Escritorio.
6. El celular se conecta igual que con Windows: misma red Wi-Fi y la dirección https que muestra la Terminal. La primera vez, macOS puede
   preguntar si permite conexiones entrantes: pulse «Permitir».

Importante: los datos de la Mac y los de la PC con Windows son **independientes** (cada computadora es su propio servidor). Para pasar a
la Mac lo que ya tiene en Windows: cierre el programa en ambas, copie con una USB la carpeta `C:\GastroMed\datos` completa a la
Mac como `GastroMed/datos` (en su carpeta de usuario, reemplazando la que esté) y abra el programa en la Mac. Desde entonces use solo una
de las dos para no tener datos distintos en cada una.


## Activar el programa en una computadora (desde la versión 0.24.0)

El programa solo funciona en computadoras activadas por su titular. La primera vez (o al usarlo en otra PC):
1. Al abrir GastroMed Pro aparece «Activar GastroMed Pro» con el **código de esta computadora** (también sale en la ventana negra).
   Pulse «Copiar».
2. En su cuenta de GitHub abra el programa → pestaña **Actions** → «**Activar una computadora**» → **Run workflow** → pegue el código →
   **Run workflow**. En un minuto termina: ábralo y copie la **clave de activación** (una línea que empieza con «GM1.»).
3. Vuelva al programa, pegue la clave en el cuadro y pulse **Activar**. Listo: no se vuelve a pedir en esa PC.

Si el programa se copia a otra computadora, pedirá una clave nueva (la clave de una PC no sirve en otra). Si reinstala Windows, el
código cambia y hay que activar de nuevo. Los celulares no necesitan activación: se conectan a la PC ya activada.
