# Probar GastroMed Pro en su computadora Windows (opcional)

> **Importante:** para el uso diario desde PC **y** celular, la aplicación debe estar en un servidor en internet con HTTPS. Ese paso requiere contratar un servidor (ver `ARQUITECTURA.md` §5) y se hará con su aprobación. **No necesita instalar nada en su PC para el uso normal.**
>
> Esta guía es solo para probar la versión de demostración en su propia computadora, con pacientes ficticios.

## 1. Instalar Python (una sola vez)
1. Entre a **https://www.python.org/downloads/windows/** y descargue el instalador de **Python 3.13** («Windows installer (64-bit)»).
2. Ejecútelo. **Marque la casilla «Add python.exe to PATH»** en la primera pantalla y pulse «Install Now».
3. Compruebe: abra el menú Inicio, escriba `cmd`, abra «Símbolo del sistema» y escriba:
   ```
   python --version
   ```
   Debe responder `Python 3.13.x`.

## 2. Copiar el proyecto
Descomprima la carpeta `gastromed-pro` en, por ejemplo, `C:\GastroMed\gastromed-pro`.

## 3. Instalar las dependencias
En el Símbolo del sistema:
```
cd C:\GastroMed\gastromed-pro
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
Verá al final «Successfully installed …».

## 4. Crear la base de demostración
```
python scripts\seed_demo.py
```
Mostrará cinco usuarios de prueba (uno por rol) con sus contraseñas. También quedan en `instance\credenciales_demo.txt`.

## 5. Abrir la aplicación
```
python run.py
```
Abra Chrome o Edge en **http://127.0.0.1:8000** e ingrese con `medico@demo.gastromed` y la contraseña mostrada.

Para detenerla: vuelva a la ventana negra y pulse `Ctrl + C`.

## 6. Comprobar que todo funciona (opcional)
```
python -m pytest -q
```
Debe terminar con `38 passed`.

## Qué probar
1. Agenda → «Registrar llegada» en una cita → «Iniciar consulta» → escriba la nota (se guarda sola) → «Finalizar…».
2. Desde la nota, «Emitir receta» → «PDF carta» → imprima.
3. Cierre sesión e ingrese como `recepcion@demo.gastromed`: verá agenda y datos administrativos, pero no notas, alergias ni recetas.
