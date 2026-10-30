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
- **Celular:** conectado al mismo Wi-Fi, abra en el navegador la dirección que muestra la ventana negra
  (por ejemplo `http://192.168.1.25:8000`) y guárdela como favorito.
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

## Límites (léalos)
- La PC debe estar encendida y el programa abierto.
- Solo funciona dentro del Wi-Fi del consultorio; la conexión celular ↔ PC aún no está cifrada (HTTPS local: próxima versión).
- Si algo falla, la ventana negra muestra el error: tome una foto y compártala.
