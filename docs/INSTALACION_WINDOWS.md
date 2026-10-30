# Instalar GastroMed Pro en su PC con Windows 11 (servidor privado)

Todo queda guardado **en esta PC**, en `C:\GastroMed`. No se usa ningún servicio en internet.
La instalación tarda unos 10 minutos y solo necesita internet la primera vez (para descargar Python y los componentes).

## Antes de empezar (5 minutos)
1. **Cifrado del disco.** Abra *Configuración → Privacidad y seguridad → Cifrado del dispositivo* (o *BitLocker* en Windows 11 Pro) y verifique que esté **activado**. Si roban la PC, esto impide leer los datos.
2. **Contraseña de Windows.** Su usuario de Windows debe tener contraseña o PIN, y la pantalla debe bloquearse sola (*Configuración → Cuentas → Opciones de inicio de sesión*).
3. **Wi-Fi del consultorio** con contraseña (WPA2 o WPA3). No use el sistema desde redes públicas.
4. Tenga a mano una **memoria USB o disco externo** para la copia de los respaldos (opcional pero muy recomendado), y otra USB distinta para guardar las claves.

## Instalar
1. Descargue `gastromed-pro-<versión>.zip`.
2. Clic derecho sobre el ZIP → **Propiedades** → marque **Desbloquear** (abajo) → **Aceptar**. Así Windows no bloqueará el instalador.
3. Clic derecho → **Extraer todo…** → **Extraer**.
4. En la carpeta extraída, doble clic en **`INSTALAR.bat`**.
   - Si aparece «Windows protegió su PC», pulse **Más información → Ejecutar de todas formas**.
5. Responda las preguntas del instalador:
   - **Carpeta de copia externa:** escriba la carpeta del disco externo (p. ej. `E:\RespaldosGastroMed`) o pulse Enter para configurarla después.
   - **Nombre del consultorio** y **nombre profesional** (Enter acepta «Dr. Mario Lainez»).
   - **Correo y contraseña** para ingresar (mínimo 12 caracteres con mayúsculas, minúsculas y números; no se ve al escribir).
   - **Iniciar automáticamente al encender:** recomendado «S».
   - **Permitir acceso desde el celular:** «S». Windows pedirá permiso de administrador: pulse **Sí**.
6. Al terminar, el instalador ejecuta las pruebas automáticas en su PC, hace el primer respaldo y abre el sistema.

## ¡Importante! Las claves
En su escritorio aparece el archivo **«GastroMed - CLAVES (copiar a USB y borrar de aqui).txt»**.
Cópielo a una USB (no la de los respaldos) o imprímalo, guárdelo en un lugar seguro y **bórrelo del escritorio**.
Sin esas claves, si la PC se daña, los respaldos y los estudios adjuntos no se podrán abrir.

## Uso diario
- **Abrir:** doble clic en **GastroMed Pro** (escritorio). Se abre una ventana negra minimizada (el servidor) y el navegador.
  **No cierre la ventana negra** mientras use el sistema.
- **Desde el celular:** conéctelo al mismo Wi-Fi y abra en Chrome o Safari la dirección que muestra la ventana negra,
  por ejemplo `http://192.168.1.25:8000`. Guárdela en favoritos o en la pantalla de inicio.
- **Practicar:** **GastroMed Pro - DEMOSTRACION** abre una copia separada con pacientes ficticios (solo en esta PC, puerto 8001).
  Lo que haga ahí no afecta los datos reales.
- **Revisar el estado:** **GastroMed Pro - Verificar estado** muestra si la base está sana, cuándo fue el último respaldo y si la copia externa funciona.

## Primeros pasos recomendados en el sistema
1. *Ajustes → Clínica y documentos:* complete colegiación, dirección y teléfonos (aparecen en las recetas).
2. *Menú de usuario → Verificación en dos pasos:* actívela.
3. *Ajustes → Usuarios y permisos:* cree las cuentas de recepción y enfermería. Luego marque «Exigir verificación en dos pasos».
4. Use primero la **DEMOSTRACIÓN** unos días antes de registrar pacientes reales.

## Respaldos
- Automáticos **todos los días a las 21:00**. Si la PC está apagada a esa hora, se hacen al encenderla.
- Cada respaldo se **verifica restaurándolo** en una carpeta temporal antes de darlo por bueno.
- Se conservan los últimos 30 en `C:\GastroMed\respaldos` y, si configuró un disco externo, también allí.
- El registro está en `C:\GastroMed\datos\respaldo.log`.
- Para cambiar la carpeta externa: edite `C:\GastroMed\datos\gastromed.env`, línea `GASTROMED_BACKUP_COPY_DIR=`.
- Recomendación: una vez por semana lleve una copia del disco externo fuera del consultorio.

## Actualizar a una versión nueva
Descomprima la nueva versión y ejecute su `INSTALAR.bat`. El instalador hace primero un respaldo, conserva datos, claves y usuarios, y reemplaza solo el programa.

## Límites de esta modalidad (léalos)
- **La PC debe estar encendida** y el programa abierto para usar el sistema desde el celular.
- **Solo funciona dentro del Wi-Fi del consultorio.** Fuera de él no hay acceso (se puede añadir después con una VPN privada).
- La conexión celular ↔ PC en el Wi-Fi **no usa HTTPS** todavía: por eso es esencial que el Wi-Fi tenga contraseña y no sea compartido con pacientes. Instalar la PWA en el celular («Agregar a pantalla de inicio» como aplicación) requiere HTTPS; por ahora use un favorito.
- El instalador **no pudo probarse en una PC con Windows real** durante el desarrollo (el entorno de desarrollo es Linux). Se probó todo el programa y una simulación completa de la instalación. Si algo falla, el instalador muestra un mensaje claro y no toca sus datos: tome una foto de la pantalla.
