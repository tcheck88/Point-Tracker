import os
import sys

# 1. DEFINE PATHS
basedir = os.path.abspath(os.path.dirname(__file__))
translations_dir = os.path.join(basedir, 'translations')
es_dir = os.path.join(translations_dir, 'es', 'LC_MESSAGES')
po_file = os.path.join(es_dir, 'messages.po')
mo_file = os.path.join(es_dir, 'messages.mo')

# 2. ENSURE DIRECTORIES EXIST
os.makedirs(es_dir, exist_ok=True)

# 3. DEFINE TRANSLATIONS
PO_HEADER = r"""
msgid ""
msgstr ""
"Project-Id-Version: 1.0\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2024-01-01 00:00+0000\n"
"PO-Revision-Date: 2024-01-01 00:00+0000\n"
"Last-Translator: \n"
"Language-Team: \n"
"Language: es\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"""

TRANSLATIONS = {
    # --- NAVIGATION & GENERAL ---
    "Dashboard": "Panel de Control",
    "Student Actions": "Acciones de Estudiantes",
    "Management": "Administración",
    "System Status": "Estado del Sistema",
    "Help": "Ayuda",
    "Back to Dashboard": "Volver al Panel",
    "Back": "Atrás",
    "Search": "Buscar",
    "Reset": "Reiniciar",
    
    # --- BUTTONS ---
    "Reward Points (Activity)": "Otorgar Puntos (Actividad)",
    "Redeem Points (Prizes)": "Canjear Puntos (Premios)",
    "Student Directory": "Directorio de Estudiantes",
    "Add New Student": "Agregar Nuevo Estudiante",
    "Prize Inventory": "Inventario de Premios",
    "Activity Catalog": "Catálogo de Actividades",
    "App Logs": "Registros de la App",
    "System Audit Logs": "Auditoría del Sistema",
    "Reports": "Reportes",
    "View Redemption Log": "Ver Bitácora de Canjes",
    "View Inventory Report": "Ver Reporte de Inventario",
    "Download CSV": "Descargar CSV",

    # --- HELP & DOCUMENTATION ---
    "Help & Documentation": "Ayuda y Documentación",
    "Staff Support Center": "Centro de Soporte al Personal",
    "Print Guide": "Imprimir Guía",
    "Cheat Sheet": "Hoja de Referencia",
    "User Manual": "Manual de Usuario",
    "FAQ": "Preguntas Frecuentes",
    
    # Cheat Sheet Steps
    "How to Reward Points": "Cómo Otorgar Puntos",
    "Go to": "Ir a",
    "Click": "Hacer clic en",
    "for the student (Type name → Click their name).": "el estudiante (Escriba nombre → Seleccione de la lista).",
    "Select the": "Seleccione la",
    "Activity": "Actividad",
    "from the list.": "de la lista.",
    "Post Transaction": "Registrar Transacción",
    "The new balance appears immediately at the top.": "El nuevo saldo aparece inmediatamente arriba.",
    
    "How to Redeem a Prize": "Cómo Canjear un Premio",
    "for the student.": "el estudiante.",
    "Check their": "Verifique su",
    "Balance": "Saldo",
    "Find the prize and click": "Encuentre el premio y haga clic en",
    "Redeem": "Canjear",
    
    # Manual Section
    "Managing Students": "Gestión de Estudiantes",
    "Adding a New Student": "Agregar Nuevo Estudiante",
    "Navigate to \"Add New Student\". Enter their Full Name, Grade, and Classroom. Always check the directory first to ensure they do not already exist.": "Vaya a \"Agregar Nuevo Estudiante\". Ingrese Nombre Completo, Grado y Salón. ¡Siempre verifique el directorio primero para asegurarse de que no existan!",
    
    "Viewing History": "Ver Historial",
    "Go to the Student Directory, search for a student, and click \"View Profile\". You can see their last 10 transactions and download their full history.": "Vaya al Directorio, busque al estudiante y haga clic en \"Ver Perfil\". Puede ver sus últimas 10 transacciones y descargar el historial completo.",
    
    "Managing Inventory": "Gestión de Inventario",
    "Adding/Updating Prizes": "Agregar/Actualizar Premios",
    "Go to \"Prize Inventory\". To add a new prize, use the form at the top. To update stock for an existing prize, find it in the list below and click \"Edit\".": "Vaya a \"Inventario de Premios\". Para agregar uno nuevo, use el formulario superior. Para actualizar existencias, busque el premio abajo y haga clic en \"Editar\".",
    
    "Access reports from the Dashboard. You can view them on-screen or download CSV files for Excel.": "Acceda a los reportes desde el Panel. Puede verlos en pantalla o descargar archivos CSV para Excel.",
    "Redemption Log:": "Bitácora de Canjes:",
    "See who bought what and when.": "Vea quién canjeó qué y cuándo.",
    "Inventory Report:": "Reporte de Inventario:",
    "See current stock levels for stocktaking.": "Vea los niveles actuales para el conteo de existencias.",

    # FAQ Section
    "Frequently Asked Questions": "Preguntas Frecuentes",
    "I entered the wrong points! How do I undo it?": "¡Ingresé los puntos incorrectos! ¿Cómo lo deshago?",
    "Go to \"Reward Points\", select the student, and post a transaction with a **negative** point value (e.g., -50) to reverse the error.": "Vaya a \"Otorgar Puntos\", seleccione al estudiante y registre una transacción con valor **negativo** (ej. -50) para revertir el error.",
    
    "Why is the Redeem button grayed out?": "¿Por qué el botón Canjear está gris?",
    "Either the student does not have enough points, OR the item is out of stock.": "El estudiante no tiene suficientes puntos O el artículo está agotado.",
    
    "Can I delete a student?": "¿Puedo eliminar a un estudiante?",
    "No. We do not delete students to preserve historical data. Please ask an administrator to mark them as inactive.": "No. No eliminamos estudiantes para preservar los datos históricos. Pida a un administrador que los marque como inactivos.",
    
    "The Spanish translation is missing?": "¿Falta la traducción al español?",
    "Refresh the page. If it persists, click \"ES\" in the top right corner.": "Refresque la página. Si persiste, haga clic en \"ES\" en la esquina superior derecha."
}

# 4. WRITE PO FILE
print(f"Generating {po_file}...")
with open(po_file, 'w', encoding='utf-8') as f:
    f.write(PO_HEADER)
    for k, v in TRANSLATIONS.items():
        # Escape quotes just in case
        k_esc = k.replace('"', '\\"')
        v_esc = v.replace('"', '\\"')
        f.write(f'\nmsgid "{k_esc}"\n')
        f.write(f'msgstr "{v_esc}"\n')

# 5. COMPILE TO MO FILE
try:
    # Removed unnecessary 'import pybabel' to prevent errors
    from babel.messages.pofile import read_po
    from babel.messages.mofile import write_mo
    
    print(f"Compiling to {mo_file}...")
    with open(po_file, 'rb') as f:
        catalog = read_po(f)
    
    with open(mo_file, 'wb') as f:
        write_mo(f, catalog)
        
    print("SUCCESS: Translations updated!")

except ImportError:
    print("ERROR: 'Babel' library not found.")
    print("Please run this command manually:")
    print("pip install Babel")