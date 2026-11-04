"""Genera la clave de activación de una computadora (se ejecuta SOLO en GitHub Actions, con el secreto GM_LICENCIA_CLAVE).

  GM_LICENCIA_CLAVE=... python build/firmar_licencia.py "3F2A-91C0-7B44-0DE1" "Dr. Mario Lainez"
"""
import datetime
import os
import sys
from pathlib import Path

import importlib.util  # noqa: E402

# Se carga solo app/license.py (sin el resto del programa ni Flask)
_spec = importlib.util.spec_from_file_location("gm_license", Path(__file__).resolve().parent.parent / "app" / "license.py")
_lic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lic)
CODE_RE, sign, verify = _lic.CODE_RE, _lic.sign, _lic.verify


def main():
    code = (sys.argv[1] if len(sys.argv) > 1 else "").strip().upper()
    holder = (sys.argv[2] if len(sys.argv) > 2 else "").strip() or "Dr. Mario Lainez"
    priv = os.environ.get("GM_LICENCIA_CLAVE", "").strip()
    if not priv:
        print("::error title=Falta el secreto::Guarde la llave privada como secreto GM_LICENCIA_CLAVE (Settings > Secrets > Actions).")
        sys.exit(1)
    if not CODE_RE.match(code):
        print(f"::error title=Código no válido::El código de equipo debe verse así: 3F2A-91C0-7B44-0DE1 (recibí «{code}»).")
        sys.exit(1)
    clave = sign(priv, code, holder, datetime.date.today().isoformat())
    verify(clave, code)   # comprobación: la clave funciona con la llave pública del programa
    print(f"::notice title=Clave de activación para {code}::{clave}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"## Clave de activación\n\nComputadora: **{code}** · Titular: **{holder}**\n\n"
                    "Copie la clave completa (una sola línea) y péguela en la pantalla «Activar GastroMed Pro» de esa PC:\n\n"
                    f"```\n{clave}\n```\n")


if __name__ == "__main__":
    main()
